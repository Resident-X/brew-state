#!/usr/bin/env python3
"""The pre-order check's fiducial rule and polarity-mark rule, driven on synthetic layouts with no KiCad involved."""

from __future__ import annotations

import os
import sys
import unittest

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)

import board_check  # noqa: E402
import board_geometry  # noqa: E402
import sexpr  # noqa: E402

DESIGN = board_check.Design("a/a.kicad_pro")


def tree_of(*items: str) -> list:
    return sexpr.parse_one("(kicad_pcb (version 20260206) " + " ".join(items) + ")")


def pad(number, x, y, net, size=(0.6, 0.6), kind="smd", extra="", side="F"):
    layers = f'"{side}.Cu" "{side}.Mask"' if kind == "smd" else '"*.Cu"'
    drill = "" if kind == "smd" else "(drill 0.8)"
    return (f'(pad "{number}" {kind} rect (at {x} {y}) (size {size[0]} {size[1]}) {drill} (layers {layers}) '
            f'{extra} (net "{net}"))')


def lines(layer, *segments):
    return " ".join(f'(fp_line (start {a} {b}) (end {c} {d}) (layer "{layer}"))' for a, b, c, d in segments)


def part(reference, pads, silk="", attr="smd", at=(10, 10), side="F.Cu", angle=0):
    place = f"{at[0]} {at[1]} {angle}" if angle else f"{at[0]} {at[1]}"
    return (f'(footprint "lib:part" (layer "{side}") (at {place}) (attr {attr}) '
            f'(property "Reference" "{reference}" (at 0 -3 0) (layer "F.SilkS")) ' + " ".join(pads) + " " + silk + ")")


def fiducial(reference, at, side="F.Cu"):
    return part(reference, [pad("", 0, 0, "", (1, 1), extra="(property pad_prop_fiducial_glob)")], attr="smd exclude_from_bom",
                at=at, side=side)


def resistor(reference, side="F.Cu", at=(10, 10), attr="smd"):
    return part(reference, [pad(1, -1, 0, "A"), pad(2, 1, 0, "B")], attr=attr, at=at, side=side)


def three_fiducials(side="F.Cu", prefix="FID"):
    return [fiducial(f"{prefix}{i}", (2 + 10 * i, 2), side) for i in range(3)]


class EachSideWithAssembledPartsCarriesThreeFiducials(unittest.TestCase):
    def found(self, *items):
        return board_check.missing_fiducials(DESIGN, tree_of(*items))

    def test_a_side_with_surface_mount_parts_and_three_fiducials_passes(self):
        # SOL-PRE-ORDER-CHECK-FIDUCIALS-AND-POLARITY-MARKS.C1: A fiducial is a pad carrying KiCad's global fiducial pad property, counted on the side its footprint sits on, and the rule requires at least three on each side that carries surface-mount parts
        self.assertEqual(self.found(resistor("R1"), *three_fiducials()), [])

    def test_a_side_short_of_fiducials_fails_naming_the_side_and_the_count_found(self):
        # SOL-PRE-ORDER-CHECK-FIDUCIALS-AND-POLARITY-MARKS.C1: A fiducial is a pad carrying KiCad's global fiducial pad property, counted on the side its footprint sits on, and the rule requires at least three on each side that carries surface-mount parts
        # SOL-PRE-ORDER-CHECK-FIDUCIALS-AND-POLARITY-MARKS.C3: A failure of any rule in this leaf is reported with the rule's name, the design, and the offending item
        found = self.found(resistor("R1"), *three_fiducials()[:2])
        self.assertEqual([(v.design, v.rule, v.location) for v in found], [("a/a.kicad_pro", "side_fiducials", "the front side (F.Cu)")])
        self.assertIn("the front side has 1 surface-mount parts and 2 fiducials; add 1 or more", found[0].message)
        self.assertEqual(len(self.found(resistor("R1"))), 1)

    def test_each_side_is_counted_on_its_own_so_the_front_fiducials_do_not_serve_the_back(self):
        # SOL-PRE-ORDER-CHECK-FIDUCIALS-AND-POLARITY-MARKS.C1: A fiducial is a pad carrying KiCad's global fiducial pad property, counted on the side its footprint sits on, and the rule requires at least three on each side that carries surface-mount parts
        found = self.found(resistor("R1"), resistor("R2", side="B.Cu"), *three_fiducials())
        self.assertEqual([v.location for v in found], ["the back side (B.Cu)"])
        self.assertIn("0 fiducials", found[0].message)
        self.assertEqual(self.found(resistor("R1"), resistor("R2", side="B.Cu"), *three_fiducials(), *three_fiducials("B.Cu", "BF")), [])

    def test_a_pad_without_the_global_fiducial_property_is_no_fiducial(self):
        # SOL-PRE-ORDER-CHECK-FIDUCIALS-AND-POLARITY-MARKS.C1: A fiducial is a pad carrying KiCad's global fiducial pad property, counted on the side its footprint sits on, and the rule requires at least three on each side that carries surface-mount parts
        plain = [part(f"MK{i}", [pad("", 0, 0, "", (1, 1))], attr="smd exclude_from_bom", at=(2 + 10 * i, 2)) for i in range(3)]
        local = [part(f"LF{i}", [pad("", 0, 0, "", (1, 1), extra="(property pad_prop_fiducial_loc)")], at=(2 + 10 * i, 2)) for i in range(3)]
        for marks in (plain, local):
            self.assertEqual(len(self.found(resistor("R1"), *marks)), 1)

    def test_a_test_point_left_out_of_the_position_file_does_not_make_a_side_count(self):
        # SOL-PRE-ORDER-CHECK-FIDUCIALS-AND-POLARITY-MARKS.C1: so a test point the assembler does not place does not make a side count
        point = resistor("TP1", side="B.Cu", attr="smd exclude_from_pos_files")
        self.assertEqual(self.found(resistor("R1"), point, *three_fiducials()), [])
        self.assertEqual(len(self.found(resistor("R1"), resistor("TP1", side="B.Cu"), *three_fiducials())), 1)

    def test_a_design_with_no_surface_mount_part_is_not_failed_for_fiducials(self):
        # SOL-PRE-ORDER-CHECK-FIDUCIALS-AND-POLARITY-MARKS.C1: a design with no surface-mount part is not failed for fiducials
        self.assertEqual(self.found(part("J1", [pad(1, 0, 0, "A", kind="thru_hole")], attr="through_hole")), [])
        self.assertEqual(self.found(), [])

    def test_a_fiducial_footprint_is_not_itself_a_part_that_makes_a_side_count(self):
        # SOL-PRE-ORDER-CHECK-FIDUCIALS-AND-POLARITY-MARKS.C1: a side carrying them when it holds a footprint with the surface-mount attribute that is neither a fiducial nor excluded from the position file
        self.assertEqual(self.found(*three_fiducials("B.Cu")), [])

    def test_the_surface_mount_attribute_decides_not_the_pads_and_a_fiducial_left_out_of_the_position_file_still_counts(self):
        # SOL-PRE-ORDER-CHECK-FIDUCIALS-AND-POLARITY-MARKS.C1: a side carrying them when it holds a footprint with the surface-mount attribute that is neither a fiducial nor excluded from the position file
        # The side follows the attribute: a footprint of surface-mount pads that does not carry it makes no side count.
        unflagged = part("R1", [pad(1, -1, 0, "A"), pad(2, 1, 0, "B")], attr="through_hole")
        self.assertEqual(self.found(unflagged), [])
        self.assertEqual(len(self.found(resistor("R1"))), 1)
        left_out = [part(f"FID{i}", [pad("", 0, 0, "", (1, 1), extra="(property pad_prop_fiducial_glob)")],
                         attr="smd exclude_from_pos_files exclude_from_bom", at=(2 + 10 * i, 2)) for i in range(3)]
        self.assertEqual(self.found(resistor("R1"), *left_out), [])


def diode(reference="D1", silk="", pads=None, side="F.Cu", angle=0):
    pads = pads or [pad(1, -1.5, 0, "K"), pad(2, 1.5, 0, "A")]
    return part(reference, pads, silk, side=side, angle=angle)


NAMED = {"D1": ("D", ["k", "a"])}


class AMarkedFirstPin(unittest.TestCase):
    def found(self, *items, parts=None):
        return board_check.unmarked_pins(DESIGN, tree_of(*items), NAMED if parts is None else parts)

    BAR = lines("F.SilkS", (-2.2, -1, -2.2, 1))
    OUTLINE = lines("F.SilkS", (-2.8, -1, 2.8, -1), (-2.8, 1, 2.8, 1))

    def test_a_bar_beside_pad_one_on_an_outline_marks_a_diode(self):
        # SOL-PRE-ORDER-CHECK-FIDUCIALS-AND-POLARITY-MARKS.C1: its mark is present when a graphic item of the part's own footprint, not text, on the silkscreen layer of the part's own side lies nearer to the copper of pad one than to the copper of every other pad
        self.assertEqual(self.found(diode(silk=self.OUTLINE + " " + self.BAR)), [])

    def test_a_diode_with_no_silkscreen_fails_naming_the_part_and_its_first_pad(self):
        # SOL-PRE-ORDER-CHECK-FIDUCIALS-AND-POLARITY-MARKS.C1: The rule fails ... a polarised part without its mark on its own side
        # SOL-PRE-ORDER-CHECK-FIDUCIALS-AND-POLARITY-MARKS.C3: reported with the rule's name, the design, and the offending item (... the part reference with its first pad)
        found = self.found(diode())
        self.assertEqual([(v.design, v.rule, v.location) for v in found], [("a/a.kicad_pro", "polarity_mark", "D1 pad 1 at (8.5, 10) mm")])
        self.assertIn("D1 is not marked at pad 1, it draws nothing on F.SilkS", found[0].message)

    def test_an_outline_equidistant_from_both_pads_marks_nothing(self):
        # SOL-PRE-ORDER-CHECK-FIDUCIALS-AND-POLARITY-MARKS.C1: nearer to the copper of pad one than to the copper of every other pad by more than 0.05 mm
        found = self.found(diode(silk=self.OUTLINE))
        self.assertEqual(len(found), 1)
        self.assertIn("no graphic on F.SilkS nearer pad 1 than every other pad", found[0].message)

    def test_a_graphic_nearer_pad_one_by_no_more_than_the_margin_marks_nothing(self):
        # SOL-PRE-ORDER-CHECK-FIDUCIALS-AND-POLARITY-MARKS.C1: nearer to the copper of pad one than to the copper of every other pad by more than 0.05 mm
        # A line across the part at x from its centre stands 1.2 + x from pad 1's copper and 1.2 - x from pad 2's, a gap of 2x.
        for x, expected in ((-0.02, 1), (-0.1, 0)):
            with self.subTest(x=x):
                self.assertEqual(len(self.found(diode(silk=lines("F.SilkS", (x, -3, x, 3))))), expected)

    def test_text_is_no_mark(self):
        # SOL-PRE-ORDER-CHECK-FIDUCIALS-AND-POLARITY-MARKS.C1: a graphic item of the part's own footprint, not text
        text = '(fp_text user "K" (at -2.2 0) (layer "F.SilkS"))'
        self.assertEqual(len(self.found(diode(silk=text))), 1)

    def test_a_mark_on_the_wrong_side_of_the_part_does_not_count(self):
        # SOL-PRE-ORDER-CHECK-FIDUCIALS-AND-POLARITY-MARKS.C1: on the silkscreen layer of the part's own side
        wrong = lines("B.SilkS", (-2.2, -1, -2.2, 1))
        self.assertEqual(len(self.found(diode(silk=wrong))), 1)
        self.assertEqual(len(self.found(diode(silk=self.BAR, side="B.Cu"))), 1)
        self.assertEqual(self.found(diode(silk=wrong, side="B.Cu")), [])

    def test_a_polarised_part_with_no_pad_numbered_one_has_no_first_pin_to_mark(self):
        # SOL-PRE-ORDER-CHECK-FIDUCIALS-AND-POLARITY-MARKS.C1: a polarised part with no pad numbered 1
        found = self.found(diode(silk=self.BAR, pads=[pad("A", -1.5, 0, "K"), pad("B", 1.5, 0, "A")]))
        self.assertEqual(len(found), 1)
        self.assertIn("has no pad numbered 1", found[0].message)

    def test_a_symmetric_outline_on_a_symmetric_pad_pattern_marks_nothing_though_one_segment_stands_nearer(self):
        # SOL-PRE-ORDER-CHECK-FIDUCIALS-AND-POLARITY-MARKS.C1: those graphics taken together are not unchanged, to within 0.05 mm, by any reflection or rotation that maps the footprint's pads onto themselves while moving pad one
        pads = [pad(1, -1.5, 0, "K"), pad(2, 1.5, 0, "A")]
        symmetric = lines("F.SilkS", (-2.8, -1, 2.8, -1), (-2.8, 1, 2.8, 1), (-2.8, -1, -2.8, 1), (2.8, -1, 2.8, 1))
        # Its end segment at x = -2.8 stands nearer pad 1 than pad 2, yet the drawing is the same turned half way round.
        found = self.found(diode(silk=symmetric, pads=pads))
        self.assertEqual(len(found), 1)
        self.assertIn("looks the same when its pads are turned or reflected", found[0].message)
        asymmetric = symmetric + " " + lines("F.SilkS", (-2.2, -1, -2.2, 1))
        self.assertEqual(self.found(diode(silk=asymmetric, pads=pads)), [])

    def test_a_reflection_alone_that_leaves_the_drawing_unchanged_is_found(self):
        # SOL-PRE-ORDER-CHECK-FIDUCIALS-AND-POLARITY-MARKS.C1: any reflection or rotation that maps the footprint's pads onto themselves while moving pad one
        pads = [pad(1, -1.5, 0.5, "K"), pad(2, 1.5, 0.5, "A"), pad(3, 0, -1.5, "G")]
        mirrored = lines("F.SilkS", (-2.8, -2.5, 2.8, -2.5), (-2.8, -2.5, -2.8, 1.5), (2.8, -2.5, 2.8, 1.5))
        found = self.found(part("Q1", pads, mirrored), parts={"Q1": ("Q", [])})
        self.assertEqual(len(found), 1)
        self.assertIn("looks the same", found[0].message)

    def test_a_part_turned_on_the_board_is_judged_as_it_lies(self):
        # SOL-PRE-ORDER-CHECK-FIDUCIALS-AND-POLARITY-MARKS.C1: the part's own footprint ... nearer to the copper of pad one
        self.assertEqual(self.found(diode(silk=self.OUTLINE + " " + self.BAR, angle=90)), [])
        self.assertEqual(len(self.found(diode(silk=self.OUTLINE, angle=90))), 1)

    def test_a_bottom_side_part_is_judged_with_its_mirrored_coordinates_as_kicad_saves_them(self):
        # SOL-PRE-ORDER-CHECK-FIDUCIALS-AND-POLARITY-MARKS.C1: on the silkscreen layer of the part's own side
        # KiCad saves a footprint flipped to the back with its pads and graphics already mirrored: pad 1, left of the part on the
        # front, lies at +1.5 and its bar on B.SilkS at +2.2, the whole part at its place on the board.
        pads = [pad(1, 1.5, 0, "K", side="B"), pad(2, -1.5, 0, "A", side="B")]
        bar = lines("B.SilkS", (2.2, -1, 2.2, 1))
        wrong_end = lines("B.SilkS", (-2.2, -1, -2.2, 1))
        outline = lines("B.SilkS", (-2.8, -1, 2.8, -1), (-2.8, 1, 2.8, 1))
        self.assertEqual(self.found(diode(silk=outline + " " + bar, pads=pads, side="B.Cu")), [])
        self.assertEqual(len(self.found(diode(silk=outline + " " + wrong_end, pads=pads, side="B.Cu"))), 1)
        self.assertEqual(len(self.found(diode(silk=outline, pads=pads, side="B.Cu"))), 1)
        self.assertEqual(len(self.found(diode(silk=lines("F.SilkS", (2.2, -1, 2.2, 1)), pads=pads, side="B.Cu"))), 1)

    def test_a_symmetric_outline_is_found_however_the_part_is_turned(self):
        # SOL-PRE-ORDER-CHECK-FIDUCIALS-AND-POLARITY-MARKS.C1: those graphics taken together are not unchanged, to within 0.05 mm, by any reflection or rotation that maps the footprint's pads onto themselves while moving pad one
        symmetric = lines("F.SilkS", (-2.8, -1, 2.8, -1), (-2.8, 1, 2.8, 1), (-2.8, -1, -2.8, 1), (2.8, -1, 2.8, 1))
        for angle in (90, 180, 270):
            with self.subTest(angle=angle):
                self.assertEqual(len(self.found(diode(silk=symmetric, angle=angle))), 1)
                self.assertEqual(self.found(diode(silk=symmetric + " " + self.BAR, angle=angle)), [])

    def test_a_mark_stands_nearer_pad_one_only_by_more_than_the_margin(self):
        # SOL-PRE-ORDER-CHECK-FIDUCIALS-AND-POLARITY-MARKS.C1: nearer to the copper of pad one than to the copper of every other pad by more than 0.05 mm
        # A line across the part at x from its centre is 2x nearer one pad than the other, so 0.05 mm is x = 0.025; the boundary itself is left to float rounding.
        for x, expected in ((-0.0249, 1), (-0.0251, 0), (0.0251, 1)):
            with self.subTest(x=x):
                self.assertEqual(len(self.found(diode(silk=lines("F.SilkS", (x, -3, x, 3))))), expected)

    def test_a_drawing_differing_from_its_image_by_more_than_the_margin_is_no_longer_symmetric(self):
        # SOL-PRE-ORDER-CHECK-FIDUCIALS-AND-POLARITY-MARKS.C1: not unchanged, to within 0.05 mm, by any reflection or rotation
        # The right end of the outline stands `by` beyond where a half turn would put the left end.
        for by, expected in ((0.0, 1), (0.04, 1), (0.2, 0)):
            with self.subTest(by=by):
                outline = lines("F.SilkS", (-2.8, -1, 2.8 + by, -1), (-2.8, 1, 2.8 + by, 1), (-2.8, -1, -2.8, 1), (2.8 + by, -1, 2.8 + by, 1))
                self.assertEqual(len(self.found(diode(silk=outline))), expected)

    def test_two_pads_numbered_one_are_one_first_pin_for_the_nearer_test_and_the_symmetry_test_alike(self):
        # SOL-PRE-ORDER-CHECK-FIDUCIALS-AND-POLARITY-MARKS.C1: the first pin is the pad numbered 1
        # Pad 1 is two pads, one end of the part; a bar beside the end is a mark though a reflection swaps the two pads.
        pads = [pad(1, -1.5, 0, "K"), pad(1, -1.5, 2, "K"), pad(2, 1.5, 1, "A")]
        bar = lines("F.SilkS", (-2.2, -1, -2.2, 3))
        self.assertEqual(self.found(diode(silk=bar, pads=pads)), [])
        found = self.found(diode(silk=lines("F.SilkS", (-2.2, 1, -2.2, 3)), pads=pads))
        self.assertEqual(found, [])
        self.assertEqual(len(self.found(diode(silk=lines("F.SilkS", (2.2, -1, 2.2, 3)), pads=pads))), 1)


def hole(number, x, y, net, drill="0.8", shape="rect", size=(1.6, 1.6), kind="thru_hole", angle=0):
    at = f"{x} {y} {angle}" if angle else f"{x} {y}"
    return (f'(pad "{number}" {kind} {shape} (at {at}) (size {size[0]} {size[1]}) (drill {drill}) (layers "*.Cu") '
            f'(net "{net}"))')


def relay(reference, pads):
    return part(reference, pads, attr="through_hole")




class EverySymbolPolarised(dict):
    """Names every part's symbol a polarised capacitor's, so the pads' nets alone need not make a part polarised."""

    def get(self, key, default=None):
        return ("C_Polarized", [])


NO_SYMBOLS = EverySymbolPolarised()


class APolarisedPartWithNoPadNumberedOne(unittest.TestCase):
    def found(self, *items):
        return board_check.unmarked_pins(DESIGN, tree_of(*items), NO_SYMBOLS)

    # An asymmetric pattern of four named holes, as a relay's: no turn but the identity maps it onto itself.
    ASYMMETRIC = [hole("13", -3, -2, "A"), hole("14", 3, -2, "B"), hole("A1", -3, 2, "C"), hole("A2", 0, 2, "D")]

    def test_named_through_hole_pads_in_an_asymmetric_pattern_need_no_first_pin(self):
        # SOL-PRE-ORDER-CHECK-POLARITY-MARK-SKIPS-A-PART-WHOSE-HOLES-FIX-ITS-ORIENTATION.C1: On a synthetic design, a polarised part with no pad numbered 1 passes the polarity mark when every plated pad is through-hole, at least two plated holes lie apart, at least one pad is named and no turn other than the identity maps the holes onto themselves in position and drill, as with pads named 13, 14, A1 and A2 in an asymmetric pattern, and with duplicate pads 13 and 14 added
        self.assertEqual(self.found(relay("K731", self.ASYMMETRIC)), [])

    def test_duplicate_pads_at_the_same_holes_leave_the_pattern_asymmetric_and_exempt(self):
        # SOL-PRE-ORDER-CHECK-POLARITY-MARK-SKIPS-A-PART-WHOSE-HOLES-FIX-ITS-ORIENTATION.C1: and with duplicate pads 13 and 14 added
        duplicated = self.ASYMMETRIC + [hole("13", -3, -2, "A"), hole("14", 3, -2, "B")]
        self.assertEqual(self.found(relay("K201", duplicated)), [])

    def test_a_non_plated_mounting_hole_is_ignored_by_the_comparison(self):
        # SOL-PRE-ORDER-CHECK-POLARITY-MARK-SKIPS-A-PART-WHOSE-HOLES-FIX-ITS-ORIENTATION.C1: every plated pad is through-hole
        mounted = self.ASYMMETRIC + [hole("", 6, 6, "", kind="np_thru_hole", shape="circle")]
        self.assertEqual(self.found(relay("K731", mounted)), [])
        square = [hole("A1", -2, -2, "A"), hole("A2", 2, -2, "B"), hole("13", 2, 2, "C"), hole("14", -2, 2, "D"),
                  hole("", 5, 1, "", kind="np_thru_hole", shape="circle")]
        self.assertEqual(len(self.found(relay("K731", square))), 1)

    def test_holes_a_quarter_turn_maps_onto_themselves_fail_naming_the_part(self):
        # SOL-PRE-ORDER-CHECK-POLARITY-MARK-SKIPS-A-PART-WHOSE-HOLES-FIX-ITS-ORIENTATION.C2: A polarised part with no pad numbered 1 and only through-hole pads fails polarity_mark when a turn other than the identity maps its holes onto themselves in position and drill, as with four pads named A1, A2, 13 and 14 in a square, naming the part
        square = [hole("A1", -2, -2, "A"), hole("A2", 2, -2, "B"), hole("13", 2, 2, "C"), hole("14", -2, 2, "D")]
        found = self.found(relay("K9", square))
        self.assertEqual([(v.design, v.rule) for v in found], [("a/a.kicad_pro", "polarity_mark")])
        self.assertIn("K9 at (10, 10) mm", found[0].location)
        self.assertIn("K9 has no pad numbered 1", found[0].message)

    def test_the_turn_is_found_however_the_part_is_turned_on_the_board(self):
        # SOL-PRE-ORDER-CHECK-POLARITY-MARK-SKIPS-A-PART-WHOSE-HOLES-FIX-ITS-ORIENTATION.C2: when a turn other than the identity maps its holes onto themselves in position and drill
        square = [hole("A1", -2, -2, "A"), hole("A2", 2, -2, "B"), hole("13", 2, 2, "C"), hole("14", -2, 2, "D")]
        for angle in (30, 90, 180):
            with self.subTest(angle=angle):
                self.assertEqual(len(self.found(part("K9", square, attr="through_hole", angle=angle))), 1)
                self.assertEqual(self.found(part("K731", self.ASYMMETRIC, attr="through_hole", angle=angle)), [])

    def test_a_half_turn_of_two_equal_holes_fails_whatever_their_copper(self):
        # SOL-PRE-ORDER-CHECK-POLARITY-MARK-SKIPS-A-PART-WHOSE-HOLES-FIX-ITS-ORIENTATION.C3: A polarised part with two through-hole pads named + and -, no pad numbered 1, holes of one drill and the pads one rect and one round, or of two sizes of copper, fails polarity_mark, because the holes fit the board either way
        names = {"D1": ("X", ["+", "-"])}
        shapes = [hole("+", -1.27, 0, "A", shape="rect"), hole("-", 1.27, 0, "B", shape="circle")]
        sizes = [hole("+", -1.27, 0, "A", size=(2.4, 2.4)), hole("-", 1.27, 0, "B", size=(1.6, 1.6))]
        for pads in (shapes, sizes):
            found = board_check.unmarked_pins(DESIGN, tree_of(part("D1", pads, attr="through_hole")), names)
            self.assertEqual(len(found), 1)
            self.assertIn("its holes map onto themselves when turned", found[0].message)

    def test_holes_of_two_drill_diameters_key_the_part_and_pass(self):
        # SOL-PRE-ORDER-CHECK-POLARITY-MARK-SKIPS-A-PART-WHOSE-HOLES-FIX-ITS-ORIENTATION.C3: The same part with holes of two different drill diameters passes
        names = {"D1": ("X", ["+", "-"])}
        keyed = [hole("+", -1.27, 0, "A", drill="1.0"), hole("-", 1.27, 0, "B", drill="0.8")]
        self.assertEqual(board_check.unmarked_pins(DESIGN, tree_of(part("D1", keyed, attr="through_hole")), names), [])
        within = [hole("+", -1.27, 0, "A", drill="0.8"), hole("-", 1.27, 0, "B", drill="0.805")]
        self.assertEqual(len(board_check.unmarked_pins(DESIGN, tree_of(part("D1", within, attr="through_hole")), names)), 1)

    def test_two_oval_holes_pass_when_their_long_axes_differ_and_fail_when_they_agree(self):
        # SOL-PRE-ORDER-CHECK-POLARITY-MARK-SKIPS-A-PART-WHOSE-HOLES-FIX-ITS-ORIENTATION.C3: The same part with two oval holes of the same size whose long axes lie at different angles passes, because a turn of the part does not bring the holes onto themselves; with the same oval holes at the same angle it fails
        names = {"D1": ("X", ["+", "-"])}
        oval = "oval 1.2 0.7"
        differing = [hole("+", -1.27, 0, "A", drill=oval), hole("-", 1.27, 0, "B", drill=oval, angle=90)]
        same = [hole("+", -1.27, 0, "A", drill=oval), hole("-", 1.27, 0, "B", drill=oval)]
        self.assertEqual(board_check.unmarked_pins(DESIGN, tree_of(part("D1", differing, attr="through_hole")), names), [])
        found = board_check.unmarked_pins(DESIGN, tree_of(part("D1", same, attr="through_hole")), names)
        self.assertEqual(len(found), 1)
        self.assertIn("its holes map onto themselves when turned", found[0].message)
        upright = [hole("+", -1.27, 0, "A", drill="oval 0.7 1.2"), hole("-", 1.27, 0, "B", drill="oval 1.2 0.7")]
        self.assertEqual(board_check.unmarked_pins(DESIGN, tree_of(part("D1", upright, attr="through_hole")), names), [])

    def test_a_surface_mount_pad_fails_however_asymmetric_the_pattern(self):
        # SOL-PRE-ORDER-CHECK-POLARITY-MARK-SKIPS-A-PART-WHOSE-HOLES-FIX-ITS-ORIENTATION.C4: A polarised part with no pad numbered 1 and any surface-mount plated pad fails polarity_mark however asymmetric its pads are, as with surface-mount pads A and B at (-1.5, 0) and (1.5, 0) and with an asymmetric surface-mount pattern
        two = self.found(diode(pads=[pad("A", -1.5, 0, "K"), pad("B", 1.5, 0, "A")]))
        self.assertEqual(len(two), 1)
        asymmetric = [pad("13", -3, -2, "A"), pad("14", 3, -2, "B"), pad("A1", -3, 2, "C"), pad("A2", 0, 2, "D")]
        found = self.found(part("K1", asymmetric))
        self.assertEqual(len(found), 1)
        self.assertIn("its pads are surface-mount", found[0].message)
        mixed = self.ASYMMETRIC[:3] + [pad("A2", 0, 2, "D")]
        found = self.found(part("K1", mixed, attr="through_hole"))
        self.assertEqual(len(found), 1)
        self.assertIn("its pads are surface-mount", found[0].message)

    def test_a_single_plated_pad_or_holes_at_one_point_fix_no_orientation(self):
        # SOL-PRE-ORDER-CHECK-POLARITY-MARK-SKIPS-A-PART-WHOSE-HOLES-FIX-ITS-ORIENTATION.C5: A polarised part with no pad numbered 1 whose footprint has a single plated pad, or whose plated holes all lie at one point, fails polarity_mark, naming the part and saying its holes fix no orientation; a degenerate pattern is never exempt
        single = part("K1", [hole("A1", 0, 0, "A"), hole("", 4, 0, "B", kind="np_thru_hole", shape="circle"),
                             hole("", 0, 4, "C", kind="np_thru_hole", shape="circle")], attr="through_hole")
        one_point = part("K2", [hole("A1", 1, 1, "A"), hole("A2", 1, 1, "B"), hole("13", 1, 1.005, "C")], attr="through_hole")
        for item, name in ((single, "K1"), (one_point, "K2")):
            with self.subTest(part=name):
                found = self.found(item)
                self.assertEqual(len(found), 1)
                self.assertIn(f"{name} at", found[0].location)
                self.assertIn(f"{name} has no pad numbered 1", found[0].message)
                self.assertIn("its holes fix no orientation", found[0].message)

    def test_a_footprint_with_no_named_pad_fails_even_where_its_holes_are_asymmetric(self):
        # SOL-PRE-ORDER-CHECK-POLARITY-MARK-SKIPS-A-PART-WHOSE-HOLES-FIX-ITS-ORIENTATION.C6: A polarised through-hole footprint none of whose pads is named fails polarity_mark even where its holes are asymmetric under every turn, naming the part and saying none of its pads is named
        unnamed = [hole("", -3, -2, "A"), hole("", 3, -2, "B"), hole("", -3, 2, "C"), hole("", 0, 2, "D")]
        found = self.found(relay("K5", unnamed))
        self.assertEqual(len(found), 1)
        self.assertIn("K5 at", found[0].location)
        self.assertIn("none of its pads is named", found[0].message)
        one_named = [hole("", -3, -2, "A"), hole("", 3, -2, "B"), hole("", -3, 2, "C"), hole("X", 0, 2, "D")]
        self.assertEqual(self.found(relay("K5", one_named)), [])

    def test_each_failure_carries_the_old_text_and_one_reason(self):
        # SOL-PRE-ORDER-CHECK-POLARITY-MARK-SKIPS-A-PART-WHOSE-HOLES-FIX-ITS-ORIENTATION.C7: Each failure of a polarised part with no pad numbered 1 carries the text "has no pad numbered 1" and one reason in the check's text report, which is its only report: its pads are surface-mount, its holes map onto themselves when turned, its holes fix no orientation, or none of its pads is named
        reasons = ("its pads are surface-mount", "its holes map onto themselves when turned", "its holes fix no orientation",
                   "none of its pads is named")
        cases = [part("K1", [pad("A", -1.5, 0, "K"), pad("B", 1.5, 0, "A")]),
                 relay("K2", [hole("A1", -2, -2, "A"), hole("A2", 2, -2, "B"), hole("13", 2, 2, "C"), hole("14", -2, 2, "D")]),
                 relay("K3", [hole("A1", 0, 0, "A")] + [hole("", 4, 0, "B", kind="np_thru_hole", shape="circle")]),
                 relay("K4", [hole("", -3, -2, "A"), hole("", 3, -2, "B"), hole("", -3, 2, "C")])]
        for item, reason in zip(cases, reasons):
            with self.subTest(reason=reason):
                found = self.found(item)
                self.assertEqual(len(found), 1)
                self.assertIn("has no pad numbered 1", found[0].message)
                self.assertEqual([r for r in reasons if r in found[0].message], [reason])

    def test_a_part_with_a_pad_numbered_one_is_judged_on_that_pad_whatever_its_holes(self):
        # SOL-PRE-ORDER-CHECK-POLARITY-MARK-SKIPS-A-PART-WHOSE-HOLES-FIX-ITS-ORIENTATION.C8: A part with a pad numbered 1 is judged on that pad whatever its pads are, a mark on the wrong side, a text-only mark and a part that is not polarised report as they did, and every design that passes before still passes
        keyed = [hole("1", -3, -2, "A"), hole("14", 3, -2, "B"), hole("A1", -3, 2, "C"), hole("A2", 0, 2, "D")]
        found = self.found(relay("K7", keyed))
        self.assertEqual([(v.rule, v.location) for v in found], [("polarity_mark", "K7 pad 1 at (7, 8) mm")])
        self.assertIn("K7 is not marked at pad 1, it draws nothing on F.SilkS", found[0].message)
        self.assertNotIn("has no pad numbered 1", found[0].message)
        marked = part("K7", keyed, lines("F.SilkS", (-3.8, -3, -3.8, -1)), attr="through_hole")
        self.assertEqual(self.found(marked), [])
        text = part("K7", keyed, '(fp_text user "1" (at -3.8 -2) (layer "F.SilkS"))', attr="through_hole")
        self.assertEqual(len(self.found(text)), 1)
        wrong = part("K7", keyed, lines("B.SilkS", (-3.8, -3, -3.8, -1)), attr="through_hole")
        self.assertEqual(len(self.found(wrong)), 1)
        self.assertEqual(self.found(part("R1", [pad(1, -1, 0, "A"), pad(2, 1, 0, "A")])), [])


class TheHardwareNotesStateWhenAPartNeedsNoFirstPin(unittest.TestCase):
    def test_the_paragraph_and_the_checks_table_row_carry_every_clause(self):
        # SOL-PRE-ORDER-CHECK-POLARITY-MARK-SKIPS-A-PART-WHOSE-HOLES-FIX-ITS-ORIENTATION.C10: The hardware notes' polarity_mark entry and the paragraph on the rule state that a polarised part with no pad numbered 1 needs no first pin only when every plated pad is through-hole, its holes lie at two or more positions, at least one pad is named and no turn other than the identity maps its holes onto themselves in position and drill, that the size and shape of the copper are not compared, and that it fails otherwise with the reason
        with open(os.path.join(os.path.dirname(TOOLS), "README.md"), encoding="utf-8") as handle:
            lines = handle.read().splitlines()
        paragraph = next(line for line in lines if line.lstrip().startswith("- The polarity mark (`polarity_mark`)"))
        row = next(line for line in lines if line.startswith("| `polarity_mark` |"))
        for where, text in (("paragraph", paragraph), ("row", row)):
            for clause in ("every plated pad is through-hole", "two or more positions", "a pad is named" if where == "row" else "at least one of its pads is named",
                           "other than the identity maps" if where == "paragraph" else "no turn but the identity maps", "in position and drill",
                           "its pads are surface-mount", "none of its pads is named", "its holes fix no orientation",
                           "its holes map onto themselves when turned"):
                with self.subTest(where=where, clause=clause):
                    self.assertIn(clause, text)
        self.assertIn("size and shape of the copper are not compared", paragraph)
        self.assertIn("size and shape are not compared", row)


class WhichPartsArePolarised(unittest.TestCase):
    def found(self, *items, parts):
        return board_check.unmarked_pins(DESIGN, tree_of(*items), parts)

    def test_pins_named_for_plus_and_minus_or_anode_and_cathode_make_a_part_polarised(self):
        # SOL-PRE-ORDER-CHECK-FIDUCIALS-AND-POLARITY-MARKS.C1: its schematic pins are named for anode and cathode or plus and minus
        for names in (["+", "-"], ["plus", "minus"], ["anode", "cathode"], ["a", "k"]):
            with self.subTest(names=names):
                self.assertEqual(len(self.found(diode(), parts={"D1": ("X", names)})), 1)
        for names in (["+"], ["a"], ["in", "out"], []):
            with self.subTest(names=names):
                self.assertEqual(self.found(diode(), parts={"D1": ("X", names)}), [])

    def test_a_polarised_capacitor_is_polarised_by_its_symbol_alone(self):
        # SOL-PRE-ORDER-CHECK-FIDUCIALS-AND-POLARITY-MARKS.C1: its schematic symbol is a polarised capacitor, a library item whose name begins C_Polarized
        for symbol in ("C_Polarized", "C_Polarized_US"):
            self.assertEqual(len(self.found(diode(), parts={"D1": (symbol, ["1", "2"])})), 1)
        self.assertEqual(self.found(diode(), parts={"D1": ("C", ["1", "2"])}), [])

    def test_three_pads_on_distinct_nets_make_a_part_polarised(self):
        # SOL-PRE-ORDER-CHECK-FIDUCIALS-AND-POLARITY-MARKS.C1: it has three or more pads on distinct nets
        three = [pad(1, -1, 0, "A"), pad(2, 1, 0, "B"), pad(3, 0, 1, "C")]
        self.assertEqual(len(self.found(part("U1", three), parts={})), 1)
        shared = [pad(1, -1, 0, "A"), pad(2, 1, 0, "B"), pad(3, 0, 1, "B")]
        self.assertEqual(self.found(part("U1", shared), parts={}), [])

    def test_a_footprint_of_one_net_or_of_non_plated_holes_alone_is_excluded_even_by_symbol(self):
        # SOL-PRE-ORDER-CHECK-FIDUCIALS-AND-POLARITY-MARKS.C1: A footprint whose pads are all one net or all non-plated holes is excluded
        one_net = part("C1", [pad(1, -1, 0, "A"), pad(2, 1, 0, "A")])
        one_net_holes = part("C3", [pad(1, -1, 0, "A", kind="thru_hole"), pad(2, 1, 0, "A", kind="thru_hole")], attr="through_hole")
        mounting = part("H1", [pad(1, -1, 0, "A", kind="np_thru_hole"), pad(2, 1, 0, "B", kind="np_thru_hole")], attr="through_hole")
        symbols = {name: ("C_Polarized", []) for name in ("C1", "C2", "C3", "H1")}
        self.assertEqual(self.found(one_net, one_net_holes, mounting, parts=symbols), [])

    def test_a_plated_through_hole_polarised_part_is_judged_by_the_mark_rule(self):
        # SOL-PRE-ORDER-CHECK-FIDUCIALS-AND-POLARITY-MARKS.C1: a footprint with any plated pad, through-hole or surface-mount, is a candidate and is polarised if it meets any of the three
        holes = [pad(1, -1, 0, "A", kind="thru_hole"), pad(2, 1, 0, "B", kind="thru_hole")]
        radial = part("C2", holes, attr="through_hole")
        found = self.found(radial, parts={"C2": ("C_Polarized", [])})
        self.assertEqual([(v.rule, v.location) for v in found], [("polarity_mark", "C2 pad 1 at (9, 10) mm")])
        marked = part("C2", holes, lines("F.SilkS", (-1.8, -1, -1.8, 1)), attr="through_hole")
        self.assertEqual(self.found(marked, parts={"C2": ("C_Polarized", [])}), [])
        led = part("D2", holes, attr="through_hole")
        self.assertEqual(len(self.found(led, parts={"D2": ("LED", ["a", "k"])})), 1)
        mixed = part("C2", [pad(1, -1, 0, "A", kind="thru_hole"), pad(2, 1, 0, "B", kind="np_thru_hole")], attr="through_hole")
        self.assertEqual(len(self.found(mixed, parts={"C2": ("C_Polarized", [])})), 1)

    def test_a_part_the_schematic_does_not_name_is_polarised_only_by_its_pads(self):
        # SOL-PRE-ORDER-CHECK-FIDUCIALS-AND-POLARITY-MARKS.C1: it has three or more pads on distinct nets
        self.assertEqual(self.found(diode(), parts={}), [])


class TheRulesReadAKiCadNetlist(unittest.TestCase):
    def test_a_symbol_name_and_pin_names_are_read_per_reference(self):
        # SOL-PRE-ORDER-CHECK-FIDUCIALS-AND-POLARITY-MARKS.C2: The fiducial rule and the polarity-mark rule are added to the existing pre-order check as further rules, each reading only the design's files
        netlist = sexpr.parse_one(
            '(export (components (comp (ref "C1") (libsource (lib "Device") (part "C_Polarized"))) '
            '(comp (ref "D1") (libsource (lib "Device") (part "D")))) '
            '(nets (net (code 1) (name "N") (node (ref "D1") (pin "1") (pinfunction "K_1")) '
            '(node (ref "D1") (pin "2") (pinfunction "A_2")) (node (ref "C1") (pin "1") (pinfunction "~_1")))))')
        parts = board_check.schematic_parts(netlist)
        self.assertEqual(parts["C1"][0], "C_Polarized")
        self.assertEqual(sorted(parts["D1"][1]), ["a", "k"])
        self.assertEqual(parts["D1"][0], "D")


if __name__ == "__main__":
    unittest.main()
