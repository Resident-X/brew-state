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
import sexpr  # noqa: E402
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
        # SOL-PRE-ORDER-CHECK-MOUNTING-HOLE-LEAVES-A-PLATED-TERMINAL-ALONE.C6: The seeded-fault harness still shows the check failing mounting_hole on a copy of the throwaway proof design for a hole, a plated hole and a fixing's courtyard inside the signed distance of its mains pads, and every tracked design passes the mounting-hole rules, which run in the build round for board changes and nightly on main. Out of scope: every other rule's seeded fault.
        faults = [fault for fault in board_prove.FAULTS if fault[1].startswith("mounting holes:")]
        self.assertEqual({fault[2] for fault in faults}, {"mounting_hole"})
        self.assertEqual(len(faults), 5)
        self.assertCaught(*[fault[0] for fault in faults])


class FloorAndHolesRunDirectly(Copy):
    def holes(self, lines):
        return [v for v in self.violations(lines) if v[2] in ("mounting_hole", "separation_floor")]

    def test_mains_copper_inside_a_fixings_courtyard_distance_fails_by_track_and_by_pour_and_names_the_gap(self):
        # SOL-PRE-ORDER-CHECK-MOUNTING-HOLE-LEAVES-A-PLATED-TERMINAL-ALONE.C1: A mounting hole is a footprint whose pads are all drilled holes and which has at least one mark of a fixing, namely every pad non-plated, exclusion from the bill of materials, a library item name beginning MountingHole, or exactly one pad that is plated and on no net. A plated pad on a net is an electrical terminal and is no mark of a fixing by its being the footprint's only pad, so a one-pad blade-tab terminal on a Mains or a low-voltage net is a part and not a hole. Every non-plated hole is held as well, in any footprint. A fixing's extent is the larger of its pad and its courtyard. After the signed Mains rule the check appends rules holding the hole clearance to the Mains class at no less than the larger of the signed clearance and the signed creepage on every layer, and measures from the layout file the distance from each mounting-hole footprint's pad copper and courtyard to every pad, track, via and pour fill of a Mains net on every layer, held to the same distance. The check fails a hole, its plating or fixing inside that distance of a Mains net, and a plated hole on a non-Mains net inside that distance. The signed figure governs whether or not the fixing is bonded to protective earth, and a fixing of any of the four marks keeps that distance whatever its net, while a plated pad on a net that has neither the exclusion nor the name is no fixing and keeps only the signed Mains rule and the plated-hole rule. A design with no mounting hole is not failed for that. Out of scope: the mechanical strength of the fixing and any fixing outside the board file.
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
        # SOL-PRE-ORDER-CHECK-MOUNTING-HOLE-LEAVES-A-PLATED-TERMINAL-ALONE.C3: On a synthetic layout, a mounting hole of each of the four marks fails mounting_hole when its pad copper stands inside the signed distance of a Mains pad, track, via or pour fill, or its courtyard stands inside it of a Mains pad, and passes at exactly that distance; a plated mounting pad on a protective-earth net that is excluded from the bill of materials fails the same way. The check's text report, which is its only report, names the rule mounting_hole, the design, the hole, the Mains net and the distance required. Out of scope: the mechanical strength of the fixing.
        self.seed.layout(lambda tree: (tree.insert(len(tree) - 1, board_prove.seeded_hole(
            "H9", board_prove.FIXING_X, 10, board_prove.FIXING_UUID, courtyard=10)),
            tree.insert(len(tree) - 1, board_prove.segment("/MAINS_N", 25.5, 4, 25.5, 16, "0b0e5c1a-0000-4000-8000-000000000c10"))))
        status, lines = self.check()
        self.assertEqual([v for v in self.holes(lines) if v[2] == "mounting_hole"], [], lines)

    def test_a_footprint_of_one_plated_pad_left_out_of_the_bom_is_a_fixing_whose_courtyard_is_measured(self):
        # SOL-PRE-ORDER-CHECK-MOUNTING-HOLE-LEAVES-A-PLATED-TERMINAL-ALONE.C1: A mounting hole is a footprint whose pads are all drilled holes and which has at least one mark of a fixing, namely every pad non-plated, exclusion from the bill of materials, a library item name beginning MountingHole, or exactly one pad that is plated and on no net. A plated pad on a net is an electrical terminal and is no mark of a fixing by its being the footprint's only pad, so a one-pad blade-tab terminal on a Mains or a low-voltage net is a part and not a hole. Every non-plated hole is held as well, in any footprint. A fixing's extent is the larger of its pad and its courtyard. After the signed Mains rule the check appends rules holding the hole clearance to the Mains class at no less than the larger of the signed clearance and the signed creepage on every layer, and measures from the layout file the distance from each mounting-hole footprint's pad copper and courtyard to every pad, track, via and pour fill of a Mains net on every layer, held to the same distance. The check fails a hole, its plating or fixing inside that distance of a Mains net, and a plated hole on a non-Mains net inside that distance. The signed figure governs whether or not the fixing is bonded to protective earth, and a fixing of any of the four marks keeps that distance whatever its net, while a plated pad on a net that has neither the exclusion nor the name is no fixing and keeps only the signed Mains rule and the plated-hole rule. A design with no mounting hole is not failed for that. Out of scope: the mechanical strength of the fixing and any fixing outside the board file.
        self.seed.layout(lambda tree: (tree.insert(len(tree) - 1, board_prove.seeded_hole(
            "H9", board_prove.FIXING_X, 10, board_prove.FIXING_UUID, plated_net="/LV_A", courtyard=10, excluded=True)),
            tree.insert(len(tree) - 1, board_prove.segment("/MAINS_N", 27, 4, 27, 16, "0b0e5c1a-0000-4000-8000-000000000c10"))))
        status, lines = self.check()
        found = [v for v in self.holes(lines) if v[2] == "mounting_hole"]
        self.assertTrue(any("H9 courtyard" in v[3] for v in found), lines)

    def test_a_plated_pad_on_protective_earth_left_out_of_the_bom_is_a_fixing_whose_courtyard_is_measured(self):
        # SOL-PRE-ORDER-CHECK-MOUNTING-HOLE-LEAVES-A-PLATED-TERMINAL-ALONE.C3: On a synthetic layout, a mounting hole of each of the four marks fails mounting_hole when its pad copper stands inside the signed distance of a Mains pad, track, via or pour fill, or its courtyard stands inside it of a Mains pad, and passes at exactly that distance; a plated mounting pad on a protective-earth net that is excluded from the bill of materials fails the same way. The check's text report, which is its only report, names the rule mounting_hole, the design, the hole, the Mains net and the distance required. Out of scope: the mechanical strength of the fixing.
        self.seed.layout(lambda tree: (tree.insert(len(tree) - 1, board_prove.seeded_hole(
            "H9", board_prove.FIXING_X, 10, board_prove.FIXING_UUID, plated_net="/PE", courtyard=10, excluded=True)),
            tree.insert(len(tree) - 1, board_prove.segment("/MAINS_N", 27, 4, 27, 16, "0b0e5c1a-0000-4000-8000-000000000c10"))))
        status, lines = self.check()
        self.assertEqual(status, 1)
        found = [v for v in self.holes(lines) if v[2] == "mounting_hole" and "H9 courtyard" in v[3]]
        self.assertEqual(len(found), 1, lines)
        self.assertIn("/MAINS_N", found[0][3])
        self.assertIn("inside the 4 mm", found[0][4])

    def test_a_footprint_of_one_plated_pad_on_no_net_with_no_bom_flag_is_a_fixing_whose_courtyard_is_measured(self):
        # SOL-PRE-ORDER-CHECK-MOUNTING-HOLE-LEAVES-A-PLATED-TERMINAL-ALONE.C3: On a synthetic layout, a mounting hole of each of the four marks fails mounting_hole when its pad copper stands inside the signed distance of a Mains pad, track, via or pour fill, or its courtyard stands inside it of a Mains pad, and passes at exactly that distance; a plated mounting pad on a protective-earth net that is excluded from the bill of materials fails the same way. The check's text report, which is its only report, names the rule mounting_hole, the design, the hole, the Mains net and the distance required. Out of scope: the mechanical strength of the fixing.
        self.seed.layout(lambda tree: (tree.insert(len(tree) - 1, board_prove.seeded_hole(
            "H9", board_prove.FIXING_X, 10, board_prove.FIXING_UUID, plated_net="", courtyard=10)),
            tree.insert(len(tree) - 1, board_prove.segment("/MAINS_N", 27, 4, 27, 16, "0b0e5c1a-0000-4000-8000-000000000c10"))))
        status, lines = self.check()
        found = [v for v in self.holes(lines) if v[2] == "mounting_hole"]
        self.assertTrue(any("H9 courtyard" in v[3] for v in found), lines)

    def test_a_footprint_of_one_plated_pad_on_a_net_is_a_terminal_whose_courtyard_is_not_measured_as_a_fixings(self):
        # SOL-PRE-ORDER-CHECK-MOUNTING-HOLE-LEAVES-A-PLATED-TERMINAL-ALONE.C2: On a synthetic layout, a footprint of one plated drilled pad on a Mains net, and one on a low-voltage net, each in the bill of materials and with a library item name that does not begin MountingHole, are not among the mounting holes, and neither gives a mounting_hole violation when its courtyard is drawn inside the signed distance of another Mains net's copper; a footprint of one plated drilled pad on no net, a footprint whose every pad is non-plated, a plated footprint excluded from the bill of materials and a plated footprint whose library item name begins MountingHole are each among them, the last two whatever the net of their pads, a protective-earth net included. A one-pin through-hole part such as a test point is held the same way: on a net it is a part and not a hole. A footprint with a surface-mount pad is no hole whatever its marks. Out of scope: which parts the main board draws as tabs.
        self.seed.layout(lambda tree: (tree.insert(len(tree) - 1, board_prove.seeded_hole(
            "H9", board_prove.FIXING_X, 10, board_prove.FIXING_UUID, plated_net="/LV_A", courtyard=10)),
            tree.insert(len(tree) - 1, board_prove.segment("/MAINS_N", 27, 4, 27, 16, "0b0e5c1a-0000-4000-8000-000000000c10"))))
        status, lines = self.check()
        self.assertFalse([v for v in self.holes(lines) if "H9 courtyard" in v[3]], lines)

    def test_an_unmarked_one_pad_plated_fixing_on_protective_earth_loses_only_its_courtyard_measure(self):
        # SOL-PRE-ORDER-CHECK-MOUNTING-HOLE-LEAVES-A-PLATED-TERMINAL-ALONE.C7: On a synthetic design through KiCad's rule check, a footprint of one plated drilled pad on a protective-earth net, in the bill of materials and with a library item name that does not begin MountingHole, is not a mounting hole, and its pad copper inside the signed distance of a Mains pad, track, via or pour fill still fails under the signed Mains rule and its drilled hole inside that distance of Mains copper still fails under the plated-hole rule, so a fixing left unmarked loses only its courtyard measure. Out of scope: the signed figures themselves.
        self.seed.layout(lambda tree: (tree.insert(len(tree) - 1, board_prove.seeded_hole(
            "H9", board_prove.PLATED_X - 1.0, 10, board_prove.FIXING_UUID, plated_net="/PE", courtyard=10))))
        status, lines = self.check()
        self.assertEqual(status, 1)
        found = self.violations(lines)
        pad_pair = [v for v in found if v[2] == "clearance" and "[/PE] of H9" in v[3] and "[/MAINS_N] of R1" in v[3]]
        self.assertTrue(pad_pair, lines)
        self.assertIn("pre-order check: signed separation basis' clearance 3.0000 mm", pad_pair[0][4])
        plated = [v for v in found if v[2] == "mounting_hole" and "plated hole" in v[4] and "[/PE] of H9" in v[3]]
        self.assertEqual(len(plated), 1, lines)
        self.assertFalse([v for v in found if v[2] == "mounting_hole" and "H9 courtyard" in v[3]],
                         "the unmarked fixing is a part and its courtyard is not measured as a fixing's")

    def test_a_pad_larger_than_its_hole_is_held_at_its_edge_in_a_hole_footprint_and_in_a_part(self):
        # SOL-PRE-ORDER-CHECK-MOUNTING-HOLE-LEAVES-A-PLATED-TERMINAL-ALONE.C1: A mounting hole is a footprint whose pads are all drilled holes and which has at least one mark of a fixing, namely every pad non-plated, exclusion from the bill of materials, a library item name beginning MountingHole, or exactly one pad that is plated and on no net. A plated pad on a net is an electrical terminal and is no mark of a fixing by its being the footprint's only pad, so a one-pad blade-tab terminal on a Mains or a low-voltage net is a part and not a hole. Every non-plated hole is held as well, in any footprint. A fixing's extent is the larger of its pad and its courtyard. After the signed Mains rule the check appends rules holding the hole clearance to the Mains class at no less than the larger of the signed clearance and the signed creepage on every layer, and measures from the layout file the distance from each mounting-hole footprint's pad copper and courtyard to every pad, track, via and pour fill of a Mains net on every layer, held to the same distance. The check fails a hole, its plating or fixing inside that distance of a Mains net, and a plated hole on a non-Mains net inside that distance. The signed figure governs whether or not the fixing is bonded to protective earth, and a fixing of any of the four marks keeps that distance whatever its net, while a plated pad on a net that has neither the exclusion nor the name is no fixing and keeps only the signed Mains rule and the plated-hole rule. A design with no mounting hole is not failed for that. Out of scope: the mechanical strength of the fixing and any fixing outside the board file.
        for surface_pad, who in ((False, "the pad copper of a hole footprint"), (True, "KiCad's physical clearance of a part")):
            with self.subTest(who):
                self.setUp()
                self.seed.layout(lambda tree: tree.insert(len(tree) - 1, board_prove.seeded_hole(
                    "H9", board_prove.OVERSIZE_X, 10, board_prove.FIXING_UUID, pad=6, surface_pad=surface_pad)))
                status, lines = self.check()
                self.assertEqual(status, 1)
                self.assertTrue([v for v in self.holes(lines) if v[2] == "mounting_hole"], lines)

    def test_the_hole_that_is_clear_with_its_pad_clear_too_passes(self):
        # SOL-PRE-ORDER-CHECK-MOUNTING-HOLE-LEAVES-A-PLATED-TERMINAL-ALONE.C3: On a synthetic layout, a mounting hole of each of the four marks fails mounting_hole when its pad copper stands inside the signed distance of a Mains pad, track, via or pour fill, or its courtyard stands inside it of a Mains pad, and passes at exactly that distance; a plated mounting pad on a protective-earth net that is excluded from the bill of materials fails the same way. The check's text report, which is its only report, names the rule mounting_hole, the design, the hole, the Mains net and the distance required. Out of scope: the mechanical strength of the fixing.
        self.seed.layout(lambda tree: tree.insert(len(tree) - 1, board_prove.seeded_hole(
            "H9", board_prove.OVERSIZE_X + 2.8, 10, board_prove.FIXING_UUID, pad=6, surface_pad=True)))
        status, lines = self.check()
        self.assertEqual([v for v in self.holes(lines) if v[2] == "mounting_hole"], [], lines)

    def test_without_its_physical_clearance_constraint_the_part_with_an_oversize_pad_would_pass(self):
        # SOL-PRE-ORDER-CHECK-MOUNTING-HOLE-LEAVES-A-PLATED-TERMINAL-ALONE.C1: A mounting hole is a footprint whose pads are all drilled holes and which has at least one mark of a fixing, namely every pad non-plated, exclusion from the bill of materials, a library item name beginning MountingHole, or exactly one pad that is plated and on no net. A plated pad on a net is an electrical terminal and is no mark of a fixing by its being the footprint's only pad, so a one-pad blade-tab terminal on a Mains or a low-voltage net is a part and not a hole. Every non-plated hole is held as well, in any footprint. A fixing's extent is the larger of its pad and its courtyard. After the signed Mains rule the check appends rules holding the hole clearance to the Mains class at no less than the larger of the signed clearance and the signed creepage on every layer, and measures from the layout file the distance from each mounting-hole footprint's pad copper and courtyard to every pad, track, via and pour fill of a Mains net on every layer, held to the same distance. The check fails a hole, its plating or fixing inside that distance of a Mains net, and a plated hole on a non-Mains net inside that distance. The signed figure governs whether or not the fixing is bonded to protective earth, and a fixing of any of the four marks keeps that distance whatever its net, while a plated pad on a net that has neither the exclusion nor the name is no fixing and keeps only the signed Mains rule and the plated-hole rule. A design with no mounting hole is not failed for that. Out of scope: the mechanical strength of the fixing and any fixing outside the board file.
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
        # SOL-PRE-ORDER-CHECK-MOUNTING-HOLE-LEAVES-A-PLATED-TERMINAL-ALONE.C1: A mounting hole is a footprint whose pads are all drilled holes and which has at least one mark of a fixing, namely every pad non-plated, exclusion from the bill of materials, a library item name beginning MountingHole, or exactly one pad that is plated and on no net. A plated pad on a net is an electrical terminal and is no mark of a fixing by its being the footprint's only pad, so a one-pad blade-tab terminal on a Mains or a low-voltage net is a part and not a hole. Every non-plated hole is held as well, in any footprint. A fixing's extent is the larger of its pad and its courtyard. After the signed Mains rule the check appends rules holding the hole clearance to the Mains class at no less than the larger of the signed clearance and the signed creepage on every layer, and measures from the layout file the distance from each mounting-hole footprint's pad copper and courtyard to every pad, track, via and pour fill of a Mains net on every layer, held to the same distance. The check fails a hole, its plating or fixing inside that distance of a Mains net, and a plated hole on a non-Mains net inside that distance. The signed figure governs whether or not the fixing is bonded to protective earth, and a fixing of any of the four marks keeps that distance whatever its net, while a plated pad on a net that has neither the exclusion nor the name is no fixing and keeps only the signed Mains rule and the plated-hole rule. A design with no mounting hole is not failed for that. Out of scope: the mechanical strength of the fixing and any fixing outside the board file.
        status, lines = self.check()
        self.assertEqual(status, 0, lines)
        self.assertEqual(self.holes(lines), [])
        self.assertIn("barrier_types: []", self.seed.read("separation-basis.yaml"))

    def test_a_hole_beyond_the_signed_distance_passes_and_one_inside_it_fails_with_the_gap_named(self):
        # SOL-PRE-ORDER-CHECK-MOUNTING-HOLE-LEAVES-A-PLATED-TERMINAL-ALONE.C1: A mounting hole is a footprint whose pads are all drilled holes and which has at least one mark of a fixing, namely every pad non-plated, exclusion from the bill of materials, a library item name beginning MountingHole, or exactly one pad that is plated and on no net. A plated pad on a net is an electrical terminal and is no mark of a fixing by its being the footprint's only pad, so a one-pad blade-tab terminal on a Mains or a low-voltage net is a part and not a hole. Every non-plated hole is held as well, in any footprint. A fixing's extent is the larger of its pad and its courtyard. After the signed Mains rule the check appends rules holding the hole clearance to the Mains class at no less than the larger of the signed clearance and the signed creepage on every layer, and measures from the layout file the distance from each mounting-hole footprint's pad copper and courtyard to every pad, track, via and pour fill of a Mains net on every layer, held to the same distance. The check fails a hole, its plating or fixing inside that distance of a Mains net, and a plated hole on a non-Mains net inside that distance. The signed figure governs whether or not the fixing is bonded to protective earth, and a fixing of any of the four marks keeps that distance whatever its net, while a plated pad on a net that has neither the exclusion nor the name is no fixing and keeps only the signed Mains rule and the plated-hole rule. A design with no mounting hole is not failed for that. Out of scope: the mechanical strength of the fixing and any fixing outside the board file.
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
        # SOL-PRE-ORDER-CHECK-MOUNTING-HOLE-LEAVES-A-PLATED-TERMINAL-ALONE.C3: On a synthetic layout, a mounting hole of each of the four marks fails mounting_hole when its pad copper stands inside the signed distance of a Mains pad, track, via or pour fill, or its courtyard stands inside it of a Mains pad, and passes at exactly that distance; a plated mounting pad on a protective-earth net that is excluded from the bill of materials fails the same way. The check's text report, which is its only report, names the rule mounting_hole, the design, the hole, the Mains net and the distance required. Out of scope: the mechanical strength of the fixing.
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
        # SOL-PRE-ORDER-CHECK-MOUNTING-HOLE-LEAVES-A-PLATED-TERMINAL-ALONE.C1: A mounting hole is a footprint whose pads are all drilled holes and which has at least one mark of a fixing, namely every pad non-plated, exclusion from the bill of materials, a library item name beginning MountingHole, or exactly one pad that is plated and on no net. A plated pad on a net is an electrical terminal and is no mark of a fixing by its being the footprint's only pad, so a one-pad blade-tab terminal on a Mains or a low-voltage net is a part and not a hole. Every non-plated hole is held as well, in any footprint. A fixing's extent is the larger of its pad and its courtyard. After the signed Mains rule the check appends rules holding the hole clearance to the Mains class at no less than the larger of the signed clearance and the signed creepage on every layer, and measures from the layout file the distance from each mounting-hole footprint's pad copper and courtyard to every pad, track, via and pour fill of a Mains net on every layer, held to the same distance. The check fails a hole, its plating or fixing inside that distance of a Mains net, and a plated hole on a non-Mains net inside that distance. The signed figure governs whether or not the fixing is bonded to protective earth, and a fixing of any of the four marks keeps that distance whatever its net, while a plated pad on a net that has neither the exclusion nor the name is no fixing and keeps only the signed Mains rule and the plated-hole rule. A design with no mounting hole is not failed for that. Out of scope: the mechanical strength of the fixing and any fixing outside the board file.
        board_prove.hole_near_mains("/MAINS_L")(self.seed)
        status, lines = self.check()
        self.assertEqual([v for v in self.holes(lines) if "plated hole" in v[4]], [], lines)

    def test_a_hole_inside_the_distance_fails_whether_or_not_it_is_on_a_protective_earth_net(self):
        # SOL-PRE-ORDER-CHECK-MOUNTING-HOLE-LEAVES-A-PLATED-TERMINAL-ALONE.C1: A mounting hole is a footprint whose pads are all drilled holes and which has at least one mark of a fixing, namely every pad non-plated, exclusion from the bill of materials, a library item name beginning MountingHole, or exactly one pad that is plated and on no net. A plated pad on a net is an electrical terminal and is no mark of a fixing by its being the footprint's only pad, so a one-pad blade-tab terminal on a Mains or a low-voltage net is a part and not a hole. Every non-plated hole is held as well, in any footprint. A fixing's extent is the larger of its pad and its courtyard. After the signed Mains rule the check appends rules holding the hole clearance to the Mains class at no less than the larger of the signed clearance and the signed creepage on every layer, and measures from the layout file the distance from each mounting-hole footprint's pad copper and courtyard to every pad, track, via and pour fill of a Mains net on every layer, held to the same distance. The check fails a hole, its plating or fixing inside that distance of a Mains net, and a plated hole on a non-Mains net inside that distance. The signed figure governs whether or not the fixing is bonded to protective earth, and a fixing of any of the four marks keeps that distance whatever its net, while a plated pad on a net that has neither the exclusion nor the name is no fixing and keeps only the signed Mains rule and the plated-hole rule. A design with no mounting hole is not failed for that. Out of scope: the mechanical strength of the fixing and any fixing outside the board file.
        for net in ("/LV_A", "/LV_B"):
            with self.subTest(net=net):
                self.setUp()
                board_prove.hole_near_mains(net)(self.seed)
                status, lines = self.check()
                self.assertEqual(status, 1)
                self.assertEqual({v[2] for v in self.holes(lines)}, {"mounting_hole"}, lines)

    def test_the_distance_is_the_larger_of_the_signed_clearance_and_creepage_whichever_it_is(self):
        # SOL-PRE-ORDER-CHECK-MOUNTING-HOLE-LEAVES-A-PLATED-TERMINAL-ALONE.C1: A mounting hole is a footprint whose pads are all drilled holes and which has at least one mark of a fixing, namely every pad non-plated, exclusion from the bill of materials, a library item name beginning MountingHole, or exactly one pad that is plated and on no net. A plated pad on a net is an electrical terminal and is no mark of a fixing by its being the footprint's only pad, so a one-pad blade-tab terminal on a Mains or a low-voltage net is a part and not a hole. Every non-plated hole is held as well, in any footprint. A fixing's extent is the larger of its pad and its courtyard. After the signed Mains rule the check appends rules holding the hole clearance to the Mains class at no less than the larger of the signed clearance and the signed creepage on every layer, and measures from the layout file the distance from each mounting-hole footprint's pad copper and courtyard to every pad, track, via and pour fill of a Mains net on every layer, held to the same distance. The check fails a hole, its plating or fixing inside that distance of a Mains net, and a plated hole on a non-Mains net inside that distance. The signed figure governs whether or not the fixing is bonded to protective earth, and a fixing of any of the four marks keeps that distance whatever its net, while a plated pad on a net that has neither the exclusion nor the name is no fixing and keeps only the signed Mains rule and the plated-hole rule. A design with no mounting hole is not failed for that. Out of scope: the mechanical strength of the fixing and any fixing outside the board file.
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

    def part_hole_beside_mains(self, slotted: bool) -> list:
        """The plated hole of a part H9 on /LV_A 3.9 mm in a straight line from R1's Mains pad, with a slot between them or none."""
        board_prove.hole_near_mains("/LV_A")(self.seed)
        if slotted:
            self.seed.layout(lambda tree: tree.insert(len(tree) - 1, ["gr_rect", ["start", "27", "2"], ["end", "28.2", "18"], ["stroke", ["width", "0.1"], ["type", "default"]],
                ["fill", "no"], ["layer", sexpr.Quoted("Edge.Cuts")], ["uuid", sexpr.Quoted("0b0e5c1a-0000-4000-8000-000000001a04")]]))
        _, lines = self.check()
        return [v for v in self.violations(lines) if v[2] == "mounting_hole" and "H9" in v[3]]

    def test_a_part_hole_across_a_long_slot_from_mains_copper_gives_no_line_from_the_real_kicad_report(self):
        # SOL-PRE-ORDER-CHECK-PLATED-HOLE-OF-A-LOW-VOLTAGE-PART-IS-MEASURED-ROUND-THE-SLOTS.C1: On a synthetic layout with a barrier slot between a plated hole of a part's pad on a net outside Mains and a Mains-class item (a pad, track, via or pour fill), where the straight-line distance between them is at or above the signed clearance but under the signed creepage and the shortest route round the slot is at or above the signed creepage, the check gives no mounting_hole violation for the pair. Each of these fails naming the hole, the Mains item and the distance measured: the same pair with the slot absent, a pair whose route round the slot is under the signed creepage, and a pair whose straight-line distance is under the signed clearance although its route round the slot is at or above the creepage. The same holds for each kind of Mains item, so a build that reads only pads fails: a track, a via and a pour fill each get the same three failing cases and the passing case. A plated hole of a fixing and every non-plated hole keep the straight measure they have now. Out of scope is a fixing's own pad and courtyard, and the signed figures.
        self.assertEqual(self.part_hole_beside_mains(True), [])

    def test_the_same_part_hole_with_no_slot_gives_exactly_one_line_of_the_checks_own_and_not_kicads_straight_line(self):
        # SOL-PRE-ORDER-CHECK-PLATED-HOLE-OF-A-LOW-VOLTAGE-PART-IS-MEASURED-ROUND-THE-SLOTS.C1: On a synthetic layout with a barrier slot between a plated hole of a part's pad on a net outside Mains and a Mains-class item (a pad, track, via or pour fill), where the straight-line distance between them is at or above the signed clearance but under the signed creepage and the shortest route round the slot is at or above the signed creepage, the check gives no mounting_hole violation for the pair. Each of these fails naming the hole, the Mains item and the distance measured: the same pair with the slot absent, a pair whose route round the slot is under the signed creepage, and a pair whose straight-line distance is under the signed clearance although its route round the slot is at or above the creepage. The same holds for each kind of Mains item, so a build that reads only pads fails: a track, a via and a pour fill each get the same three failing cases and the passing case. A plated hole of a fixing and every non-plated hole keep the straight measure they have now. Out of scope is a fixing's own pad and courtyard, and the signed figures.
        found = self.part_hole_beside_mains(False)
        self.assertEqual(len(found), 1, found)
        self.assertIn("pad 1 [/LV_A] of H9", found[0][3])
        self.assertIn("of /MAINS_N", found[0][3])
        self.assertIn("3.900 mm in a straight line", found[0][4])
        self.assertIn("signed clearance of 3 mm", found[0][4])
        self.assertNotIn("actual", found[0][4])

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
        # SOL-PRE-ORDER-CHECK-MOUNTING-HOLE-LEAVES-A-PLATED-TERMINAL-ALONE.C6: The seeded-fault harness still shows the check failing mounting_hole on a copy of the throwaway proof design for a hole, a plated hole and a fixing's courtyard inside the signed distance of its mains pads, and every tracked design passes the mounting-hole rules, which run in the build round for board changes and nightly on main. Out of scope: every other rule's seeded fault.
        out = io.StringIO()
        board_check.run(board_prove.REPO, KICAD_CLI, out=out)
        lines = out.getvalue().splitlines()
        self.assertGreaterEqual(len([line for line in lines if line.startswith("DESIGN | ")]), 5)
        self.assertEqual([line for line in lines if " | separation_floor | " in line or " | mounting_hole | " in line], [], out.getvalue())
        self.assertTrue(all("synthetic: true" in open(path, encoding="utf-8").read() for path in
                            __import__("glob").glob(os.path.join(board_prove.REPO, "hardware", "proof", "*", "separation-basis.yaml"))))
