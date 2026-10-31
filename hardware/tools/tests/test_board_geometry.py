#!/usr/bin/env python3
"""Where a board's pads sit, and the shortest straight-line tree joining a net's pads, on synthetic layouts.

The geometry is read once for every board tool that needs it -- the pre-order
check's route-length rule, the review views' decoupling crops and the
placement checkpoint -- so a pad placed or turned wrongly here would be wrong
in all of them at once. Each case is a layout written out by hand with its
answer worked by hand.
"""

from __future__ import annotations

import heapq
import math
import os
import random
import sys
import time
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


def outlined(*shapes: str) -> list:
    return sexpr.parse_one("(kicad_pcb (version 20260206) " + "".join(shapes) + ")")


def line(a: str, b: str, layer: str = "Edge.Cuts") -> str:
    return f'(gr_line (start {a}) (end {b}) (stroke (width 0.1) (type default)) (layer "{layer}"))'


def rectangle(x1: float, y1: float, x2: float, y2: float) -> str:
    return "".join(line(a, b) for a, b in ((f"{x1} {y1}", f"{x2} {y1}"), (f"{x2} {y1}", f"{x2} {y2}"),
                                           (f"{x2} {y2}", f"{x1} {y2}"), (f"{x1} {y2}", f"{x1} {y1}")))


def square(x1: float, y1: float, x2: float, y2: float):
    return [(x1, y1), (x2, y1), (x2, y2), (x1, y2)]


class TheOutlineLayerIsReadAsClosedLines(unittest.TestCase):
    def test_lines_arcs_circles_rectangles_and_polygons_each_close_into_a_line_of_their_own(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-APART-FROM-LOW-VOLTAGE-COPPER-ON-EVERY-LAYER.C3: On a throwaway copy of a proof design, a copper item of any net on an inner layer whose plan-view distance to the wall of a barrier slot (a closed cut-out inside the board outline that is not a round hole) is under 1.5 mm fails as mains_layer_separation naming the item, its layer and the slot; the same item at 1.5 mm or more passes, and a surface-layer item at the same distance is not reported by this test. Out of scope is the width of the slot, which the existing slot rule holds.
        tree = outlined(rectangle(0, 0, 60, 40),
                        '(gr_rect (start 10 10) (end 12 20) (stroke (width 0.1) (type default)) (fill no) (layer "Edge.Cuts"))',
                        '(gr_circle (center 30 10) (end 31 10) (stroke (width 0.1) (type default)) (fill no) (layer "Edge.Cuts"))',
                        '(gr_poly (pts (xy 40 10) (xy 42 10) (xy 41 15)) (stroke (width 0.1) (type default)) (fill no) (layer "Edge.Cuts"))',
                        line("5 5", "6 6", "F.Cu"))
        loops = board_geometry.edge_loops(tree)
        self.assertEqual(len(loops), 4)
        self.assertEqual(sorted(loop.round for loop in loops), [False, False, False, True])
        slots = board_geometry.barrier_slots(tree)
        self.assertEqual(len(slots), 2)
        self.assertEqual(sorted(round(slot.area(), 3) for slot in slots), [5.0, 20.0])

    def test_a_line_drawn_end_to_end_in_either_direction_closes_and_a_gap_does_not(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-APART-FROM-LOW-VOLTAGE-COPPER-ON-EVERY-LAYER.C3: On a throwaway copy of a proof design, a copper item of any net on an inner layer whose plan-view distance to the wall of a barrier slot (a closed cut-out inside the board outline that is not a round hole) is under 1.5 mm fails as mains_layer_separation naming the item, its layer and the slot; the same item at 1.5 mm or more passes, and a surface-layer item at the same distance is not reported by this test. Out of scope is the width of the slot, which the existing slot rule holds.
        backwards = outlined(line("0 0", "10 0"), line("10 10", "10 0"), line("10 10", "0 10"), line("0 0", "0 10"))
        (loop,) = board_geometry.edge_loops(backwards)
        self.assertAlmostEqual(loop.area(), 100.0)
        with self.assertRaises(board_geometry.Unreadable):
            board_geometry.edge_loops(outlined(line("0 0", "10 0"), line("10 0", "10 10"), line("10 10", "0 10")))

    def test_a_footprints_cut_out_is_placed_with_the_footprint(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-APART-FROM-LOW-VOLTAGE-COPPER-ON-EVERY-LAYER.C3: On a throwaway copy of a proof design, a copper item of any net on an inner layer whose plan-view distance to the wall of a barrier slot (a closed cut-out inside the board outline that is not a round hole) is under 1.5 mm fails as mains_layer_separation naming the item, its layer and the slot; the same item at 1.5 mm or more passes, and a surface-layer item at the same distance is not reported by this test. Out of scope is the width of the slot, which the existing slot rule holds.
        part = ('(footprint "lib:slot" (layer "F.Cu") (at 20 20 90) (property "Reference" "S1" (at 0 0 0))'
                '(fp_rect (start -1 -3) (end 1 3) (stroke (width 0.1) (type default)) (fill no) (layer "Edge.Cuts")))')
        (slot,) = board_geometry.barrier_slots(outlined(rectangle(0, 0, 60, 40), part))
        left, top, right, bottom = slot.bounds
        self.assertAlmostEqual(right - left, 6.0, places=6)
        self.assertAlmostEqual(bottom - top, 2.0, places=6)
        self.assertAlmostEqual((left + right) / 2, 20.0, places=6)


class AWayRoundASlotIsExact(unittest.TestCase):
    SLOT = board_geometry.Loop(square(30, 5, 31, 15), False)

    def test_with_no_slot_in_reach_the_way_is_the_straight_line(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-APART-FROM-LOW-VOLTAGE-COPPER-ON-EVERY-LAYER.C2: On a throwaway copy of a proof design with a barrier slot between a Mains-class item and a low-voltage item on different layers, the shortest plan-view path between them that does not cross the slot, going round its ends, is compared with creepage_mm; a pair whose path is shorter fails as mains_layer_separation naming the items, the layers and the path length, and a pair whose path is at least the figure passes even where its straight-line distance is under it. Out of scope is any path through the thickness of the board.
        one, other = board_geometry.Shape([square(0, 0, 1, 1)]), board_geometry.Shape([square(3, 0, 4, 1)])
        self.assertEqual(board_geometry.route_length(one, other, [], 10), (2.0, 0))
        far = board_geometry.Loop(square(30, 30, 31, 31), False)
        self.assertEqual(board_geometry.route_length(one, other, [far], 10), (2.0, 0))

    def test_a_slot_between_the_pieces_lengthens_the_way_to_the_corners_it_goes_round(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-APART-FROM-LOW-VOLTAGE-COPPER-ON-EVERY-LAYER.C2: On a throwaway copy of a proof design with a barrier slot between a Mains-class item and a low-voltage item on different layers, the shortest plan-view path between them that does not cross the slot, going round its ends, is compared with creepage_mm; a pair whose path is shorter fails as mains_layer_separation naming the items, the layers and the path length, and a pair whose path is at least the figure passes even where its straight-line distance is under it. Out of scope is any path through the thickness of the board.
        one, other = board_geometry.Shape([square(27, 9, 29, 11)]), board_geometry.Shape([square(32, 9, 34, 11)])
        length, rounds = board_geometry.route_length(one, other, [self.SLOT], 20)
        self.assertAlmostEqual(length, 2 * math.hypot(1, 4) + 1.0, places=9)
        self.assertEqual(rounds, 1)
        self.assertGreater(length, 3.0)

    def test_the_way_goes_the_shorter_end_and_two_slots_in_line_count_two(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-APART-FROM-LOW-VOLTAGE-COPPER-ON-EVERY-LAYER.C2: On a throwaway copy of a proof design with a barrier slot between a Mains-class item and a low-voltage item on different layers, the shortest plan-view path between them that does not cross the slot, going round its ends, is compared with creepage_mm; a pair whose path is shorter fails as mains_layer_separation naming the items, the layers and the path length, and a pair whose path is at least the figure passes even where its straight-line distance is under it. Out of scope is any path through the thickness of the board.
        one, other = board_geometry.Shape([square(27, 12, 29, 14)]), board_geometry.Shape([square(32, 12, 34, 14)])
        length, _ = board_geometry.route_length(one, other, [self.SLOT], 20)
        self.assertAlmostEqual(length, math.hypot(1, 1) + 1.0 + math.hypot(1, 1), places=9)
        second = board_geometry.Loop(square(30.5, 16, 31.5, 25), False)
        wide = board_geometry.Shape([square(27, 12, 29, 14)]), board_geometry.Shape([square(34, 12, 36, 14)])
        _, rounds = board_geometry.route_length(wide[0], wide[1], [self.SLOT, second], 30)
        self.assertGreaterEqual(rounds, 1)

    def test_a_way_not_under_the_reach_is_not_worked_out(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-APART-FROM-LOW-VOLTAGE-COPPER-ON-EVERY-LAYER.C2: On a throwaway copy of a proof design with a barrier slot between a Mains-class item and a low-voltage item on different layers, the shortest plan-view path between them that does not cross the slot, going round its ends, is compared with creepage_mm; a pair whose path is shorter fails as mains_layer_separation naming the items, the layers and the path length, and a pair whose path is at least the figure passes even where its straight-line distance is under it. Out of scope is any path through the thickness of the board.
        one, other = board_geometry.Shape([square(0, 0, 1, 1)]), board_geometry.Shape([square(30, 0, 31, 1)])
        self.assertGreaterEqual(board_geometry.route_length(one, other, [self.SLOT], 10)[0], 10)


class ALargeShapeIsWalkedOnlyWhereTheOtherLies(unittest.TestCase):
    def ring(self, count: int):
        return [(50 + 40 * math.cos(2 * math.pi * i / count) * (1 + 0.001 * math.sin(i)), 50 + 40 * math.sin(2 * math.pi * i / count))
                for i in range(count)]

    def test_its_distance_is_polygon_distance_wherever_that_is_under_the_reach(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-APART-FROM-LOW-VOLTAGE-COPPER-ON-EVERY-LAYER.C9: On a throwaway proof design carrying filled ground and mains pours on four copper layers, the check including the new rule adds no KiCad run to the existing one, the rule's own computation finishes within a stated time bound on a synthetic fill of 50,000 vertices, and the existing test that a hung KiCad run still fails the design stands. Out of scope is the limit's value.
        points = self.ring(2000)
        big = board_geometry.Shape([points])
        self.assertTrue(big.indexed())
        for x, y in ((88, 48), (95, 50), (50, 50), (10, 10), (0, 0), (91, 91), (49, 8), (60, 12)):
            small = board_geometry.Shape([square(x, y, x + 2, y + 3)])
            exact = board_geometry.polygon_distance(points, small.polygons[0])
            walked = board_geometry.shape_distance(big, small, 10)
            self.assertTrue(abs(walked - exact) < 1e-9 or (walked >= 10 and exact >= 10), (x, y, walked, exact))

    def test_one_shape_inside_the_other_or_covering_it_is_contact(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-APART-FROM-LOW-VOLTAGE-COPPER-ON-EVERY-LAYER.C9: On a throwaway proof design carrying filled ground and mains pours on four copper layers, the check including the new rule adds no KiCad run to the existing one, the rule's own computation finishes within a stated time bound on a synthetic fill of 50,000 vertices, and the existing test that a hung KiCad run still fails the design stands. Out of scope is the limit's value.
        big = board_geometry.Shape([self.ring(2000)])
        self.assertEqual(board_geometry.shape_distance(big, board_geometry.Shape([square(48, 48, 52, 52)]), 10), 0.0)
        self.assertEqual(board_geometry.shape_distance(big, board_geometry.Shape([square(-10, -10, 110, 110)]), 10), 0.0)
        self.assertGreaterEqual(board_geometry.shape_distance(big, board_geometry.Shape([square(200, 200, 201, 201)]), 10), 10)

    def test_a_hole_in_the_fill_is_outside_it(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-APART-FROM-LOW-VOLTAGE-COPPER-ON-EVERY-LAYER.C9: On a throwaway proof design carrying filled ground and mains pours on four copper layers, the check including the new rule adds no KiCad run to the existing one, the rule's own computation finishes within a stated time bound on a synthetic fill of 50,000 vertices, and the existing test that a hung KiCad run still fails the design stands. Out of scope is the limit's value.
        outer = self.ring(2000)
        hole = [(50 + 5 * math.cos(2 * math.pi * i / 100), 50 + 5 * math.sin(2 * math.pi * i / 100)) for i in range(100)]
        shape = board_geometry.Shape([outer, hole])
        inside_hole = board_geometry.Shape([square(49, 49, 51, 51)])
        self.assertAlmostEqual(board_geometry.shape_distance(shape, inside_hole, 10), 5 - math.hypot(1, 1), places=2)


def wavy(centre, radius, count, seed):
    """A star-shaped polygon of `count` corners round a centre, its radius wandering about `radius` so no side runs along a circle."""
    rng = random.Random(seed)
    return [(centre[0] + radius * (1 + 0.15 * rng.uniform(-1, 1)) * math.cos(2 * math.pi * i / count),
             centre[1] + radius * (1 + 0.15 * rng.uniform(-1, 1)) * math.sin(2 * math.pi * i / count)) for i in range(count)]


def brute_route_length(first, second, slots, reach):
    """The way round the slots as it was worked out before the box trees and the kept sight lines: every side against every side, every pair of corners asked afresh."""
    rings = [slot.points for slot in slots]
    straight = board_geometry.polygon_distance(first.polygons[0], second.polygons[0])
    if not rings or straight >= reach:
        return straight
    best = math.inf
    for a, b in first.sides:
        for c, d in second.sides:
            distance, p, q = board_geometry.closest_points(a, b, c, d)
            if distance < best and not board_geometry.blocked(p, q, rings):
                best = distance
    nodes = [corner for ring in rings for corner in ring]

    def reaching(shape, corner):
        found = math.inf
        for a, b in shape.sides:
            foot = board_geometry.nearest_on_segment(corner, a, b)
            distance = math.dist(corner, foot)
            if distance < min(found, reach) and not board_geometry.blocked(corner, foot, rings):
                found = distance
        return found

    cost = [reaching(first, corner) for corner in nodes]
    finish = [reaching(second, corner) for corner in nodes]
    queue = [(cost[i], i) for i in range(len(nodes)) if cost[i] < math.inf]
    heapq.heapify(queue)
    settled = set()
    found = best
    while queue:
        distance, position = heapq.heappop(queue)
        if position in settled or distance >= found:
            continue
        settled.add(position)
        found = min(found, distance + finish[position])
        for other in range(len(nodes)):
            step = math.dist(nodes[position], nodes[other])
            if other not in settled and distance + step < cost[other] and not board_geometry.blocked(nodes[position], nodes[other], rings):
                cost[other] = distance + step
                heapq.heappush(queue, (distance + step, other))
    return found


class TheNearestPairOfLargeShapesIsTheBruteForceOne(unittest.TestCase):
    def test_the_distance_of_two_large_shapes_equals_the_distance_of_every_side_against_every_side(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-APART-FROM-LOW-VOLTAGE-COPPER-ON-EVERY-LAYER.C9: On a throwaway proof design carrying filled ground and mains pours on four copper layers, the check including the new rule adds no KiCad run to the existing one, the rule's own computation finishes within a stated time bound on a synthetic fill of 50,000 vertices, and the existing test that a hung KiCad run still fails the design stands. Out of scope is the limit's value.
        rng = random.Random(7)
        checked = 0
        for trial in range(60):
            one = wavy((rng.uniform(0, 30), rng.uniform(0, 30)), rng.uniform(2, 9), rng.choice([40, 90, 300]), trial)
            other = wavy((rng.uniform(0, 30), rng.uniform(0, 30)), rng.uniform(2, 9), rng.choice([40, 90, 300]), 1000 + trial)
            margins = (rng.choice([0.0, 0.0, 0.4]), rng.choice([0.0, 0.0, 0.25]))
            exact = board_geometry.polygon_distance(one, other)
            exact = 0.0 if exact <= sum(margins) else exact - sum(margins)
            walked = board_geometry.shape_distance(board_geometry.Shape([one], margins[0]), board_geometry.Shape([other], margins[1]), 10)
            if exact < 10:
                self.assertAlmostEqual(walked, exact, places=9, msg=(trial, margins))
                checked += 1
            else:
                self.assertGreaterEqual(walked, 10, (trial, margins))
        self.assertGreater(checked, 25, "the cases must reach the exact branch often")

    def test_a_shape_inside_a_hole_of_another_and_a_shape_across_its_edge_are_told_apart(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-APART-FROM-LOW-VOLTAGE-COPPER-ON-EVERY-LAYER.C9: On a throwaway proof design carrying filled ground and mains pours on four copper layers, the check including the new rule adds no KiCad run to the existing one, the rule's own computation finishes within a stated time bound on a synthetic fill of 50,000 vertices, and the existing test that a hung KiCad run still fails the design stands. Out of scope is the limit's value.
        outer = wavy((50, 50), 30, 400, 3)
        hole = [(50 + 8 * math.cos(2 * math.pi * i / 90), 50 + 8 * math.sin(2 * math.pi * i / 90)) for i in range(90)]
        fill = board_geometry.Shape([outer, hole])
        self.assertAlmostEqual(board_geometry.shape_distance(fill, board_geometry.Shape([wavy((50, 50), 3, 80, 4)]), 10),
                               max(8 * math.cos(math.pi / 90) - 3 * 1.15, 0.0), delta=1.2)
        self.assertEqual(board_geometry.shape_distance(fill, board_geometry.Shape([wavy((50, 20), 6, 80, 5)]), 10), 0.0)
        self.assertEqual(board_geometry.shape_distance(fill, board_geometry.Shape([wavy((50, 70), 2, 80, 6)]), 10), 0.0)

    def test_a_margin_is_taken_off_the_distance_and_a_shape_within_it_is_in_contact(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-APART-FROM-LOW-VOLTAGE-COPPER-ON-EVERY-LAYER.C9: On a throwaway proof design carrying filled ground and mains pours on four copper layers, the check including the new rule adds no KiCad run to the existing one, the rule's own computation finishes within a stated time bound on a synthetic fill of 50,000 vertices, and the existing test that a hung KiCad run still fails the design stands. Out of scope is the limit's value.
        left, right = square(0, 0, 4, 4), square(5, 0, 9, 4)
        self.assertAlmostEqual(board_geometry.shape_distance(board_geometry.Shape([left]), board_geometry.Shape([right]), 10), 1.0)
        self.assertAlmostEqual(board_geometry.shape_distance(board_geometry.Shape([left], 0.25), board_geometry.Shape([right]), 10), 0.75)
        self.assertAlmostEqual(board_geometry.shape_distance(board_geometry.Shape([left], 0.25), board_geometry.Shape([right], 0.5), 10), 0.25)
        self.assertEqual(board_geometry.shape_distance(board_geometry.Shape([left], 0.5), board_geometry.Shape([right], 0.5), 10), 0.0)
        self.assertEqual(board_geometry.shape_distance(board_geometry.Shape([left], 0.75), board_geometry.Shape([right], 0.5), 10), 0.0)

    def test_the_way_round_slots_equals_the_way_worked_out_side_against_side_on_random_pieces_and_slots(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-APART-FROM-LOW-VOLTAGE-COPPER-ON-EVERY-LAYER.C2: On a throwaway copy of a proof design with a barrier slot between a Mains-class item and a low-voltage item on different layers, the shortest plan-view path between them that does not cross the slot, going round its ends, is compared with creepage_mm; a pair whose path is shorter fails as mains_layer_separation naming the items, the layers and the path length, and a pair whose path is at least the figure passes even where its straight-line distance is under it. Out of scope is any path through the thickness of the board.
        rng = random.Random(11)
        compared = 0
        for trial in range(40):
            first = board_geometry.Shape([wavy((rng.uniform(0, 6), rng.uniform(0, 6)), rng.uniform(0.3, 1.2), rng.choice([4, 80]), trial)])
            second = board_geometry.Shape([wavy((rng.uniform(10, 16), rng.uniform(0, 6)), rng.uniform(0.3, 1.2), rng.choice([4, 80]), 500 + trial)])
            slots = []
            for _ in range(rng.choice([1, 2, 3])):
                x, y = rng.uniform(5, 11), rng.uniform(-3, 8)
                slots.append(board_geometry.Loop(square(x, y, x + rng.uniform(0.2, 0.8), y + rng.uniform(2, 8)), False))
            straight = board_geometry.shape_distance(first, second, 30)
            exact = brute_route_length(first, second, slots, 30)
            length, _ = board_geometry.route_length(first, second, slots, 30, straight)
            self.assertAlmostEqual(length, exact, places=9, msg=trial)
            self.assertAlmostEqual(board_geometry.route_length(first, second, board_geometry.Detours(slots), 30)[0], exact, places=9)
            compared += length > straight + 1e-6
        self.assertGreater(compared, 10, "the cases must have slots that lengthen the way")

    def test_large_pieces_with_a_long_slot_between_them_are_worked_out_as_side_against_side_does(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-APART-FROM-LOW-VOLTAGE-COPPER-ON-EVERY-LAYER.C2: On a throwaway copy of a proof design with a barrier slot between a Mains-class item and a low-voltage item on different layers, the shortest plan-view path between them that does not cross the slot, going round its ends, is compared with creepage_mm; a pair whose path is shorter fails as mains_layer_separation naming the items, the layers and the path length, and a pair whose path is at least the figure passes even where its straight-line distance is under it. Out of scope is any path through the thickness of the board.
        rng = random.Random(5)
        for trial in range(12):
            first = board_geometry.Shape([wavy((0, rng.uniform(-2, 2)), rng.uniform(2, 3), 300, trial)])
            second = board_geometry.Shape([wavy((rng.uniform(7, 9), rng.uniform(-2, 2)), rng.uniform(2, 3), 300, 50 + trial)])
            low = rng.uniform(-9, -3) if trial % 2 == 0 else rng.uniform(-1, 1)
            slot = board_geometry.Loop(square(4, low, 4.4, low + (rng.uniform(8, 14) if trial % 2 == 0 else rng.uniform(1.5, 3))), False)
            exact = brute_route_length(first, second, [slot], 20)
            self.assertAlmostEqual(board_geometry.route_length(first, second, [slot], 20)[0], exact, places=9, msg=trial)

    def test_a_wall_screens_two_boxes_only_where_every_line_between_them_crosses_it(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-APART-FROM-LOW-VOLTAGE-COPPER-ON-EVERY-LAYER.C2: On a throwaway copy of a proof design with a barrier slot between a Mains-class item and a low-voltage item on different layers, the shortest plan-view path between them that does not cross the slot, going round its ends, is compared with creepage_mm; a pair whose path is shorter fails as mains_layer_separation naming the items, the layers and the path length, and a pair whose path is at least the figure passes even where its straight-line distance is under it. Out of scope is any path through the thickness of the board.
        ways = board_geometry.Detours([board_geometry.Loop(square(0, 0, 1, 10), False)])
        self.assertFalse(ways.screens((-3, 4, -1, 6), (2, 4, 3, 6)), "no wall has stopped a line yet")
        self.assertTrue(ways.blocks((-2, 5), (0.5, 5)))
        wall = ways.recent[0]
        self.assertEqual(sorted(wall), [(0, 0), (0, 10)])
        self.assertTrue(ways.screens((-3, 4, -1, 6), (0.2, 4, 3, 6)))
        self.assertFalse(ways.screens((-3, 4, -1, 6), (0.2, 11, 3, 13)), "lines from the first box pass the end of the wall")
        self.assertFalse(ways.screens((-3, 4, -2, 5), (-1, 4, -0.5, 5)), "both boxes on one side of the wall")

    def test_a_margin_shortens_the_way_by_its_width_at_each_end(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-APART-FROM-LOW-VOLTAGE-COPPER-ON-EVERY-LAYER.C2: On a throwaway copy of a proof design with a barrier slot between a Mains-class item and a low-voltage item on different layers, the shortest plan-view path between them that does not cross the slot, going round its ends, is compared with creepage_mm; a pair whose path is shorter fails as mains_layer_separation naming the items, the layers and the path length, and a pair whose path is at least the figure passes even where its straight-line distance is under it. Out of scope is any path through the thickness of the board.
        slot = board_geometry.Loop(square(30, 5, 31, 15), False)
        bare = board_geometry.route_length(board_geometry.Shape([square(27, 9, 29, 11)]), board_geometry.Shape([square(32, 9, 34, 11)]), [slot], 20)[0]
        grown = board_geometry.route_length(board_geometry.Shape([square(27, 9, 29, 11)], 0.25), board_geometry.Shape([square(32, 9, 34, 11)], 0.25),
                                            [slot], 20)[0]
        self.assertAlmostEqual(bare - grown, 0.5, delta=0.02)
        aside = board_geometry.Loop(square(30, 25, 31, 35), False)
        straight = board_geometry.shape_distance(board_geometry.Shape([square(27, 9, 29, 11)], 0.25), board_geometry.Shape([square(32, 9, 34, 11)], 0.25), 20)
        self.assertAlmostEqual(straight, 2.5)
        self.assertAlmostEqual(board_geometry.route_length(board_geometry.Shape([square(27, 9, 29, 11)], 0.25),
                                                           board_geometry.Shape([square(32, 9, 34, 11)], 0.25), [aside], 20)[0], 2.5)


class TheNearestPairOfLargeShapesIsFound(unittest.TestCase):
    #: The seconds the two large fills may take, over five times what they took when the bound was set.
    BOUND_S = 10.0

    def test_a_two_thousand_corner_fill_against_a_fifty_thousand_corner_fill_is_measured_within_the_bound(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-APART-FROM-LOW-VOLTAGE-COPPER-ON-EVERY-LAYER.C9: On a throwaway proof design carrying filled ground and mains pours on four copper layers, the check including the new rule adds no KiCad run to the existing one, the rule's own computation finishes within a stated time bound on a synthetic fill of 50,000 vertices, and the existing test that a hung KiCad run still fails the design stands. Out of scope is the limit's value.
        def ring(centre, count):
            return [(centre[0] + 8 * math.cos(2 * math.pi * i / count) * (1 + 0.02 * (i % 2)), centre[1] + 8 * math.sin(2 * math.pi * i / count))
                    for i in range(count)]
        mains, ground = board_geometry.Shape([ring((20, 20), 2000)]), board_geometry.Shape([ring((44, 20), 50000)])
        started = time.monotonic()
        distance = board_geometry.shape_distance(mains, ground, 10)
        length, rounds = board_geometry.route_length(mains, ground, [board_geometry.Loop(square(31, 10, 32, 30), False)], 10, distance)
        elapsed = time.monotonic() - started
        self.assertAlmostEqual(distance, 24 - 2 * 8 * 1.02, delta=0.01)
        self.assertGreater(length, distance)
        self.assertEqual(rounds, 1)
        self.assertLess(elapsed, self.BOUND_S)


if __name__ == "__main__":
    unittest.main()
