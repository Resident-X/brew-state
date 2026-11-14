#!/usr/bin/env python3
"""The pre-order check's pad numbering rule, driven on synthetic layouts with no KiCad involved, and one test that has KiCad place the pads of a back footprint.

A dual-row or four-sided package is numbered counter-clockwise from pin 1 seen
from the top of the part. The rule fails a footprint whose numbers run
clockwise, and judges nothing whose numbers follow no single direction round
the part. The layouts here are written from text, every footprint with generic
references and part numbers.
"""

from __future__ import annotations

import os
import sys
import unittest

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import board_check  # noqa: E402
import board_fixtures  # noqa: E402
import sexpr  # noqa: E402
import test_severity_policy as policy_tests  # noqa: E402
import test_workmanship_acceptance as acceptance_tests  # noqa: E402

DESIGN = board_check.Design("hardware/synth/board/board.kicad_pro")
RULE = "pad_numbering"


def pad(number, x, y, kind="smd", layers=('"F.Cu"', '"F.Mask"', '"F.Paste"'), size=(1, 0.6)):
    return (f'(pad "{number}" {kind} rect (at {x} {y}) (size {size[0]} {size[1]}) (layers {" ".join(layers)}) '
            f'(net "/NET_{number}") (uuid {board_fixtures.uuid()}))')


def part(reference, pads, name="synth:Package", x=30.0, y=20.0, angle=0, layer="F.Cu", mpn=None):
    """A footprint with `pads`, placed at (x, y) turned to `angle` on `layer`, with an MPN field where one is given."""
    field = f'(property "MPN" "{mpn}" (at 0 0) (layer "F.Fab") (uuid {board_fixtures.uuid()})) ' if mpn else ""
    return (f'(footprint "{name}" (layer "{layer}") (uuid {board_fixtures.uuid()}) (at {x} {y} {angle}) '
            f'(property "Reference" "{reference}" (at 0 -4) (layer "F.SilkS") (uuid {board_fixtures.uuid()})) {field}'
            + " ".join(pads) + ")")


def dual_row(count, clockwise, pitch=1.27, half_width=2.7, numbers=None, **kwargs):
    """The pads of a dual-row package of `count` pins. Counter-clockwise on the screen, y pointing down the board: pin 1 at
    the upper left, down the left side, then up the right side. Clockwise is its mirror image."""
    per = count // 2
    span = [(i - (per - 1) / 2) * pitch for i in range(per)]
    pins = [(-half_width, y) for y in span] + [(half_width, y) for y in reversed(span)]
    if clockwise:
        pins = [(-x, y) for x, y in pins]
    return [pad(n, x, y, **kwargs) for n, (x, y) in zip(numbers or range(1, count + 1), pins)]


def quad_points(per_side, clockwise, pitch=0.5, half=3.0):
    """Where the pins of a four-sided package stand, `per_side` to a side, in the order of its numbers. Counter-clockwise:
    pin 1 at the upper left of the left side, down the left side, along the bottom to the right, up the right side, along
    the top to the left. Clockwise is its mirror image."""
    span = [(i - (per_side - 1) / 2) * pitch for i in range(per_side)]
    left = [(-half, y) for y in span]
    bottom = [(x, half) for x in span]
    right = [(half, -y) for y in span]
    top = [(-x, -half) for x in span]
    pins = left + bottom + right + top
    return [(-x, y) for x, y in pins] if clockwise else pins


def quad(per_side, clockwise, **kwargs):
    return [pad(n, x, y) for n, (x, y) in enumerate(quad_points(per_side, clockwise, **kwargs), 1)]


def judged(*footprints):
    tree = sexpr.parse_one(board_fixtures.layout(list(footprints)))
    return board_check.pad_numbering(DESIGN, tree)


class AClockwiseFootprintFails(unittest.TestCase):
    def test_a_dual_row_footprint_numbered_clockwise_fails_naming_its_reference_footprint_and_part_number(self):
        # SOL-PRE-ORDER-CHECK-FAILS-A-FOOTPRINT-NUMBERED-CLOCKWISE.C1: A dual-row or four-sided footprint whose pad numbers run clockwise seen from the top of the part fails the design, naming the footprint
        for count in (4, 6, 8, 16):
            with self.subTest(pins=count):
                found = judged(part("U7", dual_row(count, True), name="synth:Dual_Row", mpn="GEN-123"))
                self.assertEqual([v.rule for v in found], [RULE])
                self.assertEqual(found[0].location, "U7 (Dual_Row, part GEN-123)")
                self.assertIn("run clockwise round the part as seen from its top", found[0].message)
                self.assertIn("mirror image of the counter-clockwise numbering from pin 1", found[0].message)

    def test_a_four_sided_footprint_numbered_clockwise_fails_and_a_footprint_without_a_part_number_is_named_by_footprint_alone(self):
        # SOL-PRE-ORDER-CHECK-FAILS-A-FOOTPRINT-NUMBERED-CLOCKWISE.C1: A dual-row or four-sided footprint whose pad numbers run clockwise seen from the top of the part fails the design, naming the footprint
        found = judged(part("U8", quad(4, True), name="synth:Quad"))
        self.assertEqual([(v.rule, v.location) for v in found], [(RULE, "U8 (Quad)")])

    def test_a_clockwise_footprint_fails_wherever_it_is_placed_and_however_it_is_turned(self):
        # SOL-PRE-ORDER-CHECK-FAILS-A-FOOTPRINT-NUMBERED-CLOCKWISE.C1: A dual-row or four-sided footprint whose pad numbers run clockwise seen from the top of the part fails the design, naming the footprint
        for angle in (0, 90, 180, 270, 37, -45):
            with self.subTest(angle=angle):
                self.assertEqual(len(judged(part("U1", dual_row(8, True), x=12.5, y=33.1, angle=angle))), 1)
                self.assertEqual(len(judged(part("U1", quad(5, True), x=40, y=7, angle=angle))), 1)

    def test_only_the_clockwise_footprints_of_a_layout_are_named(self):
        # SOL-PRE-ORDER-CHECK-FAILS-A-FOOTPRINT-NUMBERED-CLOCKWISE.C1: A dual-row or four-sided footprint whose pad numbers run clockwise seen from the top of the part fails the design, naming the footprint
        found = judged(part("U1", dual_row(8, False), x=10), part("U2", dual_row(8, True), x=25),
                       part("U3", quad(4, False), x=40), part("U4", quad(4, True), x=55))
        self.assertEqual(sorted(v.location.split()[0] for v in found), ["U2", "U4"])

    def test_an_exposed_centre_pad_and_pads_without_copper_or_a_whole_number_do_not_hide_a_clockwise_numbering(self):
        # SOL-PRE-ORDER-CHECK-FAILS-A-FOOTPRINT-NUMBERED-CLOCKWISE.C1: A dual-row or four-sided footprint whose pad numbers run clockwise seen from the top of the part fails the design, naming the footprint
        extras = [pad(9, 0, 0, size=(2, 2)),
                  pad("EP", 0.3, 0.2),
                  pad(10, 5, 5, layers=('"F.Paste"',)),
                  pad(11, -5, 5, kind="np_thru_hole", layers=('"*.Cu"',)),
                  pad(12, -2.7, 3.5), pad(12, 2.7, 3.5)]
        self.assertEqual(len(judged(part("U1", dual_row(8, True) + extras))), 1)


class ACounterClockwiseFootprintPasses(unittest.TestCase):
    def test_counter_clockwise_dual_row_and_four_sided_footprints_pass_on_the_front(self):
        # SOL-PRE-ORDER-CHECK-FAILS-A-FOOTPRINT-NUMBERED-CLOCKWISE.C2: A footprint numbered counter-clockwise passes, on the front and on the back of the board
        for angle in (0, 90, 37):
            for pads in (dual_row(4, False), dual_row(6, False), dual_row(16, False), quad(4, False), quad(5, False)):
                with self.subTest(angle=angle, pads=len(pads)):
                    self.assertEqual(judged(part("U1", pads, angle=angle)), [])

    def test_a_footprint_on_the_back_of_the_board_is_seen_from_the_back_so_its_sense_is_turned_about(self):
        # SOL-PRE-ORDER-CHECK-FAILS-A-FOOTPRINT-NUMBERED-CLOCKWISE.C2: A footprint numbered counter-clockwise passes, on the front and on the back of the board
        # KiCad writes a back footprint's pads already placed: its position plus each pad's own position, turned by its angle.
        # Its pad 1 on the upper left of the board seen from the front and its pads running counter-clockwise on that view
        # is a part numbered clockwise as seen from its top, which is the back.
        back = ('"B.Cu"', '"B.Mask"', '"B.Paste"')
        for angle in (0, 90, 37):
            with self.subTest(angle=angle):
                self.assertEqual(len(judged(part("U1", dual_row(8, False, layers=back), layer="B.Cu", angle=angle))), 1)
                self.assertEqual(judged(part("U1", dual_row(8, True, layers=back), layer="B.Cu", angle=angle)), [])
                self.assertEqual(judged(part("U1", quad(4, True), layer="B.Cu", angle=angle)), [])
                self.assertEqual(len(judged(part("U1", quad(4, False), layer="B.Cu", angle=angle))), 1)


class AFootprintWithNoSingleDirectionIsNotJudged(unittest.TestCase):
    def test_zig_zag_and_row_by_row_headers_relays_and_in_line_parts_are_not_judged(self):
        # SOL-PRE-ORDER-CHECK-FAILS-A-FOOTPRINT-NUMBERED-CLOCKWISE.C3: A footprint whose pad numbers follow no single direction round the part is not judged
        zigzag = [pad(n, x, y) for n, (x, y) in enumerate(
            [(-1.27, -2.54), (1.27, -2.54), (-1.27, -1.27), (1.27, -1.27), (-1.27, 0), (1.27, 0), (-1.27, 1.27), (1.27, 1.27),
             (-1.27, 2.54), (1.27, 2.54)], 1)]
        by_rows = [pad(n, x, y) for n, (x, y) in enumerate(
            [(-1.27, -2.54), (-1.27, -1.27), (-1.27, 0), (-1.27, 1.27), (-1.27, 2.54), (1.27, -2.54), (1.27, -1.27), (1.27, 0),
             (1.27, 1.27), (1.27, 2.54)], 1)]
        relay = [pad(n, x, y, kind="thru_hole", layers=('"*.Cu"',)) for n, (x, y) in
                 [(1, (0, 0)), (2, (7.6, 3.5)), (3, (0, 3.5)), (4, (7.6, -3.5)), (5, (0, -3.5))]]
        in_line = [pad(n, 2.54 * (n - 1), 0, kind="thru_hole", layers=('"*.Cu"',)) for n in range(1, 8)]
        for name, pads in (("zig-zag header", zigzag), ("header numbered by rows", by_rows), ("relay", relay), ("in-line header", in_line)):
            with self.subTest(footprint=name):
                self.assertEqual(judged(part("J1", pads)), [])
                self.assertEqual(judged(part("J1", pads, layer="B.Cu")), [])

    def test_a_part_of_fewer_than_four_distinct_numbers_two_pad_parts_and_a_number_a_part_repeats_are_not_judged(self):
        # SOL-PRE-ORDER-CHECK-FAILS-A-FOOTPRINT-NUMBERED-CLOCKWISE.C3: A footprint whose pad numbers follow no single direction round the part is not judged
        three = [pad(1, -1, -1), pad(2, 1, -1), pad(3, 1, 1)]
        two = [pad(1, -1, 0), pad(2, 1, 0)]
        repeated = [pad(1, -1, -1), pad(1, 1, -1), pad(1, 1, 1), pad(1, -1, 1)]
        for name, pads in (("three distinct numbers", three), ("two pads", two), ("one number only", repeated)):
            with self.subTest(footprint=name):
                self.assertEqual(judged(part("Q1", pads)), [])

    def test_non_numeric_numbering_and_pads_with_no_number_are_not_judged(self):
        # SOL-PRE-ORDER-CHECK-FAILS-A-FOOTPRINT-NUMBERED-CLOCKWISE.C3: A footprint whose pad numbers follow no single direction round the part is not judged
        grid = [pad(name, x, y) for name, (x, y) in zip(("A1", "A2", "B2", "B1"), [(-1, -1), (1, -1), (1, 1), (-1, 1)])]
        unnumbered = [pad("", x, y) for x, y in [(-1, -1), (1, -1), (1, 1), (-1, 1)]]
        self.assertEqual(judged(part("U1", grid)), [])
        self.assertEqual(judged(part("U2", unnumbered)), [])

    def test_a_footprint_whose_pads_stand_in_neither_two_rows_nor_four_sides_is_not_judged(self):
        # SOL-PRE-ORDER-CHECK-FAILS-A-FOOTPRINT-NUMBERED-CLOCKWISE.C3: A footprint whose pad numbers follow no single direction round the part is not judged
        import math
        circle = [pad(n, 2 * math.cos(math.radians(-90 + 60 * (n - 1))), 2 * math.sin(math.radians(-90 + 60 * (n - 1))))
                  for n in range(1, 7)]
        self.assertEqual(judged(part("J1", circle)), [])

    def test_numbers_that_wind_more_than_once_round_the_part_or_run_across_it_follow_no_single_direction(self):
        # SOL-PRE-ORDER-CHECK-FAILS-A-FOOTPRINT-NUMBERED-CLOCKWISE.C3: A footprint whose pad numbers follow no single direction round the part is not judged
        ring = quad_points(3, False)
        wound = [pad(n, *ring[(-5 * (n - 1)) % 12]) for n in range(1, 13)]
        self.assertEqual(judged(part("U1", wound)), [])
        across = [pad(1, -3, -1), pad(2, 3, 1), pad(3, 3, -1), pad(4, -3, 1)]
        self.assertEqual(judged(part("U2", across)), [])

    def test_a_dual_row_footprint_whose_numbers_stop_following_one_direction_is_not_judged(self):
        # SOL-PRE-ORDER-CHECK-FAILS-A-FOOTPRINT-NUMBERED-CLOCKWISE.C3: A footprint whose pad numbers follow no single direction round the part is not judged
        swapped = dual_row(8, True, numbers=[1, 2, 4, 3, 5, 6, 7, 8])
        self.assertEqual(judged(part("U1", swapped)), [])


class NoRecordWaivesAClockwiseFootprint(policy_tests.Policed):
    def line(self):
        return board_check.Violation(acceptance_tests.PROJECT, RULE, "U7 (Dual_Row)", "the pad numbers of U7 run clockwise")

    def test_a_workmanship_acceptance_entry_for_the_rule_covers_nothing_and_fails_naming_the_rules_it_accepts(self):
        # SOL-PRE-ORDER-CHECK-FAILS-A-FOOTPRINT-NUMBERED-CLOCKWISE.C4: No acceptance record waives a clockwise-numbered footprint
        self.assertNotIn(RULE, board_check.ACCEPTABLE_WORKMANSHIP)
        left, accepted = self.judge([self.line()], [acceptance_tests.entry(rule=RULE, scope="R1")])
        self.assertEqual(accepted, [])
        self.assertIn(self.line().location, [v.location for v in left if v.rule == RULE])
        failures = [v for v in left if v.rule == "workmanship_acceptance"]
        self.assertEqual(len(failures), 1)
        self.assertIn(f"names the rule {RULE}, which the record does not accept", failures[0].message)

    def test_a_severity_policy_entry_for_the_rule_is_refused_and_the_line_stays_a_violation_with_no_warning(self):
        # SOL-PRE-ORDER-CHECK-FAILS-A-FOOTPRINT-NUMBERED-CLOCKWISE.C4: No acceptance record waives a clockwise-numbered footprint
        self.assertNotIn(RULE, board_check.POLICY_CLASSES)
        for severity in ("WARNING", "ERROR"):
            with self.subTest(severity=severity):
                left, warnings, _ = self.run_policy([self.line()], [policy_tests.entry(RULE, severity)])
                self.assertEqual(warnings, [])
                self.assertIn(RULE, [v.rule for v in left])
                self.assertIn("severity_policy", [v.rule for v in left])


class TheReportLineFailsTheDesign(unittest.TestCase):
    def test_the_line_is_a_violation_in_the_checks_report_shape(self):
        # SOL-PRE-ORDER-CHECK-FAILS-A-FOOTPRINT-NUMBERED-CLOCKWISE.C1: A dual-row or four-sided footprint whose pad numbers run clockwise seen from the top of the part fails the design, naming the footprint
        line = judged(part("U7", dual_row(6, True), name="synth:Package", mpn="GEN-123"))[0].line()
        self.assertTrue(line.startswith(f"VIOLATION | {DESIGN.project} | {RULE} | U7 (Package, part GEN-123) | "))


class TheHardwareNotesStateTheRule(unittest.TestCase):
    def test_the_notes_and_the_verify_task_state_the_rule_what_it_judges_and_what_it_leaves_unjudged(self):
        # SOL-PRE-ORDER-CHECK-FAILS-A-FOOTPRINT-NUMBERED-CLOCKWISE.C6: The hardware notes state the rule, what it judges and what it leaves unjudged
        repository = os.path.dirname(os.path.dirname(TOOLS))
        with open(os.path.join(repository, "hardware", "README.md"), encoding="utf-8") as handle:
            notes = handle.read()
        with open(os.path.join(repository, "Taskfile.yml"), encoding="utf-8") as handle:
            taskfile = handle.read()
        verify = taskfile[taskfile.index("  hw:verify:"):]
        verify = verify[: verify.index("\n\n")]
        paragraph = notes[notes.index("**Pad numbering** (`pad_numbering`)"):]
        paragraph = paragraph[: paragraph.index("\n")]
        for words in ("counter-clockwise from pin 1", "two parallel straight lines", "four lines", "at least four distinct numbers",
                      "exposed centre pad", "not judged", "zig-zag", "seen from the back", "No acceptance record waives"):
            self.assertIn(words, paragraph)
        self.assertIn("| `pad_numbering` |", notes)
        self.assertIn("pad_numbering", notes[notes.index("task hw:prove` adds"):])
        for words in ("clockwise", "no acceptance record waives it"):
            self.assertIn(words, verify)


if __name__ == "__main__":
    unittest.main()
