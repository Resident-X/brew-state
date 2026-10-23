#!/usr/bin/env python3
"""The pre-order check against KiCad itself, on the throwaway proof design, here the connectivity check, the separation floor and the mounting holes: the floor part.

One of the files the original test file is divided into by topic; the tests are unchanged and only live elsewhere.
"""

from __future__ import annotations

import io
import os
import sys
import unittest
from unittest import mock

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import board_check  # noqa: E402
import board_prove  # noqa: E402
from board_kicad_fixtures import load_tests, setUpModule  # noqa: E402,F401
from board_kicad_fixtures import Copy, KICAD_CLI, Proved  # noqa: E402


class SeparationFloorProof(Proved):
    def test_each_floor_fault_is_caught_on_a_copy_of_the_throwaway_design_and_the_committed_design_stays_passing(self):
        # SOL-PRE-ORDER-CHECK-SEPARATION-FLOOR-AND-MOUNTING-HOLES.C5: The on-demand seeded-fault proof introduces into a copy of a throwaway design, outside the tracked tree, a signed clearance below its floor, a signed creepage below its floor, a mains-present design with no applicable row
        faults = [fault for fault in board_prove.FAULTS if fault[1].startswith("separation floor:")]
        self.assertEqual({fault[2] for fault in faults}, {"separation_floor"})
        self.assertEqual({board_prove.target_of(fault) for fault in faults}, {(board_prove.DESIGN, board_prove.NAME)})
        self.assertEqual(len(faults), 4)
        for words in ("clearance_mm is 3 mm, below the 3.5", "creepage_mm is 4 mm, below the 4.5", "no table row of the record gives",
                      "lacks altitude_m"):
            self.assertTrue(any(words in fault[3] for fault in faults), words)
        self.assertCaught(*[fault[0] for fault in faults])


class MountingHoleProof(Proved):
    def test_each_hole_fault_is_caught_on_a_copy_of_the_throwaway_design(self):
        # SOL-PRE-ORDER-CHECK-SEPARATION-FLOOR-AND-MOUNTING-HOLES.C5: a mounting hole inside the larger of the signed clearance and creepage of a Mains net, and a plated hole on a non-Mains net inside that distance, and requires the check to fail each
        faults = [fault for fault in board_prove.FAULTS if fault[1].startswith("mounting holes:")]
        self.assertEqual({fault[2] for fault in faults}, {"mounting_hole"})
        self.assertEqual(len(faults), 5)
        self.assertCaught(*[fault[0] for fault in faults])


class FloorAndHolesRunDirectly(Copy):
    def holes(self, lines):
        return [v for v in self.violations(lines) if v[2] in ("mounting_hole", "separation_floor")]

    def test_mains_copper_inside_a_fixings_courtyard_distance_fails_by_track_and_by_pour_and_names_the_gap(self):
        # SOL-PRE-ORDER-CHECK-SEPARATION-FLOOR-AND-MOUNTING-HOLES.C2: measures from the layout file the distance from each mounting-hole footprint's courtyard to every track and pour fill of a Mains net on every layer
        for seed, kind, gap in ((board_prove.fixing_near_mains_track, "track of /MAINS_N on F.Cu", "2.875 mm"),
                                (board_prove.fixing_near_mains_pour, "zone fill of /MAINS_N on B.Cu", "2.000 mm")):
            with self.subTest(kind=kind):
                self.setUp()
                seed(self.seed)
                status, lines = self.check()
                self.assertEqual(status, 1)
                found = [v for v in self.holes(lines) if v[2] == "mounting_hole"]
                self.assertEqual(len(found), 1, lines)
                self.assertIn("H9 courtyard", found[0][3])
                self.assertIn(kind, found[0][3])
                self.assertIn(f"stands {gap}", found[0][4])
                self.assertIn("inside the 4 mm", found[0][4])

    def test_the_same_fixing_with_the_mains_copper_beyond_the_distance_passes(self):
        # SOL-PRE-ORDER-CHECK-SEPARATION-FLOOR-AND-MOUNTING-HOLES.C2: A clean design passes
        self.seed.layout(lambda tree: (tree.insert(len(tree) - 1, board_prove.seeded_hole(
            "H9", board_prove.FIXING_X, 10, board_prove.FIXING_UUID, courtyard=10)),
            tree.insert(len(tree) - 1, board_prove.segment("/MAINS_N", 25.5, 4, 25.5, 16, "0b0e5c1a-0000-4000-8000-000000000c10"))))
        status, lines = self.check()
        self.assertEqual([v for v in self.holes(lines) if v[2] == "mounting_hole"], [], lines)

    def test_a_footprint_of_one_plated_pad_left_out_of_the_bom_is_a_fixing_whose_courtyard_is_measured(self):
        # SOL-PRE-ORDER-CHECK-SEPARATION-FLOOR-AND-MOUNTING-HOLES.C2: a footprint whose pads are all drilled holes, plated or not, is a mounting hole
        self.seed.layout(lambda tree: (tree.insert(len(tree) - 1, board_prove.seeded_hole(
            "H9", board_prove.FIXING_X, 10, board_prove.FIXING_UUID, plated_net="/LV_A", courtyard=10, excluded=True)),
            tree.insert(len(tree) - 1, board_prove.segment("/MAINS_N", 27, 4, 27, 16, "0b0e5c1a-0000-4000-8000-000000000c10"))))
        status, lines = self.check()
        found = [v for v in self.holes(lines) if v[2] == "mounting_hole"]
        self.assertTrue(any("H9 courtyard" in v[3] for v in found), lines)

    def test_a_footprint_of_one_plated_pad_with_no_bom_flag_is_a_fixing_whose_courtyard_is_measured(self):
        # SOL-PRE-ORDER-CHECK-SEPARATION-FLOOR-AND-MOUNTING-HOLES.C2: a footprint whose pads are all drilled holes and which has exactly one pad is a mounting hole, so a forgotten exclude_from_bom does not skip the extent checks
        self.seed.layout(lambda tree: (tree.insert(len(tree) - 1, board_prove.seeded_hole(
            "H9", board_prove.FIXING_X, 10, board_prove.FIXING_UUID, plated_net="/LV_A", courtyard=10)),
            tree.insert(len(tree) - 1, board_prove.segment("/MAINS_N", 27, 4, 27, 16, "0b0e5c1a-0000-4000-8000-000000000c10"))))
        status, lines = self.check()
        found = [v for v in self.holes(lines) if v[2] == "mounting_hole"]
        self.assertTrue(any("H9 courtyard" in v[3] for v in found), lines)

    def test_a_pad_larger_than_its_hole_is_held_at_its_edge_in_a_hole_footprint_and_in_a_part(self):
        # SOL-PRE-ORDER-CHECK-SEPARATION-FLOOR-AND-MOUNTING-HOLES.C2: the check fails a hole, its plating or fixing inside that distance of a Mains net
        for surface_pad, who in ((False, "the pad copper of a hole footprint"), (True, "KiCad's physical clearance of a part")):
            with self.subTest(who):
                self.setUp()
                self.seed.layout(lambda tree: tree.insert(len(tree) - 1, board_prove.seeded_hole(
                    "H9", board_prove.OVERSIZE_X, 10, board_prove.FIXING_UUID, pad=6, surface_pad=surface_pad)))
                status, lines = self.check()
                self.assertEqual(status, 1)
                self.assertTrue([v for v in self.holes(lines) if v[2] == "mounting_hole"], lines)

    def test_the_hole_that_is_clear_with_its_pad_clear_too_passes(self):
        # SOL-PRE-ORDER-CHECK-SEPARATION-FLOOR-AND-MOUNTING-HOLES.C2: A clean design passes
        self.seed.layout(lambda tree: tree.insert(len(tree) - 1, board_prove.seeded_hole(
            "H9", board_prove.OVERSIZE_X + 2.8, 10, board_prove.FIXING_UUID, pad=6, surface_pad=True)))
        status, lines = self.check()
        self.assertEqual([v for v in self.holes(lines) if v[2] == "mounting_hole"], [], lines)

    def test_without_its_physical_clearance_constraint_the_part_with_an_oversize_pad_would_pass(self):
        # SOL-PRE-ORDER-CHECK-SEPARATION-FLOOR-AND-MOUNTING-HOLES.C2: the pad of a hole inside the distance is held by the rule's physical clearance
        board_prove.hole_with_oversize_pad(self.seed)
        board_prove.git(self.seed, "add", "-A")
        board_prove.git(self.seed, "commit", "-q", "--allow-empty", "-m", "seeded copy")
        real = board_check.hole_rules
        out = io.StringIO()
        with mock.patch.object(board_check, "hole_rules", lambda distance: real(distance).replace(
                f"\n\t(constraint physical_clearance (min {distance:g}mm))", "")):
            board_check.run(self.seed.root, KICAD_CLI, out=out)
        lines = out.getvalue().splitlines()
        self.assertEqual([v for v in self.holes(lines) if v[2] == "mounting_hole"], [], lines)

    def test_the_unmodified_throwaway_design_passes_both_rules(self):
        # SOL-PRE-ORDER-CHECK-SEPARATION-FLOOR-AND-MOUNTING-HOLES.C2: A clean design passes
        status, lines = self.check()
        self.assertEqual(status, 0, lines)
        self.assertEqual(self.holes(lines), [])
        self.assertIn("barrier_types: []", self.seed.read("separation-basis.yaml"))

    def test_a_hole_beyond_the_signed_distance_passes_and_one_inside_it_fails_with_the_gap_named(self):
        # SOL-PRE-ORDER-CHECK-SEPARATION-FLOOR-AND-MOUNTING-HOLES.C2: fails a hole, its plating or fixing inside that distance of a Mains net
        far = 25.96 + 4.5 + 1.6
        self.seed.layout(lambda tree: tree.insert(len(tree) - 1, board_prove.seeded_hole("H9", far, 10, "0b0e5c1a-0000-4000-8000-000000000c00")))
        status, lines = self.check()
        self.assertEqual(self.holes(lines), [], lines)
        near = 25.96 + 3.5 + 1.6
        self.seed.layout(lambda tree: tree[-2].__setitem__(slice(None), board_prove.seeded_hole("H9", near, 10, "0b0e5c1a-0000-4000-8000-000000000c00")))
        status, lines = self.check()
        self.assertEqual(status, 1)
        found = self.holes(lines)
        self.assertEqual({v[2] for v in found}, {"mounting_hole"}, lines)
        self.assertEqual(len({frozenset(v[3].split("; ")) for v in found}), len(found), lines)
        kicad = [v for v in found if "NPTH pad of H9" in v[3]]
        self.assertEqual(len(kicad), 1, lines)
        self.assertIn("stands 3.5", kicad[0][4])
        self.assertIn("4 mm", kicad[0][4])
        measured = [v for v in found if "H9 pad" in v[3]]
        self.assertEqual(len(measured), 1, lines)
        self.assertIn("stands 3.500 mm", measured[0][4])

    def test_the_failure_is_in_the_same_report_as_the_existing_checks_with_the_rule_design_and_item(self):
        # SOL-PRE-ORDER-CHECK-SEPARATION-FLOOR-AND-MOUNTING-HOLES.C4: in the same report as the existing checks
        board_prove.hole_near_mains()(self.seed)
        status, lines = self.check()
        self.assertEqual(status, 1)
        self.assertTrue(any(line.startswith("DESIGN | hardware/proof/gate-proof/gate-proof.kicad_pro | FAIL") for line in lines), lines)
        found = [v for v in self.violations(lines) if v[2] == "mounting_hole"]
        self.assertTrue(found)
        self.assertEqual(len({frozenset(v[3].split("; ")) for v in found}), len(found),
                         "an item pair is named once, however many constraints of KiCad it breaks and whichever way round")
        for violation in found:
            self.assertEqual(violation[1], "hardware/proof/gate-proof/gate-proof.kicad_pro")
            self.assertIn("H9", violation[3])
        self.assertTrue(any(v[2] in ("extra_footprint", "missing_courtyard") for v in self.violations(lines)),
                        "KiCad's own findings are reported beside it")

    def test_a_plated_hole_on_a_mains_net_is_not_failed_by_the_plated_hole_rule(self):
        # SOL-PRE-ORDER-CHECK-SEPARATION-FLOOR-AND-MOUNTING-HOLES.C2: a plated hole on a non-Mains net inside that distance
        board_prove.hole_near_mains("/MAINS_L")(self.seed)
        status, lines = self.check()
        self.assertEqual([v for v in self.holes(lines) if "plated hole" in v[4]], [], lines)

    def test_a_hole_inside_the_distance_fails_whether_or_not_it_is_on_a_protective_earth_net(self):
        # SOL-PRE-ORDER-CHECK-SEPARATION-FLOOR-AND-MOUNTING-HOLES.C2: The signed figure governs whether or not the fixing is bonded to protective earth
        for net in ("/LV_A", "/LV_B"):
            with self.subTest(net=net):
                self.setUp()
                board_prove.hole_near_mains(net)(self.seed)
                status, lines = self.check()
                self.assertEqual(status, 1)
                self.assertEqual({v[2] for v in self.holes(lines)}, {"mounting_hole"}, lines)

    def test_the_distance_is_the_larger_of_the_signed_clearance_and_creepage_whichever_it_is(self):
        # SOL-PRE-ORDER-CHECK-SEPARATION-FLOOR-AND-MOUNTING-HOLES.C2: no less than the larger of the signed clearance and the signed creepage
        at_4_2 = 25.96 + 4.2 + 1.6
        self.seed.layout(lambda tree: tree.insert(len(tree) - 1, board_prove.seeded_hole("H9", at_4_2, 10, "0b0e5c1a-0000-4000-8000-000000000c00")))
        status, lines = self.check()
        self.assertEqual(self.holes(lines), [], "a 4.2 mm gap clears the signed creepage of 4 mm, the larger of 3 and 4")
        self.seed.replace("separation-basis.yaml", "  clearance_mm: 3.0\n  creepage_mm: 4.0", "  clearance_mm: 4.5\n  creepage_mm: 4.0")
        self.seed.replace(".kicad_dru", "(constraint clearance (min 3mm))", "(constraint clearance (min 4.5mm))")
        status, lines = self.check()
        found = [v for v in self.holes(lines) if v[2] == "mounting_hole"]
        self.assertTrue(found, "a 4.2 mm gap is inside the signed clearance of 4.5 mm, the larger of 4.5 and 4")
        self.assertTrue(all("inside the 4.5 mm that is the larger of the signed clearance" in v[4] for v in found), found)

    def test_a_basis_lacking_the_floor_inputs_fails_the_run_by_key_and_still_runs_every_other_check(self):
        # SOL-PRE-ORDER-CHECK-SEPARATION-FLOOR-AND-MOUNTING-HOLES.C3: each reading only the design's files and the records the design is held to
        self.seed.replace("separation-basis.yaml", "barrier_types: []\n", "")
        board_prove.hole_near_mains()(self.seed)
        status, lines = self.check()
        self.assertEqual(status, 1)
        self.assertEqual([v[3].split(" ")[-1] for v in self.violations(lines) if v[2] == "separation_floor"], ["barrier_types"])
        self.assertTrue([v for v in self.violations(lines) if v[2] == "mounting_hole"], "the hole is still held to the signed distance")


class EveryTrackedDesignPassesTheFloorAndHoleRules(unittest.TestCase):
    def test_no_design_the_repository_tracks_fails_either_rule_and_each_carries_the_inputs_the_floor_reads(self):
        # SOL-PRE-ORDER-CHECK-SEPARATION-FLOOR-AND-MOUNTING-HOLES.C6: Every design git tracks passes the separation-floor rule and the mounting-hole rule, carrying the records they read, synthetic where the design is not for manufacture
        out = io.StringIO()
        board_check.run(board_prove.REPO, KICAD_CLI, out=out)
        lines = out.getvalue().splitlines()
        self.assertGreaterEqual(len([line for line in lines if line.startswith("DESIGN | ")]), 5)
        self.assertEqual([line for line in lines if " | separation_floor | " in line or " | mounting_hole | " in line], [], out.getvalue())
        self.assertTrue(all("synthetic: true" in open(path, encoding="utf-8").read() for path in
                            __import__("glob").glob(os.path.join(board_prove.REPO, "hardware", "proof", "*", "separation-basis.yaml"))))
