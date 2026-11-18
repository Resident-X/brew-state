#!/usr/bin/env python3
"""The mains-copper compare of the locked-copper tool, driven on synthetic boards against the real kicad-cli."""

from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import unittest

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import board_fixtures  # noqa: E402
import locked_copper  # noqa: E402
from locked_copper_fixtures import KICAD_CLI, layout, project  # noqa: E402

MAINS_PROJECT = project({"/AC": "Mains", "/AC2": "Mains"}, [], classes=("Mains",), mains="present")


def setUpModule():
    board_fixtures.require_tools(KICAD_CLI)


TEXT = {
    "track": '(segment (start 0 0) (end 5 0) (width 0.5) (locked yes) (layer "F.Cu") (net "/AC") (uuid "00000000-0000-4000-8000-000000000001"))',
    "arc": '(arc (start 0 10) (mid 2 12) (end 4 10) (width 0.5) (locked yes) (layer "F.Cu") (net "/AC2") (uuid "00000000-0000-4000-8000-000000000002"))',
    "via": '(via (at 20 20) (size 0.8) (drill 0.4) (layers "F.Cu" "B.Cu") (locked yes) (net "/AC") (uuid "00000000-0000-4000-8000-000000000003"))',
    "zone": '(zone (net "/AC") (locked yes) (layer "B.Cu") (uuid "00000000-0000-4000-8000-000000000004") (hatch edge 0.5) '
            '(connect_pads (clearance 0.5)) (min_thickness 0.25) (fill (thermal_gap 0.5) (thermal_bridge_width 0.5)) '
            '(polygon (pts (xy 30 30) (xy 40 30) (xy 40 40) (xy 30 40))))',
    "lv": '(segment (start 0 20) (end 5 20) (width 0.25) (layer "F.Cu") (net "/LV") (uuid "00000000-0000-4000-8000-000000000006"))',
}


def item(kind, *replace):
    """The base board's item `kind` as KiCad writes it, with each (old, new) pair of `replace` applied to its text."""
    text = TEXT[kind]
    for old, new in replace:
        assert old in text, (old, text)
        text = text.replace(old, new)
    return text


BASE = ["track", "arc", "via", "zone", "lv"]


def base(*leave_out):
    return [item(kind) for kind in BASE if kind not in leave_out]


def lv_track(y, layer="F.Cu", x0=0, x1=5, width=0.25, net="/LV", number=9):
    return (f'(segment (start {x0} {y}) (end {x1} {y}) (width {width}) (layer "{layer}") (net "{net}") '
            f'(uuid "00000000-0000-4000-8000-{number:012d}"))')


def part(reference, x, y, pads, layer="F.Cu"):
    """A footprint at (x, y) holding `pads`, each (number, net, kind, size, dx, layers)."""
    body = "".join(f'(pad "{number}" {kind} rect (at {dx} 0) (size {size} {size})' + (" (drill 0.5)" if kind == "thru_hole" else "")
                   + f' (layers {layers}) (net "{net}") (uuid "00000000-0000-4000-8000-{900 + index:012d}")) '
                   for index, (number, net, kind, size, dx, layers) in enumerate(pads))
    return (f'(footprint "test:P" (layer "{layer}") (uuid "00000000-0000-4000-8000-{int(x * 100 + y):012d}") (at {x} {y}) '
            f'(property "Reference" "{reference}" (at 0 -2 0) (layer "F.SilkS") (uuid "00000000-0000-4000-8000-{int(x * 100 + y) + 1:012d}") '
            f'(effects (font (size 1 1) (thickness 0.15)))) {body})')


def rule_area(name, layers, corners, net=None):
    points = " ".join(f"(xy {x} {y})" for x, y in corners)
    return (f'(zone {f"(net {net})" if net else ""} (layers {layers}) (uuid "00000000-0000-4000-8000-{abs(hash(name)) % 10**12:012d}") '
            f'(name "{name}") (hatch edge 0.5) (connect_pads (clearance 0.5)) (min_thickness 0.25) '
            '(keepout (tracks not_allowed) (vias not_allowed) (pads allowed) (copperpour not_allowed) (footprints allowed)) '
            f'(polygon (pts {points})))')


class MainsCompare(unittest.TestCase):
    """Two boards, each with the project file beside it, in folders of their own."""

    def setUp(self):
        scratch = tempfile.TemporaryDirectory(prefix="mains-compare-test-")
        self.addCleanup(scratch.cleanup)
        self.root = scratch.name
        self.first = self.make("first", base())
        self.second = self.make("second", base())

    def make(self, name, items, project_text=MAINS_PROJECT):
        folder = os.path.join(self.root, name)
        os.makedirs(folder, exist_ok=True)
        board = os.path.join(folder, "b.kicad_pcb")
        with open(board, "w", encoding="utf-8") as handle:
            handle.write(layout(items))
        with open(os.path.join(folder, "b.kicad_pro"), "w", encoding="utf-8") as handle:
            handle.write(project_text)
        return board

    def compare(self, distance="1", fmt=None, first=None, second=None, classes=()):
        first, second = first or self.first, second or self.second
        argv = ["--kicad-cli", KICAD_CLI, "mains-compare", "--before-board", first,
                "--before-project", os.path.splitext(first)[0] + ".kicad_pro", "--board", second,
                "--project", os.path.splitext(second)[0] + ".kicad_pro", "--distance", str(distance)]
        for name in classes:
            argv += ["--class", name]
        out = io.StringIO()
        status = locked_copper.main(argv + (["--format", fmt] if fmt else []), out=out)
        text = out.getvalue()
        return (status, json.loads(text)) if fmt == "json" else (status, text.splitlines())

    def findings(self, lines, kind):
        return [line.split(" | ") for line in lines if line.startswith(kind + " | ")]

    def test_identical_boards_pass_in_text_and_json(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C1: Run over two synthetic boards, the command exits successfully only when every Mains-class item is identical in both and no low-voltage copper in the second board lies nearer to Mains-class copper than the stated distance. It exits with failure, naming the item or the copper, when a Mains-class item is added, removed or changed, and when low-voltage copper is nearer than the stated distance. Tests cover identical boards, each kind of change, copper exactly at the distance and an empty board, and the report in text and in JSON. This does not cover a board's choice of which distance to state.
        status, lines = self.compare()
        self.assertEqual(status, 0, lines)
        self.assertEqual(lines, ["RESULT | PASS | all 4 Mains-class items identical on both boards and no low-voltage copper nearer than 1 mm"])
        status, found = self.compare(fmt="json")
        self.assertEqual((status, found["result"], found["findings"], found["mains_items_first"], found["mains_items_second"],
                          found["distance_mm"]), (0, "PASS", [], 4, 4, 1.0))

    def test_a_mains_item_added_removed_or_changed_fails_naming_it(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C1: Run over two synthetic boards, the command exits successfully only when every Mains-class item is identical in both and no low-voltage copper in the second board lies nearer to Mains-class copper than the stated distance. It exits with failure, naming the item or the copper, when a Mains-class item is added, removed or changed, and when low-voltage copper is nearer than the stated distance. Tests cover identical boards, each kind of change, copper exactly at the distance and an empty board, and the report in text and in JSON. This does not cover a board's choice of which distance to state.
        added = ('(segment (start 0 50) (end 5 50) (width 0.5) (locked yes) (layer "F.Cu") (net "/AC") '
                 '(uuid "00000000-0000-4000-8000-000000000020"))')
        cases = {
            "ADDED": (base() + [added], "track [/AC] on F.Cu from (0, 50) mm"),
            "MISSING": (base("track"), "track [/AC] on F.Cu from (0, 0) mm to (5, 0) mm"),
            "CHANGED": ([item("track", ("(end 5 0)", "(end 6 0)"))] + base("track"), "end (5, 0) mm -> (6, 0) mm"),
        }
        for finding, (items, needle) in cases.items():
            with self.subTest(finding=finding):
                second = self.make("second", items)
                status, lines = self.compare(second=second)
                self.assertEqual(status, 1, lines)
                found = self.findings(lines, finding)
                self.assertEqual(len(found), 1, lines)
                self.assertIn(needle, " | ".join(found[0]))
                self.assertTrue(lines[-1].startswith("RESULT | FAIL | 1 finding"), lines)
                status, report = self.compare(second=second, fmt="json")
                self.assertEqual((status, report["result"], [f["finding"] for f in report["findings"]]), (1, "FAIL", [finding]))

    def test_each_kind_of_mains_item_is_held_a_via_an_arc_and_a_zone_as_well_as_a_track(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C1: Run over two synthetic boards, the command exits successfully only when every Mains-class item is identical in both and no low-voltage copper in the second board lies nearer to Mains-class copper than the stated distance. It exits with failure, naming the item or the copper, when a Mains-class item is added, removed or changed, and when low-voltage copper is nearer than the stated distance. Tests cover identical boards, each kind of change, copper exactly at the distance and an empty board, and the report in text and in JSON. This does not cover a board's choice of which distance to state.
        changes = {
            "via": item("via", ("(drill 0.4)", "(drill 0.5)")),
            "arc": item("arc", ("(mid 2 12)", "(mid 2 12.5)")),
            "zone": item("zone", ("(xy 40 40)", "(xy 41 40)")),
        }
        for kind, changed in changes.items():
            with self.subTest(kind=kind):
                second = self.make("second", [changed if k == kind else item(k) for k in BASE])
                status, lines = self.compare(second=second)
                self.assertEqual(status, 1, lines)
                found = self.findings(lines, "CHANGED")
                self.assertEqual(len(found), 1, lines)
                self.assertTrue(found[0][1].startswith(kind), found)

    def test_a_mains_item_unlocked_or_moved_to_a_low_voltage_net_fails(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C1: Run over two synthetic boards, the command exits successfully only when every Mains-class item is identical in both and no low-voltage copper in the second board lies nearer to Mains-class copper than the stated distance. It exits with failure, naming the item or the copper, when a Mains-class item is added, removed or changed, and when low-voltage copper is nearer than the stated distance. Tests cover identical boards, each kind of change, copper exactly at the distance and an empty board, and the report in text and in JSON. This does not cover a board's choice of which distance to state.
        second = self.make("second", [item("track").replace(" (locked yes)", "")] + base("track"))
        status, lines = self.compare(second=second)
        self.assertEqual(status, 1, lines)
        self.assertEqual(len(self.findings(lines, "UNLOCKED")), 1, lines)
        second = self.make("second", [item("track", ('(net "/AC")', '(net "/LV")'))] + base("track"))
        status, lines = self.compare(second=second)
        self.assertEqual(status, 1, lines)
        self.assertEqual(len(self.findings(lines, "MISSING")), 1, lines)

    def test_low_voltage_copper_nearer_than_the_distance_fails_naming_it_and_exactly_at_it_passes(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C1: Run over two synthetic boards, the command exits successfully only when every Mains-class item is identical in both and no low-voltage copper in the second board lies nearer to Mains-class copper than the stated distance. It exits with failure, naming the item or the copper, when a Mains-class item is added, removed or changed, and when low-voltage copper is nearer than the stated distance. Tests cover identical boards, each kind of change, copper exactly at the distance and an empty board, and the report in text and in JSON. This does not cover a board's choice of which distance to state.
        # The /AC track runs along y 0 and is 0.5 wide, so its edge is at y 0.25. A 0.25 wide track at y 2.375 has its
        # edge at y 2.25: exactly 2 mm away.
        second = self.make("second", base() + [lv_track(2.375)])
        status, lines = self.compare(distance=2, second=second)
        self.assertEqual(status, 0, lines)
        status, lines = self.compare(distance=2.001, second=second)
        self.assertEqual(status, 1, lines)
        near = self.findings(lines, "NEAR")
        self.assertEqual(len(near), 1, lines)
        self.assertIn("track [/LV] on F.Cu from (0, 2.375) mm", near[0][1])
        self.assertIn("is 2 mm from track [/AC]", near[0][2])
        self.assertIn("nearer than 2.001 mm", near[0][2])
        status, found = self.compare(distance=2.001, second=second, fmt="json")
        self.assertEqual([f["finding"] for f in found["findings"]], ["NEAR"])
        status, lines = self.compare(distance=1.999, second=second)
        self.assertEqual(status, 0, lines)

    def test_distance_is_measured_to_each_kind_of_mains_copper(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C1: Run over two synthetic boards, the command exits successfully only when every Mains-class item is identical in both and no low-voltage copper in the second board lies nearer to Mains-class copper than the stated distance. It exits with failure, naming the item or the copper, when a Mains-class item is added, removed or changed, and when low-voltage copper is nearer than the stated distance. Tests cover identical boards, each kind of change, copper exactly at the distance and an empty board, and the report in text and in JSON. This does not cover a board's choice of which distance to state.
        # A via at (20, 20) of 0.8 diameter, a zone outline from (30, 30) to (40, 40), an arc from (0, 10) to (4, 10) through (2, 12).
        probes = {
            "via": lv_track(20, x0=21.4, x1=25),     # 21.4 - 20 - 0.4 - 0.125 edge to edge
            "zone": lv_track(41, x0=30, x1=40, layer="B.Cu"),   # on the zone's layer, 1 mm below the outline, less half the width
            "arc": lv_track(13, x0=1, x1=3),         # 1 mm above the arc's top at (2, 12)
        }
        for kind, probe in probes.items():
            with self.subTest(kind=kind):
                second = self.make("second", base("lv") + [probe])
                status, lines = self.compare(distance=5, second=second)
                self.assertEqual(status, 1, lines)
                near = self.findings(lines, "NEAR")
                self.assertEqual(len(near), 1, lines)
                self.assertIn(f"from {kind} [", near[0][2], near)
                status, lines = self.compare(distance=0.5, second=second)
                self.assertEqual(status, 0, lines)

    def test_copper_on_another_layer_or_in_the_first_board_only_is_not_near(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C1: Run over two synthetic boards, the command exits successfully only when every Mains-class item is identical in both and no low-voltage copper in the second board lies nearer to Mains-class copper than the stated distance. It exits with failure, naming the item or the copper, when a Mains-class item is added, removed or changed, and when low-voltage copper is nearer than the stated distance. Tests cover identical boards, each kind of change, copper exactly at the distance and an empty board, and the report in text and in JSON. This does not cover a board's choice of which distance to state.
        on_other_layer = self.make("second", base("lv") + [lv_track(0.5, layer="In1.Cu")])
        status, lines = self.compare(distance=5, second=on_other_layer)
        self.assertEqual(status, 0, lines)
        near_in_first_only = self.make("first", base() + [lv_track(0.5)])
        status, lines = self.compare(distance=5, first=near_in_first_only, second=on_other_layer)
        self.assertEqual(status, 0, "the extra low-voltage track is in the first board only, and is not Mains-class")
        self.assertEqual(self.findings(lines, "NEAR"), [], lines)

    def test_low_voltage_copper_overlapping_mains_copper_is_zero_away(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C1: Run over two synthetic boards, the command exits successfully only when every Mains-class item is identical in both and no low-voltage copper in the second board lies nearer to Mains-class copper than the stated distance. It exits with failure, naming the item or the copper, when a Mains-class item is added, removed or changed, and when low-voltage copper is nearer than the stated distance. Tests cover identical boards, each kind of change, copper exactly at the distance and an empty board, and the report in text and in JSON. This does not cover a board's choice of which distance to state.
        second = self.make("second", base("lv") + [lv_track(0, x0=2, x1=3, width=0.1)])
        status, lines = self.compare(distance=0.001, second=second)
        self.assertEqual(status, 1, lines)
        self.assertIn("is 0 mm from", self.findings(lines, "NEAR")[0][2])

    def test_empty_boards_pass_and_say_there_is_no_mains_copper(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C1: Run over two synthetic boards, the command exits successfully only when every Mains-class item is identical in both and no low-voltage copper in the second board lies nearer to Mains-class copper than the stated distance. It exits with failure, naming the item or the copper, when a Mains-class item is added, removed or changed, and when low-voltage copper is nearer than the stated distance. Tests cover identical boards, each kind of change, copper exactly at the distance and an empty board, and the report in text and in JSON. This does not cover a board's choice of which distance to state.
        empty_first, empty_second = self.make("empty-first", []), self.make("empty-second", [])
        status, lines = self.compare(first=empty_first, second=empty_second)
        self.assertEqual(status, 0, lines)
        self.assertEqual(lines, ["RESULT | PASS | all 0 Mains-class items identical on both boards and no low-voltage copper nearer than 1 mm "
                                 "(no Mains-class copper on either board)"])
        status, found = self.compare(first=empty_first, second=empty_second, fmt="json")
        self.assertEqual((status, found["result"], found["mains_items_first"], found["mains_items_second"]), (0, "PASS", 0, 0))
        status, lines = self.compare(first=empty_first)
        self.assertEqual(status, 1, "mains copper appearing on an empty board is an addition")
        self.assertEqual(len(self.findings(lines, "ADDED")), 4, lines)
        status, lines = self.compare(second=empty_second)
        self.assertEqual(status, 1, "mains copper gone from a board is a removal")
        self.assertEqual(len(self.findings(lines, "MISSING")), 4, lines)

    def test_refusals_name_what_is_wrong_and_nothing_is_taken_as_a_pass(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C1: Run over two synthetic boards, the command exits successfully only when every Mains-class item is identical in both and no low-voltage copper in the second board lies nearer to Mains-class copper than the stated distance. It exits with failure, naming the item or the copper, when a Mains-class item is added, removed or changed, and when low-voltage copper is nearer than the stated distance. Tests cover identical boards, each kind of change, copper exactly at the distance and an empty board, and the report in text and in JSON. This does not cover a board's choice of which distance to state.
        for distance in ("0", "-1", "nan"):
            with self.subTest(distance=distance):
                status, lines = self.compare(distance=distance)
                self.assertEqual(status, 1, lines)
                self.assertTrue(lines[0].startswith("REFUSED | --distance | "), lines)
        undeclared = self.make("second", base(), project(None, [], classes=("Mains",), mains=None))
        status, lines = self.compare(second=undeclared)
        self.assertEqual(status, 1, lines)
        self.assertTrue(any("MAINS" in field for field in self.findings(lines, "REFUSED")[0]), lines)
        status, lines = self.compare(classes=["NoSuchClass"])
        self.assertEqual(status, 1, lines)
        self.assertTrue(any("defines no net class of this name" in found[2] and found[1] == "NoSuchClass"
                            for found in self.findings(lines, "REFUSED")), lines)
        open(os.path.join(self.root, "second", "~b.kicad_pcb.lck"), "w").close()
        status, lines = self.compare()
        self.assertEqual(status, 1, lines)
        self.assertEqual(len(self.findings(lines, "OPEN")), 1, lines)
        status, found = self.compare(fmt="json")
        self.assertEqual((status, found["result"]), (1, "FAIL"))

    def test_boards_that_cannot_be_read_fail_in_text_and_json(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C1: Run over two synthetic boards, the command exits successfully only when every Mains-class item is identical in both and no low-voltage copper in the second board lies nearer to Mains-class copper than the stated distance. It exits with failure, naming the item or the copper, when a Mains-class item is added, removed or changed, and when low-voltage copper is nearer than the stated distance. Tests cover identical boards, each kind of change, copper exactly at the distance and an empty board, and the report in text and in JSON. This does not cover a board's choice of which distance to state.
        bad = self.make("second", [])
        with open(bad, "w", encoding="utf-8") as handle:
            handle.write("(kicad_sch)")
        status, lines = self.compare(second=bad)
        self.assertEqual(status, 1, lines)
        self.assertTrue(lines[0].startswith("UNREADABLE | "), lines)
        self.assertTrue(lines[-1].startswith("RESULT | FAIL | the input cannot be read"), lines)
        status, found = self.compare(second=bad, fmt="json")
        self.assertEqual((status, found["result"], found["findings"][0]["finding"]), (1, "FAIL", "UNREADABLE"))

    def test_a_low_voltage_pad_on_mains_copper_is_near_and_a_pad_exactly_at_the_distance_passes(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C1: Run over two synthetic boards, the command exits successfully only when every Mains-class item is identical in both and no low-voltage copper in the second board lies nearer to Mains-class copper than the stated distance. It exits with failure, naming the item or the copper, when a Mains-class item is added, removed or changed, and when low-voltage copper is nearer than the stated distance. Tests cover identical boards, each kind of change, copper exactly at the distance and an empty board, and the report in text and in JSON. This does not cover a board's choice of which distance to state.
        lv = lambda x, layers='"F.Cu"', kind="smd": part("U1", x, 0, [("1", "/LV", kind, 1, 0, layers)])
        # The /AC track ends at x 5, 0.25 wide to either side; a 1 mm square pad centred at x 5.3 overlaps it.
        for fmt in (None, "json"):
            status, report = self.compare(distance=0.5, second=self.make("second", base("lv") + [lv(5.3)]), fmt=fmt)
            self.assertEqual(status, 1, report)
            near = ([line for line in (l.split(" | ") for l in report) if line[0] == "NEAR"] if fmt is None
                    else [[f["finding"], f["item"], f["detail"]] for f in report["findings"] if f["finding"] == "NEAR"])
            self.assertEqual(len(near), 1, report)
            self.assertIn("pad [/LV] U1 pad 1", near[0][1])
            self.assertIn("is 0 mm from track [/AC]", near[0][2])
        # Track edge at x 5.25; a pad whose near edge is at x 6.25 (centre 6.75, 1 wide) is exactly 1 mm away.
        second = self.make("second", base("lv") + [lv(6.75)])
        self.assertEqual(self.compare(distance=1, second=second)[0], 0)
        self.assertEqual(self.compare(distance=1.001, second=second)[0], 1)

    def test_a_through_hole_pad_is_on_every_layer_and_a_surface_pad_only_on_its_own(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C1: Run over two synthetic boards, the command exits successfully only when every Mains-class item is identical in both and no low-voltage copper in the second board lies nearer to Mains-class copper than the stated distance. It exits with failure, naming the item or the copper, when a Mains-class item is added, removed or changed, and when low-voltage copper is nearer than the stated distance. Tests cover identical boards, each kind of change, copper exactly at the distance and an empty board, and the report in text and in JSON. This does not cover a board's choice of which distance to state.
        in2 = ('(segment (start 0 30) (end 5 30) (width 0.5) (locked yes) (layer "In2.Cu") (net "/AC") '
               '(uuid "00000000-0000-4000-8000-000000000040"))')
        inner = self.make("first", base("lv") + [in2])
        through = part("J1", 5, 30, [("1", "/LV", "thru_hole", 1.5, 0.5, '"*.Cu" "*.Mask"')])
        surface = part("J1", 5, 30, [("1", "/LV", "smd", 1.5, 0.5, '"F.Cu" "F.Mask"')])
        for pads, expected in ((through, 1), (surface, 0)):
            second = self.make("second", base("lv") + [in2, pads])
            status, lines = self.compare(distance=0.5, first=inner, second=second)
            self.assertEqual(len(self.findings(lines, "NEAR")), expected, lines)

    def test_a_pad_with_no_copper_layer_is_not_copper_and_is_never_near(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C1: Run over two synthetic boards, the command exits successfully only when every Mains-class item is identical in both and no low-voltage copper in the second board lies nearer to Mains-class copper than the stated distance. It exits with failure, naming the item or the copper, when a Mains-class item is added, removed or changed, and when low-voltage copper is nearer than the stated distance. Tests cover identical boards, each kind of change, copper exactly at the distance and an empty board, and the report in text and in JSON. This does not cover a board's choice of which distance to state.
        mains = part("J2", 10, 60, [("1", "/AC", "smd", 1, 0, '"F.Cu" "F.Mask" "F.Paste"')])
        for layers in ('"F.Paste"', '"F.Mask"', '"F.Paste" "F.Mask"'):
            for net in ("/LV", ""):
                aperture = part("T1", 10.7, 60, [("", net, "smd", 0.5, 0, layers)])
                with self.subTest(layers=layers, net=net):
                    first = self.make("first", base() + [mains])
                    second = self.make("second", base() + [mains, aperture])
                    for fmt in (None, "json"):
                        status, report = self.compare(distance=3, first=first, second=second, fmt=fmt)
                        self.assertEqual(status, 0, report)
        # the same pad with copper is near, so the pad above is passed for its layers and not for its place
        copper = part("T1", 10.7, 60, [("", "/LV", "smd", 0.5, 0, '"F.Cu" "F.Paste"')])
        status, lines = self.compare(distance=3, first=self.make("first", base() + [mains]), second=self.make("second", base() + [mains, copper]))
        self.assertEqual((status, len(self.findings(lines, "NEAR"))), (1, 1), lines)
        # a mains pad that is itself paste-only is no mains copper either: it is not held, and nothing is near it
        paste_mains = part("J3", 10, 60, [("1", "/AC", "smd", 1, 0, '"F.Paste"')])
        status, report = self.compare(distance=3, first=self.make("first", base() + [paste_mains]), second=self.make("second", base() + [paste_mains]), fmt="json")
        self.assertEqual((status, report["mains_items_first"]), (0, 4), report)

    def test_a_mains_pad_added_removed_or_moved_fails_naming_it_in_text_and_json(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C1: Run over two synthetic boards, the command exits successfully only when every Mains-class item is identical in both and no low-voltage copper in the second board lies nearer to Mains-class copper than the stated distance. It exits with failure, naming the item or the copper, when a Mains-class item is added, removed or changed, and when low-voltage copper is nearer than the stated distance. Tests cover identical boards, each kind of change, copper exactly at the distance and an empty board, and the report in text and in JSON. This does not cover a board's choice of which distance to state.
        pad = lambda x=10: part("J2", x, 60, [("1", "/AC", "smd", 1, 0, '"F.Cu" "F.Mask"')])
        first = self.make("first", base() + [pad()])
        cases = {"MISSING": self.make("a", base()), "CHANGED": self.make("b", base() + [pad(12)]),
                 "ADDED": None}
        for finding, second in cases.items():
            with self.subTest(finding=finding):
                a, b = (self.make("c", base()), self.make("d", base() + [pad()])) if finding == "ADDED" else (first, second)
                status, lines = self.compare(first=a, second=b)
                self.assertEqual(status, 1, lines)
                found = self.findings(lines, finding)
                self.assertEqual(len(found), 1, lines)
                self.assertIn("pad [/AC] J2 pad 1", found[0][1])
                status, report = self.compare(first=a, second=b, fmt="json")
                self.assertEqual([f["finding"] for f in report["findings"]], [finding])
        status, found = self.compare(first=first, second=first, fmt="json")
        self.assertEqual((status, found["mains_items_first"], found["mains_items_second"]), (0, 5, 5))

    def test_a_rule_area_is_not_copper_and_an_unnetted_pour_is(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C1: Run over two synthetic boards, the command exits successfully only when every Mains-class item is identical in both and no low-voltage copper in the second board lies nearer to Mains-class copper than the stated distance. It exits with failure, naming the item or the copper, when a Mains-class item is added, removed or changed, and when low-voltage copper is nearer than the stated distance. Tests cover identical boards, each kind of change, copper exactly at the distance and an empty board, and the report in text and in JSON. This does not cover a board's choice of which distance to state.
        corners = [(-1, -1), (6, -1), (6, 1), (-1, 1)]
        area = rule_area("mains", '"F.Cu"', corners)
        pour = area.replace('(keepout (tracks not_allowed) (vias not_allowed) (pads allowed) (copperpour not_allowed) (footprints allowed)) ',
                            '(fill (thermal_gap 0.5) (thermal_bridge_width 0.5)) ').replace('(name "mains") ', "")
        self.assertNotIn("keepout", pour)
        for fmt in (None, "json"):
            status, report = self.compare(distance=1, second=self.make("second", base() + [area]), fmt=fmt)
            self.assertEqual(status, 0, report)
            status, report = self.compare(distance=1, second=self.make("second", base() + [pour]), fmt=fmt)
            self.assertEqual(status, 1, report)
            kinds = ([l.split(" | ")[0] for l in report if " | " in l][:1] if fmt is None else [f["finding"] for f in report["findings"]])
            self.assertEqual(kinds, ["NEAR"])

    def test_the_indexed_search_finds_what_a_search_of_every_pair_finds(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C1: Run over two synthetic boards, the command exits successfully only when every Mains-class item is identical in both and no low-voltage copper in the second board lies nearer to Mains-class copper than the stated distance. It exits with failure, naming the item or the copper, when a Mains-class item is added, removed or changed, and when low-voltage copper is nearer than the stated distance. Tests cover identical boards, each kind of change, copper exactly at the distance and an empty board, and the report in text and in JSON. This does not cover a board's choice of which distance to state.
        import random
        rng = random.Random(7)
        items, number = [], 100
        for index in range(120):
            net = rng.choice(["/AC", "/AC2", "/LV", "/LV", "/LV2"])
            layer = rng.choice(["F.Cu", "B.Cu"])
            x, y = rng.uniform(0, 80), rng.uniform(0, 80)
            number += 1
            kind = rng.choice(["track", "track", "via", "pad", "zone"])
            if kind == "track":
                items.append(f'(segment (start {x:.3f} {y:.3f}) (end {x + rng.uniform(-8, 8):.3f} {y + rng.uniform(-8, 8):.3f}) '
                             f'(width 0.25) (layer "{layer}") (net "{net}") (uuid "00000000-0000-4000-8000-{number:012d}"))')
            elif kind == "via":
                items.append(f'(via (at {x:.3f} {y:.3f}) (size 0.8) (drill 0.4) (layers "F.Cu" "B.Cu") (net "{net}") '
                             f'(uuid "00000000-0000-4000-8000-{number:012d}"))')
            elif kind == "pad":
                items.append(part(f"P{index}", round(x, 2), round(y, 2), [("1", net, "smd", rng.uniform(0.5, 2), 0, f'"{layer}" "{layer[0]}.Paste"')]))
            else:
                w, h = rng.uniform(2, 20), rng.uniform(2, 20)
                items.append(f'(zone (net "{net}") (layer "{layer}") (uuid "00000000-0000-4000-8000-{number:012d}") (hatch edge 0.5) '
                             '(connect_pads (clearance 0.5)) (min_thickness 0.25) (fill (thermal_gap 0.5) (thermal_bridge_width 0.5)) '
                             f'(polygon (pts (xy {x:.2f} {y:.2f}) (xy {x + w:.2f} {y:.2f}) (xy {x + w:.2f} {y + h:.2f}) (xy {x:.2f} {y + h:.2f}))))')
        board = self.make("random", items)
        lay = locked_copper.read_layout(board)
        every = locked_copper.copper(lay, board, rule_areas=False) + locked_copper.pad_items(lay)
        mains = [i for i in every if i["net"] in ("/AC", "/AC2")]
        others = [i for i in every if i["net"] not in ("/AC", "/AC2")]
        self.assertGreater(len(mains), 20)
        self.assertGreater(len(others), 40)
        for distance in (0.3, 3.0, 12.0):
            with self.subTest(distance=distance):
                indexed = locked_copper.near_findings(others, mains, distance, indexed=True)
                every_pair = locked_copper.near_findings(others, mains, distance, indexed=False)
                self.assertEqual(indexed, every_pair)
                self.assertGreater(len(indexed), 0, "the board holds what is near, so the comparison is not of two empty lists")
                self.assertLess(len(indexed), len(others), "and what is not")

    def test_the_capped_polygon_gap_is_the_exact_gap_wherever_that_is_under_the_cap(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C1: Run over two synthetic boards, the command exits successfully only when every Mains-class item is identical in both and no low-voltage copper in the second board lies nearer to Mains-class copper than the stated distance. It exits with failure, naming the item or the copper, when a Mains-class item is added, removed or changed, and when low-voltage copper is nearer than the stated distance. Tests cover identical boards, each kind of change, copper exactly at the distance and an empty board, and the report in text and in JSON. This does not cover a board's choice of which distance to state.
        import random
        import board_geometry
        rng = random.Random(3)
        def polygon():
            x, y = rng.uniform(0, 30), rng.uniform(0, 30)
            return [(x + rng.uniform(0, 3), y + rng.uniform(0, 3)), (x + 5 + rng.uniform(0, 3), y + rng.uniform(0, 3)),
                    (x + 5 + rng.uniform(0, 3), y + 5 + rng.uniform(0, 3)), (x + rng.uniform(0, 3), y + 5 + rng.uniform(0, 3))]
        seen = 0
        for _ in range(300):
            one, other = polygon(), polygon()
            exact = board_geometry.polygon_distance(one, other)
            capped = locked_copper.polygons_gap([one], [other], 4.0)
            if exact < 4.0:
                seen += 1
                self.assertAlmostEqual(capped, exact, places=9)
            else:
                self.assertGreaterEqual(capped, 4.0)
        self.assertGreater(seen, 30)


if __name__ == "__main__":
    unittest.main()
