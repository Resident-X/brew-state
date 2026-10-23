#!/usr/bin/env python3
"""The rules the layout review proof design's review added in KiCad's own form, against KiCad itself: the clean part.

One of the files the original test file is divided into by topic; the tests are unchanged and only live elsewhere.
"""

from __future__ import annotations

import os
import sys

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import review_seed  # noqa: E402
from review_proof_fixtures import ReviewProofCopy, SharedReviewProofCopy, setUpModule  # noqa: E402,F401


class TheCleanDesignPassesEveryRule(SharedReviewProofCopy):
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
