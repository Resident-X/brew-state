#!/usr/bin/env python3
"""The pre-order check's reading and judgement of the owner's net-pair spacing exceptions, driven on synthetic fixtures with no KiCad involved.

The net-pair form excuses a mains_to_mains shortfall between two sets of nets,
down to a distance no lower than the creepage and clearance the record's
functional band rows give for the working voltage the entry states. What is
under test is what the check decides for itself: whether an entry is in its
one form, what figure the band rows give, and what each entry makes of the
spacing shortfalls a layout rule check reported, given as the report KiCad
writes them. What KiCad then reports of a seeded layout is driven against the
real tool in test_board_check_kicad_net_pair_exceptions.py.
"""

from __future__ import annotations

import datetime
import os
import sys
import unittest
from fractions import Fraction

import yaml

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)

import board_check  # noqa: E402
import sexpr  # noqa: E402
from test_board_spacing_exceptions import RECORD, DESIGN, TODAY, basis, read, read_text  # noqa: E402

MAINS_L, MAINS_N, MAINS_M, LV_A = "/MAINS_L", "/MAINS_N", "/MAINS_M", "/LV_A"
#: The layout's nets: three of the Mains class and one low-voltage net.
LAYOUT = sexpr.parse_one(
    '(kicad_pcb'
    ' (footprint "R" (property "Reference" "R1") (pad "1" thru_hole circle (net "/MAINS_L")) (pad "2" thru_hole circle (net "/MAINS_N")))'
    ' (footprint "K" (property "Reference" "K1") (pad "1" thru_hole circle (net "/MAINS_M")) (pad "2" thru_hole circle (net "/LV_A"))))')
MAINS = {MAINS_L, MAINS_N, MAINS_M}

#: How KiCad's report describes a copper item of each kind.
PAD = "PTH pad 1 [{}] of R1 @ (1, 2) mm"
TRACK = "Track [{}] on F.Cu, length 5.0000 mm @ (10, 10) mm"
VIA = "Via [{}] on F.Cu - B.Cu @ (12.5, 10.95) mm"
ZONE = "Zone [{}] on F.Cu, priority 0 @ (11, 10.5) mm"


def band(volts, creepage, clearance, **inputs) -> dict:
    """One functional band row of a record at pollution degree 2 and material group IIIb, `inputs` set over its inputs."""
    held = {"working_voltage_v": volts, "insulation": "functional", "location": "conductor", "pollution_degree": 2,
            "material_group": "IIIb"}
    held.update(inputs)
    figure = {"creepage_mm": creepage, "clearance_mm": clearance}
    return {"citation": {"document": "synthetic", "edition": "none", "locator": f"row at {volts} V"},
            "inputs": {key: value for key, value in held.items() if value is not None},
            "figure": {key: value for key, value in figure.items() if value is not None}}


#: At 125 V the creepage band is 0.5 mm and the clearance band 0.4 mm.
BANDS = [band(50, 0.3, 0.2), band(125, 0.5, 0.4), band(250, 1.0, 0.8)]


def net_entry(**changes) -> dict:
    """A well-formed net-pair entry, with `changes` set over it and a key set to None left out."""
    held = {"pair": "mains_to_mains", "constraint": "clearance", "nets_a": [MAINS_L], "nets_b": [MAINS_N],
            "working_voltage_v": 125, "accepted_mm": 0.8, "reason": "a synthetic divider chain",
            "bounded_by": "a synthetic independent element", "accepted_by": "maintainer", "accepted_on": "2026-10-01"}
    held.update(changes)
    return {key: value for key, value in held.items() if value is not None}


def between_entry(**changes) -> dict:
    held = {"pair": "mains_to_mains", "constraint": "clearance", "between": [MAINS_L, MAINS_N], "accepted_mm": 0.7,
            "reason": "a synthetic ground", "bounded_by": "a synthetic element", "accepted_by": "maintainer",
            "accepted_on": "2026-10-01"}
    held.update(changes)
    return {key: value for key, value in held.items() if value is not None}


def net_basis(*entries, rows=None, **changes) -> dict:
    return basis(*entries, table_rows=BANDS if rows is None else rows, **changes)


def reported(kind: str, figure: float, actual, first: str, second: str, rule: str = board_check.MAINS_TO_MAINS_RULE) -> dict:
    """One violation as KiCad's JSON report writes it, between two items described as above; `actual` None leaves the distance out."""
    distance = "" if actual is None else f"; actual {actual:.4f} mm"
    return {"type": kind, "severity": "error",
            "description": f"{kind.capitalize()} violation (rule '{rule}' {kind} {figure:.4f} mm{distance})",
            "items": [{"description": first, "pos": {"x": 1, "y": 2}}, {"description": second, "pos": {"x": 3, "y": 4}}]}


def clearance_between(first: str, second: str, actual=0.84, figure=1.0, **more) -> dict:
    return reported("clearance", figure, actual, first, second, **more)


def judge(violations, *entries, mains=MAINS, **changes):
    signed, problems = read(net_basis(*entries, **changes))
    assert problems == [], [problem.line() for problem in problems]
    return board_check.judge_exceptions(DESIGN, RECORD, signed, violations, LAYOUT, TODAY, mains)


def failures(judged) -> list:
    return [(found.rule, found.location.rsplit(" ", 1)[-1], found.message) for found in judged.violations]


class TheNetPairFormIsRead(unittest.TestCase):
    def assertFails(self, data: dict, location_end: str, words: str):
        signed, problems = read(data)
        self.assertIsNone(signed)
        self.assertTrue(any(v.rule == "separation_basis" and v.location.endswith(location_end) and words in v.message
                            for v in problems), [problem.line() for problem in problems])

    def test_a_well_formed_entry_is_read_with_no_problem_and_kept(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-NET-PAIR-SPACING-EXCEPTIONS.C1: A record, read with the form selected by the presence of nets_a, holding an entry that lacks a key, holds a key outside the form, repeats a key, holds both between and nets_a, gives an empty or repeating nets list, names a pair other than mains_to_mains, a constraint outside creepage and clearance, or a working_voltage_v or accepted_mm that is not a positive number, fails as separation_basis naming the entry and the key. A well-formed entry is read with no problem. Out of scope is whether the entry is signed or used, which the judgement decides.
        signed, problems = read(net_basis(net_entry(), net_entry(nets_b=None, nets_a=[MAINS_L, MAINS_N], constraint="creepage")))
        self.assertEqual(problems, [])
        self.assertEqual(signed.exceptions[0]["nets_b"], [MAINS_N])
        self.assertNotIn("nets_b", signed.exceptions[1])
        self.assertEqual(len(signed.exceptions), 2)

    def test_an_entry_lacking_a_required_key_fails_naming_its_position_and_the_key(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-NET-PAIR-SPACING-EXCEPTIONS.C1: A record, read with the form selected by the presence of nets_a, holding an entry that lacks a key, holds a key outside the form, repeats a key, holds both between and nets_a, gives an empty or repeating nets list, names a pair other than mains_to_mains, a constraint outside creepage and clearance, or a working_voltage_v or accepted_mm that is not a positive number, fails as separation_basis naming the entry and the key. A well-formed entry is read with no problem. Out of scope is whether the entry is signed or used, which the judgement decides.
        for key in ("pair", "constraint", "working_voltage_v", "accepted_mm", "reason", "bounded_by", "accepted_by",
                    "accepted_on"):
            with self.subTest(key=key):
                self.assertFails(net_basis(net_entry(), net_entry(**{key: None})), f"accepted_exceptions[1].{key}", f"lacks {key}")

    def test_an_entry_lacking_nets_a_is_not_of_the_form_and_is_read_as_the_between_form(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-NET-PAIR-SPACING-EXCEPTIONS.C1: A record, read with the form selected by the presence of nets_a, holding an entry that lacks a key, holds a key outside the form, repeats a key, holds both between and nets_a, gives an empty or repeating nets list, names a pair other than mains_to_mains, a constraint outside creepage and clearance, or a working_voltage_v or accepted_mm that is not a positive number, fails as separation_basis naming the entry and the key. A well-formed entry is read with no problem. Out of scope is whether the entry is signed or used, which the judgement decides.
        self.assertFails(net_basis(net_entry(nets_a=None)), "accepted_exceptions[0].between", "lacks between")

    def test_a_missing_nets_b_is_no_fault_and_an_unknown_key_is_named(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-NET-PAIR-SPACING-EXCEPTIONS.C1: A record, read with the form selected by the presence of nets_a, holding an entry that lacks a key, holds a key outside the form, repeats a key, holds both between and nets_a, gives an empty or repeating nets list, names a pair other than mains_to_mains, a constraint outside creepage and clearance, or a working_voltage_v or accepted_mm that is not a positive number, fails as separation_basis naming the entry and the key. A well-formed entry is read with no problem. Out of scope is whether the entry is signed or used, which the judgement decides.
        signed, problems = read(net_basis(net_entry(nets_b=None)))
        self.assertEqual(problems, [])
        self.assertFails(net_basis(net_entry(), net_entry(nets_c=[MAINS_N])), "accepted_exceptions[1].nets_c", "holds the key 'nets_c'")

    def test_an_entry_holding_both_between_and_nets_a_fails_once_naming_both(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-NET-PAIR-SPACING-EXCEPTIONS.C1: A record, read with the form selected by the presence of nets_a, holding an entry that lacks a key, holds a key outside the form, repeats a key, holds both between and nets_a, gives an empty or repeating nets list, names a pair other than mains_to_mains, a constraint outside creepage and clearance, or a working_voltage_v or accepted_mm that is not a positive number, fails as separation_basis naming the entry and the key. A well-formed entry is read with no problem. Out of scope is whether the entry is signed or used, which the judgement decides.
        signed, problems = read(net_basis(net_entry(between=[MAINS_L, MAINS_N])))
        self.assertIsNone(signed)
        mixed = [v for v in problems if v.location.endswith("accepted_exceptions[0].between")]
        self.assertEqual(len(mixed), 1, [problem.line() for problem in problems])
        self.assertIn("both between and nets_a", mixed[0].message)

    def test_a_nets_list_that_is_empty_repeats_a_net_or_holds_a_non_text_item_fails_naming_the_list(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-NET-PAIR-SPACING-EXCEPTIONS.C1: A record, read with the form selected by the presence of nets_a, holding an entry that lacks a key, holds a key outside the form, repeats a key, holds both between and nets_a, gives an empty or repeating nets list, names a pair other than mains_to_mains, a constraint outside creepage and clearance, or a working_voltage_v or accepted_mm that is not a positive number, fails as separation_basis naming the entry and the key. A well-formed entry is read with no problem. Out of scope is whether the entry is signed or used, which the judgement decides.
        for key in ("nets_a", "nets_b"):
            for bad, words in (([], "lists no net names"), ([MAINS_L, MAINS_L], "more than once"), ([3], "non-empty string"),
                               ([None], "non-empty string"), (["  "], "non-empty string"), ("/MAINS_L", "is not a list")):
                with self.subTest(key=key, bad=bad):
                    self.assertFails(net_basis(net_entry(**{key: bad})), f"accepted_exceptions[0].{key}" if bad in ([], [MAINS_L, MAINS_L], "/MAINS_L") else f"accepted_exceptions[0].{key}[0]", words)

    def test_a_pair_other_than_mains_to_mains_or_a_constraint_outside_creepage_and_clearance_fails(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-NET-PAIR-SPACING-EXCEPTIONS.C1: A record, read with the form selected by the presence of nets_a, holding an entry that lacks a key, holds a key outside the form, repeats a key, holds both between and nets_a, gives an empty or repeating nets list, names a pair other than mains_to_mains, a constraint outside creepage and clearance, or a working_voltage_v or accepted_mm that is not a positive number, fails as separation_basis naming the entry and the key. A well-formed entry is read with no problem. Out of scope is whether the entry is signed or used, which the judgement decides.
        for pair in ("mains_to_low_voltage", "same_connector_pins", "other"):
            with self.subTest(pair=pair):
                signed, problems = read(net_basis(net_entry(pair=pair)))
                self.assertIsNone(signed)
                self.assertTrue(any(v.rule == "separation_basis" and "accepted_exceptions[0]" in v.location for v in problems))
        for constraint in ("hole_to_hole", "other"):
            with self.subTest(constraint=constraint):
                self.assertFails(net_basis(net_entry(constraint=constraint)), "accepted_exceptions[0].constraint", "where it is clearance or creepage")
        self.assertFails(net_basis(net_entry(pair="mains_to_low_voltage")), "accepted_exceptions[0].pair", "where it is mains_to_mains")

    def test_a_working_voltage_or_accepted_distance_that_is_not_a_positive_number_fails_naming_it(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-NET-PAIR-SPACING-EXCEPTIONS.C1: A record, read with the form selected by the presence of nets_a, holding an entry that lacks a key, holds a key outside the form, repeats a key, holds both between and nets_a, gives an empty or repeating nets list, names a pair other than mains_to_mains, a constraint outside creepage and clearance, or a working_voltage_v or accepted_mm that is not a positive number, fails as separation_basis naming the entry and the key. A well-formed entry is read with no problem. Out of scope is whether the entry is signed or used, which the judgement decides.
        for key in ("working_voltage_v", "accepted_mm"):
            for bad in (0, -1, "250", True, None, float("inf")):
                with self.subTest(key=key, bad=bad):
                    data = net_basis(net_entry(**{key: bad if bad is not None else None}))
                    if bad is None:
                        self.assertFails(data, f"accepted_exceptions[0].{key}", f"lacks {key}")
                    else:
                        self.assertFails(data, f"accepted_exceptions[0].{key}", "not a positive number")

    def test_a_key_given_twice_is_refused_by_the_one_rule_for_repeated_keys(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-NET-PAIR-SPACING-EXCEPTIONS.C1: A record, read with the form selected by the presence of nets_a, holding an entry that lacks a key, holds a key outside the form, repeats a key, holds both between and nets_a, gives an empty or repeating nets list, names a pair other than mains_to_mains, a constraint outside creepage and clearance, or a working_voltage_v or accepted_mm that is not a positive number, fails as separation_basis naming the entry and the key. A well-formed entry is read with no problem. Out of scope is whether the entry is signed or used, which the judgement decides.
        written = yaml.safe_dump(net_basis(net_entry(accepted_by=None)))
        self.assertIn("\n  accepted_on: '2026-10-01'", written)
        written = written.replace("\n  accepted_on: '2026-10-01'", "\n  accepted_by: maintainer\n  accepted_by: someone\n  accepted_on: '2026-10-01'", 1)
        signed, problems = read_text(written)
        self.assertIsNone(signed)
        self.assertTrue(any(v.rule == "separation_basis" and "gives the key 'accepted_by' more than once" in v.message
                            for v in problems), [problem.line() for problem in problems])

    def test_the_other_forms_keep_their_key_sets(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-NET-PAIR-SPACING-EXCEPTIONS.C1: A record, read with the form selected by the presence of nets_a, holding an entry that lacks a key, holds a key outside the form, repeats a key, holds both between and nets_a, gives an empty or repeating nets list, names a pair other than mains_to_mains, a constraint outside creepage and clearance, or a working_voltage_v or accepted_mm that is not a positive number, fails as separation_basis naming the entry and the key. A well-formed entry is read with no problem. Out of scope is whether the entry is signed or used, which the judgement decides.
        signed, problems = read(net_basis(between_entry(), between_entry(nets_b=[MAINS_N], between=None)))
        self.assertIsNone(signed)
        self.assertTrue(any(v.location.endswith("accepted_exceptions[1].nets_b") and "holds the key 'nets_b'" in v.message
                            for v in problems), [problem.line() for problem in problems])
        self.assertTrue(any(v.location.endswith("accepted_exceptions[1].between") and "lacks between" in v.message for v in problems))
        signed, problems = read(net_basis(between_entry(), between_entry(constraint="creepage", between=[MAINS_M, MAINS_N])))
        self.assertEqual(problems, [])


class TheBandFigureIsReadFromTheRecord(unittest.TestCase):
    COMMITTED = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                             "sunbeam-em7000", "separation-basis.yaml")

    @classmethod
    def setUpClass(cls):
        with open(cls.COMMITTED, encoding="utf-8") as handle:
            cls.record = yaml.safe_load(handle)

    def test_the_creepage_band_figure_of_the_committed_record_at_each_voltage(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-NET-PAIR-SPACING-EXCEPTIONS.C2: The check's creepage band figure for a working voltage is 0.4 mm at 10 V, 0.7 mm at 30 V, 1.4 mm at 84.5 V, 1.5 mm at 125 V, 1.6 mm at 126.5 V and 160 V, 1.7 mm at 168.5 V, 1.8 mm at 178.7 V, 2.0 mm at 200 V, 2.5 mm at 250 V, 2.6 mm at 253 V and 3.2 mm at 320 V, and its clearance band figure 0.2 mm at 10 V and 50 V and 1.5 mm at 125 V, from the rows of the committed record, and both are absent above 320 V. Out of scope is the use of the figure in the judgement.
        for volts, expected in ((10, "0.4"), (30, "0.7"), (84.5, "1.4"), (125, "1.5"), (126.5, "1.6"), (160, "1.6"),
                                (168.5, "1.7"), (178.7, "1.8"), (200, "2.0"), (250, "2.5"), (253, "2.6"), (320, "3.2")):
            with self.subTest(volts=volts):
                self.assertEqual(board_check.band_figure(self.record, "creepage_mm", volts), Fraction(expected))

    def test_the_clearance_band_figure_of_the_committed_record_and_no_figure_above_320_volts(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-NET-PAIR-SPACING-EXCEPTIONS.C2: The check's creepage band figure for a working voltage is 0.4 mm at 10 V, 0.7 mm at 30 V, 1.4 mm at 84.5 V, 1.5 mm at 125 V, 1.6 mm at 126.5 V and 160 V, 1.7 mm at 168.5 V, 1.8 mm at 178.7 V, 2.0 mm at 200 V, 2.5 mm at 250 V, 2.6 mm at 253 V and 3.2 mm at 320 V, and its clearance band figure 0.2 mm at 10 V and 50 V and 1.5 mm at 125 V, from the rows of the committed record, and both are absent above 320 V. Out of scope is the use of the figure in the judgement.
        for volts, expected in ((10, "0.2"), (50, "0.2"), (125, "1.5")):
            with self.subTest(volts=volts):
                self.assertEqual(board_check.band_figure(self.record, "clearance_mm", volts), Fraction(expected))
        for key in ("creepage_mm", "clearance_mm"):
            for volts in (320.1, 321, 1000):
                with self.subTest(key=key, volts=volts):
                    self.assertIsNone(board_check.band_figure(self.record, key, volts))

    def test_below_the_lowest_row_that_row_is_read(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-NET-PAIR-SPACING-EXCEPTIONS.C2: The check's creepage band figure for a working voltage is 0.4 mm at 10 V, 0.7 mm at 30 V, 1.4 mm at 84.5 V, 1.5 mm at 125 V, 1.6 mm at 126.5 V and 160 V, 1.7 mm at 168.5 V, 1.8 mm at 178.7 V, 2.0 mm at 200 V, 2.5 mm at 250 V, 2.6 mm at 253 V and 3.2 mm at 320 V, and its clearance band figure 0.2 mm at 10 V and 50 V and 1.5 mm at 125 V, from the rows of the committed record, and both are absent above 320 V. Out of scope is the use of the figure in the judgement.
        self.assertEqual(board_check.band_figure(self.record, "creepage_mm", 5), Fraction("0.4"))
        self.assertEqual(board_check.band_figure(self.record, "clearance_mm", 0.5), Fraction("0.2"))

    def test_the_interpolation_is_exact_in_decimal_and_rounded_up_to_a_tenth(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-NET-PAIR-SPACING-EXCEPTIONS.C2: The check's creepage band figure for a working voltage is 0.4 mm at 10 V, 0.7 mm at 30 V, 1.4 mm at 84.5 V, 1.5 mm at 125 V, 1.6 mm at 126.5 V and 160 V, 1.7 mm at 168.5 V, 1.8 mm at 178.7 V, 2.0 mm at 200 V, 2.5 mm at 250 V, 2.6 mm at 253 V and 3.2 mm at 320 V, and its clearance band figure 0.2 mm at 10 V and 50 V and 1.5 mm at 125 V, from the rows of the committed record, and both are absent above 320 V. Out of scope is the use of the figure in the judgement.
        rows = [band(10, 0.5, 0.2), band(20, 0.9, 0.2)]
        data = net_basis(rows=rows)
        # exactly 0.7 mid-way, which floating point cannot hold, stays 0.7 and is not pushed to 0.8
        self.assertEqual(board_check.band_figure(data, "creepage_mm", 15), Fraction("0.7"))
        # 0.5 + 0.4 * 0.1 = 0.54 rounds up to 0.6; a hair over a tenth goes up whole
        self.assertEqual(board_check.band_figure(data, "creepage_mm", 11), Fraction("0.6"))
        self.assertEqual(board_check.band_figure(net_basis(rows=[band(10, 0.5, 0.2), band(20, 0.8, 0.2)]), "creepage_mm", 15), Fraction("0.7"))
        self.assertEqual(board_check.band_figure(net_basis(rows=[band(10, 0.1, 0.2), band(20, 0.2, 0.2)]), "creepage_mm", 12.5), Fraction("0.2"))
        self.assertEqual(board_check.band_figure(net_basis(rows=[band(10, 0.1, 0.2), band(30, 0.3, 0.2)]), "creepage_mm", 20.1), Fraction("0.3"))

    def test_only_functional_conductor_rows_at_the_records_pollution_degree_and_material_group_are_band_rows(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-NET-PAIR-SPACING-EXCEPTIONS.C2: The check's creepage band figure for a working voltage is 0.4 mm at 10 V, 0.7 mm at 30 V, 1.4 mm at 84.5 V, 1.5 mm at 125 V, 1.6 mm at 126.5 V and 160 V, 1.7 mm at 168.5 V, 1.8 mm at 178.7 V, 2.0 mm at 200 V, 2.5 mm at 250 V, 2.6 mm at 253 V and 3.2 mm at 320 V, and its clearance band figure 0.2 mm at 10 V and 50 V and 1.5 mm at 125 V, from the rows of the committed record, and both are absent above 320 V. Out of scope is the use of the figure in the judgement.
        data = net_basis(rows=[band(10, 0.4, 0.2), band(50, 9, 9, insulation="basic"), band(50, 9, 9, location="terminal"),
                               band(50, 9, 9, pollution_degree=3), band(50, 9, 9, material_group="IIIa"),
                               band(50, 1.0, 0.5, location=None, overvoltage_category=2, altitude_m=2000)])
        self.assertEqual(board_check.band_figure(data, "creepage_mm", 50), Fraction("1.0"))
        self.assertEqual(board_check.band_figure(data, "clearance_mm", 50), Fraction("0.5"))
        self.assertEqual([volts for volts, _ in board_check.band_rows(data)], [10, 50])

    def test_a_row_lacking_the_figure_read_gives_none_and_two_rows_at_one_voltage_take_the_larger(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-NET-PAIR-SPACING-EXCEPTIONS.C2: The check's creepage band figure for a working voltage is 0.4 mm at 10 V, 0.7 mm at 30 V, 1.4 mm at 84.5 V, 1.5 mm at 125 V, 1.6 mm at 126.5 V and 160 V, 1.7 mm at 168.5 V, 1.8 mm at 178.7 V, 2.0 mm at 200 V, 2.5 mm at 250 V, 2.6 mm at 253 V and 3.2 mm at 320 V, and its clearance band figure 0.2 mm at 10 V and 50 V and 1.5 mm at 125 V, from the rows of the committed record, and both are absent above 320 V. Out of scope is the use of the figure in the judgement.
        data = net_basis(rows=[band(10, 0.4, None), band(50, 0.8, None), band(50, 0.9, 0.2)])
        self.assertEqual(board_check.band_figure(data, "creepage_mm", 50), Fraction("0.9"))
        self.assertEqual(board_check.band_figure(data, "clearance_mm", 50), Fraction("0.2"))
        self.assertIsNone(board_check.band_figure(net_basis(rows=[band(10, 0.4, None)]), "clearance_mm", 10))
        self.assertIsNone(board_check.band_figure(net_basis(rows=[]), "creepage_mm", 10))


class TheEntryIsJudgedAgainstTheBasisAlone(unittest.TestCase):
    def test_a_sound_entry_has_no_problem_and_a_flawed_one_the_problem_the_check_reports(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-NET-PAIR-SPACING-EXCEPTIONS.C3: The pure helper judging one entry against the basis, called with no layout, finds a well-formed signed entry sound and a flawed one flawed with the same findings the check reports. On a synthetic layout with a signed entry, net-pair entries being judged after the between and same-connector entries, a creepage shortfall between a pad of a net in nets_a and a track of a net in nets_b at or above accepted_mm is printed as one ACCEPTED line per entry carrying the constraint, both lists, the number of shortfalls covered, the narrowest reported distance, the accepted distance, the signed figure, the working voltage with its band figure, the reason and the bounding element, and fails nothing. The same holds for a via and a zone as either item, and for a pair inside nets_a where nets_b is omitted. Out of scope is a shortfall outside the lists.
        data = net_basis()
        self.assertIsNone(board_check.net_pair_entry_problem(net_entry(), data))
        self.assertIsNone(board_check.net_pair_entry_problem(net_entry(constraint="creepage", accepted_mm=0.5), data))
        flawed = net_entry(constraint="creepage", accepted_mm=0.45)
        problem = board_check.net_pair_entry_problem(flawed, data)
        self.assertIn("below the band creepage 0.5 mm", problem)
        judged = judge([clearance_between(TRACK.format(MAINS_L), PAD.format(MAINS_N))], flawed)
        (found,) = failures(judged)
        self.assertIn(problem, found[2])

    def test_the_least_distance_the_band_and_the_clearance_of_the_pair_each_bound_the_entry(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-NET-PAIR-SPACING-EXCEPTIONS.C5: An entry whose acceptance is empty, a placeholder, in angle brackets, later than today or later than the record's own, whose constraint is creepage and accepted_mm is below the creepage band figure for its working_voltage_v or below its clearance band figure, whose constraint is clearance and accepted_mm is below the clearance band figure for its working_voltage_v, whose accepted_mm is below 0.2 mm, whose working_voltage_v exceeds the record's working voltage or the highest band row, or whose accepted_mm is not below the figure of the rule that reports its shortfalls, fails as spacing_exception naming the entry and excuses nothing. Out of scope is any entry of another form.
        data = net_basis()
        problem = board_check.net_pair_entry_problem
        self.assertIn("below 0.2 mm", problem(net_entry(accepted_mm=0.19, working_voltage_v=50), data))
        self.assertIsNone(problem(net_entry(accepted_mm=0.2, working_voltage_v=50), data))
        self.assertIn("below the band clearance 0.4 mm", problem(net_entry(accepted_mm=0.39), data))
        self.assertIsNone(problem(net_entry(accepted_mm=0.4), data))
        self.assertIn("below the band creepage 0.5 mm", problem(net_entry(constraint="creepage", accepted_mm=0.49), data))
        self.assertIsNone(problem(net_entry(constraint="creepage", accepted_mm=0.5), data))
        # a creepage entry is held to the clearance band as well, where the clearance band is the larger
        wide = net_basis(rows=[band(50, 0.3, 0.2), band(125, 0.5, 0.7)])
        self.assertIn("below the band clearance 0.7 mm", problem(net_entry(constraint="creepage", accepted_mm=0.6), wide))
        self.assertIsNone(problem(net_entry(constraint="creepage", accepted_mm=0.7), wide))

    def test_a_working_voltage_above_the_records_or_above_the_highest_row_has_no_band_figure_to_be_held_to(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-NET-PAIR-SPACING-EXCEPTIONS.C5: An entry whose acceptance is empty, a placeholder, in angle brackets, later than today or later than the record's own, whose constraint is creepage and accepted_mm is below the creepage band figure for its working_voltage_v or below its clearance band figure, whose constraint is clearance and accepted_mm is below the clearance band figure for its working_voltage_v, whose accepted_mm is below 0.2 mm, whose working_voltage_v exceeds the record's working voltage or the highest band row, or whose accepted_mm is not below the figure of the rule that reports its shortfalls, fails as spacing_exception naming the entry and excuses nothing. Out of scope is any entry of another form.
        problem = board_check.net_pair_entry_problem
        self.assertIn("above the record's working voltage 250 V", problem(net_entry(working_voltage_v=253), net_basis()))
        self.assertIsNone(problem(net_entry(working_voltage_v=250, accepted_mm=1.0), net_basis()))
        # the record states 400 V and its rows stop at 250 V: only the highest row is exceeded
        high = net_basis(working_voltage="400 V rms")
        found = problem(net_entry(working_voltage_v=300), high)
        self.assertIn("above the highest functional band row", found)
        self.assertNotIn("record's working voltage", found)
        self.assertIsNone(problem(net_entry(working_voltage_v=250, accepted_mm=1.0), high))
        self.assertIn("holds none", problem(net_entry(), net_basis(rows=[])))

    def test_a_band_row_set_lacking_a_figure_fails_the_entry_naming_it(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-NET-PAIR-SPACING-EXCEPTIONS.C5: An entry whose acceptance is empty, a placeholder, in angle brackets, later than today or later than the record's own, whose constraint is creepage and accepted_mm is below the creepage band figure for its working_voltage_v or below its clearance band figure, whose constraint is clearance and accepted_mm is below the clearance band figure for its working_voltage_v, whose accepted_mm is below 0.2 mm, whose working_voltage_v exceeds the record's working voltage or the highest band row, or whose accepted_mm is not below the figure of the rule that reports its shortfalls, fails as spacing_exception naming the entry and excuses nothing. Out of scope is any entry of another form.
        problem = board_check.net_pair_entry_problem
        no_clearance = net_basis(rows=[band(50, 0.3, None), band(125, 0.5, None)])
        self.assertIn("no clearance_mm", problem(net_entry(), no_clearance))
        self.assertIn("no clearance_mm", problem(net_entry(constraint="creepage", accepted_mm=0.6), no_clearance))
        no_creepage = net_basis(rows=[band(50, None, 0.2), band(125, None, 0.4)])
        self.assertIn("no creepage_mm", problem(net_entry(constraint="creepage", accepted_mm=0.6), no_creepage))
        self.assertIsNone(problem(net_entry(), no_creepage))


class TheJudgementAcceptsAShortfallBetweenTheLists(unittest.TestCase):
    def accepted_line(self, judged) -> str:
        (line,) = judged.accepted
        return line

    def test_a_shortfall_at_or_above_the_accepted_distance_is_one_accepted_line_and_fails_nothing(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-NET-PAIR-SPACING-EXCEPTIONS.C3: The pure helper judging one entry against the basis, called with no layout, finds a well-formed signed entry sound and a flawed one flawed with the same findings the check reports. On a synthetic layout with a signed entry, net-pair entries being judged after the between and same-connector entries, a creepage shortfall between a pad of a net in nets_a and a track of a net in nets_b at or above accepted_mm is printed as one ACCEPTED line per entry carrying the constraint, both lists, the number of shortfalls covered, the narrowest reported distance, the accepted distance, the signed figure, the working voltage with its band figure, the reason and the bounding element, and fails nothing. The same holds for a via and a zone as either item, and for a pair inside nets_a where nets_b is omitted. Out of scope is a shortfall outside the lists.
        judged = judge([clearance_between(PAD.format(MAINS_L), TRACK.format(MAINS_N))], net_entry())
        self.assertEqual(failures(judged), [])
        line = self.accepted_line(judged)
        self.assertTrue(line.startswith("ACCEPTED | "))
        for words in ("spacing_exception", "accepted_exceptions[0]", "net pair mains_to_mains clearance", "[/MAINS_L] and [/MAINS_N]",
                      "1 of 1 shortfalls covered", "narrowest 0.84 mm", "accepted down to 0.8 mm", "against the signed 1 mm",
                      "working voltage 125 V, band 0.4 mm", "reason: a synthetic divider chain",
                      "bounded by: a synthetic independent element"):
            self.assertIn(words, line)

    def test_a_via_and_a_zone_stand_as_either_item(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-NET-PAIR-SPACING-EXCEPTIONS.C3: The pure helper judging one entry against the basis, called with no layout, finds a well-formed signed entry sound and a flawed one flawed with the same findings the check reports. On a synthetic layout with a signed entry, net-pair entries being judged after the between and same-connector entries, a creepage shortfall between a pad of a net in nets_a and a track of a net in nets_b at or above accepted_mm is printed as one ACCEPTED line per entry carrying the constraint, both lists, the number of shortfalls covered, the narrowest reported distance, the accepted distance, the signed figure, the working voltage with its band figure, the reason and the bounding element, and fails nothing. The same holds for a via and a zone as either item, and for a pair inside nets_a where nets_b is omitted. Out of scope is a shortfall outside the lists.
        for first, second in ((VIA, PAD), (PAD, VIA), (ZONE, TRACK), (TRACK, ZONE), (ZONE, VIA), (VIA, VIA)):
            with self.subTest(first=first[:5], second=second[:5]):
                judged = judge([clearance_between(first.format(MAINS_L), second.format(MAINS_N))], net_entry())
                self.assertEqual(failures(judged), [])
                self.assertEqual(len(judged.accepted), 1)
        judged = judge([clearance_between(VIA.format(MAINS_N), ZONE.format(MAINS_L))], net_entry())
        self.assertEqual(failures(judged), [])

    def test_a_creepage_entry_accepts_a_creepage_shortfall_and_prints_its_band_figure(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-NET-PAIR-SPACING-EXCEPTIONS.C3: The pure helper judging one entry against the basis, called with no layout, finds a well-formed signed entry sound and a flawed one flawed with the same findings the check reports. On a synthetic layout with a signed entry, net-pair entries being judged after the between and same-connector entries, a creepage shortfall between a pad of a net in nets_a and a track of a net in nets_b at or above accepted_mm is printed as one ACCEPTED line per entry carrying the constraint, both lists, the number of shortfalls covered, the narrowest reported distance, the accepted distance, the signed figure, the working voltage with its band figure, the reason and the bounding element, and fails nothing. The same holds for a via and a zone as either item, and for a pair inside nets_a where nets_b is omitted. Out of scope is a shortfall outside the lists.
        judged = judge([reported("creepage", 0.8, 0.6, TRACK.format(MAINS_L), VIA.format(MAINS_N))],
                       net_entry(constraint="creepage", accepted_mm=0.55))
        self.assertEqual(failures(judged), [])
        line = self.accepted_line(judged)
        self.assertIn("net pair mains_to_mains creepage", line)
        self.assertIn("band 0.5 mm", line)
        self.assertIn("against the signed 0.8 mm", line)

    def test_nets_b_omitted_or_equal_covers_every_pair_of_different_nets_inside_nets_a(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-NET-PAIR-SPACING-EXCEPTIONS.C3: The pure helper judging one entry against the basis, called with no layout, finds a well-formed signed entry sound and a flawed one flawed with the same findings the check reports. On a synthetic layout with a signed entry, net-pair entries being judged after the between and same-connector entries, a creepage shortfall between a pad of a net in nets_a and a track of a net in nets_b at or above accepted_mm is printed as one ACCEPTED line per entry carrying the constraint, both lists, the number of shortfalls covered, the narrowest reported distance, the accepted distance, the signed figure, the working voltage with its band figure, the reason and the bounding element, and fails nothing. The same holds for a via and a zone as either item, and for a pair inside nets_a where nets_b is omitted. Out of scope is a shortfall outside the lists.
        for entry in (net_entry(nets_a=[MAINS_L, MAINS_N], nets_b=None), net_entry(nets_a=[MAINS_L, MAINS_N], nets_b=[MAINS_N, MAINS_L])):
            with self.subTest(entry=entry.get("nets_b")):
                judged = judge([clearance_between(PAD.format(MAINS_L), PAD.format(MAINS_N)),
                                clearance_between(PAD.format(MAINS_N), VIA.format(MAINS_L), actual=0.9)], entry)
                self.assertEqual(failures(judged), [])
                line = self.accepted_line(judged)
                self.assertIn("2 of 2 shortfalls covered", line)
                self.assertIn("narrowest 0.84 mm", line)

    def test_a_pair_inside_nets_a_on_one_net_is_no_pair(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-NET-PAIR-SPACING-EXCEPTIONS.C3: The pure helper judging one entry against the basis, called with no layout, finds a well-formed signed entry sound and a flawed one flawed with the same findings the check reports. On a synthetic layout with a signed entry, net-pair entries being judged after the between and same-connector entries, a creepage shortfall between a pad of a net in nets_a and a track of a net in nets_b at or above accepted_mm is printed as one ACCEPTED line per entry carrying the constraint, both lists, the number of shortfalls covered, the narrowest reported distance, the accepted distance, the signed figure, the working voltage with its band figure, the reason and the bounding element, and fails nothing. The same holds for a via and a zone as either item, and for a pair inside nets_a where nets_b is omitted. Out of scope is a shortfall outside the lists.
        judged = judge([clearance_between(PAD.format(MAINS_L), TRACK.format(MAINS_L))], net_entry(nets_a=[MAINS_L, MAINS_N], nets_b=None))
        self.assertEqual(judged.accepted, [])
        self.assertEqual(len(failures(judged)), 1)
        self.assertEqual(judged.consumed, set())

    def test_one_line_for_an_entry_however_many_shortfalls_it_covers(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-NET-PAIR-SPACING-EXCEPTIONS.C3: The pure helper judging one entry against the basis, called with no layout, finds a well-formed signed entry sound and a flawed one flawed with the same findings the check reports. On a synthetic layout with a signed entry, net-pair entries being judged after the between and same-connector entries, a creepage shortfall between a pad of a net in nets_a and a track of a net in nets_b at or above accepted_mm is printed as one ACCEPTED line per entry carrying the constraint, both lists, the number of shortfalls covered, the narrowest reported distance, the accepted distance, the signed figure, the working voltage with its band figure, the reason and the bounding element, and fails nothing. The same holds for a via and a zone as either item, and for a pair inside nets_a where nets_b is omitted. Out of scope is a shortfall outside the lists.
        judged = judge([clearance_between(PAD.format(MAINS_L), TRACK.format(MAINS_N), actual=0.9),
                        clearance_between(VIA.format(MAINS_L), TRACK.format(MAINS_N), actual=0.85),
                        clearance_between(ZONE.format(MAINS_L), PAD.format(MAINS_N), actual=0.95)], net_entry())
        self.assertEqual(failures(judged), [])
        line = self.accepted_line(judged)
        self.assertIn("3 of 3 shortfalls covered", line)
        self.assertIn("narrowest 0.85 mm", line)
        self.assertEqual(len(judged.consumed), 3)

    def test_a_shortfall_a_between_entry_has_taken_is_not_judged_again_whatever_the_order_of_the_record(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-NET-PAIR-SPACING-EXCEPTIONS.C3: The pure helper judging one entry against the basis, called with no layout, finds a well-formed signed entry sound and a flawed one flawed with the same findings the check reports. On a synthetic layout with a signed entry, net-pair entries being judged after the between and same-connector entries, a creepage shortfall between a pad of a net in nets_a and a track of a net in nets_b at or above accepted_mm is printed as one ACCEPTED line per entry carrying the constraint, both lists, the number of shortfalls covered, the narrowest reported distance, the accepted distance, the signed figure, the working voltage with its band figure, the reason and the bounding element, and fails nothing. The same holds for a via and a zone as either item, and for a pair inside nets_a where nets_b is omitted. Out of scope is a shortfall outside the lists.
        violation = clearance_between(PAD.format(MAINS_L), PAD.format(MAINS_N))
        for entries in ((net_entry(), between_entry()), (between_entry(), net_entry())):
            with self.subTest(first=entries[0].get("pair")):
                judged = judge([violation], *entries)
                self.assertEqual(len(judged.accepted), 1)
                self.assertIn("between /MAINS_L and /MAINS_N", judged.accepted[0])
                (found,) = failures(judged)
                self.assertEqual(found[1], "accepted_exceptions[0]" if "nets_a" in entries[0] else "accepted_exceptions[1]")
                self.assertIn("reports no shortfall", found[2])


class TheJudgementFailsWhatLiesOutsideTheLists(unittest.TestCase):
    def test_a_shortfall_between_a_listed_net_and_one_outside_both_lists_stays_ordinary(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-NET-PAIR-SPACING-EXCEPTIONS.C4: On the same layout a shortfall between a net inside a list and a net outside both lists, a shortfall of the constraint the entry does not name, a shortfall of a pair already judged by a between entry, and a shortfall below accepted_mm each fail, the last naming the entry, and a report with no distance counts as 0.0 mm and fails. Out of scope is the plated-hole form.
        outside = clearance_between(PAD.format(MAINS_L), PAD.format(MAINS_M))
        judged = judge([outside, clearance_between(PAD.format(MAINS_L), PAD.format(MAINS_N))], net_entry())
        self.assertEqual(failures(judged), [])
        self.assertNotIn(id(outside), judged.consumed)
        self.assertEqual(len(judged.consumed), 1)
        self.assertEqual(len(judged.accepted), 1)
        alone = judge([outside], net_entry())
        self.assertEqual(alone.consumed, set())
        (found,) = failures(alone)
        self.assertEqual((found[0], found[1]), ("spacing_exception", "accepted_exceptions[0]"))

    def test_a_shortfall_of_the_constraint_the_entry_does_not_name_stays_ordinary(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-NET-PAIR-SPACING-EXCEPTIONS.C4: On the same layout a shortfall between a net inside a list and a net outside both lists, a shortfall of the constraint the entry does not name, a shortfall of a pair already judged by a between entry, and a shortfall below accepted_mm each fail, the last naming the entry, and a report with no distance counts as 0.0 mm and fails. Out of scope is the plated-hole form.
        creepage = reported("creepage", 0.8, 0.6, PAD.format(MAINS_L), PAD.format(MAINS_N))
        judged = judge([creepage], net_entry())
        self.assertEqual(judged.consumed, set())
        self.assertEqual(judged.accepted, [])
        self.assertEqual(len(failures(judged)), 1)
        both = judge([creepage, clearance_between(PAD.format(MAINS_L), PAD.format(MAINS_N))], net_entry())
        self.assertEqual(len(both.consumed), 1)
        self.assertNotIn(id(creepage), both.consumed)

    def test_a_shortfall_below_the_accepted_distance_fails_naming_the_entry_the_nets_and_both_distances(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-NET-PAIR-SPACING-EXCEPTIONS.C4: On the same layout a shortfall between a net inside a list and a net outside both lists, a shortfall of the constraint the entry does not name, a shortfall of a pair already judged by a between entry, and a shortfall below accepted_mm each fail, the last naming the entry, and a report with no distance counts as 0.0 mm and fails. Out of scope is the plated-hole form.
        judged = judge([clearance_between(TRACK.format(MAINS_L), VIA.format(MAINS_N), actual=0.79)], net_entry(accepted_mm=0.8))
        self.assertEqual(judged.accepted, [])
        ((rule, where, message),) = failures(judged)
        self.assertEqual((rule, where), ("spacing_exception", "accepted_exceptions[0]"))
        for words in ("accepted_exceptions[0]", "[/MAINS_L] and [/MAINS_N]", "down to 0.8 mm", "leaves 0.79 mm", "/MAINS_L and /MAINS_N"):
            self.assertIn(words, message)

    def test_a_shortfall_at_exactly_the_accepted_distance_is_accepted(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-NET-PAIR-SPACING-EXCEPTIONS.C4: On the same layout a shortfall between a net inside a list and a net outside both lists, a shortfall of the constraint the entry does not name, a shortfall of a pair already judged by a between entry, and a shortfall below accepted_mm each fail, the last naming the entry, and a report with no distance counts as 0.0 mm and fails. Out of scope is the plated-hole form.
        judged = judge([clearance_between(TRACK.format(MAINS_L), VIA.format(MAINS_N), actual=0.8)], net_entry(accepted_mm=0.8))
        self.assertEqual(failures(judged), [])
        self.assertEqual(len(judged.accepted), 1)

    def test_a_report_with_no_distance_counts_as_nothing_and_fails(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-NET-PAIR-SPACING-EXCEPTIONS.C4: On the same layout a shortfall between a net inside a list and a net outside both lists, a shortfall of the constraint the entry does not name, a shortfall of a pair already judged by a between entry, and a shortfall below accepted_mm each fail, the last naming the entry, and a report with no distance counts as 0.0 mm and fails. Out of scope is the plated-hole form.
        judged = judge([clearance_between(TRACK.format(MAINS_L), VIA.format(MAINS_N), actual=None)], net_entry())
        self.assertEqual(judged.accepted, [])
        ((_, _, message),) = failures(judged)
        self.assertIn("leaves 0 mm", message)

    def test_a_dropped_item_among_several_fails_alone_and_the_rest_are_accepted(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-NET-PAIR-SPACING-EXCEPTIONS.C4: On the same layout a shortfall between a net inside a list and a net outside both lists, a shortfall of the constraint the entry does not name, a shortfall of a pair already judged by a between entry, and a shortfall below accepted_mm each fail, the last naming the entry, and a report with no distance counts as 0.0 mm and fails. Out of scope is the plated-hole form.
        judged = judge([clearance_between(PAD.format(MAINS_L), TRACK.format(MAINS_N), actual=0.9),
                        clearance_between(VIA.format(MAINS_L), TRACK.format(MAINS_N), actual=0.5)], net_entry())
        self.assertEqual(len(failures(judged)), 1)
        self.assertEqual(len(judged.accepted), 1)
        self.assertIn("1 of 2 shortfalls covered", judged.accepted[0])

    def test_a_shortfall_a_rule_of_the_other_pair_reports_is_never_excused(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-NET-PAIR-SPACING-EXCEPTIONS.C4: On the same layout a shortfall between a net inside a list and a net outside both lists, a shortfall of the constraint the entry does not name, a shortfall of a pair already judged by a between entry, and a shortfall below accepted_mm each fail, the last naming the entry, and a report with no distance counts as 0.0 mm and fails. Out of scope is the plated-hole form.
        low_voltage = clearance_between(PAD.format(MAINS_L), PAD.format(LV_A), rule=board_check.SIGNED_RULE)
        held = clearance_between(PAD.format(MAINS_L), PAD.format(MAINS_N), rule=f"{board_check.REINFORCED_RULE} 1", figure=3.0, actual=0.84)
        for violation in (low_voltage, held):
            with self.subTest(rule=violation["description"][:40]):
                judged = judge([violation], net_entry(nets_a=[MAINS_L], nets_b=[MAINS_N]))
                self.assertEqual(judged.consumed, set())
                self.assertEqual(judged.accepted, [])
                (found,) = failures(judged)
                self.assertIn("reports no shortfall", found[2])
        # not even by an entry listing the low-voltage side's net
        judged = judge([low_voltage], net_entry(nets_a=[MAINS_L], nets_b=[LV_A]))
        self.assertEqual(judged.consumed, set())


class TheJudgementFailsClosed(unittest.TestCase):
    SHORTFALL = clearance_between(PAD.format(MAINS_L), PAD.format(MAINS_N))

    def assertOneFailure(self, judged, words: str, index: int = 0):
        self.assertEqual(judged.accepted, [])
        ((rule, where, message),) = failures(judged)
        self.assertEqual((rule, where), ("spacing_exception", f"accepted_exceptions[{index}]"))
        self.assertTrue(message.startswith(f"accepted_exceptions[{index}] "), message)
        self.assertIn(words, message)

    def test_an_entry_whose_acceptance_is_empty_a_placeholder_bracketed_or_dated_wrongly_fails(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-NET-PAIR-SPACING-EXCEPTIONS.C5: An entry whose acceptance is empty, a placeholder, in angle brackets, later than today or later than the record's own, whose constraint is creepage and accepted_mm is below the creepage band figure for its working_voltage_v or below its clearance band figure, whose constraint is clearance and accepted_mm is below the clearance band figure for its working_voltage_v, whose accepted_mm is below 0.2 mm, whose working_voltage_v exceeds the record's working voltage or the highest band row, or whose accepted_mm is not below the figure of the rule that reports its shortfalls, fails as spacing_exception naming the entry and excuses nothing. Out of scope is any entry of another form.
        for changes, words in (({"accepted_by": ""}, "accepted_by"), ({"accepted_by": "unsigned"}, "placeholder"),
                               ({"accepted_by": "<owner>"}, "placeholder"), ({"accepted_by": None}, "accepted_by"),
                               ({"accepted_on": "2026-10-13"}, "later than today"), ({"accepted_on": "2026-10-06"}, "later than the record's own"),
                               ({"accepted_on": "not a date"}, "not a valid calendar date")):
            with self.subTest(changes=changes):
                data = net_basis(net_entry(**{**changes}))
                signed, problems = read(data)
                if signed is None:
                    self.assertTrue(any("lacks accepted_by" in v.message for v in problems), [v.line() for v in problems])
                    continue
                judged = board_check.judge_exceptions(DESIGN, RECORD, signed, [self.SHORTFALL], LAYOUT, TODAY, MAINS)
                self.assertOneFailure(judged, words)
                self.assertEqual(judged.consumed, set())

    def test_the_acceptance_dated_the_day_of_the_record_or_today_is_signed(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-NET-PAIR-SPACING-EXCEPTIONS.C5: An entry whose acceptance is empty, a placeholder, in angle brackets, later than today or later than the record's own, whose constraint is creepage and accepted_mm is below the creepage band figure for its working_voltage_v or below its clearance band figure, whose constraint is clearance and accepted_mm is below the clearance band figure for its working_voltage_v, whose accepted_mm is below 0.2 mm, whose working_voltage_v exceeds the record's working voltage or the highest band row, or whose accepted_mm is not below the figure of the rule that reports its shortfalls, fails as spacing_exception naming the entry and excuses nothing. Out of scope is any entry of another form.
        judged = judge([self.SHORTFALL], net_entry(accepted_on="2026-10-05"))
        self.assertEqual(failures(judged), [])
        self.assertEqual(len(judged.accepted), 1)

    def test_an_entry_below_its_band_figures_below_the_least_distance_or_above_the_voltages_fails(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-NET-PAIR-SPACING-EXCEPTIONS.C5: An entry whose acceptance is empty, a placeholder, in angle brackets, later than today or later than the record's own, whose constraint is creepage and accepted_mm is below the creepage band figure for its working_voltage_v or below its clearance band figure, whose constraint is clearance and accepted_mm is below the clearance band figure for its working_voltage_v, whose accepted_mm is below 0.2 mm, whose working_voltage_v exceeds the record's working voltage or the highest band row, or whose accepted_mm is not below the figure of the rule that reports its shortfalls, fails as spacing_exception naming the entry and excuses nothing. Out of scope is any entry of another form.
        creepage = reported("creepage", 0.8, 0.6, PAD.format(MAINS_L), PAD.format(MAINS_N))
        for violation, changes, words in (
                (creepage, {"constraint": "creepage", "accepted_mm": 0.49}, "below the band creepage 0.5 mm"),
                (self.SHORTFALL, {"accepted_mm": 0.39}, "below the band clearance 0.4 mm"),
                (self.SHORTFALL, {"accepted_mm": 0.19, "working_voltage_v": 10}, "below 0.2 mm"),
                (self.SHORTFALL, {"working_voltage_v": 251}, "above the record's working voltage 250 V"),
                (self.SHORTFALL, {"working_voltage_v": 300}, "above the record's working voltage")):
            with self.subTest(changes=changes):
                judged = judge([violation], net_entry(**changes))
                self.assertOneFailure(judged, words)
                self.assertEqual(judged.consumed, set())

    def test_a_working_voltage_above_the_highest_row_alone_fails(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-NET-PAIR-SPACING-EXCEPTIONS.C5: An entry whose acceptance is empty, a placeholder, in angle brackets, later than today or later than the record's own, whose constraint is creepage and accepted_mm is below the creepage band figure for its working_voltage_v or below its clearance band figure, whose constraint is clearance and accepted_mm is below the clearance band figure for its working_voltage_v, whose accepted_mm is below 0.2 mm, whose working_voltage_v exceeds the record's working voltage or the highest band row, or whose accepted_mm is not below the figure of the rule that reports its shortfalls, fails as spacing_exception naming the entry and excuses nothing. Out of scope is any entry of another form.
        judged = judge([self.SHORTFALL], net_entry(working_voltage_v=300), working_voltage="400 V rms")
        self.assertOneFailure(judged, "above the highest functional band row")

    def test_a_creepage_entry_below_the_clearance_band_of_the_pair_fails(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-NET-PAIR-SPACING-EXCEPTIONS.C5: An entry whose acceptance is empty, a placeholder, in angle brackets, later than today or later than the record's own, whose constraint is creepage and accepted_mm is below the creepage band figure for its working_voltage_v or below its clearance band figure, whose constraint is clearance and accepted_mm is below the clearance band figure for its working_voltage_v, whose accepted_mm is below 0.2 mm, whose working_voltage_v exceeds the record's working voltage or the highest band row, or whose accepted_mm is not below the figure of the rule that reports its shortfalls, fails as spacing_exception naming the entry and excuses nothing. Out of scope is any entry of another form.
        creepage = reported("creepage", 0.9, 0.7, PAD.format(MAINS_L), PAD.format(MAINS_N))
        wide = [band(50, 0.3, 0.2), band(125, 0.5, 0.7), band(250, 1.0, 1.0)]
        judged = judge([creepage], net_entry(constraint="creepage", accepted_mm=0.6), rows=wide)
        self.assertOneFailure(judged, "below the band clearance 0.7 mm")

    def test_a_record_with_no_band_rows_or_lacking_a_figure_fails_every_net_pair_entry_and_spares_the_other_forms(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-NET-PAIR-SPACING-EXCEPTIONS.C5: An entry whose acceptance is empty, a placeholder, in angle brackets, later than today or later than the record's own, whose constraint is creepage and accepted_mm is below the creepage band figure for its working_voltage_v or below its clearance band figure, whose constraint is clearance and accepted_mm is below the clearance band figure for its working_voltage_v, whose accepted_mm is below 0.2 mm, whose working_voltage_v exceeds the record's working voltage or the highest band row, or whose accepted_mm is not below the figure of the rule that reports its shortfalls, fails as spacing_exception naming the entry and excuses nothing. Out of scope is any entry of another form.
        for rows, words in (([], "holds none"), ([band(50, 0.3, None), band(125, 0.5, None)], "no clearance_mm")):
            with self.subTest(words=words):
                judged = judge([self.SHORTFALL, clearance_between(PAD.format(MAINS_L), PAD.format(MAINS_M))],
                               net_entry(), between_entry(between=[MAINS_L, MAINS_M]), rows=rows)
                self.assertEqual(len(judged.accepted), 1)
                self.assertIn("between /MAINS_L and /MAINS_M", judged.accepted[0])
                ((_, where, message),) = failures(judged)
                self.assertEqual(where, "accepted_exceptions[0]")
                self.assertIn(words, message)

    def test_an_entry_accepting_no_less_than_the_figure_of_the_rule_relaxes_nothing(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-NET-PAIR-SPACING-EXCEPTIONS.C5: An entry whose acceptance is empty, a placeholder, in angle brackets, later than today or later than the record's own, whose constraint is creepage and accepted_mm is below the creepage band figure for its working_voltage_v or below its clearance band figure, whose constraint is clearance and accepted_mm is below the clearance band figure for its working_voltage_v, whose accepted_mm is below 0.2 mm, whose working_voltage_v exceeds the record's working voltage or the highest band row, or whose accepted_mm is not below the figure of the rule that reports its shortfalls, fails as spacing_exception naming the entry and excuses nothing. Out of scope is any entry of another form.
        for accepted in (1.0, 1.5):
            with self.subTest(accepted=accepted):
                self.assertOneFailure(judge([self.SHORTFALL], net_entry(accepted_mm=accepted)), "relaxes nothing")
        judged = judge([clearance_between(PAD.format(MAINS_L), PAD.format(MAINS_N), actual=0.995)], net_entry(accepted_mm=0.99))
        self.assertEqual(failures(judged), [])

    def test_a_record_unsigned_or_synthetic_on_an_orderable_board_is_honoured_for_no_entry(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-NET-PAIR-SPACING-EXCEPTIONS.C6: With the Mains class unresolved every net-pair entry fails closed, and an entry listing a net the layout lacks, a net outside the Mains class, both nets of a pair in held_at_reinforced on opposite sides, or covering no reported shortfall fails as spacing_exception naming the entry, and a record that is unsigned or synthetic on an orderable board is honoured for no entry. Out of scope is a shortfall the check does not report.
        signed, problems = read(net_basis(net_entry(), accepted_on="2999-01-01"))
        self.assertIsNone(signed)
        self.assertTrue(any(v.rule == "separation_basis" and "unsigned" in v.message for v in problems))
        signed, problems = read(net_basis(net_entry(), accepted_by=None))
        self.assertIsNone(signed)
        with_record = yaml.safe_dump(net_basis(net_entry()))
        import tempfile
        with tempfile.TemporaryDirectory() as folder:
            os.makedirs(os.path.join(folder, os.path.dirname(RECORD)))
            with open(os.path.join(folder, RECORD), "w", encoding="utf-8") as handle:
                handle.write(with_record)
            signed, problems = board_check.read_record(yaml, folder, DESIGN, RECORD, False, TODAY)
        self.assertIsNone(signed)
        self.assertTrue(any("marked synthetic" in v.message for v in problems))

    def test_an_entry_listing_a_net_the_layout_lacks_fails_naming_it(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-NET-PAIR-SPACING-EXCEPTIONS.C6: With the Mains class unresolved every net-pair entry fails closed, and an entry listing a net the layout lacks, a net outside the Mains class, both nets of a pair in held_at_reinforced on opposite sides, or covering no reported shortfall fails as spacing_exception naming the entry, and a record that is unsigned or synthetic on an orderable board is honoured for no entry. Out of scope is a shortfall the check does not report.
        judged = judge([self.SHORTFALL], net_entry(nets_a=[MAINS_L, "/MAINS_X"]))
        self.assertOneFailure(judged, "/MAINS_X, which the layout lacks")
        judged = judge([self.SHORTFALL], net_entry(nets_b=["/MAINS_X"]))
        self.assertOneFailure(judged, "/MAINS_X, which the layout lacks")
        self.assertEqual(judged.consumed, set())

    def test_an_entry_listing_a_net_outside_the_mains_class_fails_naming_it(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-NET-PAIR-SPACING-EXCEPTIONS.C6: With the Mains class unresolved every net-pair entry fails closed, and an entry listing a net the layout lacks, a net outside the Mains class, both nets of a pair in held_at_reinforced on opposite sides, or covering no reported shortfall fails as spacing_exception naming the entry, and a record that is unsigned or synthetic on an orderable board is honoured for no entry. Out of scope is a shortfall the check does not report.
        self.assertOneFailure(judge([self.SHORTFALL], net_entry(nets_a=[MAINS_L, LV_A])), "LV_A, which is not in the Mains net class")
        self.assertOneFailure(judge([self.SHORTFALL], net_entry(nets_b=[MAINS_N, LV_A])), "LV_A, which is not in the Mains net class")
        self.assertOneFailure(judge([self.SHORTFALL], net_entry(), mains={MAINS_L}), "/MAINS_N, which is not in the Mains net class")

    def test_a_pair_spanning_mains_and_low_voltage_is_not_excused_by_the_form(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-NET-PAIR-SPACING-EXCEPTIONS.C6: With the Mains class unresolved every net-pair entry fails closed, and an entry listing a net the layout lacks, a net outside the Mains class, both nets of a pair in held_at_reinforced on opposite sides, or covering no reported shortfall fails as spacing_exception naming the entry, and a record that is unsigned or synthetic on an orderable board is honoured for no entry. Out of scope is a shortfall the check does not report.
        spanning = clearance_between(PAD.format(MAINS_L), PAD.format(LV_A), rule=board_check.SIGNED_RULE, figure=3.0)
        judged = judge([spanning], net_entry(nets_a=[MAINS_L], nets_b=[LV_A]))
        self.assertEqual(judged.consumed, set())
        self.assertEqual(judged.accepted, [])
        self.assertOneFailure(judged, "not in the Mains net class")

    def test_with_the_mains_class_unresolved_every_entry_fails_closed(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-NET-PAIR-SPACING-EXCEPTIONS.C6: With the Mains class unresolved every net-pair entry fails closed, and an entry listing a net the layout lacks, a net outside the Mains class, both nets of a pair in held_at_reinforced on opposite sides, or covering no reported shortfall fails as spacing_exception naming the entry, and a record that is unsigned or synthetic on an orderable board is honoured for no entry. Out of scope is a shortfall the check does not report.
        self.assertOneFailure(judge([self.SHORTFALL], net_entry(), mains=None), "cannot be judged")
        signed, _ = read(net_basis(net_entry()))
        self.assertOneFailure(board_check.judge_exceptions(DESIGN, RECORD, signed, [self.SHORTFALL], LAYOUT, TODAY), "cannot be judged")

    def test_the_pair_held_at_reinforced_on_opposite_sides_fails_in_either_order_and_inside_one_list(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-NET-PAIR-SPACING-EXCEPTIONS.C6: With the Mains class unresolved every net-pair entry fails closed, and an entry listing a net the layout lacks, a net outside the Mains class, both nets of a pair in held_at_reinforced on opposite sides, or covering no reported shortfall fails as spacing_exception naming the entry, and a record that is unsigned or synthetic on an orderable board is honoured for no entry. Out of scope is a shortfall the check does not report.
        held = {"mains_to_mains": {**basis()["mains_to_mains"], "held_at_reinforced": [[MAINS_L, MAINS_N]]}}
        for changes in ({"nets_a": [MAINS_L], "nets_b": [MAINS_N]}, {"nets_a": [MAINS_N], "nets_b": [MAINS_L]},
                        {"nets_a": [MAINS_L, MAINS_M], "nets_b": [MAINS_M, MAINS_N]}, {"nets_a": [MAINS_L, MAINS_N], "nets_b": None}):
            with self.subTest(changes=changes):
                judged = judge([self.SHORTFALL], net_entry(**changes), **held)
                self.assertOneFailure(judged, "held at reinforced across the open contact")
                self.assertEqual(judged.consumed, set())

    def test_a_held_pair_listed_on_the_same_side_or_not_at_all_is_not_the_open_contact(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-NET-PAIR-SPACING-EXCEPTIONS.C6: With the Mains class unresolved every net-pair entry fails closed, and an entry listing a net the layout lacks, a net outside the Mains class, both nets of a pair in held_at_reinforced on opposite sides, or covering no reported shortfall fails as spacing_exception naming the entry, and a record that is unsigned or synthetic on an orderable board is honoured for no entry. Out of scope is a shortfall the check does not report.
        held = {"mains_to_mains": {**basis()["mains_to_mains"], "held_at_reinforced": [[MAINS_L, MAINS_N]]}}
        judged = judge([clearance_between(PAD.format(MAINS_L), PAD.format(MAINS_M))],
                       net_entry(nets_a=[MAINS_L, MAINS_N], nets_b=[MAINS_M]), **held)
        self.assertEqual(failures(judged), [])
        self.assertEqual(len(judged.accepted), 1)

    def test_an_entry_no_reported_shortfall_uses_fails_and_so_does_one_whose_shortfalls_another_entry_took(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-NET-PAIR-SPACING-EXCEPTIONS.C6: With the Mains class unresolved every net-pair entry fails closed, and an entry listing a net the layout lacks, a net outside the Mains class, both nets of a pair in held_at_reinforced on opposite sides, or covering no reported shortfall fails as spacing_exception naming the entry, and a record that is unsigned or synthetic on an orderable board is honoured for no entry. Out of scope is a shortfall the check does not report.
        self.assertOneFailure(judge([], net_entry()), "reports no shortfall")
        judged = judge([self.SHORTFALL], net_entry(), net_entry(accepted_mm=0.7))
        self.assertEqual(len(judged.accepted), 1)
        (found,) = failures(judged)
        self.assertEqual(found[1], "accepted_exceptions[1]")
        self.assertIn("reports no shortfall", found[2])


class TheHardwareNotesStateTheNetPairForm(unittest.TestCase):
    NOTES = os.path.join(os.path.dirname(os.path.dirname(TOOLS)), "hardware", "README.md")

    def sections(self):
        with open(self.NOTES, encoding="utf-8") as handle:
            text = handle.read()
        (records,) = [line for line in text.splitlines() if line.startswith("- be held to a signed **separation basis record**")]
        rows = [line for line in text.splitlines() if line.startswith("| ")]
        adopter = text[text.index("## Re-deriving the separation basis"):]
        return records, rows, adopter

    def test_the_record_keys_the_reader_row_the_spacing_exception_row_and_the_adopter_step_state_the_form(self):
        # SOL-PRE-ORDER-CHECK-JUDGES-NET-PAIR-SPACING-EXCEPTIONS.C8: The check over every tracked design reports no new failure, and hardware/README.md states the net-pairs form in the record keys, the reader row, the spacing_exception row and the adopter step for exceptions, including that the working voltage is the owner's assertion and the check does not recompute it. Out of scope is the main board's own design, whose record entries are another leaf's.
        records, rows, adopter = self.sections()
        for words in ("`nets_a`", "`nets_b`", "`working_voltage_v`", "fourth form", "holds no `between`",
                      "The working voltage is the owner's assertion", "the check does not recompute it"):
            self.assertIn(words, records)
        (reader,) = [row for row in rows if row.startswith("| Separation basis record |")]
        for words in ("`nets_a`", "`working_voltage_v`", "optionally `nets_b`"):
            self.assertIn(words, reader)
        (table,) = [row for row in rows if row.startswith("| `spacing_exception` |")]
        for words in ("A `nets_a` entry is judged after every other form", "outside the `Mains` net class", "band creepage",
                      "open contact", "`ACCEPTED` line naming the constraint, both lists of nets", "every `nets_a` entry fails"):
            self.assertIn(words, table)
        for words in ("`nets_a` entry", "the working voltage is the owner's assertion", "does not recompute it",
                      "functional band rows"):
            self.assertIn(words, adopter)


if __name__ == "__main__":
    unittest.main()
