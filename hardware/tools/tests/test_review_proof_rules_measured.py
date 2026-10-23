#!/usr/bin/env python3
"""The rules the layout review proof design's review added in KiCad's own form, against KiCad itself: the measured part.

One of the files the original test file is divided into by topic; the tests are unchanged and only live elsewhere.
"""

from __future__ import annotations

import os
import sys

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import review_seed  # noqa: E402
from review_proof_fixtures import ReviewProofCopy, setUpModule  # noqa: E402,F401


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


class TheTestPadCourtyardRuleOnTheProofDesign(ReviewProofCopy):
    def test_a_test_point_moved_into_a_courtyard_fails_and_the_clean_design_passes(self):
        # SOL-PRE-ORDER-CHECK-TEST-POINT-COURTYARD-DISTANCE.C2: Show the rule fail on a test point seeded inside a part's courtyard and closer than the distance, in a throwaway design built outside the repository, and pass the clean design.
        status, violations = self.check()
        self.assertEqual([v for v in violations if v[2] == "test_point_courtyard"], [], violations)
        self.seed.layout(lambda tree: review_seed.move(tree, "TP2", 41, 19))
        status, violations = self.check()
        self.assertEqual(status, 1, violations)
        found = [v for v in violations if v[2] == "test_point_courtyard"]
        self.assertEqual(len(found), 1, violations)
        self.assertIn("test point TP2", found[0][4])
        self.assertIn("requires 1 mm", found[0][4])
