#!/usr/bin/env python3
"""The pre-order check against KiCad itself, on the throwaway proof design, here the workmanship rules and how a track meets a pad.

This is one of the files the check's KiCad tests are divided into by topic; the
shared setup, the seeded-fault proof's pooled outcomes and the exclusion of what
needs that proof are in board_kicad_fixtures.py.
"""

from __future__ import annotations

import os
import sys


TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)

import board_check  # noqa: E402
import board_geometry  # noqa: E402
import board_prove  # noqa: E402
import sexpr  # noqa: E402
from board_kicad_fixtures import load_tests, setUpModule  # noqa: E402,F401
from board_kicad_fixtures import Copy, Proved, outcomes  # noqa: E402



class TheWorkmanshipRules(Proved):
    # SOL-BOARD-LAYOUT-WORKMANSHIP-ITEMS.C2: The pre-order check measures every rule-kind workmanship item and fails a board that breaks one
    """Each rule, KiCad's and measured alike, fails on a fault seeded for it in a
    throwaway copy of the gate's proof design outside the repository, and the
    clean copy passes with every rule in force.
    """

    def test_every_workmanship_rule_fails_on_its_seeded_fault(self):
        workmanship = [fault[0] for fault in board_prove.FAULTS if fault[1].startswith("workmanship:")]
        self.assertCaught(*workmanship)
        rules = {fault[2] for fault in board_prove.FAULTS if fault[1].startswith("workmanship:")}
        # Every KiCad check a workmanship item rests on, every measured rule, and the figures and rules the design must carry.
        self.assertGreaterEqual(rules, {"track_angle", "track_segment_length", "track_dangling", "via_dangling", "workmanship_pad_corner",
                                        "workmanship_detour", "workmanship_direction", "workmanship_pad_entry",
                                        "workmanship_width", "workmanship_pad_copper", "workmanship_rule", "workmanship_figure"})

    def test_each_kicad_finding_and_measured_failure_names_the_item(self):
        found = outcomes()
        for name, item in (("a right-angled corner", "WORK-4"), ("a short jog", "WORK-5"), ("an unneeded via", "WORK-7"),
                           ("a short stub", "WORK-6"), ("a route wandering the long way round", "WORK-2"),
                           ("a route narrowed partway along", "WORK-8"),
                           ("a track off the board's edges and the 45 degrees to them", "WORK-9"),
                           ("a track entering a long pad from its side", "WORK-10")):
            with self.subTest(fault=name):
                caught, line = found[name]
                self.assertTrue(caught, line)
                self.assertIn(item, line)
                self.assertRegex(line.split(" | ")[3], r"\(\d+(\.\d+)?, \d+(\.\d+)?\) mm", "a failure names where on the board it is")



class KiCadComparesTracksEverywhereButAtAPad(Copy):
    # SOL-BOARD-LAYOUT-WORKMANSHIP-ITEMS.C2: The pre-order check measures every rule-kind workmanship item and fails a board that breaks one
    """The method tells a designer to branch a route at a pad because KiCad's
    corner rule compares every two tracks meeting on one layer anywhere else;
    this holds that to what the installed KiCad does.
    """

    def test_a_branch_at_a_pad_passes_and_one_off_a_track_or_a_via_fails(self):
        at_pad = board_prove.reroute("/LV_A", (board_prove.LV_A_ENDS,), [(40, 10), (45, 10), (45, 7)])
        at_pad(self.seed)
        drc = self.drc()
        self.assertFalse([v for v in drc["violations"] if v["type"] == "track_angle"], drc["violations"])
        self.setUp()
        board_prove.reroute("/LV_A", (board_prove.LV_A_ENDS,), [(40, 10), (42, 10), (45, 10)])(self.seed)
        self.seed.layout(lambda tree: tree.insert(len(tree) - 1, board_prove.segment("/LV_A", 42, 10, 42, 6, "0b0e5c1a-0000-4000-8000-0000000002ff")))
        angles = [v for v in self.drc()["violations"] if v["type"] == "track_angle"]
        self.assertTrue(angles, "a branch off the middle of a route is compared with each side of it")
        self.assertIn("actual 90.000", angles[0]["description"])



class KiCadReportsATrackEndingFreeUnaided(Copy):
    # SOL-BOARD-LAYOUT-WORKMANSHIP-ITEMS.C2: The pre-order check measures every rule-kind workmanship item and fails a board that breaks one
    """The stub item rests on KiCad's own unconnected-track-end check, with no
    rule and no figure of the check's own, so this holds that to what the
    installed KiCad does for a stub wherever it leaves the route, and to the
    check failing the design on it.
    """

    def test_a_stub_off_a_pad_off_a_track_or_lying_loose_is_reported_and_fails_the_design(self):
        stubs = {
            "off a pad": [("/LV_A", 45, 10, 45, 8.5)],
            "off the middle of a track": [("/LV_A", 42, 10, 42, 8.5)],
            "lying loose": [("/LV_A", 47, 6, 49, 6)],
        }
        for where, tracks in stubs.items():
            with self.subTest(stub=where):
                self.setUp()
                self.seed.layout(lambda tree: [tree.insert(len(tree) - 1, board_prove.segment(*track, f"0b0e5c1a-0000-4000-8000-0000000005{index:02d}"))
                                               for index, track in enumerate(tracks)])
                if where == "off the middle of a track":
                    board_prove.reroute("/LV_A", (board_prove.LV_A_ENDS,), [(40, 10), (42, 10), (45, 10)])(self.seed)
                dangling = [v for v in self.drc()["violations"] if v["type"] == "track_dangling"]
                self.assertTrue(dangling, f"KiCad reports no stub {where}")
                status, lines = self.check()
                self.assertEqual(status, 1, lines)
                self.assertTrue([line for line in lines if " | track_dangling | " in line and "workmanship item WORK-6" in line], lines)



class TheCheckReadsATrackMeetingAPadAsKiCadDoes(Copy):
    # SOL-BOARD-LAYOUT-WORKMANSHIP-ITEMS.C2: The pre-order check measures every rule-kind workmanship item and fails a board that breaks one
    """Every measure that asks whether a track meets a pad rests on
    board_geometry's contact rule, so this holds that rule to the installed
    KiCad's own connectivity: /LV_A is redrawn as one track meeting R2's
    1.6 mm round pad 1 just so or just missing it, and the rule must join the
    two exactly when KiCad reports no unconnected item between them.
    """

    CASES = (
        ("an end cap reaching the pad's edge by 0.025 mm", [(40, 10), (44.1, 10)], True),
        ("an end cap stopping 0.025 mm short of it", [(40, 10), (44.05, 10)], False),
        ("copper running over the pad 0.025 mm deep, off its centre, neither end on it", [(40, 10.9), (48, 10.9)], True),
        ("copper running past the pad 0.025 mm clear of it", [(40, 10.95), (48, 10.95)], False),
    )

    def test_the_contact_rule_joins_a_track_to_a_pad_exactly_when_kicad_does(self):
        for what, points, joined in self.CASES:
            with self.subTest(track=what):
                self.setUp()
                board_prove.reroute("/LV_A", (board_prove.LV_A_ENDS,), points)(self.seed)
                report = self.drc()
                kicad = not any("pad 1 [/LV_A] of R2" in item["description"]
                                for unconnected in report["unconnected_items"] for item in unconnected["items"])
                self.assertEqual(kicad, joined, f"KiCad was expected {'to join' if joined else 'not to join'} {what}")
                layout = board_check.Layout(sexpr.parse_one(self.seed.read(".kicad_pcb")))
                pad = next(pad for pad in layout.pads if pad.name() == "pad 1 of R2")
                ours = any(board_geometry.joins(pad, copper.points(), copper.width) for copper in layout.copper if copper.net == "/LV_A")
                self.assertEqual(ours, kicad, f"the contact rule and KiCad disagree on {what}")
