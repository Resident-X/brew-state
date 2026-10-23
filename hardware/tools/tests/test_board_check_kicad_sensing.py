#!/usr/bin/env python3
"""The pre-order check against KiCad itself, on the throwaway proof design, here the sensing clearance and ground-return rules.

This is one of the files the check's KiCad tests are divided into by topic; the
shared setup, the seeded-fault proof's pooled outcomes and the exclusion of what
needs that proof are in board_kicad_fixtures.py.
"""

from __future__ import annotations

import io
import os
import subprocess
import sys
import tempfile
import unittest


TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)

import board_check  # noqa: E402
import board_prove  # noqa: E402
import sexpr  # noqa: E402
from board_kicad_fixtures import load_tests, setUpModule  # noqa: E402,F401
from board_kicad_fixtures import Copy, KICAD_CLI, Proved, outcomes  # noqa: E402



SENSING_RULES = ("sensing_clearance", "sensing_override", "ground_return", "board_rules_record")



class SensingAndGroundReturnProof(Proved):
    def test_each_sensing_and_ground_return_fault_is_caught_on_a_copy_of_the_proof_design_and_the_committed_design_stays_passing(self):
        # SOL-PRE-ORDER-CHECK-SENSING-CLEARANCE-AND-GROUND-RETURNS.C5: The on-demand seeded-fault proof introduces into a copy of a throwaway design, outside the tracked tree, a sensing item closer than the declared clearance to a noisy net outside the Mains class and to one inside it (the latter at a declared clearance above the signed one), a pad clearance override below the declared sensing clearance, a board rules record that is silent on sensing, a board rules record with a misspelt key, a connector whose signal pins exceed the declared signal pins per return, a connector with signal pins and no ground-return pin, a connector pin on a class declared neither ground nor signal and a connector of two signal classes over the smaller signal pins per return, and requires the check to fail each
        # OBL-VERIFICATION-DISCIPLINE-001.C9: A check is shown to fail on the defect it exists to catch rather than asserted to be capable of it
        faults = [fault for fault in board_prove.FAULTS if fault[1].startswith(("sensing clearance:", "ground returns:", "board rules:"))]
        self.assertEqual(len(faults), 15)
        self.assertEqual({board_prove.target_of(fault) for fault in faults}, {board_prove.SENSING_TARGET})
        self.assertEqual({fault[2] for fault in faults}, set(SENSING_RULES))
        wanted = {
            "of the noisy class Power, inside the 0.5 mm": "sensing_clearance",
            "of the noisy class Mains, inside the 40 mm": "sensing_clearance",
            "pad 1 of U3 is on the sensing or noisy class net /AMP_OUT and sets a local clearance override": "sensing_override",
            "footprint J4 has a pad on a sensing or noisy class net and sets a local clearance override": "sensing_override",
            "the record lacks sensing": "board_rules_record",
            "holds the key 'clearence_mm'": "board_rules_record",
            "connector J9 has 2 signal pins": "ground_return",
            "connector J9 has 1 signal pins (1 [/AMP_OUT]) and 0 ground-return pins": "ground_return",
            "declares as none of ground, signal or non-signal": "ground_return",
            "lets one return serve 1 signal pins at most": "ground_return",
        }
        for words, rule in wanted.items():
            with self.subTest(fault=words):
                self.assertTrue(any(words in fault[3] and fault[2] == rule for fault in faults), words)
        self.assertCaught(*[fault[0] for fault in faults])

    def test_a_seeded_sensing_or_ground_fault_names_the_fault_and_the_rule_in_the_record_of_the_run(self):
        # SOL-PRE-ORDER-CHECK-SENSING-CLEARANCE-AND-GROUND-RETURNS.C5: the record of each seeded run naming the fault and the rule that caught it
        # SOL-PRE-ORDER-CHECK-SENSING-CLEARANCE-AND-GROUND-RETURNS.C4: A failure of any rule in this leaf is reported with the rule's name, the design, and the offending item
        for fault in board_prove.FAULTS:
            if fault[1].startswith(("sensing clearance:", "ground returns:", "board rules:")):
                caught, evidence = outcomes()[fault[0]]
                self.assertTrue(caught, evidence)
                self.assertIn(f" | {fault[2]} | ", evidence)
                self.assertIn("hardware/proof/review-proof/review-proof.kicad_pro", evidence)
                self.assertIn(fault[3], evidence)

    def test_the_proof_requires_the_mains_pair_rule_to_decide_after_the_signed_rule(self):
        # SOL-PRE-ORDER-CHECK-SENSING-CLEARANCE-AND-GROUND-RETURNS.C1: and after the signed rule, one rule per pair that involves the Mains class holding a clearance constraint only at the larger of the declared clearance and the signed clearance
        fault = next(fault for fault in board_prove.FAULTS if "above the signed one" in fault[0])
        # the nearest Sensing copper is 34 mm from Mains copper, so a rule written ahead of the signed 3 mm rule, or at the signed
        # figure alone, would let the 40 mm declared pass; the proof is caught only by the larger figure deciding
        self.assertCaught(fault[0])
        self.assertIn("inside the 40 mm", outcomes()[fault[0]][1])



class SensingCopy(Copy):
    """A fresh copy of the layout review proof design, the one with a sensing net class and a ground net class."""

    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory(prefix="board-test-")
        self.addCleanup(self.scratch.cleanup)
        self.seed = board_prove.prepare(self.scratch.name, *board_prove.SENSING_TARGET)

    def found(self, rule):
        status, lines = self.check()
        return [v for v in self.violations(lines) if v[2] == rule], lines



class TheSensingRulesRunDirectly(SensingCopy):
    def test_a_pair_with_mains_is_held_to_the_signed_figure_when_the_declared_one_is_smaller_so_the_rule_does_not_loosen_it(self):
        # SOL-PRE-ORDER-CHECK-SENSING-CLEARANCE-AND-GROUND-RETURNS.C1: one rule per pair that involves the Mains class holding a clearance constraint only at the larger of the declared clearance and the signed clearance, so that no rule loosens the signed figure
        # the 1 mm mains tracks /MAINS_SW and /MAINS_L end at x = 24.19, their round ends reaching 24.69: a Sensing track 2 mm
        # beyond is inside the signed 3 mm and far outside the declared 0.5 mm
        x = 24.69 + 2.0 + 0.125
        self.seed.layout(lambda tree: tree.insert(len(tree) - 1, board_prove.segment("/AMP_OUT", x, 19, x, 25, "0b0e5c1a-0000-4000-8000-000000001002")))
        found, lines = self.found("sensing_clearance")
        mains = [v for v in found if "noisy class Mains" in v[4]]
        self.assertTrue(mains, lines)
        self.assertIn("inside the 3 mm that hardware/proof/review-proof/board-rules.yaml declares, the larger of the declared 0.5 mm and the signed clearance 3 mm", mains[0][4])
        self.assertIn("/AMP_OUT", mains[0][3])

    def test_a_pair_without_mains_is_held_to_the_declared_figure_alone_and_a_gap_at_the_figure_passes(self):
        # SOL-PRE-ORDER-CHECK-SENSING-CLEARANCE-AND-GROUND-RETURNS.C1: one rule per sensing and noisy class pair that does not involve the Mains class at the declared clearance; it fails where a sensing item sits closer than its pair's figure
        # the track at 0.3 mm of the Power pad fails against 0.5 mm; moved to 0.6 mm it passes
        for edge, fails in ((0.3, True), (0.6, False)):
            with self.subTest(edge=edge):
                self.setUp()
                x = 37 - 0.85 - edge - 0.125
                self.seed.layout(lambda tree: tree.insert(len(tree) - 1, board_prove.segment("/AMP_OUT", x, 2.5, x, 4.5, board_prove.SENSED_UUID)))
                found, lines = self.found("sensing_clearance")
                self.assertEqual(bool([v for v in found if "noisy class Power" in v[4]]), fails, lines)

    def test_a_class_only_the_layout_gives_a_connector_net_is_resolved_not_taken_for_default(self):
        # SOL-PRE-ORDER-CHECK-SENSING-CLEARANCE-AND-GROUND-RETURNS.C2: A connector pin on a class declared none of ground, signal or non-signal fails
        # Default is a declared signal class in this record, so a pin KiCad places in Foo but the check read as Default would pass
        Q = board_prove.sexpr.Quoted
        board_prove.connector("/F0", "/GND")(self.seed)
        self.seed.layout(lambda tree: tree.insert(len(tree) - 1, ["net_class", Q("Foo"), Q("written by an older KiCad"), ["add_net", Q("/F0")]]))
        found, lines = self.found("ground_return")
        pin = [v for v in found if v[3].endswith("connector J9 pin 1 [/F0]")]
        self.assertEqual(len(pin), 1, lines)
        self.assertIn("pin 1 of connector J9 is on net /F0, in the net class Foo, which", pin[0][4])

    def test_the_design_own_stricter_rule_is_still_held_because_the_sensing_rules_run_apart_from_it(self):
        # SOL-PRE-ORDER-CHECK-SENSING-CLEARANCE-AND-GROUND-RETURNS.C1: inserts on a temporary copy, after the design's own rules
        self.seed.write(".kicad_dru", self.seed.read(".kicad_dru")
                        + "(rule \"sensing keep-out\"\n\t(condition \"A.hasNetclass('Sensing') && B.hasNetclass('Power')\")\n\t(constraint clearance (min 1.2mm)))\n")
        status, lines = self.check()
        own = [v for v in self.violations(lines) if v[2] == "clearance" and "sensing keep-out" in v[4]]
        self.assertTrue(own, lines)
        self.assertEqual([v for v in self.violations(lines) if v[2] == "sensing_clearance"], [])

    def test_a_declared_class_that_holds_no_net_fails_so_a_pattern_that_misses_cannot_pass(self):
        # SOL-PRE-ORDER-CHECK-SENSING-CLEARANCE-AND-GROUND-RETURNS.C1: a class the rules would apply to nothing for fails
        def add_class(data):
            quiet = dict(next(c for c in data["net_settings"]["classes"] if c["name"] == "Power"), name="Quiet", priority=9)
            data["net_settings"]["classes"].append(quiet)
        self.seed.project(add_class)
        self.seed.replace("board-rules.yaml", "    - Power\n  clearance_mm", "    - Power\n    - Quiet\n  clearance_mm")
        found, lines = self.found("sensing_clearance")
        self.assertEqual(len(found), 1, lines)
        self.assertIn("the class 'Quiet' holds no net on the layout", found[0][4])

    def test_a_design_that_declares_no_mains_may_still_declare_sensing_classes_and_is_held_to_the_override_rule(self):
        # SOL-PRE-ORDER-CHECK-SENSING-CLEARANCE-AND-GROUND-RETURNS.C1: the clearance-override check gains a sensing figure that does not wait for a signed figure
        with tempfile.TemporaryDirectory(prefix="board-test-") as scratch:
            seed = board_prove.prepare(scratch, "hardware/proof/method-proof", "method-proof")
            seed.write("board-rules.yaml", "sensing:\n  classes:\n    - Supply\n  noisy_classes:\n    - Power\n  clearance_mm: 0.15\n"
                                           "  source: none -- synthetic\nground_returns: none\nfabrication:\n  outer_copper_oz: 1\n  source: none -- synthetic\nsynthetic: true\n")

            def override(tree):
                target = next(pad for footprint in sexpr.children(tree, "footprint") for pad in sexpr.children(footprint, "pad")
                              if board_check.net_of(pad) == "+3V3")
                target.insert(len(target) - 1, ["clearance", "0.05"])
            seed.layout(override)
            status, lines = board_prove.check(seed, KICAD_CLI)[:2]
        found = [line.split(" | ") for line in lines if line.startswith("VIOLATION | ")]
        self.assertEqual(status, 1)
        self.assertTrue([v for v in found if v[2] == "sensing_override" and "+3V3" in v[4]], lines)
        self.assertEqual([v for v in found if v[2] in ("sensing_clearance", "board_rules_record") and "did not load" in v[4]], [])
        self.assertEqual([v for v in found if v[2] == "local_clearance_override"], [], "a design with no signed figure is held by the sensing figure alone")



class EveryTrackedDesignPassesTheSensingAndGroundReturnRules(unittest.TestCase):
    def test_no_design_the_repository_tracks_fails_either_rule_and_each_carries_a_synthetic_board_rules_record(self):
        # SOL-PRE-ORDER-CHECK-SENSING-CLEARANCE-AND-GROUND-RETURNS.C6: Every design git tracks passes the sensing-clearance rule and the ground-return rule, carrying the records they read, synthetic where the design is not for manufacture
        out = io.StringIO()
        board_check.run(board_prove.REPO, KICAD_CLI, out=out)
        lines = out.getvalue().splitlines()
        self.assertGreaterEqual(len([line for line in lines if line.startswith("DESIGN | ")]), 5)
        for rule in SENSING_RULES:
            self.assertEqual([line for line in lines if f" | {rule} | " in line], [], out.getvalue())
        yaml = board_check.require_yaml()
        records = {}
        for path in __import__("glob").glob(os.path.join(board_prove.REPO, "hardware", "proof", "*", "board-rules.yaml")):
            with open(path, encoding="utf-8") as handle:
                records[os.path.basename(os.path.dirname(path))] = yaml.safe_load(handle)
        self.assertEqual(set(records), {"gate-proof", "record-keys-proof", "review-proof", "method-proof", "circuit-review-proof"})
        self.assertTrue(all(record["synthetic"] is True for record in records.values()))
        self.assertIsInstance(records["review-proof"]["sensing"], dict)
        self.assertIsInstance(records["review-proof"]["ground_returns"], dict)
        self.assertTrue(all(record["sensing"] == "none" and record["ground_returns"] == "none"
                            for name, record in records.items() if name != "review-proof"))
        figures = [line for line in lines if line.startswith("FIGURE | ") and "SENSE-6 sensing clearance" in line]
        self.assertEqual(len(figures), 1)
        self.assertIn("review-proof", figures[0])
        self.assertIn("board-rules.yaml sensing.clearance_mm | 0.5 mm", figures[0])

    def test_the_round_learns_a_change_to_the_record_reaches_a_design_through_the_reads_listing(self):
        # SOL-PRE-ORDER-CHECK-SENSING-CLEARANCE-AND-GROUND-RETURNS.C6: A change to a design's board files or to any record these rules read re-runs the board tier of the build round
        result = subprocess.run([sys.executable, os.path.join(TOOLS, "board_check.py"), "--root", board_prove.REPO, "--list-reads"],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        reads = result.stdout.splitlines()
        for design in ("gate-proof", "record-keys-proof", "review-proof", "method-proof", "circuit-review-proof"):
            self.assertIn(f"hardware/proof/{design}/board-rules.yaml", reads)
