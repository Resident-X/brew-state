#!/usr/bin/env python3
"""Where a board's pads sit, and the shortest straight-line tree joining a net's pads, on synthetic layouts.

The geometry is read once for every board tool that needs it -- the pre-order
check's route-length rule, the review views' decoupling crops and the
placement checkpoint -- so a pad placed or turned wrongly here would be wrong
in all of them at once. Each case is a layout written out by hand with its
answer worked by hand.
"""

from __future__ import annotations

import math
import os
import sys
import unittest

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)

import board_geometry  # noqa: E402
import sexpr  # noqa: E402


def footprint(reference: str, at: str, *pads: str) -> str:
    return (f'(footprint "lib:part" (layer "F.Cu") (at {at}) (property "Reference" "{reference}" (at 0 0 0))\n'
            + "".join(f"\t{pad}\n" for pad in pads) + ")\n")


def layout(*footprints: str) -> list:
    return sexpr.parse_one("(kicad_pcb (version 20260206)\n" + "".join(footprints) + ")")


def near(a, b, places: int = 6) -> bool:
    return all(abs(x - y) < 10 ** -places for x, y in zip(a, b))


class PadsArePlacedAsKiCadPlacesThem(unittest.TestCase):
    # SOL-BOARD-LAYOUT-WORKMANSHIP-ITEMS.C2: The pre-order check measures every rule-kind workmanship item and fails a board that breaks one
    """A pad's place on the board is its footprint's place plus its own point turned as KiCad turns the footprint."""

    def test_an_unturned_footprint_adds_its_place(self):
        board = layout(footprint("R1", "10 20", '(pad "1" smd rect (at -1 0) (size 0.8 0.95) (layers "F.Cu") (net "/A"))',
                                 '(pad "2" smd rect (at 1 0) (size 0.8 0.95) (layers "F.Cu") (net "/B"))'))
        placed = board_geometry.pads(board)
        self.assertEqual([(pad.reference, pad.number, pad.net) for pad in placed], [("R1", "1", "/A"), ("R1", "2", "/B")])
        self.assertTrue(near(placed[0].centre, (9, 20)))
        self.assertTrue(near(placed[1].centre, (11, 20)))

    def test_a_footprint_turned_ninety_degrees_puts_its_pads_above_and_below(self):
        # KiCad turns anticlockwise as the board is seen, with y running down the
        # board, so a pad at +1 mm along the part's own x lands 1 mm above it.
        board = layout(footprint("R2", "10 20 90", '(pad "1" smd rect (at 1 0 90) (size 0.8 0.95) (layers "F.Cu") (net "/A"))'))
        self.assertTrue(near(board_geometry.pads(board)[0].centre, (10, 19)))
        self.assertTrue(near(board_geometry.pad_centres(sexpr.children(board, "footprint")[0])[0], (10, 19)))

    def test_a_pads_angle_is_the_one_written_beside_it_the_footprints_turn_included(self):
        # A pad written with no angle on a turned footprint lies square to the board, as KiCad writes it.
        board = layout(footprint("U1", "0 0 90", '(pad "1" smd rect (at 0 0 90) (size 2 0.5) (layers "F.Cu") (net "/A"))',
                                 '(pad "2" smd rect (at 0 3) (size 2 0.5) (layers "F.Cu") (net "/A"))'))
        first, second = board_geometry.pads(board)
        self.assertEqual((first.angle, second.angle), (90.0, 0.0))
        self.assertTrue(near(first.long_axis(), (0, -1)))
        self.assertTrue(near(second.long_axis(), (1, 0)))

    def test_a_drill_offset_moves_the_copper_off_the_hole(self):
        board = layout(footprint("J1", "0 0", '(pad "1" thru_hole oval (at 5 5 90) (size 2 1) (drill 0.8 (offset 1 0)) '
                                              '(layers "*.Cu") (net "/A"))'))
        self.assertTrue(near(board_geometry.pads(board)[0].centre, (5, 4)))

    def test_a_pad_reads_its_layers_with_the_copper_wildcards(self):
        board = layout(footprint("J1", "0 0", '(pad "1" thru_hole circle (at 0 0) (size 1 1) (drill 0.5) (layers "*.Cu" "*.Mask") (net "/A"))',
                                 '(pad "2" smd rect (at 3 0) (size 1 1) (layers "B.Cu" "B.Mask") (net "/A"))'))
        through, bottom = board_geometry.pads(board)
        self.assertTrue(all(through.on(layer) for layer in ("F.Cu", "In1.Cu", "B.Cu")))
        self.assertTrue(bottom.on("B.Cu"))
        self.assertFalse(bottom.on("F.Cu"))

    def test_a_pad_with_no_size_or_no_place_is_unreadable_by_name(self):
        for pad in ('(pad "1" smd rect (at 0 0) (layers "F.Cu"))', '(pad "1" smd rect (size 1 1) (layers "F.Cu"))',
                    '(pad "1" smd rect (at zero 0) (size 1 1) (layers "F.Cu"))'):
            with self.subTest(pad=pad), self.assertRaises(board_geometry.Unreadable) as raised:
                board_geometry.pads(layout(footprint("Q7", "0 0", pad)))
            self.assertIn("Q7", str(raised.exception))

    def test_a_pad_naming_its_net_twice_is_unreadable(self):
        with self.assertRaises(board_geometry.Unreadable):
            board_geometry.pads(layout(footprint("R1", "0 0", '(pad "1" smd rect (at 0 0) (size 1 1) (layers "F.Cu") (net "/A") (net "/B"))')))

    def test_an_older_layouts_numbered_nets_are_named(self):
        board = sexpr.parse_one('(kicad_pcb (net 0 "") (net 3 "/SUPPLY")\n'
                                + footprint("R1", "0 0", '(pad "1" smd rect (at 0 0) (size 1 1) (layers "F.Cu") (net 3))') + ")")
        self.assertEqual(board_geometry.pads(board)[0].net, "/SUPPLY")

    def test_nets_gather_their_pads_and_padless_nets_are_left_out(self):
        board = layout(footprint("R1", "0 0", '(pad "1" smd rect (at 0 0) (size 1 1) (layers "F.Cu") (net "/A"))',
                                 '(pad "2" smd rect (at 2 0) (size 1 1) (layers "F.Cu"))'),
                       footprint("R2", "5 0", '(pad "1" smd rect (at 0 0) (size 1 1) (layers "F.Cu") (net "/A"))'))
        nets = board_geometry.net_pads(board)
        self.assertEqual(sorted(nets), ["/A"])
        self.assertEqual([pad.reference for pad in nets["/A"]], ["R1", "R2"])


class APadsCopperIsItsShape(unittest.TestCase):
    # SOL-BOARD-LAYOUT-WORKMANSHIP-ITEMS.C2: The pre-order check measures every rule-kind workmanship item and fails a board that breaks one
    """A point is on a pad's copper by the pad's own shape, size and turn."""

    def pad(self, shape: str, size: str, angle: str = "") -> board_geometry.Pad:
        return board_geometry.pads(layout(footprint("P1", "10 10", f'(pad "1" smd {shape} (at 0 0 {angle}) (size {size}) (layers "F.Cu"))')))[0]

    def test_a_rectangle_holds_its_corners_and_not_past_them(self):
        pad = self.pad("rect", "2 1")
        self.assertTrue(pad.contains((10.99, 10.49)))
        self.assertFalse(pad.contains((11.01, 10)))
        self.assertFalse(pad.contains((10, 10.51)))

    def test_a_turned_rectangle_holds_points_along_its_turned_length(self):
        pad = self.pad("roundrect", "2 1", "90")
        self.assertTrue(pad.contains((10, 9.05)))
        self.assertFalse(pad.contains((10.9, 10)))

    def test_a_circle_leaves_out_its_bounding_squares_corners(self):
        pad = self.pad("circle", "2 2")
        self.assertTrue(pad.contains((10.7, 10.7)))
        self.assertFalse(pad.contains((10.9, 10.9)))

    def test_an_oval_is_rounded_at_its_ends(self):
        pad = self.pad("oval", "3 1")
        self.assertTrue(pad.contains((11.4, 10)))
        self.assertFalse(pad.contains((11.45, 10.45)), "the corner of the bounding rectangle lies off a rounded end")
        self.assertTrue(pad.contains((10.5, 10.49)))

    def test_only_a_pad_longer_than_it_is_wide_has_a_long_axis(self):
        self.assertIsNone(self.pad("rect", "1.7 1.7").long_axis())
        self.assertIsNone(self.pad("circle", "1.6 1.6").long_axis())
        self.assertTrue(near(self.pad("rect", "0.8 1.45").long_axis(), (0, 1)))
        self.assertTrue(near(self.pad("rect", "0.8 1.45", "270").long_axis(), (-1, 0)))


class TheShortestStraightLineTree(unittest.TestCase):
    # SOL-BOARD-LAYOUT-WORKMANSHIP-ITEMS.C2: The pre-order check measures every rule-kind workmanship item and fails a board that breaks one
    """The minimum spanning tree of a net's pad centres under straight-line distance."""

    def test_fewer_than_two_points_make_no_tree(self):
        self.assertEqual(board_geometry.spanning_tree([]), (0.0, []))
        self.assertEqual(board_geometry.spanning_tree([(3, 4)]), (0.0, []))

    def test_two_points_are_joined_by_the_line_between_them(self):
        length, edges = board_geometry.spanning_tree([(0, 0), (3, 4)])
        self.assertAlmostEqual(length, 5.0)
        self.assertEqual(edges, [(0, 1)])

    def test_points_in_a_row_are_joined_neighbour_to_neighbour_not_end_to_end(self):
        length, edges = board_geometry.spanning_tree([(0, 0), (10, 0), (4, 0)])
        self.assertAlmostEqual(length, 10.0)
        self.assertEqual(sorted(tuple(sorted(edge)) for edge in edges), [(0, 2), (1, 2)])

    def test_the_corners_of_a_square_take_three_sides_and_never_a_diagonal(self):
        length, edges = board_geometry.spanning_tree([(0, 0), (2, 0), (2, 2), (0, 2)])
        self.assertAlmostEqual(length, 6.0)
        self.assertEqual(len(edges), 3)

    def test_a_star_is_joined_through_its_centre_point(self):
        points = [(0, 0)] + [(math.cos(k * math.pi / 2), math.sin(k * math.pi / 2)) for k in range(4)]
        self.assertAlmostEqual(board_geometry.spanning_tree(points)[0], 4.0)

    def test_coincident_points_add_nothing(self):
        self.assertAlmostEqual(board_geometry.spanning_tree([(1, 1), (1, 1), (4, 5)])[0], 5.0)

    def test_a_nets_pad_tree_is_measured_between_pad_centres(self):
        board = layout(footprint("R1", "0 0", '(pad "1" smd rect (at 0 0) (size 1 1) (layers "F.Cu") (net "/A"))'),
                       footprint("R2", "10 0 90", '(pad "1" smd rect (at 0 -3 90) (size 1 1) (layers "F.Cu") (net "/A"))'),
                       footprint("R3", "10 10", '(pad "1" smd rect (at 0 0) (size 1 1) (layers "F.Cu") (net "/A"))'))
        # R2's pad lands at (7, 0), its point turned with its footprint: 7 mm from R1's, and R3's at (10, 10) is nearer it than R1's.
        pads = board_geometry.net_pads(board)["/A"]
        self.assertTrue(near(pads[1].centre, (7, 0)))
        self.assertAlmostEqual(board_geometry.pad_tree(pads), 7 + math.hypot(3, 10))


if __name__ == "__main__":
    unittest.main()
