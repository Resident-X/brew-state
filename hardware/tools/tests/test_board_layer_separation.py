#!/usr/bin/env python3
"""The pre-order check's rule holding Mains-class copper apart from low-voltage copper on every layer, driven on synthetic layouts with no KiCad involved.

What is under test here is what the check decides for itself from the layout
KiCad has refilled: which pieces of copper make a pair, which tests a pair is
held to and by what figures, which copper is left to KiCad's own rule, and what
the signed exceptions make of a pair. What KiCad then does with a seeded design is
driven against the real tool in test_board_check_kicad_layer_separation.py.
"""

from __future__ import annotations

import datetime
import math
import os
import sys
import tempfile
import time
import unittest

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)

import board_check  # noqa: E402
import board_geometry  # noqa: E402
import sexpr  # noqa: E402

TODAY = datetime.date(2026, 10, 12)
RECORD = "hardware/m/separation-basis.yaml"
DESIGN = board_check.Design("hardware/m/board/board.kicad_pro")
FOUR = '(0 "F.Cu" signal) (4 "In1.Cu" signal) (6 "In2.Cu" signal) (2 "B.Cu" signal)'
MAINS, LOW = "/M", "/LV"


def outline(width: float = 60, height: float = 40) -> str:
    return "".join(f'(gr_line (start {a}) (end {b}) (stroke (width 0.1) (type default)) (layer "Edge.Cuts"))'
                   for a, b in ((f"0 0", f"{width} 0"), (f"{width} 0", f"{width} {height}"),
                                (f"{width} {height}", f"0 {height}"), (f"0 {height}", "0 0")))


def slot(x1: float, y1: float, x2: float, y2: float) -> str:
    return f'(gr_rect (start {x1} {y1}) (end {x2} {y2}) (stroke (width 0.1) (type default)) (fill no) (layer "Edge.Cuts"))'


def track(net: str, x1: float, y1: float, x2: float, y2: float, layer: str, width: float = 0.25) -> str:
    return f'(segment (start {x1} {y1}) (end {x2} {y2}) (width {width}) (layer "{layer}") (net "{net}"))'


def via(net: str, x: float, y: float, layers: tuple = ("F.Cu", "B.Cu"), size: float = 0.8) -> str:
    named = " ".join(f'"{layer}"' for layer in layers)
    return f'(via (at {x} {y}) (size {size}) (drill 0.4) (layers {named}) (net "{net}"))'


def pad(number: str, kind: str, net: str, x: float, y: float, size: tuple, layers: str, extra: str = "") -> str:
    shape = "circle" if kind == "thru_hole" and size[0] == size[1] and not extra else "rect"
    drill = " (drill 0.8)" if kind == "thru_hole" else ""
    net_text = f' (net "{net}")' if net else ""
    return (f'(pad "{number}" {kind} {shape} (at {x} {y}) (size {size[0]} {size[1]}){drill} (layers {layers}){net_text}{extra})')


def part(reference: str, x: float, y: float, *pads: str) -> str:
    return (f'(footprint "lib:part" (layer "F.Cu") (at {x} {y}) (property "Reference" "{reference}" (at 0 0 0)) '
            + " ".join(pads) + ")")


def header(reference: str, net: str, x: float, y: float, layers: str, size: float = 1.6) -> str:
    """A part of two plated pads, the second on a net of its own well away, so it is a part and not a fixing."""
    return part(reference, 0, 0, pad("1", "thru_hole", net, x, y, (size, size), layers),
                pad("2", "thru_hole", "/FAR", 55, 35, (size, size), layers))


def smd(reference: str, net: str, x: float, y: float, layer: str = "F.Cu", size: tuple = (1, 1), number: str = "1") -> str:
    return part(reference, 0, 0, pad(number, "smd", net, x, y, size, f'"{layer}"'))


def zone(net: str, layer: str, box: tuple, fill: tuple = None, keepout: bool = False) -> str:
    def points(rect: tuple) -> str:
        left, top, right, bottom = rect
        return f"(pts (xy {left} {top}) (xy {right} {top}) (xy {right} {bottom}) (xy {left} {bottom}))"
    net_text = f'(net "{net}") ' if net else ""
    filled = f'(filled_polygon (layer "{layer}") {points(fill)})' if fill else ""
    kept = "(keepout (tracks not_allowed) (vias not_allowed) (pads not_allowed) (copperpour not_allowed) (footprints allowed))" if keepout else ""
    return f'(zone {net_text}(layer "{layer}") {kept} (polygon {points(box)}) {filled})'


def board(*items: str, edge: str = None) -> list:
    return sexpr.parse_one(f"(kicad_pcb (version 20260206) (layers {FOUR}) {edge if edge is not None else outline()} {' '.join(items)})")


def found(tree: list, clearance: float = 3.0, creepage: float = 4.0, mains=(MAINS,)):
    return board_check.layer_separation(tree, set(mains), clearance, creepage)


def named(result, test: str):
    return [finding for finding in result.findings if finding.test == test]


def words(result) -> str:
    stack = ["F.Cu", "In1.Cu", "In2.Cu", "B.Cu"]
    return " ".join(violation.message for violation in board_check.layer_violations(DESIGN, result.findings, result.unmeasured, stack))


class AClearanceAcrossLayersIsHeld(unittest.TestCase):
    def test_low_voltage_copper_of_each_kind_under_the_clearance_in_plan_view_on_another_layer_fails_naming_both(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-APART-FROM-LOW-VOLTAGE-COPPER-ON-EVERY-LAYER.C1: On a throwaway copy of a proof design that declares MAINS present, a low-voltage item on one copper layer (a pour, a track, a via or a pad) whose straight-line plan-view distance to a Mains-class item on a different copper layer is less than the record's mains_to_low_voltage clearance_mm fails as mains_layer_separation naming both items, their layers and nets, and the distance; the same pair at or above the figure passes. Out of scope is a pair on the same layer that KiCad's own rule already reports.
        for label, other in (("track", track(LOW, 10, 12.4, 20, 12.4, "In1.Cu")), ("via", via(LOW, 15, 12.4, ("In1.Cu", "In2.Cu"))),
                             ("pad", smd("U1", LOW, 15, 12.4, "B.Cu")), ("pour", zone(LOW, "In1.Cu", (10, 11.9, 20, 13), (10, 11.9, 20, 13)))):
            with self.subTest(other=label):
                result = found(board(track(MAINS, 10, 10, 20, 10, "F.Cu"), other))
                (finding,) = named(result, "clearance")
                self.assertIn("Track [/M] on F.Cu", finding.mains.name)
                self.assertGreater(finding.measured, 1.0)
                self.assertLess(finding.measured, 3.0)
                text = words(result)
                for word in ("Track [/M] on F.Cu", "[/LV]", "clearance", "3 mm", f"{finding.measured:.3f} mm"):
                    self.assertIn(word, text)

    def test_the_same_pair_at_the_figure_passes_and_just_under_it_fails(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-APART-FROM-LOW-VOLTAGE-COPPER-ON-EVERY-LAYER.C1: On a throwaway copy of a proof design that declares MAINS present, a low-voltage item on one copper layer (a pour, a track, a via or a pad) whose straight-line plan-view distance to a Mains-class item on a different copper layer is less than the record's mains_to_low_voltage clearance_mm fails as mains_layer_separation naming both items, their layers and nets, and the distance; the same pair at or above the figure passes. Out of scope is a pair on the same layer that KiCad's own rule already reports.
        at = lambda centre: found(board(track(MAINS, 10, 10, 20, 10, "F.Cu"), track(LOW, 10, 10 + centre, 20, 10 + centre, "In1.Cu")))
        self.assertEqual(named(at(3.25), "clearance"), [])
        self.assertEqual(len(named(at(3.249), "clearance")), 1)

    def test_a_pair_that_shares_a_stored_layer_is_left_to_kicad(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-APART-FROM-LOW-VOLTAGE-COPPER-ON-EVERY-LAYER.C1: On a throwaway copy of a proof design that declares MAINS present, a low-voltage item on one copper layer (a pour, a track, a via or a pad) whose straight-line plan-view distance to a Mains-class item on a different copper layer is less than the record's mains_to_low_voltage clearance_mm fails as mains_layer_separation naming both items, their layers and nets, and the distance; the same pair at or above the figure passes. Out of scope is a pair on the same layer that KiCad's own rule already reports.
        same = found(board(track(MAINS, 10, 10, 20, 10, "F.Cu"), track(LOW, 10, 12.4, 20, 12.4, "F.Cu")))
        self.assertEqual(same.findings, [])
        every = found(board(track(MAINS, 10, 10, 20, 10, "In1.Cu"),
                            header("J1", LOW, 15, 12.4, '"*.Cu" "*.Mask"')))
        self.assertEqual(every.findings, [])

    def test_two_mains_class_items_and_two_low_voltage_items_are_not_a_pair(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-APART-FROM-LOW-VOLTAGE-COPPER-ON-EVERY-LAYER.C1: On a throwaway copy of a proof design that declares MAINS present, a low-voltage item on one copper layer (a pour, a track, a via or a pad) whose straight-line plan-view distance to a Mains-class item on a different copper layer is less than the record's mains_to_low_voltage clearance_mm fails as mains_layer_separation naming both items, their layers and nets, and the distance; the same pair at or above the figure passes. Out of scope is a pair on the same layer that KiCad's own rule already reports.
        result = found(board(track(MAINS, 10, 10, 20, 10, "F.Cu"), track("/M2", 10, 11, 20, 11, "In1.Cu"),
                             track(LOW, 10, 30, 20, 30, "F.Cu"), track("/LV2", 10, 30.5, 20, 30.5, "In1.Cu")), mains=(MAINS, "/M2"))
        self.assertEqual(result.findings, [])


class ACreepageIsTheShortestPathRoundTheSlots(unittest.TestCase):
    SLOT_SHORT = (21.5, 7.5, 22.5, 12.5)
    SLOT_LONG = (21.5, 5, 22.5, 15)

    def pair(self, edge: str):
        return board(smd("R1", MAINS, 20, 10, "F.Cu", (1, 4)), smd("U1", LOW, 24.5, 10, "B.Cu", (1, 4)), edge=outline() + edge)

    def test_a_path_round_a_slot_end_under_the_creepage_fails_with_its_length_and_the_slot(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-APART-FROM-LOW-VOLTAGE-COPPER-ON-EVERY-LAYER.C2: On a throwaway copy of a proof design with a barrier slot between a Mains-class item and a low-voltage item on different layers, the shortest plan-view path between them that does not cross the slot, going round its ends, is compared with creepage_mm; a pair whose path is shorter fails as mains_layer_separation naming the items, the layers and the path length, and a pair whose path is at least the figure passes even where its straight-line distance is under it. Out of scope is any path through the thickness of the board.
        result = found(self.pair(slot(*self.SLOT_SHORT)), clearance=3.0, creepage=4.0)
        (finding,) = named(result, "creepage")
        self.assertAlmostEqual(finding.measured, math.hypot(1, 0.5) + 1.0 + math.hypot(1.5, 0.5), places=4)
        self.assertEqual(finding.rounds, 1)
        self.assertEqual(named(result, "clearance"), [])
        text = words(result)
        self.assertIn("3.699 mm", text)
        self.assertIn("round 1 slot", text)
        self.assertIn("creepage", text)

    def test_a_path_that_reaches_the_creepage_passes_though_the_straight_line_is_under_it(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-APART-FROM-LOW-VOLTAGE-COPPER-ON-EVERY-LAYER.C2: On a throwaway copy of a proof design with a barrier slot between a Mains-class item and a low-voltage item on different layers, the shortest plan-view path between them that does not cross the slot, going round its ends, is compared with creepage_mm; a pair whose path is shorter fails as mains_layer_separation naming the items, the layers and the path length, and a pair whose path is at least the figure passes even where its straight-line distance is under it. Out of scope is any path through the thickness of the board.
        result = found(self.pair(slot(*self.SLOT_LONG)), creepage=4.0)
        self.assertEqual(result.findings, [])

    def test_the_same_pair_with_no_slot_fails_on_the_straight_line(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-APART-FROM-LOW-VOLTAGE-COPPER-ON-EVERY-LAYER.C2: On a throwaway copy of a proof design with a barrier slot between a Mains-class item and a low-voltage item on different layers, the shortest plan-view path between them that does not cross the slot, going round its ends, is compared with creepage_mm; a pair whose path is shorter fails as mains_layer_separation naming the items, the layers and the path length, and a pair whose path is at least the figure passes even where its straight-line distance is under it. Out of scope is any path through the thickness of the board.
        (finding,) = named(found(self.pair("")), "creepage")
        self.assertAlmostEqual(finding.measured, 3.5, places=6)
        self.assertEqual(finding.rounds, 0)

    def test_a_path_at_the_creepage_passes_and_one_under_it_fails(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-APART-FROM-LOW-VOLTAGE-COPPER-ON-EVERY-LAYER.C2: On a throwaway copy of a proof design with a barrier slot between a Mains-class item and a low-voltage item on different layers, the shortest plan-view path between them that does not cross the slot, going round its ends, is compared with creepage_mm; a pair whose path is shorter fails as mains_layer_separation naming the items, the layers and the path length, and a pair whose path is at least the figure passes even where its straight-line distance is under it. Out of scope is any path through the thickness of the board.
        long = math.hypot(1, 0.5) + 1.0 + math.hypot(1.5, 0.5)
        self.assertEqual(named(found(self.pair(slot(*self.SLOT_SHORT)), creepage=long), "creepage"), [])
        self.assertEqual(len(named(found(self.pair(slot(*self.SLOT_SHORT)), creepage=long + 0.01), "creepage")), 1)

    def test_a_round_hole_between_the_pair_is_not_a_slot(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-APART-FROM-LOW-VOLTAGE-COPPER-ON-EVERY-LAYER.C2: On a throwaway copy of a proof design with a barrier slot between a Mains-class item and a low-voltage item on different layers, the shortest plan-view path between them that does not cross the slot, going round its ends, is compared with creepage_mm; a pair whose path is shorter fails as mains_layer_separation naming the items, the layers and the path length, and a pair whose path is at least the figure passes even where its straight-line distance is under it. Out of scope is any path through the thickness of the board.
        hole = '(gr_circle (center 22 10) (end 22.5 10) (stroke (width 0.1) (type default)) (fill no) (layer "Edge.Cuts"))'
        (finding,) = named(found(self.pair(hole)), "creepage")
        self.assertAlmostEqual(finding.measured, 3.5, places=6)

    def test_the_thickness_of_the_board_is_not_a_path(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-APART-FROM-LOW-VOLTAGE-COPPER-ON-EVERY-LAYER.C2: On a throwaway copy of a proof design with a barrier slot between a Mains-class item and a low-voltage item on different layers, the shortest plan-view path between them that does not cross the slot, going round its ends, is compared with creepage_mm; a pair whose path is shorter fails as mains_layer_separation naming the items, the layers and the path length, and a pair whose path is at least the figure passes even where its straight-line distance is under it. Out of scope is any path through the thickness of the board.
        result = found(board(smd("R1", MAINS, 20, 10, "F.Cu", (1, 4)), smd("U1", LOW, 20, 10, "B.Cu", (1, 4))))
        self.assertEqual([finding.test for finding in result.findings], ["overlap", "creepage"])


class InnerCopperKeepsOffASlotWall(unittest.TestCase):
    SLOT = slot(30, 5, 31.2, 15)

    def at(self, item: str):
        return found(board(item, edge=outline() + self.SLOT))

    def test_inner_copper_of_any_net_within_the_wall_distance_fails_naming_the_item_layer_and_slot(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-APART-FROM-LOW-VOLTAGE-COPPER-ON-EVERY-LAYER.C3: On a throwaway copy of a proof design, a copper item of any net on an inner layer whose plan-view distance to the wall of a barrier slot (a closed cut-out inside the board outline that is not a round hole) is under 1.5 mm fails as mains_layer_separation naming the item, its layer and the slot; the same item at 1.5 mm or more passes, and a surface-layer item at the same distance is not reported by this test. Out of scope is the width of the slot, which the existing slot rule holds.
        for label, item in (("low voltage track", track(LOW, 28.5, 7, 28.5, 12, "In1.Cu")), ("netless track", track("", 28.5, 7, 28.5, 12, "In2.Cu")),
                            ("mains track", track(MAINS, 28.5, 7, 28.5, 12, "In1.Cu"))):
            with self.subTest(item=label):
                result = self.at(item)
                (finding,) = named(result, "pull-back")
                self.assertAlmostEqual(finding.measured, 1.5 - 0.125 - 0.0, places=2)
                text = words(result)
                for word in ("pull-back", "the cut-out at (30.60, 10.00) mm", "1.5 mm", "Track"):
                    self.assertIn(word, text)

    def test_the_same_item_at_the_distance_passes_and_a_surface_item_at_the_same_distance_is_not_reported(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-APART-FROM-LOW-VOLTAGE-COPPER-ON-EVERY-LAYER.C3: On a throwaway copy of a proof design, a copper item of any net on an inner layer whose plan-view distance to the wall of a barrier slot (a closed cut-out inside the board outline that is not a round hole) is under 1.5 mm fails as mains_layer_separation naming the item, its layer and the slot; the same item at 1.5 mm or more passes, and a surface-layer item at the same distance is not reported by this test. Out of scope is the width of the slot, which the existing slot rule holds.
        wall = 30 - 1.5 - 0.125
        self.assertEqual(self.at(track(LOW, wall, 7, wall, 12, "In1.Cu")).findings, [])
        self.assertEqual(len(self.at(track(LOW, wall + 0.01, 7, wall + 0.01, 12, "In1.Cu")).findings), 1)
        self.assertEqual(self.at(track(LOW, 29.5, 7, 29.5, 12, "F.Cu")).findings, [])
        self.assertEqual(self.at(smd("U1", LOW, 29.5, 10, "B.Cu")).findings, [])

    def test_a_plated_hole_stored_on_the_surface_only_has_copper_in_the_inner_layers(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-APART-FROM-LOW-VOLTAGE-COPPER-ON-EVERY-LAYER.C3: On a throwaway copy of a proof design, a copper item of any net on an inner layer whose plan-view distance to the wall of a barrier slot (a closed cut-out inside the board outline that is not a round hole) is under 1.5 mm fails as mains_layer_separation naming the item, its layer and the slot; the same item at 1.5 mm or more passes, and a surface-layer item at the same distance is not reported by this test. Out of scope is the width of the slot, which the existing slot rule holds.
        surface = header("J1", LOW, 29.0, 10, '"F.Cu" "B.Cu"')
        self.assertEqual(len(named(self.at(surface), "pull-back")), 1)
        self.assertEqual(self.at(part("J1", 0, 0, pad("1", "smd", LOW, 29.0, 10, (1.6, 1.6), '"F.Cu"'))).findings, [])

    def test_a_pour_covering_the_slot_and_a_pour_beside_it_fail_alike(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-APART-FROM-LOW-VOLTAGE-COPPER-ON-EVERY-LAYER.C3: On a throwaway copy of a proof design, a copper item of any net on an inner layer whose plan-view distance to the wall of a barrier slot (a closed cut-out inside the board outline that is not a round hole) is under 1.5 mm fails as mains_layer_separation naming the item, its layer and the slot; the same item at 1.5 mm or more passes, and a surface-layer item at the same distance is not reported by this test. Out of scope is the width of the slot, which the existing slot rule holds.
        self.assertEqual(len(named(self.at(zone(LOW, "In1.Cu", (20, 2, 40, 18), (20, 2, 40, 18))), "pull-back")), 1)
        self.assertEqual(len(named(self.at(zone(LOW, "In2.Cu", (20, 2, 29, 18), (20, 2, 29, 18))), "pull-back")), 1)
        self.assertEqual(self.at(zone(LOW, "In2.Cu", (20, 2, 28.4, 18), (20, 2, 28.4, 18))).findings, [])

    def test_only_a_closed_cut_inside_the_outline_that_is_not_round_is_a_slot(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-APART-FROM-LOW-VOLTAGE-COPPER-ON-EVERY-LAYER.C3: On a throwaway copy of a proof design, a copper item of any net on an inner layer whose plan-view distance to the wall of a barrier slot (a closed cut-out inside the board outline that is not a round hole) is under 1.5 mm fails as mains_layer_separation naming the item, its layer and the slot; the same item at 1.5 mm or more passes, and a surface-layer item at the same distance is not reported by this test. Out of scope is the width of the slot, which the existing slot rule holds.
        round_hole = '(gr_circle (center 30 10) (end 30.6 10) (stroke (width 0.1) (type default)) (fill no) (layer "Edge.Cuts"))'
        near = track(LOW, 28.7, 7, 28.7, 12, "In1.Cu")
        self.assertEqual(found(board(near, edge=outline() + round_hole)).findings, [])
        notch = ''.join(f'(gr_line (start {a}) (end {b}) (stroke (width 0.1) (type default)) (layer "Edge.Cuts"))'
                        for a, b in (("20 0", "20 8"), ("20 8", "21 8"), ("21 8", "21 0")))
        notched = ''.join(f'(gr_line (start {a}) (end {b}) (stroke (width 0.1) (type default)) (layer "Edge.Cuts"))'
                          for a, b in (("0 0", "20 0"), ("20 0", "20 8"), ("20 8", "21 8"), ("21 8", "21 0"), ("21 0", "60 0"),
                                       ("60 0", "60 40"), ("60 40", "0 40"), ("0 40", "0 0")))
        self.assertEqual(found(board(track(LOW, 22.2, 2, 22.2, 7, "In1.Cu"), edge=notched)).findings, [])
        halves = ('(gr_arc (start 30 9.4) (mid 30.6 10) (end 30 10.6) (stroke (width 0.1) (type default)) (layer "Edge.Cuts"))'
                  '(gr_arc (start 30 10.6) (mid 29.4 10) (end 30 9.4) (stroke (width 0.1) (type default)) (layer "Edge.Cuts"))')
        self.assertEqual(found(board(near, edge=outline() + halves)).findings, [])

    def test_a_slot_drawn_with_round_ends_out_of_lines_and_arcs_is_one_slot(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-APART-FROM-LOW-VOLTAGE-COPPER-ON-EVERY-LAYER.C3: On a throwaway copy of a proof design, a copper item of any net on an inner layer whose plan-view distance to the wall of a barrier slot (a closed cut-out inside the board outline that is not a round hole) is under 1.5 mm fails as mains_layer_separation naming the item, its layer and the slot; the same item at 1.5 mm or more passes, and a surface-layer item at the same distance is not reported by this test. Out of scope is the width of the slot, which the existing slot rule holds.
        ends = ('(gr_line (start 30 6) (end 30 14) (stroke (width 0.1) (type default)) (layer "Edge.Cuts"))'
                '(gr_arc (start 30 14) (mid 30.5 14.5) (end 31 14) (stroke (width 0.1) (type default)) (layer "Edge.Cuts"))'
                '(gr_line (start 31 14) (end 31 6) (stroke (width 0.1) (type default)) (layer "Edge.Cuts"))'
                '(gr_arc (start 31 6) (mid 30.5 5.5) (end 30 6) (stroke (width 0.1) (type default)) (layer "Edge.Cuts"))')
        tree = board(track(LOW, 28.5, 7, 28.5, 12, "In1.Cu"), edge=outline() + ends)
        self.assertEqual(len(board_geometry.barrier_slots(tree)), 1)
        (finding,) = named(found(tree), "pull-back")
        self.assertAlmostEqual(finding.measured, 30 - 28.5 - 0.125, places=2)


class TheRuleFinishesWithinItsBoundOnLargeFillsAndManyPairs(unittest.TestCase):
    #: The seconds each case may take, over five times what it took when the bound was set.
    LARGE_FILLS_BOUND_S = 10.0
    MANY_PAIRS_BOUND_S = 10.0

    def fill(self, net: str, layer: str, centre: tuple, count: int) -> str:
        corners = " ".join(f"(xy {centre[0] + 8 * math.cos(2 * math.pi * i / count):.4f} {centre[1] + 8 * math.sin(2 * math.pi * i / count):.4f})"
                           for i in range(count))
        return (f'(zone (net "{net}") (layer "{layer}") (polygon (pts (xy 0 0) (xy 60 0) (xy 60 40) (xy 0 40))) '
                f'(filled_polygon (layer "{layer}") (pts {corners})))')

    def test_a_two_thousand_vertex_mains_pour_against_a_fifty_thousand_vertex_pour_on_other_layers_is_judged_within_the_bound(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-APART-FROM-LOW-VOLTAGE-COPPER-ON-EVERY-LAYER.C9: On a throwaway proof design carrying filled ground and mains pours on four copper layers, the check including the new rule adds no KiCad run to the existing one, the rule's own computation finishes within a stated time bound on a synthetic fill of 50,000 vertices, and the existing test that a hung KiCad run still fails the design stands. Out of scope is the limit's value.
        tree = board(self.fill(MAINS, "F.Cu", (16, 20), 2000), self.fill(LOW, "In1.Cu", (44, 20), 50000),
                     edge=outline() + slot(29.5, 5, 30.5, 35))
        started = time.monotonic()
        result = found(tree, clearance=3.0, creepage=40.0)
        elapsed = time.monotonic() - started
        (finding,) = named(result, "creepage")
        self.assertEqual(finding.rounds, 1)
        self.assertGreater(finding.measured, 12.0)
        self.assertEqual(named(result, "clearance"), [])
        self.assertLess(elapsed, self.LARGE_FILLS_BOUND_S)

    def test_sixty_four_pairs_round_a_hundred_vertex_slot_are_judged_within_the_bound(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-APART-FROM-LOW-VOLTAGE-COPPER-ON-EVERY-LAYER.C9: On a throwaway proof design carrying filled ground and mains pours on four copper layers, the check including the new rule adds no KiCad run to the existing one, the rule's own computation finishes within a stated time bound on a synthetic fill of 50,000 vertices, and the existing test that a hung KiCad run still fails the design stands. Out of scope is the limit's value.
        corners = " ".join(f"(xy {30 + 0.5 * math.cos(2 * math.pi * i / 100):.4f} {20 + 7 * math.sin(2 * math.pi * i / 100):.4f})" for i in range(100))
        long_slot = f'(gr_poly (pts {corners}) (stroke (width 0.1) (type default)) (fill no) (layer "Edge.Cuts"))'
        tracks = [track(MAINS, 24 + 0.2 * i, 8 + 3.0 * i, 24 + 0.2 * i, 8.5 + 3.0 * i, "F.Cu") for i in range(8)]
        tracks += [track(LOW, 36 - 0.2 * i, 8 + 3.0 * i, 36 - 0.2 * i, 8.5 + 3.0 * i, "B.Cu") for i in range(8)]
        tree = board(*tracks, edge=outline() + long_slot)
        (loop,) = board_geometry.barrier_slots(tree)
        self.assertEqual(len(loop.points), 100)
        started = time.monotonic()
        result = found(tree, clearance=3.0, creepage=25.0)
        elapsed = time.monotonic() - started
        self.assertEqual(len(named(result, "creepage")), 64)
        self.assertLess(elapsed, self.MANY_PAIRS_BOUND_S)


class AnOverlapIsNotAClearance(unittest.TestCase):
    def test_low_voltage_copper_overlapping_mains_copper_on_another_layer_fails_as_an_overlap(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-APART-FROM-LOW-VOLTAGE-COPPER-ON-EVERY-LAYER.C4: On a throwaway copy of a proof design, a low-voltage pour, track, via or pad whose plan-view outline overlaps that of a Mains-class item on another copper layer fails as mains_layer_separation naming the test as overlap, both items and their layers, and an item whose outline does not overlap but lies under the clearance fails as the clearance test and not as an overlap. Out of scope is an overlap of two Mains-class items.
        for label, other in (("pour", zone(LOW, "In1.Cu", (12, 8, 18, 12), (12, 8, 18, 12))), ("track", track(LOW, 12, 10, 18, 10, "In2.Cu")),
                             ("via", via(LOW, 15, 10, ("In1.Cu", "B.Cu"))), ("pad", smd("U1", LOW, 15, 10, "B.Cu"))):
            with self.subTest(other=label):
                result = found(board(track(MAINS, 10, 10, 20, 10, "F.Cu"), other))
                self.assertEqual(len(named(result, "overlap")), 1)
                self.assertEqual(named(result, "clearance"), [])
                text = words(result)
                for word in ("overlap", "Track [/M] on F.Cu", "[/LV]"):
                    self.assertIn(word, text)

    def test_an_item_that_does_not_overlap_but_lies_under_the_clearance_fails_as_a_clearance(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-APART-FROM-LOW-VOLTAGE-COPPER-ON-EVERY-LAYER.C4: On a throwaway copy of a proof design, a low-voltage pour, track, via or pad whose plan-view outline overlaps that of a Mains-class item on another copper layer fails as mains_layer_separation naming the test as overlap, both items and their layers, and an item whose outline does not overlap but lies under the clearance fails as the clearance test and not as an overlap. Out of scope is an overlap of two Mains-class items.
        result = found(board(smd("R1", MAINS, 10, 10, "F.Cu"), smd("U1", LOW, 12.5, 10, "B.Cu")))
        self.assertEqual(len(named(result, "clearance")), 1)
        self.assertEqual(named(result, "overlap"), [])
        self.assertNotIn("overlap", words(result))

    def test_two_mains_class_items_overlapping_are_not_held_by_this_rule(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-APART-FROM-LOW-VOLTAGE-COPPER-ON-EVERY-LAYER.C4: On a throwaway copy of a proof design, a low-voltage pour, track, via or pad whose plan-view outline overlaps that of a Mains-class item on another copper layer fails as mains_layer_separation naming the test as overlap, both items and their layers, and an item whose outline does not overlap but lies under the clearance fails as the clearance test and not as an overlap. Out of scope is an overlap of two Mains-class items.
        self.assertEqual(found(board(track(MAINS, 10, 10, 20, 10, "F.Cu"), track("/M2", 12, 10, 18, 10, "In1.Cu")),
                               mains=(MAINS, "/M2")).findings, [])


class WhatCountsAsCopper(unittest.TestCase):
    def test_a_through_hole_pad_stored_on_the_surface_only_is_held_against_inner_mains_copper(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-APART-FROM-LOW-VOLTAGE-COPPER-ON-EVERY-LAYER.C5: On throwaway proof designs, a low-voltage through-hole pad under the clearance from a Mains-class track on an inner layer fails although the pad stores copper only on its surface layers, a low-voltage pour whose stored fill reaches within the clearance of a Mains-class pad fails while the same pour's outline alone does not, and a netless copper item within the clearance of a Mains-class item fails. Out of scope is a mounting hole, which its own rule holds.
        mains = track(MAINS, 10, 10, 20, 10, "In1.Cu")
        surface = header("J1", LOW, 15, 12.0, '"F.Cu" "B.Cu"')
        self.assertEqual(len(named(found(board(mains, surface)), "clearance")), 1)
        every = header("J1", LOW, 15, 12.0, '"*.Cu" "*.Mask"')
        self.assertEqual(found(board(mains, every)).findings, [])

    def test_a_pour_counts_by_its_stored_fill_and_by_its_outline_only_where_it_stores_none(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-APART-FROM-LOW-VOLTAGE-COPPER-ON-EVERY-LAYER.C5: On throwaway proof designs, a low-voltage through-hole pad under the clearance from a Mains-class track on an inner layer fails although the pad stores copper only on its surface layers, a low-voltage pour whose stored fill reaches within the clearance of a Mains-class pad fails while the same pour's outline alone does not, and a netless copper item within the clearance of a Mains-class item fails. Out of scope is a mounting hole, which its own rule holds.
        mains = smd("R1", MAINS, 10, 10, "F.Cu")
        near_fill = zone(LOW, "In1.Cu", (30, 30, 40, 38), (11.5, 8, 14, 12))
        self.assertEqual(len(named(found(board(mains, near_fill)), "clearance")), 1)
        far_fill = zone(LOW, "In1.Cu", (8, 8, 14, 12), (30, 30, 40, 38))
        self.assertEqual(found(board(mains, far_fill)).findings, [])
        outline_only = zone(LOW, "In1.Cu", (11.5, 8, 14, 12))
        self.assertEqual(len(named(found(board(mains, outline_only)), "clearance")), 1)

    def test_a_netless_pour_track_and_pad_count_as_low_voltage_and_a_keepout_counts_as_nothing(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-APART-FROM-LOW-VOLTAGE-COPPER-ON-EVERY-LAYER.C5: On throwaway proof designs, a low-voltage through-hole pad under the clearance from a Mains-class track on an inner layer fails although the pad stores copper only on its surface layers, a low-voltage pour whose stored fill reaches within the clearance of a Mains-class pad fails while the same pour's outline alone does not, and a netless copper item within the clearance of a Mains-class item fails. Out of scope is a mounting hole, which its own rule holds.
        mains = smd("R1", MAINS, 10, 10, "F.Cu")
        for label, item in (("track", track("", 8, 12, 14, 12, "In1.Cu")), ("pour", zone("", "In1.Cu", (8, 11.5, 14, 14), (8, 11.5, 14, 14))),
                            ("pad", smd("TP1", "", 10, 12.5, "B.Cu"))):
            with self.subTest(item=label):
                (finding,) = named(found(board(mains, item)), "clearance")
                self.assertIn("[<no net>]", finding.other.name)
        self.assertEqual(found(board(mains, zone("", "In1.Cu", (8, 11.5, 14, 14), keepout=True))).findings, [])

    def test_a_via_counts_only_on_the_layers_it_spans(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-APART-FROM-LOW-VOLTAGE-COPPER-ON-EVERY-LAYER.C5: On throwaway proof designs, a low-voltage through-hole pad under the clearance from a Mains-class track on an inner layer fails although the pad stores copper only on its surface layers, a low-voltage pour whose stored fill reaches within the clearance of a Mains-class pad fails while the same pour's outline alone does not, and a netless copper item within the clearance of a Mains-class item fails. Out of scope is a mounting hole, which its own rule holds.
        blind = via(LOW, 15, 12.0, ("F.Cu", "In1.Cu"))
        self.assertEqual(found(board(track(MAINS, 10, 10, 20, 10, "In1.Cu"), blind)).findings, [])
        self.assertEqual(len(named(found(board(track(MAINS, 10, 10, 20, 10, "In2.Cu"), blind)), "clearance")), 1)
        self.assertEqual(len(named(found(board(track(MAINS, 10, 10, 20, 10, "B.Cu"), via(LOW, 15, 12.0, ("F.Cu", "B.Cu")))), "clearance")), 0)

    def test_a_mounting_hole_is_left_to_its_own_rule(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-APART-FROM-LOW-VOLTAGE-COPPER-ON-EVERY-LAYER.C5: On throwaway proof designs, a low-voltage through-hole pad under the clearance from a Mains-class track on an inner layer fails although the pad stores copper only on its surface layers, a low-voltage pour whose stored fill reaches within the clearance of a Mains-class pad fails while the same pour's outline alone does not, and a netless copper item within the clearance of a Mains-class item fails. Out of scope is a mounting hole, which its own rule holds.
        hole = part("H1", 0, 0, pad("", "np_thru_hole", "", 15, 12.0, (3.2, 3.2), '"F.Cu" "B.Cu"', "").replace("(drill 0.8)", "")
                    .replace("rect", "circle").replace("(layers", "(drill 3.2) (layers"))
        self.assertIn("H1", board_check.hole_footprints(board(hole)))
        self.assertEqual(found(board(track(MAINS, 10, 10, 20, 10, "In1.Cu"), hole)).findings, [])
        part_ = part("U9", 0, 0, pad("1", "smd", LOW, 15, 12.0, (3.2, 3.2), '"B.Cu"'))
        self.assertEqual(len(named(found(board(track(MAINS, 10, 10, 20, 10, "In1.Cu"), part_)), "clearance")), 1)

    def test_copper_graphics_are_netless_low_voltage_and_copper_text_and_custom_pads_fail_by_name(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-APART-FROM-LOW-VOLTAGE-COPPER-ON-EVERY-LAYER.C5: On throwaway proof designs, a low-voltage through-hole pad under the clearance from a Mains-class track on an inner layer fails although the pad stores copper only on its surface layers, a low-voltage pour whose stored fill reaches within the clearance of a Mains-class pad fails while the same pour's outline alone does not, and a netless copper item within the clearance of a Mains-class item fails. Out of scope is a mounting hole, which its own rule holds.
        line = '(gr_line (start 10 12) (end 20 12) (stroke (width 0.25) (type default)) (layer "In1.Cu"))'
        (finding,) = named(found(board(track(MAINS, 10, 10, 20, 10, "F.Cu"), line)), "clearance")
        self.assertEqual(finding.other.kind, "graphic")
        text = '(gr_text "L" (at 40 30 0) (layer "In1.Cu") (effects (font (size 1 1))))'
        result = found(board(text))
        self.assertIn("text on In1.Cu", " ".join(result.unmeasured))
        self.assertIn("text on In1.Cu", words(result))
        custom = part("J1", 0, 0, pad("1", "smd", LOW, 15, 12.0, (1, 1), '"B.Cu"').replace("smd rect", "smd custom"))
        result = found(board(track(MAINS, 10, 10, 20, 10, "F.Cu"), custom))
        self.assertEqual(result.findings, [])
        self.assertIn("pad 1 [/LV] of J1", " ".join(result.unmeasured))
        far = part("J1", 0, 0, pad("1", "smd", LOW, 45, 35, (1, 1), '"B.Cu"').replace("smd rect", "smd custom"))
        self.assertEqual(found(board(track(MAINS, 10, 10, 20, 10, "F.Cu"), far)).unmeasured, {})


class CopperGraphicsAndCurvesAreMeasuredAtTheirTrueEdge(unittest.TestCase):
    def mains_track(self):
        return track(MAINS, 10, 10, 20, 10, "F.Cu")

    def test_a_filled_graphic_is_measured_to_the_edge_of_its_stroke_and_not_to_its_ring(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-APART-FROM-LOW-VOLTAGE-COPPER-ON-EVERY-LAYER.C5: On throwaway proof designs, a low-voltage through-hole pad under the clearance from a Mains-class track on an inner layer fails although the pad stores copper only on its surface layers, a low-voltage pour whose stored fill reaches within the clearance of a Mains-class pad fails while the same pour's outline alone does not, and a netless copper item within the clearance of a Mains-class item fails. Out of scope is a mounting hole, which its own rule holds.
        figure = dict(clearance=0.5, creepage=0.5)
        for label, graphic, nearest in (
                ("rect", '(gr_rect (start 10 11) (end 20 12) (stroke (width 1) (type default)) (fill yes) (layer "In1.Cu"))', 11 - 0.5),
                ("poly", '(gr_poly (pts (xy 10 11) (xy 20 11) (xy 15 14)) (stroke (width 1) (type default)) (fill yes) (layer "In1.Cu"))', 11 - 0.5),
                ("circle", '(gr_circle (center 15 11.75) (end 15 12.75) (stroke (width 1) (type default)) (fill yes) (layer "In1.Cu"))', 11.75 - 1.5)):
            with self.subTest(graphic=label):
                (finding,) = named(found(board(self.mains_track(), graphic), **figure), "clearance")
                self.assertAlmostEqual(finding.measured, nearest - 10.125, places=3)

    def test_a_filled_graphic_whose_ring_stands_clear_but_whose_stroke_does_not_fails(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-APART-FROM-LOW-VOLTAGE-COPPER-ON-EVERY-LAYER.C5: On throwaway proof designs, a low-voltage through-hole pad under the clearance from a Mains-class track on an inner layer fails although the pad stores copper only on its surface layers, a low-voltage pour whose stored fill reaches within the clearance of a Mains-class pad fails while the same pour's outline alone does not, and a netless copper item within the clearance of a Mains-class item fails. Out of scope is a mounting hole, which its own rule holds.
        graphic = '(gr_rect (start 10 11) (end 20 12) (stroke (width 1) (type default)) (fill yes) (layer "In1.Cu"))'
        self.assertEqual(len(named(found(board(self.mains_track(), graphic), clearance=0.5, creepage=0.5), "clearance")), 1)
        self.assertEqual(found(board(self.mains_track(), graphic), clearance=0.375, creepage=0.375).findings, [])
        thin = graphic.replace("(width 1)", "(width 0)")
        self.assertEqual(found(board(self.mains_track(), thin), clearance=0.5, creepage=0.5).findings, [])

    def test_a_footprints_graphics_are_netless_low_voltage_copper_placed_with_the_footprint(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-APART-FROM-LOW-VOLTAGE-COPPER-ON-EVERY-LAYER.C5: On throwaway proof designs, a low-voltage through-hole pad under the clearance from a Mains-class track on an inner layer fails although the pad stores copper only on its surface layers, a low-voltage pour whose stored fill reaches within the clearance of a Mains-class pad fails while the same pour's outline alone does not, and a netless copper item within the clearance of a Mains-class item fails. Out of scope is a mounting hole, which its own rule holds.
        def holding(graphic: str, at: str = "0 0") -> str:
            return (f'(footprint "lib:part" (layer "F.Cu") (at {at}) (property "Reference" "G1" (at 0 0 0)) {graphic})')
        stroke = "(stroke (width 0.25) (type default))"
        for label, graphic, gap in (
                ("line", f'(fp_line (start 10 12.5) (end 20 12.5) {stroke} (layer "In1.Cu"))', 12.5 - 0.125 - 10.125),
                ("rect", f'(fp_rect (start 10 12.5) (end 20 14) {stroke} (fill no) (layer "In1.Cu"))', 12.5 - 0.125 - 10.125),
                ("poly", f'(fp_poly (pts (xy 10 12.5) (xy 20 12.5) (xy 15 14)) {stroke} (fill yes) (layer "In1.Cu"))', 12.5 - 0.125 - 10.125),
                ("arc", f'(fp_arc (start 10 12.5) (mid 15 13.5) (end 20 12.5) {stroke} (layer "In1.Cu"))', 12.5 - 0.125 - 10.125),
                ("circle", f'(fp_circle (center 15 13) (end 15 13.5) {stroke} (fill no) (layer "In1.Cu"))', 12.5 - 0.125 - 10.125)):
            with self.subTest(graphic=label):
                result = found(board(self.mains_track(), holding(graphic)))
                (finding,) = named(result, "clearance")
                self.assertEqual(finding.other.kind, "graphic")
                self.assertIn("Graphic on In1.Cu of G1", finding.other.name)
                self.assertAlmostEqual(finding.measured, gap, places=2)
        turned = holding('(fp_line (start 0 -5) (end 0 5) {stroke} (layer "In1.Cu"))'.replace("{stroke}", stroke), "15 12.4 90")
        (finding,) = named(found(board(self.mains_track(), turned)), "clearance")
        self.assertAlmostEqual(finding.measured, 12.4 - 0.125 - 10.125, places=3)
        far = holding('(fp_line (start 0 -5) (end 0 5) {stroke} (layer "F.SilkS"))'.replace("{stroke}", stroke), "15 12.4 90")
        self.assertEqual(found(board(self.mains_track(), far)).findings, [])

    def test_a_curve_on_a_copper_layer_fails_by_name_and_one_off_the_copper_layers_is_not_copper(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-APART-FROM-LOW-VOLTAGE-COPPER-ON-EVERY-LAYER.C5: On throwaway proof designs, a low-voltage through-hole pad under the clearance from a Mains-class track on an inner layer fails although the pad stores copper only on its surface layers, a low-voltage pour whose stored fill reaches within the clearance of a Mains-class pad fails while the same pour's outline alone does not, and a netless copper item within the clearance of a Mains-class item fails. Out of scope is a mounting hole, which its own rule holds.
        pts = "(pts (xy 10 12.4) (xy 12 12.4) (xy 18 12.4) (xy 20 12.4))"
        free = f'(gr_curve {pts} (stroke (width 0.25) (type default)) (layer "In1.Cu"))'
        inside = ('(footprint "lib:part" (layer "F.Cu") (at 0 0) (property "Reference" "G1" (at 0 0 0)) '
                  f'(fp_curve {pts} (stroke (width 0.25) (type default)) (layer "In1.Cu")))')
        for label, item, name in (("layout", free, "curve on In1.Cu"), ("footprint", inside, "curve on In1.Cu of G1")):
            with self.subTest(curve=label):
                result = found(board(item))
                self.assertIn(name, result.unmeasured)
                text = words(result)
                self.assertIn(name, text)
                self.assertIn("cannot measure a copper curve", text)
        self.assertEqual(found(board(free.replace("In1.Cu", "F.SilkS"), inside.replace("In1.Cu", "F.SilkS"))).unmeasured, {})


class ASlotFlushWithTheOutlineIsOneWhicheverCornerIsWrittenFirst(unittest.TestCase):
    EDGES = {"left": (0, 10, 1, 20), "right": (59, 10, 60, 20), "top": (20, 0, 21, 10), "bottom": (20, 30, 21, 40)}

    def test_a_closed_cut_out_sharing_an_edge_with_the_outline_is_a_slot_in_every_order_of_its_corners(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-APART-FROM-LOW-VOLTAGE-COPPER-ON-EVERY-LAYER.C3: On a throwaway copy of a proof design, a copper item of any net on an inner layer whose plan-view distance to the wall of a barrier slot (a closed cut-out inside the board outline that is not a round hole) is under 1.5 mm fails as mains_layer_separation naming the item, its layer and the slot; the same item at 1.5 mm or more passes, and a surface-layer item at the same distance is not reported by this test. Out of scope is the width of the slot, which the existing slot rule holds.
        for edge, (x1, y1, x2, y2) in self.EDGES.items():
            for order, corners in (("first", (x1, y1, x2, y2)), ("second", (x2, y1, x1, y2)), ("third", (x2, y2, x1, y1)), ("fourth", (x1, y2, x2, y1))):
                with self.subTest(edge=edge, corner=order):
                    (found_slot,) = board_geometry.barrier_slots(board(edge=outline() + slot(*corners)))
                    self.assertAlmostEqual(found_slot.area(), 10.0)

    def test_inner_copper_beside_a_flush_slot_is_pulled_back_from_its_wall_in_every_order(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-APART-FROM-LOW-VOLTAGE-COPPER-ON-EVERY-LAYER.C3: On a throwaway copy of a proof design, a copper item of any net on an inner layer whose plan-view distance to the wall of a barrier slot (a closed cut-out inside the board outline that is not a round hole) is under 1.5 mm fails as mains_layer_separation naming the item, its layer and the slot; the same item at 1.5 mm or more passes, and a surface-layer item at the same distance is not reported by this test. Out of scope is the width of the slot, which the existing slot rule holds.
        for corners in ((20, 0, 21, 10), (21, 10, 20, 0), (20, 10, 21, 0), (21, 0, 20, 10)):
            with self.subTest(corners=corners):
                tree = board(track(LOW, 19.2, 3, 19.2, 7, "In1.Cu"), edge=outline() + slot(*corners))
                (finding,) = named(found(tree), "pull-back")
                self.assertAlmostEqual(finding.measured, 0.8 - 0.125, places=3)

    def test_a_cut_out_with_a_corner_outside_the_outline_is_not_a_slot_and_a_board_with_no_cut_out_has_none(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-APART-FROM-LOW-VOLTAGE-COPPER-ON-EVERY-LAYER.C3: On a throwaway copy of a proof design, a copper item of any net on an inner layer whose plan-view distance to the wall of a barrier slot (a closed cut-out inside the board outline that is not a round hole) is under 1.5 mm fails as mains_layer_separation naming the item, its layer and the slot; the same item at 1.5 mm or more passes, and a surface-layer item at the same distance is not reported by this test. Out of scope is the width of the slot, which the existing slot rule holds.
        self.assertEqual(board_geometry.barrier_slots(board(edge=outline() + slot(-2, 10, 1, 20))), [])
        self.assertEqual(board_geometry.barrier_slots(board()), [])


class TheRoundEndOfASlotIsReadWithinTheSag(unittest.TestCase):
    def stadium(self, radius: float = 5.0) -> str:
        top, bottom = 15, 25
        return (f'(gr_arc (start {30 - radius} {top}) (mid 30 {top - radius}) (end {30 + radius} {top}) (stroke (width 0.1) (type default)) (layer "Edge.Cuts"))'
                f'(gr_line (start {30 + radius} {top}) (end {30 + radius} {bottom}) (stroke (width 0.1) (type default)) (layer "Edge.Cuts"))'
                f'(gr_arc (start {30 + radius} {bottom}) (mid 30 {bottom + radius}) (end {30 - radius} {bottom}) (stroke (width 0.1) (type default)) (layer "Edge.Cuts"))'
                f'(gr_line (start {30 - radius} {bottom}) (end {30 - radius} {top}) (stroke (width 0.1) (type default)) (layer "Edge.Cuts"))')

    def test_the_wall_of_a_round_end_is_within_a_few_micrometres_of_its_drawn_arc_at_every_angle(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-APART-FROM-LOW-VOLTAGE-COPPER-ON-EVERY-LAYER.C3: On a throwaway copy of a proof design, a copper item of any net on an inner layer whose plan-view distance to the wall of a barrier slot (a closed cut-out inside the board outline that is not a round hole) is under 1.5 mm fails as mains_layer_separation naming the item, its layer and the slot; the same item at 1.5 mm or more passes, and a surface-layer item at the same distance is not reported by this test. Out of scope is the width of the slot, which the existing slot rule holds.
        self.assertLessEqual(board_geometry.OUTLINE_SAG, 0.005)
        for turn in (0.5, 1.5, 2.5, 3.5, 4.5, 5.5):
            with self.subTest(turn=turn):
                angle = math.pi + (turn / 8) * math.pi
                x, y = 30 + 6.0 * math.cos(angle), 15 + 6.0 * math.sin(angle)
                tree = board(via(LOW, x, y, ("F.Cu", "B.Cu"), 0.8), edge=outline() + self.stadium())
                (slot_,) = board_geometry.barrier_slots(tree)
                self.assertGreater(len(slot_.points), 40)
                (finding,) = named(found(tree), "pull-back")
                self.assertAlmostEqual(finding.measured, 1.0 - 0.4, delta=0.01)


class TheOneWorstPairIsReportedForEachKindOfCopper(unittest.TestCase):
    def test_a_plane_under_a_run_of_tracks_gives_one_line_with_the_count(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-APART-FROM-LOW-VOLTAGE-COPPER-ON-EVERY-LAYER.C4: On a throwaway copy of a proof design, a low-voltage pour, track, via or pad whose plan-view outline overlaps that of a Mains-class item on another copper layer fails as mains_layer_separation naming the test as overlap, both items and their layers, and an item whose outline does not overlap but lies under the clearance fails as the clearance test and not as an overlap. Out of scope is an overlap of two Mains-class items.
        tracks = [track(MAINS, 10 + 2 * i, 10, 11 + 2 * i, 10, "F.Cu") for i in range(5)]
        result = found(board(*tracks, zone(LOW, "In1.Cu", (5, 5, 30, 15), (5, 5, 30, 15))))
        self.assertEqual(len(named(result, "overlap")), 5)
        violations = board_check.layer_violations(DESIGN, result.findings, {}, ["F.Cu", "In1.Cu", "In2.Cu", "B.Cu"])
        self.assertEqual(sorted(v.location.rsplit("; ", 1)[1] for v in violations), ["creepage", "overlap"])
        self.assertIn("4 more pairs of the same kinds", " ".join(v.message for v in violations))


def exception(**changes) -> dict:
    held = {"pair": "mains_to_low_voltage", "constraint": "clearance", "between": ["R1.1", "U1.1"], "accepted_mm": 1.0,
            "reason": "a synthetic ground", "bounded_by": "a synthetic independent element",
            "accepted_by": "maintainer", "accepted_on": "2026-10-01"}
    held.update(changes)
    return held


def judged(tree: list, *entries: dict, clearance: float = 3.0, creepage: float = 0.1):
    """What the check makes of the cross-layer findings of a layout under signed exceptions: the judgement and the violations left."""
    basis = {"mains_to_low_voltage": {"clearance_mm": clearance, "creepage_mm": creepage}, "accepted_exceptions": list(entries),
             "accepted_by": "maintainer", "accepted_on": "2026-10-05"}
    signed = board_check.Signed(clearance, creepage, basis)
    result = found(tree, clearance, creepage)
    judgement = board_check.judge_exceptions(DESIGN, RECORD, signed, [], tree, TODAY, {MAINS},
                                             [board_check.layer_shortfall(entry) for entry in result.findings if entry.mains is not None])
    left = [entry for entry in result.findings if entry.shortfall is None or id(entry.shortfall.entry) not in judgement.consumed]
    stack = ["F.Cu", "In1.Cu", "In2.Cu", "B.Cu"]
    return judgement, board_check.layer_violations(DESIGN, left, result.unmeasured, stack)


class AnExceptionExcusesItsPairAndNoOther(unittest.TestCase):
    def tree(self, gap: float):
        return board(smd("R1", MAINS, 10, 10, "F.Cu"), smd("U1", LOW, 11 + gap, 10, "B.Cu"), smd("U2", LOW, 10, 13, "B.Cu"))

    def test_a_pair_named_by_pads_at_or_above_the_accepted_distance_is_accepted_and_reported(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-APART-FROM-LOW-VOLTAGE-COPPER-ON-EVERY-LAYER.C6: On a throwaway copy of a proof design with a synthetic signed record, a cross-layer shortfall between the two pads or nets a between entry of pair mains_to_low_voltage names is accepted and reported when its distance is at least accepted_mm and fails as spacing_exception naming the entry when less, a shortfall between any other pair stays a mains_layer_separation failure, and an entry that no shortfall uses fails. Out of scope is the signing of any entry.
        judgement, left = judged(self.tree(1.5), exception())
        self.assertEqual(judgement.violations, [])
        (line,) = judgement.accepted
        self.assertIn("accepted exception: mains_to_low_voltage clearance between R1.1 and U1.1", line)
        self.assertIn("measures 1.5 mm", line)
        self.assertNotIn("U1", " ".join(violation.message for violation in left))

    def test_an_entry_that_is_unsigned_or_a_placeholder_or_dated_ahead_excuses_nothing(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-APART-FROM-LOW-VOLTAGE-COPPER-ON-EVERY-LAYER.C6: On a throwaway copy of a proof design with a synthetic signed record, a cross-layer shortfall between the two pads or nets a between entry of pair mains_to_low_voltage names is accepted and reported when its distance is at least accepted_mm and fails as spacing_exception naming the entry when less, a shortfall between any other pair stays a mains_layer_separation failure, and an entry that no shortfall uses fails. Out of scope is the signing of any entry.
        for label, changes in (("empty signer", dict(accepted_by="")), ("placeholder signer", dict(accepted_by="TODO")),
                               ("future date", dict(accepted_on="2027-01-01")), ("no date", dict(accepted_on="not a date"))):
            with self.subTest(entry=label):
                judgement, left = judged(self.tree(1.5), exception(**changes))
                self.assertEqual(judgement.accepted, [])
                self.assertEqual([violation.rule for violation in judgement.violations], ["spacing_exception"])
                self.assertIn("is not an acceptance, so it excuses nothing", judgement.violations[0].message)
                (remaining,) = left
                self.assertEqual(remaining.rule, board_check.LAYER_RULE)
                self.assertIn("1 more pair of the same kinds", remaining.message)
        judgement, left = judged(self.tree(1.5), exception())
        self.assertEqual(len(judgement.accepted), 1)

    def test_a_pair_named_by_nets_is_accepted_the_same(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-APART-FROM-LOW-VOLTAGE-COPPER-ON-EVERY-LAYER.C6: On a throwaway copy of a proof design with a synthetic signed record, a cross-layer shortfall between the two pads or nets a between entry of pair mains_to_low_voltage names is accepted and reported when its distance is at least accepted_mm and fails as spacing_exception naming the entry when less, a shortfall between any other pair stays a mains_layer_separation failure, and an entry that no shortfall uses fails. Out of scope is the signing of any entry.
        judgement, left = judged(self.tree(1.5), exception(between=[MAINS, LOW]))
        self.assertEqual(judgement.violations, [])
        self.assertEqual(len(judgement.accepted), 2)
        self.assertEqual(left, [])

    def test_a_pair_below_the_accepted_distance_fails_as_a_spacing_exception_naming_the_entry(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-APART-FROM-LOW-VOLTAGE-COPPER-ON-EVERY-LAYER.C6: On a throwaway copy of a proof design with a synthetic signed record, a cross-layer shortfall between the two pads or nets a between entry of pair mains_to_low_voltage names is accepted and reported when its distance is at least accepted_mm and fails as spacing_exception naming the entry when less, a shortfall between any other pair stays a mains_layer_separation failure, and an entry that no shortfall uses fails. Out of scope is the signing of any entry.
        judgement, _ = judged(self.tree(0.5), exception(accepted_mm=1.0))
        (violation,) = judgement.violations
        self.assertEqual(violation.rule, "spacing_exception")
        self.assertIn("accepted_exceptions[0] accepts mains_to_low_voltage clearance between R1.1 and U1.1 down to 1 mm", violation.message)
        self.assertEqual(judgement.accepted, [])

    def test_a_pair_at_the_accepted_distance_passes_and_just_under_it_fails(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-APART-FROM-LOW-VOLTAGE-COPPER-ON-EVERY-LAYER.C6: On a throwaway copy of a proof design with a synthetic signed record, a cross-layer shortfall between the two pads or nets a between entry of pair mains_to_low_voltage names is accepted and reported when its distance is at least accepted_mm and fails as spacing_exception naming the entry when less, a shortfall between any other pair stays a mains_layer_separation failure, and an entry that no shortfall uses fails. Out of scope is the signing of any entry.
        self.assertEqual(judged(self.tree(1.0), exception(accepted_mm=1.0))[0].violations, [])
        self.assertEqual(len(judged(self.tree(0.99), exception(accepted_mm=1.0))[0].violations), 1)

    def test_a_shortfall_between_any_other_pair_stays_a_layer_separation_failure(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-APART-FROM-LOW-VOLTAGE-COPPER-ON-EVERY-LAYER.C6: On a throwaway copy of a proof design with a synthetic signed record, a cross-layer shortfall between the two pads or nets a between entry of pair mains_to_low_voltage names is accepted and reported when its distance is at least accepted_mm and fails as spacing_exception naming the entry when less, a shortfall between any other pair stays a mains_layer_separation failure, and an entry that no shortfall uses fails. Out of scope is the signing of any entry.
        judgement, left = judged(self.tree(1.5), exception())
        self.assertEqual([violation.rule for violation in left], [board_check.LAYER_RULE])
        self.assertIn("[/LV]", left[0].message)
        self.assertIn("U2", left[0].message)

    def test_an_entry_no_shortfall_uses_fails(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-APART-FROM-LOW-VOLTAGE-COPPER-ON-EVERY-LAYER.C6: On a throwaway copy of a proof design with a synthetic signed record, a cross-layer shortfall between the two pads or nets a between entry of pair mains_to_low_voltage names is accepted and reported when its distance is at least accepted_mm and fails as spacing_exception naming the entry when less, a shortfall between any other pair stays a mains_layer_separation failure, and an entry that no shortfall uses fails. Out of scope is the signing of any entry.
        judgement, _ = judged(self.tree(1.5), exception(between=["R1.1", "U2.1"], constraint="creepage", accepted_mm=0.05), clearance=0.1, creepage=0.2)
        (violation,) = judgement.violations
        self.assertIn("reports no shortfall", violation.message)

    def test_a_creepage_entry_judges_the_creepage_path_and_leaves_the_clearance(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-APART-FROM-LOW-VOLTAGE-COPPER-ON-EVERY-LAYER.C6: On a throwaway copy of a proof design with a synthetic signed record, a cross-layer shortfall between the two pads or nets a between entry of pair mains_to_low_voltage names is accepted and reported when its distance is at least accepted_mm and fails as spacing_exception naming the entry when less, a shortfall between any other pair stays a mains_layer_separation failure, and an entry that no shortfall uses fails. Out of scope is the signing of any entry.
        judgement, left = judged(self.tree(1.5), exception(constraint="creepage", accepted_mm=1.0), clearance=3.0, creepage=3.0)
        self.assertEqual(judgement.violations, [])
        self.assertEqual(len(judgement.accepted), 1)
        self.assertIn("clearance", " ".join(violation.message for violation in left))


class AMainsDesignThatCannotBeReadIsNotPassedByTheRule(unittest.TestCase):
    def test_a_layout_with_an_outline_that_does_not_close_cannot_be_read(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-APART-FROM-LOW-VOLTAGE-COPPER-ON-EVERY-LAYER.C7: On throwaway proof designs, a design that declares MAINS present and whose record has no mains_to_low_voltage mapping, or whose Mains net class cannot be resolved from the project, fails under the existing names and is not passed by the new rule; a design that declares no MAINS is not held by the rule. Out of scope is the wording of the existing failures.
        edge = '(gr_line (start 0 0) (end 60 0) (stroke (width 0.1) (type default)) (layer "Edge.Cuts"))'
        with self.assertRaises(board_geometry.Unreadable):
            found(board(track(MAINS, 10, 10, 20, 10, "F.Cu"), edge=edge))

    def test_a_layout_drawing_a_curve_on_the_outline_cannot_be_read(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-APART-FROM-LOW-VOLTAGE-COPPER-ON-EVERY-LAYER.C7: On throwaway proof designs, a design that declares MAINS present and whose record has no mains_to_low_voltage mapping, or whose Mains net class cannot be resolved from the project, fails under the existing names and is not passed by the new rule; a design that declares no MAINS is not held by the rule. Out of scope is the wording of the existing failures.
        curve = '(gr_curve (pts (xy 0 0) (xy 1 1) (xy 2 1) (xy 3 0)) (layer "Edge.Cuts"))'
        with self.assertRaises(board_geometry.Unreadable):
            found(board(track(MAINS, 10, 10, 20, 10, "F.Cu"), edge=outline() + curve))

    def test_no_mains_class_item_means_no_pair(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-APART-FROM-LOW-VOLTAGE-COPPER-ON-EVERY-LAYER.C7: On throwaway proof designs, a design that declares MAINS present and whose record has no mains_to_low_voltage mapping, or whose Mains net class cannot be resolved from the project, fails under the existing names and is not passed by the new rule; a design that declares no MAINS is not held by the rule. Out of scope is the wording of the existing failures.
        self.assertEqual(found(board(track(LOW, 10, 10, 20, 10, "F.Cu"), track("/LV2", 10, 11, 20, 11, "In1.Cu")), mains=()).findings, [])


README = os.path.join(os.path.dirname(os.path.dirname(TOOLS)), "hardware", "README.md")


class TheHardwareNotesStateTheRule(unittest.TestCase):
    def notes(self):
        with open(README, encoding="utf-8") as handle:
            return handle.read()

    def test_the_rules_table_has_a_row_naming_the_four_tests_and_the_figures_it_reads(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-APART-FROM-LOW-VOLTAGE-COPPER-ON-EVERY-LAYER.C10: hardware/README.md carries a row for the mains_layer_separation rule naming its four tests and the record figures each reads, and states that KiCad's design rule check compares copper on the same layer only, which is why the rule exists. Out of scope is any other rule's row.
        row = next(line for line in self.notes().splitlines() if line.startswith(f"| `{board_check.LAYER_RULE}` |"))
        for word in ("clearance", "creepage", "overlap", "pull-back", "mains_to_low_voltage.clearance_mm", ".creepage_mm",
                     "KiCad's own rule compares copper on one layer only"):
            self.assertIn(word, row)

    def test_a_paragraph_states_that_kicad_compares_one_layer_only_and_what_the_creepage_test_fires_for(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-APART-FROM-LOW-VOLTAGE-COPPER-ON-EVERY-LAYER.C10: hardware/README.md carries a row for the mains_layer_separation rule naming its four tests and the record figures each reads, and states that KiCad's design rule check compares copper on the same layer only, which is why the rule exists. Out of scope is any other rule's row.
        paragraph = next(block for block in self.notes().split("\n\n") if block.startswith("The **mains layer separation**"))
        for word in ("compares copper on one layer only", "`mains_to_low_voltage.clearance_mm` and `.creepage_mm`", "Clearance:", "Creepage:",
                     "Overlap:", "Pull-back:", "1.5 mm", "SLOT_WALL_MM", "not only for a pair a slot lies between", "board's thickness is not added",
                     "accepted_exceptions", "adds no KiCad run", "the straight line, which is shorter than the way round the notch",
                     "whichever corner is written first", "`cannot measure a copper curve`", "to the outer edge of its stroke", "5 micrometres",
                     "a tree of boxes over their sides", "the pull-back test holds it as inner-layer copper whatever layers it is stored on"):
            self.assertIn(word, paragraph)
        self.assertEqual(board_check.SLOT_WALL_MM, 1.5)


if __name__ == "__main__":
    unittest.main()
