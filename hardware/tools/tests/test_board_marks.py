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


def pad(number, x, y, net, size=(0.6, 0.6), kind="smd", extra=""):
    layers = '"F.Cu" "F.Mask"' if kind == "smd" else '"*.Cu"'
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

    def test_a_footprint_of_one_net_or_of_holes_alone_is_excluded_even_by_symbol(self):
        # SOL-PRE-ORDER-CHECK-FIDUCIALS-AND-POLARITY-MARKS.C1: A footprint whose pads are all one net or all holes is excluded
        one_net = part("C1", [pad(1, -1, 0, "A"), pad(2, 1, 0, "A")])
        holes = part("C2", [pad(1, -1, 0, "A", kind="thru_hole"), pad(2, 1, 0, "B", kind="thru_hole")], attr="through_hole")
        self.assertEqual(self.found(one_net, holes, parts={"C1": ("C_Polarized", []), "C2": ("C_Polarized", [])}), [])

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
