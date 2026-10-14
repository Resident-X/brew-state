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
    """How far a point lies from a pad's copper, by the pad's own shape, size and turn."""

    def pad(self, shape: str, size: str, angle: str = "", extra: str = "") -> board_geometry.Pad:
        return board_geometry.pads(layout(footprint("P1", "10 10", f'(pad "1" smd {shape} (at 0 0 {angle}) (size {size}) '
                                                                   f'(layers "F.Cu") {extra})')))[0]

    def test_a_rectangle_holds_its_corners_and_not_past_them(self):
        pad = self.pad("rect", "2 1")
        self.assertEqual(pad.distance((10.99, 10.49)), 0)
        self.assertAlmostEqual(pad.distance((11.01, 10)), 0.01)
        self.assertAlmostEqual(pad.distance((11.3, 10.9)), 0.5, msg="past a corner the distance is to the corner")

    def test_a_turned_rounded_rectangle_holds_points_along_its_turned_length(self):
        pad = self.pad("roundrect", "2 1", "90", "(roundrect_rratio 0.25)")
        self.assertEqual(pad.distance((10, 9.05)), 0)
        self.assertAlmostEqual(pad.distance((10.9, 10)), 0.4)

    def test_a_rounded_rectangle_leaves_out_its_corners_by_its_own_ratio_or_kicads_when_it_writes_none(self):
        # A 2 by 1 mm pad rounded at a quarter of its 1 mm side: its corner is a 0.25 mm arc centred 0.75 and 0.25 mm off its centre.
        for extra in ("(roundrect_rratio 0.25)", ""):
            with self.subTest(extra=extra):
                pad = self.pad("roundrect", "2 1", extra=extra)
                self.assertAlmostEqual(pad.distance((11, 10.5)), math.hypot(0.25, 0.25) - 0.25)
                self.assertEqual(pad.distance((10.75, 10.5)), 0)
        self.assertAlmostEqual(self.pad("roundrect", "2 1", extra="(roundrect_rratio 0.5)").distance((11, 10.5)),
                               math.hypot(0.5, 0.5) - 0.5)

    def test_a_circle_leaves_out_its_bounding_squares_corners(self):
        pad = self.pad("circle", "2 2")
        self.assertEqual(pad.distance((10.7, 10.7)), 0)
        self.assertAlmostEqual(pad.distance((10.9, 10.9)), math.hypot(0.9, 0.9) - 1)

    def test_an_oval_is_rounded_at_its_ends(self):
        pad = self.pad("oval", "3 1")
        self.assertEqual(pad.distance((11.4, 10)), 0)
        self.assertGreater(pad.distance((11.45, 10.45)), 0, "the corner of the bounding rectangle lies off a rounded end")
        self.assertEqual(pad.distance((10.5, 10.49)), 0)

    def test_a_line_is_measured_to_the_copper_it_passes_and_is_nought_where_it_crosses_it(self):
        pad = self.pad("rect", "2 1")
        self.assertEqual(pad.distance_to_line((10, 8), (10, 12)), 0, "crossing through the middle, neither end on the pad")
        self.assertAlmostEqual(pad.distance_to_line((8, 11), (12, 11)), 0.5, msg="passing beside the long side")
        self.assertAlmostEqual(pad.distance_to_line((12, 10.5), (11, 11.5)), math.sqrt(0.5),
                               msg="passing a corner diagonally, nearest at the corner and not at either end")
        self.assertEqual(self.pad("circle", "1 1").distance_to_line((9, 9), (11, 11)), 0)
        self.assertEqual(self.pad("oval", "3 1").distance_to_line((11, 9), (11, 11)), 0, "an oval's core is a line, crossed")

    def test_only_a_pad_longer_than_it_is_wide_has_a_long_axis(self):
        self.assertIsNone(self.pad("rect", "1.7 1.7").long_axis())
        self.assertIsNone(self.pad("circle", "1.6 1.6").long_axis())
        self.assertTrue(near(self.pad("rect", "0.8 1.45").long_axis(), (0, 1)))
        self.assertTrue(near(self.pad("rect", "0.8 1.45", "270").long_axis(), (-1, 0)))

    def test_a_pad_whose_copper_is_not_a_shape_sized_here_raises_naming_it_rather_than_being_guessed(self):
        for shape, extra, why in (("custom", '(options (clearance outline) (anchor rect)) (primitives (gr_poly (pts (xy 0 0) (xy 3 0) (xy 0 3)) (width 0) (fill yes)))',
                                   "its shape is custom"),
                                  ("roundrect", "(roundrect_rratio 0.25) (chamfer_ratio 0.2) (chamfer top_left)", "its corners are chamfered"),
                                  ("trapezoid", "(rect_delta 0 0.3)", "its shape is trapezoid"),
                                  ("rect", '(padstack (mode front_inner_back) (layer "Inner" (shape rect) (size 2 2)))',
                                   "its copper is set layer by layer"),
                                  ("rect", "(primitives (gr_circle (center 0 0) (end 2 0) (width 0) (fill yes)))", "it carries custom copper")):
            with self.subTest(shape=shape, why=why):
                pad = self.pad(shape, "1 1", extra=extra)
                self.assertFalse(pad.sized())
                self.assertEqual(pad.unsized, why)
                for ask in (lambda: pad.distance((10, 10)), lambda: pad.distance_to_line((9, 10), (11, 10))):
                    with self.assertRaises(board_geometry.Unsized) as raised:
                        ask()
                    self.assertIn("pad 1 of P1", str(raised.exception))
        for shape, extra in (("circle", ""), ("oval", ""), ("rect", ""), ("roundrect", "(roundrect_rratio 0.1)"),
                             ("rect", "(chamfer_ratio 0.2)")):
            with self.subTest(shape=shape, extra=extra):
                self.assertTrue(self.pad(shape, "1 1", extra=extra).sized())


class ATrackMeetsAPadByItsCopper(unittest.TestCase):
    # SOL-BOARD-LAYOUT-WORKMANSHIP-ITEMS.C2: The pre-order check measures every rule-kind workmanship item and fails a board that breaks one
    """A track's end is a round cap of half its width, and KiCad's
    connectivity joins a track to a pad wherever the track's copper reaches
    the pad's, by an end cap or by running over it off its centre as much as
    through it; the centre line alone never decides it.
    """

    PAD = board_geometry.pads(layout(footprint("U1", "45 10", '(pad "1" smd rect (at 0 0) (size 1.6 0.4) (layers "F.Cu"))')))[0]

    def test_an_end_short_of_the_pad_reaches_it_by_its_cap(self):
        # The pad's left side is at x = 44.2: a 0.25 mm track ending at 44.1 reaches it by its 0.125 mm cap.
        self.assertTrue(board_geometry.end_reaches(self.PAD, (44.1, 10), 0.25))
        self.assertFalse(board_geometry.end_reaches(self.PAD, (44.1, 10), 0.15), "a narrower track's cap falls short")
        self.assertTrue(board_geometry.end_reaches(self.PAD, (45, 10.3), 0.25), "reaching the long side from beside it")
        self.assertFalse(board_geometry.end_reaches(self.PAD, (45, 10.4), 0.25))

    def test_a_line_reaches_a_pad_where_its_copper_overlaps_the_pads(self):
        self.assertTrue(board_geometry.line_reaches(self.PAD, (44, 10.3), (46, 10.3), 0.25), "running along the side, overlapping it")
        self.assertFalse(board_geometry.line_reaches(self.PAD, (44, 10.4), (46, 10.4), 0.25))

    def test_kicad_joins_a_track_wherever_its_copper_reaches_the_pads(self):
        self.assertTrue(board_geometry.joins(self.PAD, [(40, 10), (44.1, 10)], 0.25), "by its end cap")
        self.assertTrue(board_geometry.joins(self.PAD, [(45.1, 5), (45.1, 15)], 0.25), "running over the pad's centre")
        self.assertTrue(board_geometry.joins(self.PAD, [(45.5, 5), (45.5, 15)], 0.25),
                        "running over the pad away from its centre, neither end on it")
        self.assertTrue(board_geometry.joins(self.PAD, [(40, 10.3), (42, 10.3), (50, 10.3)], 0.25),
                        "a later piece of the line running along the pad's side, its copper overlapping it")
        self.assertFalse(board_geometry.joins(self.PAD, [(40, 10.4), (50, 10.4)], 0.25), "passing beside it")
        self.assertFalse(board_geometry.joins(self.PAD, [(40, 10), (44, 10)], 0.25), "stopping short of it")
        self.assertTrue(board_geometry.joins(self.PAD, [(44.1, 10)], 0.25), "a single point is its cap")


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
