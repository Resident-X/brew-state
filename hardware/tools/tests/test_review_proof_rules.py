#!/usr/bin/env python3
"""The rules the layout review proof design's review added in KiCad's own form, against KiCad itself.

The crystal keep-clear, the ground pad reliefs and the floorplan's regions are
custom rules in the design's rules file, which KiCad enforces; the check adds
nothing to them but reporting what KiCad finds. These run the shipped check on
copies of hardware/proof/review-proof in temporary git work trees outside the
repository, each with a fault seeded for one rule, with the real kicad-cli named
by KICAD_CLI (or found on the search path). A missing tool fails the run, since a
rule that cannot be exercised has not been shown to work.
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)

import board_fixtures  # noqa: E402
import board_prove  # noqa: E402
import review_seed  # noqa: E402

KICAD_CLI = os.environ.get("KICAD_CLI") or "kicad-cli"

def setUpModule():
    board_fixtures.require_tools(KICAD_CLI)


class ReviewProofCopy(unittest.TestCase):
    """A fresh copy of the layout review proof design in its own git work tree."""

    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory(prefix="review-proof-test-")
        self.addCleanup(self.scratch.cleanup)
        self.seed = board_prove.prepare(self.scratch.name, review_seed.DESIGN, review_seed.NAME)

    def check(self):
        status, lines, stderr = board_prove.check(self.seed, KICAD_CLI)
        self.assertNotEqual(status, 2, stderr)
        return status, [line.split(" | ") for line in lines if line.startswith("VIOLATION | ")]

    def named(self, violations, text):
        return [v for v in violations if text in v[4]]

    def thermal_gap(self, gap: str) -> None:
        def edit(tree: list) -> None:
            for zone in review_seed.sexpr.children(tree, "zone"):
                fill = review_seed.sexpr.child(zone, "fill")
                for node in review_seed.sexpr.children(fill, "thermal_gap") if fill else []:
                    node[1] = gap
        self.seed.layout(edit)


class TheCleanDesignPassesEveryRule(ReviewProofCopy):
    def test_the_proof_design_as_committed_passes_with_each_rule_in_force(self):
        # SOL-BOARD-REVIEW-PROOF-BASELINE-CLEAN.C3: Each rule the proof design's review adds fails on a fault seeded for it and passes the clean design
        status, violations = self.check()
        self.assertEqual(status, 0, violations)
        rules = self.seed.read(".kicad_dru")
        for name in ("Crystal keep-clear", "Ground pad reliefs", "Mains region parts", "Low voltage region parts",
                     "Analog sensing region parts", "Digital region parts"):
            self.assertIn(f'(rule "{name}"', rules)


class TheCrystalKeepClear(ReviewProofCopy):
    def test_an_unrelated_part_moved_within_25_mm_of_the_crystal_fails(self):
        # SOL-BOARD-REVIEW-PROOF-BASELINE-CLEAN.C3: Each rule the proof design's review adds fails on a fault seeded for it and passes the clean design
        self.seed.layout(lambda tree: review_seed.move(tree, "FB1", 73.8, 38.0))
        status, violations = self.check()
        self.assertEqual(status, 1, violations)
        found = self.named(violations, "rule 'Crystal keep-clear' clearance 25.0000 mm")
        self.assertEqual([v[2] for v in found], ["courtyards_overlap"], violations)
        self.assertIn("Footprint FB1", found[0][3] + found[0][4])

    def test_a_part_related_to_the_oscillator_may_stand_beside_the_crystal(self):
        # SOL-BOARD-REVIEW-PROOF-BASELINE-CLEAN.C3: Each rule the proof design's review adds fails on a fault seeded for it and passes the clean design
        self.seed.layout(lambda tree: review_seed.move(tree, "C4", 77.0, 17.0))
        _, violations = self.check()
        self.assertEqual(self.named(violations, "Crystal keep-clear"), [], violations)


class TheFloorplanRegions(ReviewProofCopy):
    def test_a_part_moved_into_a_region_that_does_not_list_it_fails(self):
        # SOL-BOARD-REVIEW-PROOF-BASELINE-CLEAN.C3: Each rule the proof design's review adds fails on a fault seeded for it and passes the clean design
        self.seed.layout(lambda tree: review_seed.move(tree, "D1", 80.0, 22.0))
        status, violations = self.check()
        self.assertEqual(status, 1, violations)
        found = self.named(violations, "Digital region parts")
        self.assertEqual([v[2] for v in found], ["items_not_allowed"], violations)

    def test_a_part_the_region_lists_may_cross_its_bound(self):
        # SOL-BOARD-REVIEW-PROOF-BASELINE-CLEAN.C3: Each rule the proof design's review adds fails on a fault seeded for it and passes the clean design
        # U1 bridges the barrier and is listed in both regions it straddles.
        _, violations = self.check()
        self.assertEqual(self.named(violations, "region parts"), [], violations)


class TheGroundPadReliefs(ReviewProofCopy):
    def test_a_relief_the_zones_cannot_form_fails_as_starved(self):
        # SOL-BOARD-REVIEW-PROOF-BASELINE-CLEAN.C3: Each rule the proof design's review adds fails on a fault seeded for it and passes the clean design
        self.thermal_gap("4")
        status, violations = self.check()
        self.assertEqual(status, 1, violations)
        found = [v for v in violations if v[2] == "starved_thermal"]
        self.assertTrue(found, violations)
        self.assertIn("min spoke count 2", found[0][4])

    def test_without_the_rule_the_same_zones_join_the_pads_in_full_and_nothing_is_starved(self):
        # SOL-BOARD-REVIEW-PROOF-BASELINE-CLEAN.C3: Each rule the proof design's review adds fails on a fault seeded for it and passes the clean design
        self.thermal_gap("4")
        text = self.seed.read(".kicad_dru")
        start = text.index('(rule "Ground pad reliefs"')
        end = text.index("(rule ", start + 1)
        self.seed.write(".kicad_dru", text[:start] + text[end:])
        _, violations = self.check()
        self.assertEqual([v for v in violations if v[2] == "starved_thermal"], [], violations)


class TheMeasuredRulesOnTheProofDesign(ReviewProofCopy):
    def test_a_mains_copper_area_reaching_under_the_phototriac_fails(self):
        # SOL-BOARD-REVIEW-PROOF-BASELINE-CLEAN.C3: Each rule the proof design's review adds fails on a fault seeded for it and passes the clean design
        def edit(tree: list) -> None:
            for zone in review_seed.sexpr.children(tree, "zone"):
                net = review_seed.sexpr.child(zone, "net")
                if net is not None and str(net[1]).startswith("/MAINS_"):
                    for point in review_seed.sexpr.child(review_seed.sexpr.child(zone, "polygon"), "pts")[1:]:
                        if point[1] == "24.19":
                            point[1] = "26.3"
        self.seed.layout(edit)
        status, violations = self.check()
        self.assertEqual(status, 1, violations)
        found = [v for v in violations if v[2] == "mains_barrier"]
        self.assertTrue(found, violations)
        self.assertIn("U1", found[0][3] + found[0][4])

    def test_a_via_drilled_under_the_exposed_pads_paste_fails(self):
        # SOL-BOARD-REVIEW-PROOF-BASELINE-CLEAN.C3: Each rule the proof design's review adds fails on a fault seeded for it and passes the clean design
        self.seed.layout(lambda tree: review_seed.append(tree, review_seed.new_via(review_seed.GND, (63.3, 14.0))))
        status, violations = self.check()
        self.assertEqual(status, 1, violations)
        found = [v for v in violations if v[2] == "paste_via"]
        self.assertTrue(found, violations)
        self.assertIn("(63.3, 14)", found[0][3] + found[0][4])


if __name__ == "__main__":
    unittest.main()
