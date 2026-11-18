#!/usr/bin/env python3
"""The footprint audit: body gaps from a body table, the pad dump and the rotation solver, on synthetic boards."""

from __future__ import annotations

import builtins
import contextlib
import io
import json
import math
import os
import re
import subprocess
import sys
import unittest
from unittest import mock

TESTS = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(TESTS)
HARDWARE = os.path.dirname(TOOLS)
sys.path.insert(0, TOOLS)
sys.path.insert(0, TESTS)

import footprint_audit  # noqa: E402
from footprint_audit_fixtures import board, courtyard, footprint, pad, table  # noqa: E402
from layout_tool_fixtures import Work  # noqa: E402

BOX = ("test:Box", {"rects": [("body", -2, -2, 2, 2)]})
BAR = ("test:Bar", {"rects": [("bar", 0, -1, 10, 1)]})


class Audit(Work):
    def gaps(self, parts, entries, *extra):
        """(status, lines) of `gaps` over a board of `parts` (footprint strings) and a table of `entries` (a dict)."""
        board_path = self.write("b.kicad_pcb", board(parts))
        table_path = self.write("bodies.yaml", table(entries))
        return self.run_tool(footprint_audit.main, "gaps", "--board", board_path, "--bodies", table_path, *extra)

    def gaps_json(self, parts, entries, *extra):
        board_path = self.write("b.kicad_pcb", board(parts))
        table_path = self.write("bodies.yaml", table(entries))
        return self.run_json(footprint_audit.main, "gaps", "--board", board_path, "--bodies", table_path, *extra)

    def pair_gap(self, other, entries=None, *extra):
        """The gap in mm between a Box at the origin and `other` (a footprint string), and the exit status, from the JSON report."""
        status, report = self.gaps_json([footprint("A1", "test:Box", 0, 0), other], entries or dict([BOX, BAR]), *extra)
        self.assertEqual(len(report["pairs"]), 1, report)
        return status, report["pairs"][0]["gap_mm"], report


class BodyGaps(Audit):
    def test_bodies_apart_touching_and_overlapping_are_told_apart_by_the_gap(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C10: Over a synthetic board and a body table, the audit reports the gap between each pair of part bodies from the table's real body dimensions in footprint coordinates, and names any part the table does not hold. A pad-table dump lists each pad of a footprint with its number, position, size and layers. A rotation solver, given a part, a target pad position and the pads' positions, returns the rotation in which the pads land on the target, or states that none does. Tests cover bodies apart, touching and overlapping, a rotated part, a missing table entry, a pad dump of a footprint with a rotated and an unrotated pad, and a rotation that exists and one that does not, in text and in JSON. This does not cover reading the maker's drawings or fetching an assembler's footprints, which are manual steps.
        for x, gap, finding in ((10, 6.0, None), (4, 0.0, "NEAR"), (3, -1.0, "OVERLAP")):
            with self.subTest(x=x):
                status, found, report = self.pair_gap(footprint("A2", "test:Box", x, 0), dict([BOX]))
                self.assertAlmostEqual(found, gap, places=6)
                self.assertEqual(status, 0 if finding is None else 1)
                self.assertEqual([f["finding"] for f in report["findings"]], [finding] if finding else [])
                self.assertEqual(report["result"], "PASS" if finding is None else "FAIL")

    def test_the_text_report_names_each_finding_and_lists_every_gap_on_request(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C10: Over a synthetic board and a body table, the audit reports the gap between each pair of part bodies from the table's real body dimensions in footprint coordinates, and names any part the table does not hold. A pad-table dump lists each pad of a footprint with its number, position, size and layers. A rotation solver, given a part, a target pad position and the pads' positions, returns the rotation in which the pads land on the target, or states that none does. Tests cover bodies apart, touching and overlapping, a rotated part, a missing table entry, a pad dump of a footprint with a rotated and an unrotated pad, and a rotation that exists and one that does not, in text and in JSON. This does not cover reading the maker's drawings or fetching an assembler's footprints, which are manual steps.
        parts = [footprint("A1", "test:Box", 0, 0), footprint("A2", "test:Box", 10, 0), footprint("A3", "test:Box", 3, 9)]
        status, lines = self.gaps(parts, dict([BOX]))
        self.assertEqual(status, 0, lines)
        self.assertEqual(lines, ["BASIS | A1 | maker reading", "BASIS | A2 | maker reading", "BASIS | A3 | maker reading",
                                 "RESULT | PASS | 3 pairs of 3 parts all at least 1 mm apart"])
        status, lines = self.gaps(parts, dict([BOX]), "--all-pairs")
        self.assertIn("GAP | A1 body / A2 body | 6 mm", lines)
        self.assertIn("GAP | A1 body / A3 body | 5 mm", lines)
        status, lines = self.gaps(parts, dict([BOX]), "--min-gap", "6.5")
        self.assertEqual(status, 1)
        self.assertTrue(any(line.startswith("NEAR | A1 body / A2 body | the bodies are 6 mm apart, nearer than 6.5 mm") for line in lines), lines)
        self.assertTrue(lines[-1].startswith("RESULT | FAIL | "), lines)

    def test_a_pair_exactly_at_the_least_gap_passes_and_a_touch_passes_at_zero(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C10: Over a synthetic board and a body table, the audit reports the gap between each pair of part bodies from the table's real body dimensions in footprint coordinates, and names any part the table does not hold. A pad-table dump lists each pad of a footprint with its number, position, size and layers. A rotation solver, given a part, a target pad position and the pads' positions, returns the rotation in which the pads land on the target, or states that none does. Tests cover bodies apart, touching and overlapping, a rotated part, a missing table entry, a pad dump of a footprint with a rotated and an unrotated pad, and a rotation that exists and one that does not, in text and in JSON. This does not cover reading the maker's drawings or fetching an assembler's footprints, which are manual steps.
        parts = [footprint("A1", "test:Box", 0, 0), footprint("A2", "test:Box", 10, 0)]
        self.assertEqual(self.gaps(parts, dict([BOX]), "--min-gap", "6")[0], 0)
        self.assertEqual(self.gaps(parts, dict([BOX]), "--min-gap", "6.001")[0], 1)
        touching = [footprint("A1", "test:Box", 0, 0), footprint("A2", "test:Box", 4, 0)]
        self.assertEqual(self.gaps(touching, dict([BOX]), "--min-gap", "0")[0], 0)
        overlapping = [footprint("A1", "test:Box", 0, 0), footprint("A2", "test:Box", 3, 0)]
        status, lines = self.gaps(overlapping, dict([BOX]), "--min-gap", "0")
        self.assertEqual(status, 1)
        self.assertTrue(lines[0].startswith("OVERLAP | A1 body / A2 body | the bodies overlap by 1 mm"), lines)

    def test_a_part_turned_by_a_multiple_of_ninety_has_its_body_turned_with_it(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C10: Over a synthetic board and a body table, the audit reports the gap between each pair of part bodies from the table's real body dimensions in footprint coordinates, and names any part the table does not hold. A pad-table dump lists each pad of a footprint with its number, position, size and layers. A rotation solver, given a part, a target pad position and the pads' positions, returns the rotation in which the pads land on the target, or states that none does. Tests cover bodies apart, touching and overlapping, a rotated part, a missing table entry, a pad dump of a footprint with a rotated and an unrotated pad, and a rotation that exists and one that does not, in text and in JSON. This does not cover reading the maker's drawings or fetching an assembler's footprints, which are manual steps.
        # A bar lying from x 0 to 10 of its own frame, held 5 mm along from the origin of a box 4 mm square.
        for angle, expected in ((0, 3.0), (90, 2.0), (180, -3.0)):
            with self.subTest(angle=angle):
                _, found, _ = self.pair_gap(footprint("B1", "test:Bar", 5, 0, angle))
                self.assertAlmostEqual(found, expected, places=6)

    def test_a_part_turned_to_another_angle_is_held_as_the_box_around_it(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C10: Over a synthetic board and a body table, the audit reports the gap between each pair of part bodies from the table's real body dimensions in footprint coordinates, and names any part the table does not hold. A pad-table dump lists each pad of a footprint with its number, position, size and layers. A rotation solver, given a part, a target pad position and the pads' positions, returns the rotation in which the pads land on the target, or states that none does. Tests cover bodies apart, touching and overlapping, a rotated part, a missing table entry, a pad dump of a footprint with a rotated and an unrotated pad, and a rotation that exists and one that does not, in text and in JSON. This does not cover reading the maker's drawings or fetching an assembler's footprints, which are manual steps.
        _, found, _ = self.pair_gap(footprint("B1", "test:Bar", 5, 0, 45))
        self.assertAlmostEqual(found, 5 - 1 / math.sqrt(2) - 2, places=5)

    def test_a_part_on_the_back_has_its_body_mirrored(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C10: Over a synthetic board and a body table, the audit reports the gap between each pair of part bodies from the table's real body dimensions in footprint coordinates, and names any part the table does not hold. A pad-table dump lists each pad of a footprint with its number, position, size and layers. A rotation solver, given a part, a target pad position and the pads' positions, returns the rotation in which the pads land on the target, or states that none does. Tests cover bodies apart, touching and overlapping, a rotated part, a missing table entry, a pad dump of a footprint with a rotated and an unrotated pad, and a rotation that exists and one that does not, in text and in JSON. This does not cover reading the maker's drawings or fetching an assembler's footprints, which are manual steps.
        _, front, _ = self.pair_gap(footprint("B1", "test:Bar", 5, 0))
        _, back, _ = self.pair_gap(footprint("B1", "test:Bar", 5, 0, layer="B.Cu"))
        self.assertAlmostEqual(front, 3.0, places=6)
        self.assertAlmostEqual(back, -3.0, places=6)

    def test_a_pair_of_parts_is_as_near_as_the_nearest_of_their_rectangles(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C10: Over a synthetic board and a body table, the audit reports the gap between each pair of part bodies from the table's real body dimensions in footprint coordinates, and names any part the table does not hold. A pad-table dump lists each pad of a footprint with its number, position, size and layers. A rotation solver, given a part, a target pad position and the pads' positions, returns the rotation in which the pads land on the target, or states that none does. Tests cover bodies apart, touching and overlapping, a rotated part, a missing table entry, a pad dump of a footprint with a rotated and an unrotated pad, and a rotation that exists and one that does not, in text and in JSON. This does not cover reading the maker's drawings or fetching an assembler's footprints, which are manual steps.
        entries = {"test:Two": {"rects": [("main", 0, 0, 10, 10), ("tab", 10, 4, 14, 6)]}, BOX[0]: BOX[1]}
        _, found, report = self.pair_gap(footprint("B1", "test:Two", 20, 0), entries)
        # The box ends at x 2; the main rectangle starts at x 20 and the tab at x 30, so the main one is nearer.
        self.assertAlmostEqual(found, 18.0, places=6)
        self.assertEqual((report["pairs"][0]["a_body"], report["pairs"][0]["b_body"]), ("body", "main"))

    def test_a_part_the_table_does_not_hold_is_named_and_fails_the_run(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C10: Over a synthetic board and a body table, the audit reports the gap between each pair of part bodies from the table's real body dimensions in footprint coordinates, and names any part the table does not hold. A pad-table dump lists each pad of a footprint with its number, position, size and layers. A rotation solver, given a part, a target pad position and the pads' positions, returns the rotation in which the pads land on the target, or states that none does. Tests cover bodies apart, touching and overlapping, a rotated part, a missing table entry, a pad dump of a footprint with a rotated and an unrotated pad, and a rotation that exists and one that does not, in text and in JSON. This does not cover reading the maker's drawings or fetching an assembler's footprints, which are manual steps.
        parts = [footprint("A1", "test:Box", 0, 0), footprint("A2", "test:Box", 10, 0), footprint("X1", "test:Unlisted", 30, 0)]
        status, lines = self.gaps(parts, dict([BOX]))
        self.assertEqual(status, 1)
        self.assertEqual(lines[0], "MISSING | X1 | the body table holds no entry for its footprint test:Unlisted, so its body cannot be measured")
        self.assertTrue(lines[-1].startswith("RESULT | FAIL | 1 finding over 1 pair of 2 parts"), lines)
        status, report = self.run_json(footprint_audit.main, "gaps", "--board", self.path("b.kicad_pcb"), "--bodies", self.path("bodies.yaml"))
        self.assertEqual(status, 1)
        self.assertEqual([(f["finding"], f["item"]) for f in report["findings"]], [("MISSING", "X1")])
        self.assertEqual(report["parts_measured"], 2)

    def test_audited_parts_may_be_chosen_by_reference_and_a_reference_not_on_the_board_is_missing(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C10: Over a synthetic board and a body table, the audit reports the gap between each pair of part bodies from the table's real body dimensions in footprint coordinates, and names any part the table does not hold. A pad-table dump lists each pad of a footprint with its number, position, size and layers. A rotation solver, given a part, a target pad position and the pads' positions, returns the rotation in which the pads land on the target, or states that none does. Tests cover bodies apart, touching and overlapping, a rotated part, a missing table entry, a pad dump of a footprint with a rotated and an unrotated pad, and a rotation that exists and one that does not, in text and in JSON. This does not cover reading the maker's drawings or fetching an assembler's footprints, which are manual steps.
        parts = [footprint("A1", "test:Box", 0, 0), footprint("A2", "test:Box", 10, 0), footprint("X1", "test:Unlisted", 30, 0)]
        status, report = self.gaps_json(parts, dict([BOX]), "--ref", "A1", "--ref", "A2")
        self.assertEqual((status, report["parts_measured"], report["findings"]), (0, 2, []))
        status, report = self.gaps_json(parts, dict([BOX]), "--ref", "A1", "--ref", "Z9")
        self.assertEqual(status, 1)
        self.assertEqual([(f["finding"], f["item"]) for f in report["findings"]], [("MISSING", "Z9")])
        self.assertEqual(report["pairs"], [])

    def test_every_measured_part_shows_its_body_basis_in_text_and_json_so_a_courtyard_never_looks_measured(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C10: Over a synthetic board and a body table, the audit reports the gap between each pair of part bodies from the table's real body dimensions in footprint coordinates, and names any part the table does not hold. A pad-table dump lists each pad of a footprint with its number, position, size and layers. A rotation solver, given a part, a target pad position and the pads' positions, returns the rotation in which the pads land on the target, or states that none does. Tests cover bodies apart, touching and overlapping, a rotated part, a missing table entry, a pad dump of a footprint with a rotated and an unrotated pad, and a rotation that exists and one that does not, in text and in JSON. This does not cover reading the maker's drawings or fetching an assembler's footprints, which are manual steps.
        entries = {BOX[0]: BOX[1], "test:Yard": {"courtyard": True}}
        parts = [footprint("A1", "test:Box", 0, 0), footprint("C1", "test:Yard", 10, 0, items=[courtyard(-3, -1, 3, 1)])]
        status, lines = self.gaps(parts, entries)
        self.assertEqual(status, 0, lines)
        self.assertEqual([l for l in lines if l.startswith("BASIS | ")], ["BASIS | A1 | maker reading", "BASIS | C1 | courtyard substitute"])
        self.assertTrue(lines[-1].startswith("RESULT | "), lines)
        status, report = self.gaps_json(parts, entries)
        self.assertEqual(report["basis"], {"A1": "maker reading", "C1": "courtyard substitute"})

    # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C10: Over a synthetic board and a body table, the audit reports the gap between each pair of part bodies from the table's real body dimensions in footprint coordinates, and names any part the table does not hold. A pad-table dump lists each pad of a footprint with its number, position, size and layers. A rotation solver, given a part, a target pad position and the pads' positions, returns the rotation in which the pads land on the target, or states that none does. Tests cover bodies apart, touching and overlapping, a rotated part, a missing table entry, a pad dump of a footprint with a rotated and an unrotated pad, and a rotation that exists and one that does not, in text and in JSON. This does not cover reading the maker's drawings or fetching an assembler's footprints, which are manual steps.
    def test_a_part_carrying_no_reference_is_named_as_unmeasured_and_fails_the_run(self):
        bare = ('(footprint "test:Box" (layer "F.Cu") (uuid "00000000-0000-4000-8000-000000000077") (at 40 2.5)\n\t)')
        parts = [footprint("A1", "test:Box", 0, 0), bare]
        status, lines = self.gaps(parts, dict([BOX]))
        self.assertEqual(status, 1)
        self.assertEqual(lines[0], "UNREFERENCED | test:Box at (40, 2.5) | the part carries no reference, so its body is not measured")
        status, report = self.gaps_json(parts, dict([BOX]))
        self.assertEqual((status, [(f["finding"], f["item"]) for f in report["findings"]]), (1, [("UNREFERENCED", "test:Box at (40, 2.5)")]))
        self.assertEqual(report["parts_measured"], 1)

    def test_a_body_taken_from_the_courtyard_is_measured_in_the_frame_the_board_stores_it(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C10: Over a synthetic board and a body table, the audit reports the gap between each pair of part bodies from the table's real body dimensions in footprint coordinates, and names any part the table does not hold. A pad-table dump lists each pad of a footprint with its number, position, size and layers. A rotation solver, given a part, a target pad position and the pads' positions, returns the rotation in which the pads land on the target, or states that none does. Tests cover bodies apart, touching and overlapping, a rotated part, a missing table entry, a pad dump of a footprint with a rotated and an unrotated pad, and a rotation that exists and one that does not, in text and in JSON. This does not cover reading the maker's drawings or fetching an assembler's footprints, which are manual steps.
        entries = {BOX[0]: BOX[1], "test:Yard": {"courtyard": True}}
        yard = (-3, -1, 3, 1)
        cases = (("F.Cu", "F.CrtYd", 0, (-3, -1, 3, 1), 5.0), ("F.Cu", "F.CrtYd", 90, yard, 7.0), ("B.Cu", "B.CrtYd", 0, (1, -1, 5, 1), 9.0))
        for layer, crtyd, angle, rect, expected in cases:
            with self.subTest(layer=layer, angle=angle):
                part = footprint("C1", "test:Yard", 10, 0, angle, layer, [courtyard(*rect, layer=crtyd)])
                _, found, report = self.pair_gap(part, entries)
                self.assertAlmostEqual(found, expected, places=6)
                self.assertEqual(report["basis"], {"A1": "maker reading", "C1": "courtyard substitute"})

    def test_a_courtyard_body_whose_footprint_draws_no_courtyard_cannot_be_measured(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C10: Over a synthetic board and a body table, the audit reports the gap between each pair of part bodies from the table's real body dimensions in footprint coordinates, and names any part the table does not hold. A pad-table dump lists each pad of a footprint with its number, position, size and layers. A rotation solver, given a part, a target pad position and the pads' positions, returns the rotation in which the pads land on the target, or states that none does. Tests cover bodies apart, touching and overlapping, a rotated part, a missing table entry, a pad dump of a footprint with a rotated and an unrotated pad, and a rotation that exists and one that does not, in text and in JSON. This does not cover reading the maker's drawings or fetching an assembler's footprints, which are manual steps.
        entries = {BOX[0]: BOX[1], "test:Yard": {"courtyard": True}}
        parts = [footprint("A1", "test:Box", 0, 0), footprint("C1", "test:Yard", 10, 0)]
        status, lines = self.gaps(parts, entries)
        self.assertEqual(status, 2)
        status, report = self.run_json(footprint_audit.main, "gaps", "--board", self.path("b.kicad_pcb"), "--bodies", self.path("bodies.yaml"))
        self.assertEqual((status, report["result"]), (2, "CANNOT RUN"))
        self.assertIn("draws none on F.CrtYd", report["detail"])

    def test_access_zones_are_measured_only_when_asked(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C10: Over a synthetic board and a body table, the audit reports the gap between each pair of part bodies from the table's real body dimensions in footprint coordinates, and names any part the table does not hold. A pad-table dump lists each pad of a footprint with its number, position, size and layers. A rotation solver, given a part, a target pad position and the pads' positions, returns the rotation in which the pads land on the target, or states that none does. Tests cover bodies apart, touching and overlapping, a rotated part, a missing table entry, a pad dump of a footprint with a rotated and an unrotated pad, and a rotation that exists and one that does not, in text and in JSON. This does not cover reading the maker's drawings or fetching an assembler's footprints, which are manual steps.
        entries = {"test:Hand": {"rects": [("body", -2, -2, 2, 2)], "zones": [("reach", 2, -2, 8, 2)]}}
        parts = [footprint("A1", "test:Hand", 0, 0), footprint("A2", "test:Hand", 10, 0)]
        self.assertEqual(self.gaps(parts, entries)[0], 0)
        status, lines = self.gaps(parts, entries, "--access-zones")
        self.assertEqual(status, 1)
        self.assertTrue(lines[0].startswith("NEAR | A1 access reach / A2 body | the bodies touch, nearer than 1 mm"), lines)

    def test_a_board_with_no_parts_passes_with_nothing_measured(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C10: Over a synthetic board and a body table, the audit reports the gap between each pair of part bodies from the table's real body dimensions in footprint coordinates, and names any part the table does not hold. A pad-table dump lists each pad of a footprint with its number, position, size and layers. A rotation solver, given a part, a target pad position and the pads' positions, returns the rotation in which the pads land on the target, or states that none does. Tests cover bodies apart, touching and overlapping, a rotated part, a missing table entry, a pad dump of a footprint with a rotated and an unrotated pad, and a rotation that exists and one that does not, in text and in JSON. This does not cover reading the maker's drawings or fetching an assembler's footprints, which are manual steps.
        status, lines = self.gaps([], dict([BOX]))
        self.assertEqual((status, lines), (0, ["RESULT | PASS | 0 pairs of 0 parts all at least 1 mm apart"]))
        status, report = self.gaps_json([], dict([BOX]))
        self.assertEqual((status, report["pairs"], report["parts_measured"]), (0, [], 0))

    def test_a_table_or_board_that_cannot_be_read_stops_the_run_naming_what_is_wrong(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C10: Over a synthetic board and a body table, the audit reports the gap between each pair of part bodies from the table's real body dimensions in footprint coordinates, and names any part the table does not hold. A pad-table dump lists each pad of a footprint with its number, position, size and layers. A rotation solver, given a part, a target pad position and the pads' positions, returns the rotation in which the pads land on the target, or states that none does. Tests cover bodies apart, touching and overlapping, a rotated part, a missing table entry, a pad dump of a footprint with a rotated and an unrotated pad, and a rotation that exists and one that does not, in text and in JSON. This does not cover reading the maker's drawings or fetching an assembler's footprints, which are manual steps.
        parts = [footprint("A1", "test:Box", 0, 0)]
        board_path = self.write("b.kicad_pcb", board(parts))
        rect = "{name: body, x0: -2, y0: -2, x1: 2, y1: 2}"
        bad = {
            "not yaml": ("footprints: [unclosed", "cannot be read"),
            "no mapping": ("- a\n- b\n", "no `footprints:` mapping"),
            "empty rects": ('footprints:\n  "test:Box": {kind: x}\n', "holds no body"),
            "both": (f'footprints:\n  "test:Box": {{from: courtyard, rects: [{rect}]}}\n', "give one"),
            "other source": ('footprints:\n  "test:Box": {from: fab}\n', "only source a body may be taken from is courtyard"),
            "unknown key": (f'footprints:\n  "test:Box": {{rects: [{rect}], colour: red}}\n', "colour"),
            "no area": ('footprints:\n  "test:Box": {rects: [{name: body, x0: 2, y0: -2, x1: 2, y1: 2}]}\n', "has no area"),
            "missing corner": ('footprints:\n  "test:Box": {rects: [{name: body, x0: 0, y0: 0, x1: 2}]}\n', "lacks y1"),
            "not a number": ('footprints:\n  "test:Box": {rects: [{name: body, x0: wide, y0: 0, x1: 2, y1: 2}]}\n', "not a number"),
            "not a mapping": ('footprints:\n  "test:Box": [1]\n', "is not a mapping"),
        }
        for name, (text, expected) in bad.items():
            with self.subTest(table=name):
                path = self.write("t.yaml", text)
                status, report = self.run_json(footprint_audit.main, "gaps", "--board", board_path, "--bodies", path)
                self.assertEqual((status, report["result"]), (2, "CANNOT RUN"), report)
                self.assertIn(expected, report["detail"])
                err = io.StringIO()
                with contextlib.redirect_stderr(err):
                    status, lines = self.run_tool(footprint_audit.main, "gaps", "--board", board_path, "--bodies", path)
                self.assertEqual((status, lines), (2, []))
                self.assertIn("CANNOT RUN | ", err.getvalue())
        good = self.write("good.yaml", table(dict([BOX])))
        for label, path, argv in (("board missing", self.path("gone.kicad_pcb"), ()), ("board not a layout", self.write("x.kicad_pcb", "(kicad_sch)\n"), ()),
                                  ("board unbalanced", self.write("y.kicad_pcb", "(kicad_pcb (a"), ()), ("table missing", board_path, ())):
            with self.subTest(case=label):
                args = ["gaps", "--board", path, "--bodies", self.path("none.yaml") if label == "table missing" else good]
                status, report = self.run_json(footprint_audit.main, *args)
                self.assertEqual((status, report["result"]), (2, "CANNOT RUN"))
                self.assertIn(self.path("none.yaml") if label == "table missing" else path, report["detail"])
        status, report = self.run_json(footprint_audit.main, "gaps", "--board", board_path, "--bodies", good, "--min-gap", "-1")
        self.assertEqual((status, report["result"]), (2, "CANNOT RUN"))
        self.assertIn("--min-gap", report["detail"])

    def test_a_missing_yaml_package_is_named(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C12: Each tracked layout tool that needs KiCad's scripting interface runs it in the interpreter named by a documented environment variable, and the tool and its tests fail naming that variable when it is unset or names nothing runnable. The silkscreen command names the missing package when numpy, shapely or Pillow is not installed. No tool holds a path fixed to one machine: every tool, interpreter and board path is an argument or an environment variable. Tests cover the variable unset, the variable naming a missing file, a missing package and a path given as an argument, in text and in JSON.
        board_path = self.write("b.kicad_pcb", board([]))
        table_path = self.write("t.yaml", table(dict([BOX])))
        real = builtins.__import__

        def refuse(name, *args, **kwargs):
            if name == "yaml":
                raise ImportError("No module named 'yaml'")
            return real(name, *args, **kwargs)

        with mock.patch.object(builtins, "__import__", refuse):
            status, report = self.run_json(footprint_audit.main, "gaps", "--board", board_path, "--bodies", table_path)
        self.assertEqual((status, report["result"]), (2, "CANNOT RUN"))
        self.assertIn("pyyaml", report["detail"])


class PadDump(Audit):
    def part(self):
        # A footprint turned a quarter turn: pad 1 carries the footprint's turn as KiCad writes it, pad 2 is written with no angle.
        return footprint("P1", "test:Pads", 10, 20, 90, items=[
            pad("1", 2, 0, 90, size=(1.6, 1.0), shape="rect", drill="0.8"),
            pad("2", 0, 3, None, size=(1.2, 1.2), kind="smd", shape="circle", drill=None, layers='"F.Cu" "F.Mask"')])

    def test_each_pad_is_listed_with_its_number_position_size_and_layers(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C10: Over a synthetic board and a body table, the audit reports the gap between each pair of part bodies from the table's real body dimensions in footprint coordinates, and names any part the table does not hold. A pad-table dump lists each pad of a footprint with its number, position, size and layers. A rotation solver, given a part, a target pad position and the pads' positions, returns the rotation in which the pads land on the target, or states that none does. Tests cover bodies apart, touching and overlapping, a rotated part, a missing table entry, a pad dump of a footprint with a rotated and an unrotated pad, and a rotation that exists and one that does not, in text and in JSON. This does not cover reading the maker's drawings or fetching an assembler's footprints, which are manual steps.
        path = self.write("b.kicad_pcb", board([self.part()]))
        status, report = self.run_json(footprint_audit.main, "pads", "--board", path, "P1")
        self.assertEqual(status, 0)
        item = report["parts"][0]
        self.assertEqual((item["reference"], item["footprint"], item["x"], item["y"], item["angle"], item["layer"]),
                         ("P1", "test:Pads", 10.0, 20.0, 90.0, "F.Cu"))
        rotated, plain = item["pads"]
        self.assertEqual((rotated["number"], rotated["type"], rotated["shape"], rotated["x"], rotated["y"], rotated["width"], rotated["height"],
                          rotated["angle"], rotated["layers"], rotated["drill"]),
                         ("1", "thru_hole", "rect", 2.0, 0.0, 1.6, 1.0, 90.0, ["*.Cu", "*.Mask"], "0.8"))
        self.assertAlmostEqual(rotated["board_x"], 10.0, places=6)
        self.assertAlmostEqual(rotated["board_y"], 18.0, places=6)
        self.assertEqual((plain["number"], plain["type"], plain["shape"], plain["angle"], plain["layers"], plain["drill"]),
                         ("2", "smd", "circle", 0.0, ["F.Cu", "F.Mask"], None))
        self.assertAlmostEqual(plain["board_x"], 13.0, places=6)
        self.assertAlmostEqual(plain["board_y"], 20.0, places=6)

    def test_the_text_dump_has_one_line_a_pad(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C10: Over a synthetic board and a body table, the audit reports the gap between each pair of part bodies from the table's real body dimensions in footprint coordinates, and names any part the table does not hold. A pad-table dump lists each pad of a footprint with its number, position, size and layers. A rotation solver, given a part, a target pad position and the pads' positions, returns the rotation in which the pads land on the target, or states that none does. Tests cover bodies apart, touching and overlapping, a rotated part, a missing table entry, a pad dump of a footprint with a rotated and an unrotated pad, and a rotation that exists and one that does not, in text and in JSON. This does not cover reading the maker's drawings or fetching an assembler's footprints, which are manual steps.
        path = self.write("b.kicad_pcb", board([self.part(), footprint("P2", "test:Empty", 0, 0)]))
        status, lines = self.run_tool(footprint_audit.main, "pads", "--board", path, "P1", "P2")
        self.assertEqual(status, 0, lines)
        self.assertEqual(lines, [
            "PART | P1 | test:Pads at 10 20 turn 90 on F.Cu",
            "PAD | P1 1 | thru_hole rect at 2 0 size 1.6x1 angle 90 layers *.Cu,*.Mask drill 0.8 board 10 18",
            "PAD | P1 2 | smd circle at 0 3 size 1.2x1.2 angle 0 layers F.Cu,F.Mask board 13 20",
            "PART | P2 | test:Empty at 0 0 turn 0 on F.Cu",
            "RESULT | PASS | 2 pads of 2 parts"])

    def test_a_part_not_on_the_board_is_named_and_the_others_still_listed(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C10: Over a synthetic board and a body table, the audit reports the gap between each pair of part bodies from the table's real body dimensions in footprint coordinates, and names any part the table does not hold. A pad-table dump lists each pad of a footprint with its number, position, size and layers. A rotation solver, given a part, a target pad position and the pads' positions, returns the rotation in which the pads land on the target, or states that none does. Tests cover bodies apart, touching and overlapping, a rotated part, a missing table entry, a pad dump of a footprint with a rotated and an unrotated pad, and a rotation that exists and one that does not, in text and in JSON. This does not cover reading the maker's drawings or fetching an assembler's footprints, which are manual steps.
        path = self.write("b.kicad_pcb", board([self.part()]))
        status, lines = self.run_tool(footprint_audit.main, "pads", "--board", path, "P1", "Q9")
        self.assertEqual(status, 1)
        self.assertIn("MISSING | Q9 | the board carries no part Q9", lines)
        self.assertEqual(lines[-1], "RESULT | FAIL | 1 part not on the board")
        status, report = self.run_json(footprint_audit.main, "pads", "--board", path, "P1", "Q9")
        self.assertEqual((status, len(report["parts"]), report["findings"][0]["item"]), (1, 1, "Q9"))

    def test_a_pad_with_no_size_stops_the_run(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C10: Over a synthetic board and a body table, the audit reports the gap between each pair of part bodies from the table's real body dimensions in footprint coordinates, and names any part the table does not hold. A pad-table dump lists each pad of a footprint with its number, position, size and layers. A rotation solver, given a part, a target pad position and the pads' positions, returns the rotation in which the pads land on the target, or states that none does. Tests cover bodies apart, touching and overlapping, a rotated part, a missing table entry, a pad dump of a footprint with a rotated and an unrotated pad, and a rotation that exists and one that does not, in text and in JSON. This does not cover reading the maker's drawings or fetching an assembler's footprints, which are manual steps.
        bad = footprint("P1", "test:Pads", 0, 0, items=['(pad "1" smd rect (at 0 0) (layers "F.Cu"))'])
        path = self.write("b.kicad_pcb", board([bad]))
        status, report = self.run_json(footprint_audit.main, "pads", "--board", path, "P1")
        self.assertEqual((status, report["result"]), (2, "CANNOT RUN"))
        self.assertIn("no (size", report["detail"])


class RotationSolver(Audit):
    def part(self, items=None, x=30, y=30):
        return footprint("R1", "test:Two", x, y, items=items or [pad("1", 5, 0), pad("2", 0, 5)])

    def solve(self, *argv, parts=None):
        path = self.write("b.kicad_pcb", board(parts or [self.part()]))
        return self.run_json(footprint_audit.main, "rotation", "--board", path, "--ref", "R1", *argv)

    def test_a_rotation_that_lands_the_pads_is_returned(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C10: Over a synthetic board and a body table, the audit reports the gap between each pair of part bodies from the table's real body dimensions in footprint coordinates, and names any part the table does not hold. A pad-table dump lists each pad of a footprint with its number, position, size and layers. A rotation solver, given a part, a target pad position and the pads' positions, returns the rotation in which the pads land on the target, or states that none does. Tests cover bodies apart, touching and overlapping, a rotated part, a missing table entry, a pad dump of a footprint with a rotated and an unrotated pad, and a rotation that exists and one that does not, in text and in JSON. This does not cover reading the maker's drawings or fetching an assembler's footprints, which are manual steps.
        status, report = self.solve("--pad", "1=30,35", "--pad", "2=25,30")
        self.assertEqual((status, report["exists"], report["rotations"], report["result"]), (0, True, [270.0], "PASS"))
        self.assertEqual(report["origin"], [30.0, 30.0])
        path = self.path("b.kicad_pcb")
        status, lines = self.run_tool(footprint_audit.main, "rotation", "--board", path, "--ref", "R1", "--pad", "1=30,35", "--pad", "2=25,30")
        self.assertEqual(status, 0)
        self.assertEqual(lines, ["ROTATION | R1 | 270 degrees", "RESULT | PASS | R1 lands on its targets at 270 degrees"])

    def test_pads_that_no_rotation_can_land_are_reported_as_such(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C10: Over a synthetic board and a body table, the audit reports the gap between each pair of part bodies from the table's real body dimensions in footprint coordinates, and names any part the table does not hold. A pad-table dump lists each pad of a footprint with its number, position, size and layers. A rotation solver, given a part, a target pad position and the pads' positions, returns the rotation in which the pads land on the target, or states that none does. Tests cover bodies apart, touching and overlapping, a rotated part, a missing table entry, a pad dump of a footprint with a rotated and an unrotated pad, and a rotation that exists and one that does not, in text and in JSON. This does not cover reading the maker's drawings or fetching an assembler's footprints, which are manual steps.
        # Pad 1 at (30,35) needs a quarter turn one way, and pad 2 at (35,30) the mirror image of where that puts it.
        status, report = self.solve("--pad", "1=30,35", "--pad", "2=35,30")
        self.assertEqual((status, report["exists"], report["rotations"], report["result"]), (1, False, [], "FAIL"))
        self.assertEqual(len(report["candidates"]), 4)
        self.assertTrue(all(not c["lands"] and c["worst_miss_mm"] > 1 for c in report["candidates"]))
        status, lines = self.run_tool(footprint_audit.main, "rotation", "--board", self.path("b.kicad_pcb"), "--ref", "R1",
                                      "--pad", "1=30,35", "--pad", "2=35,30")
        self.assertEqual(status, 1)
        self.assertEqual(len(lines), 1)
        self.assertTrue(lines[0].startswith("RESULT | FAIL | no turn in steps of 90 degrees lands the pads within 0.01 mm of their targets; nearest is "), lines)

    def test_every_rotation_that_lands_is_returned_when_there_are_several(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C10: Over a synthetic board and a body table, the audit reports the gap between each pair of part bodies from the table's real body dimensions in footprint coordinates, and names any part the table does not hold. A pad-table dump lists each pad of a footprint with its number, position, size and layers. A rotation solver, given a part, a target pad position and the pads' positions, returns the rotation in which the pads land on the target, or states that none does. Tests cover bodies apart, touching and overlapping, a rotated part, a missing table entry, a pad dump of a footprint with a rotated and an unrotated pad, and a rotation that exists and one that does not, in text and in JSON. This does not cover reading the maker's drawings or fetching an assembler's footprints, which are manual steps.
        centred = [self.part([pad("1", 0, 0)])]
        status, report = self.solve("--pad", "1=30,30", parts=centred)
        self.assertEqual((status, report["rotations"]), (0, [0.0, 90.0, 180.0, 270.0]))
        twin = [self.part([pad("1", 5, 0), pad("1", -5, 0)])]
        status, report = self.solve("--pad", "1=30,25", parts=twin)
        self.assertEqual((status, report["rotations"]), (0, [90.0, 270.0]))

    def test_the_step_and_tolerance_decide_which_turns_are_tried_and_how_near_counts(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C10: Over a synthetic board and a body table, the audit reports the gap between each pair of part bodies from the table's real body dimensions in footprint coordinates, and names any part the table does not hold. A pad-table dump lists each pad of a footprint with its number, position, size and layers. A rotation solver, given a part, a target pad position and the pads' positions, returns the rotation in which the pads land on the target, or states that none does. Tests cover bodies apart, touching and overlapping, a rotated part, a missing table entry, a pad dump of a footprint with a rotated and an unrotated pad, and a rotation that exists and one that does not, in text and in JSON. This does not cover reading the maker's drawings or fetching an assembler's footprints, which are manual steps.
        target = f"1={30 + 5 * math.cos(math.radians(45)):.6f},{30 - 5 * math.sin(math.radians(45)):.6f}"
        self.assertEqual(self.solve("--pad", target)[1]["rotations"], [])
        status, report = self.solve("--pad", target, "--step", "45")
        self.assertEqual((status, report["rotations"], len(report["candidates"])), (0, [45.0], 8))
        self.assertEqual(self.solve("--pad", "1=30.05,35")[1]["rotations"], [])
        self.assertEqual(self.solve("--pad", "1=30.05,35", "--tolerance", "0.1")[1]["rotations"], [270.0])

    def test_the_origin_may_be_held_elsewhere_than_the_part(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C10: Over a synthetic board and a body table, the audit reports the gap between each pair of part bodies from the table's real body dimensions in footprint coordinates, and names any part the table does not hold. A pad-table dump lists each pad of a footprint with its number, position, size and layers. A rotation solver, given a part, a target pad position and the pads' positions, returns the rotation in which the pads land on the target, or states that none does. Tests cover bodies apart, touching and overlapping, a rotated part, a missing table entry, a pad dump of a footprint with a rotated and an unrotated pad, and a rotation that exists and one that does not, in text and in JSON. This does not cover reading the maker's drawings or fetching an assembler's footprints, which are manual steps.
        status, report = self.solve("--pad", "1=50,55", "--origin", "50,50")
        self.assertEqual((status, report["rotations"], report["origin"]), (0, [270.0], [50.0, 50.0]))
        self.assertEqual(self.solve("--pad", "1=50,55")[1]["rotations"], [])

    def test_a_part_or_pad_that_is_not_there_is_named(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C10: Over a synthetic board and a body table, the audit reports the gap between each pair of part bodies from the table's real body dimensions in footprint coordinates, and names any part the table does not hold. A pad-table dump lists each pad of a footprint with its number, position, size and layers. A rotation solver, given a part, a target pad position and the pads' positions, returns the rotation in which the pads land on the target, or states that none does. Tests cover bodies apart, touching and overlapping, a rotated part, a missing table entry, a pad dump of a footprint with a rotated and an unrotated pad, and a rotation that exists and one that does not, in text and in JSON. This does not cover reading the maker's drawings or fetching an assembler's footprints, which are manual steps.
        path = self.write("b.kicad_pcb", board([self.part()]))
        status, report = self.run_json(footprint_audit.main, "rotation", "--board", path, "--ref", "Q1", "--pad", "1=0,0")
        self.assertEqual((status, report["exists"], report["findings"][0]["finding"]), (1, False, "MISSING"))
        status, lines = self.run_tool(footprint_audit.main, "rotation", "--board", path, "--ref", "R1", "--pad", "9=0,0")
        self.assertEqual(status, 1)
        self.assertEqual(lines[0], "MISSING | R1 pad 9 | the footprint has no pad of this number")

    def test_arguments_that_cannot_be_acted_on_stop_the_run(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C10: Over a synthetic board and a body table, the audit reports the gap between each pair of part bodies from the table's real body dimensions in footprint coordinates, and names any part the table does not hold. A pad-table dump lists each pad of a footprint with its number, position, size and layers. A rotation solver, given a part, a target pad position and the pads' positions, returns the rotation in which the pads land on the target, or states that none does. Tests cover bodies apart, touching and overlapping, a rotated part, a missing table entry, a pad dump of a footprint with a rotated and an unrotated pad, and a rotation that exists and one that does not, in text and in JSON. This does not cover reading the maker's drawings or fetching an assembler's footprints, which are manual steps.
        cases = (((), "at least one --pad"), (("--pad", "1"), "NUMBER=X,Y"), (("--pad", "1=3"), "NUMBER=X,Y"),
                 (("--pad", "1=a,b"), "NUMBER=X,Y"), (("--pad", "=1,2"), "NUMBER=X,Y"), (("--pad", "1=0,0", "--step", "0"), "--step"),
                 (("--pad", "1=0,0", "--step", "400"), "--step"), (("--pad", "1=0,0", "--tolerance", "-1"), "--tolerance"),
                 (("--pad", "1=0,0", "--origin", "5"), "--origin"))
        self.write("b.kicad_pcb", board([self.part()]))
        for argv, expected in cases:
            with self.subTest(argv=argv):
                status, report = self.solve(*argv)
                self.assertEqual((status, report["result"]), (2, "CANNOT RUN"))
                self.assertIn(expected, report["detail"])


class CommandLine(Work):
    def test_the_commands_run_as_scripts_with_paths_given_as_arguments(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C12: Each tracked layout tool that needs KiCad's scripting interface runs it in the interpreter named by a documented environment variable, and the tool and its tests fail naming that variable when it is unset or names nothing runnable. The silkscreen command names the missing package when numpy, shapely or Pillow is not installed. No tool holds a path fixed to one machine: every tool, interpreter and board path is an argument or an environment variable. Tests cover the variable unset, the variable naming a missing file, a missing package and a path given as an argument, in text and in JSON.
        board_path = self.write("any/place/b.kicad_pcb", board([footprint("A1", "test:Box", 0, 0), footprint("A2", "test:Box", 3, 0)]))
        table_path = self.write("elsewhere/bodies.yaml", table(dict([BOX])))
        env = {k: v for k, v in os.environ.items() if k not in ("KICAD_PYTHON", "KICAD_CLI")}
        done = subprocess.run([sys.executable, os.path.join(TOOLS, "footprint_audit.py"), "gaps", "--board", board_path, "--bodies", table_path,
                               "--format", "json"], capture_output=True, text=True, env=env, timeout=120)
        self.assertEqual(done.returncode, 1, done.stderr)
        self.assertEqual(json.loads(done.stdout)["findings"][0]["finding"], "OVERLAP")
        done = subprocess.run([sys.executable, os.path.join(TOOLS, "footprint_audit.py"), "gaps", "--board", self.path("none.kicad_pcb"),
                               "--bodies", table_path], capture_output=True, text=True, env=env, timeout=120)
        self.assertEqual(done.returncode, 2)
        self.assertIn(f"CANNOT RUN | the board {self.path('none.kicad_pcb')} cannot be read", done.stderr)

    def test_the_tool_holds_no_path_fixed_to_one_machine_and_needs_no_kicad(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C12: Each tracked layout tool that needs KiCad's scripting interface runs it in the interpreter named by a documented environment variable, and the tool and its tests fail naming that variable when it is unset or names nothing runnable. The silkscreen command names the missing package when numpy, shapely or Pillow is not installed. No tool holds a path fixed to one machine: every tool, interpreter and board path is an argument or an environment variable. Tests cover the variable unset, the variable naming a missing file, a missing package and a path given as an argument, in text and in JSON.
        fixed = re.compile(r"(/Users/|/home/[a-z]|/Applications/|/opt/homebrew|/usr/local/|/Library/|[A-Za-z]:\\|\bProgram Files\b)")
        with open(os.path.join(TOOLS, "footprint_audit.py"), encoding="utf-8") as handle:
            text = handle.read()
        self.assertEqual([line for line in text.splitlines() if fixed.search(line)], [])
        self.assertNotIn("pcbnew", text.replace("which needs no KiCad", ""))
        self.assertNotIn("subprocess", text)


class TheBodyTableOfTheMainBoard(unittest.TestCase):
    def test_the_committed_table_reads_and_every_entry_says_where_its_body_comes_from(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C10: Over a synthetic board and a body table, the audit reports the gap between each pair of part bodies from the table's real body dimensions in footprint coordinates, and names any part the table does not hold. A pad-table dump lists each pad of a footprint with its number, position, size and layers. A rotation solver, given a part, a target pad position and the pads' positions, returns the rotation in which the pads land on the target, or states that none does. Tests cover bodies apart, touching and overlapping, a rotated part, a missing table entry, a pad dump of a footprint with a rotated and an unrotated pad, and a rotation that exists and one that does not, in text and in JSON. This does not cover reading the maker's drawings or fetching an assembler's footprints, which are manual steps.
        found = footprint_audit.read_table(os.path.join(HARDWARE, "sunbeam-em7000", "main-board", "part-bodies.yaml"))
        self.assertTrue(found)
        for name, entry in found.items():
            with self.subTest(footprint=name):
                self.assertTrue(entry.courtyard or entry.rects)
                self.assertTrue(entry.source, "each entry names the maker reading it comes from, or says it is the courtyard")


    def test_the_relay_fuse_and_varistor_carry_the_makers_body_with_a_cited_page_and_sit_where_their_pads_put_them(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C10: Over a synthetic board and a body table, the audit reports the gap between each pair of part bodies from the table's real body dimensions in footprint coordinates, and names any part the table does not hold. A pad-table dump lists each pad of a footprint with its number, position, size and layers. A rotation solver, given a part, a target pad position and the pads' positions, returns the rotation in which the pads land on the target, or states that none does. Tests cover bodies apart, touching and overlapping, a rotated part, a missing table entry, a pad dump of a footprint with a rotated and an unrotated pad, and a rotation that exists and one that does not, in text and in JSON. This does not cover reading the maker's drawings or fetching an assembler's footprints, which are manual steps.
        found = footprint_audit.read_table(os.path.join(HARDWARE, "sunbeam-em7000", "main-board", "part-bodies.yaml"))
        pads = {"main-board:Relay_HF115F-I_1HS3A": [(0, 0), (0, 7.56), (20.16, 0), (20.16, 7.56), (25.2, 0), (25.2, 7.56)],
                "main-board:RV_Disc_14D471K_P7.5mm": [(0, 0), (7.5, 0)]}
        for name, points in pads.items():
            with self.subTest(footprint=name):
                entry = found[name]
                self.assertFalse(entry.courtyard, "a maker reading, not the courtyard")
                self.assertRegex(entry.source, r"p\.\d")
                for x, y in points:
                    self.assertTrue(any(x0 <= x <= x1 and y0 <= y <= y1 for _n, (x0, y0, x1, y1), _h in entry.rects), (x, y))
        fuse = found["main-board:Fuse_SETfuse_SCT520PT_Axial_P28.0mm"]
        self.assertFalse(fuse.courtyard)
        self.assertRegex(fuse.source, r"p\.\d")
        (_n, (x0, y0, x1, y1), _h), = fuse.rects
        self.assertTrue(0 < x0 < x1 < 28 and y0 < 0 < y1, "an axial cartridge lies between its two lead pads")
        self.assertAlmostEqual(x1 - x0, 20.5, places=6)


if __name__ == "__main__":
    unittest.main()
