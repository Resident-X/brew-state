#!/usr/bin/env python3
"""The pre-order check against KiCad itself, on the throwaway proof design, here the board minimums and lifecycle rules.

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
from board_kicad_fixtures import load_tests, setUpModule  # noqa: E402,F401
from board_kicad_fixtures import Copy, KICAD_CLI, Proved, outcomes  # noqa: E402



MINIMUMS_FAULT_PREFIXES = ("board minimums:", "lifecycle:")


MINIMUMS_FAULT_PREFIXES = ("board minimums:", "lifecycle:")
MINIMUMS_RULES = ("board_minimums", "board_rules_record", "manufacturer_limits_record", "parts_lifecycle")



class BoardMinimumsAndLifecycleProof(Proved):
    def test_each_minimums_and_lifecycle_fault_is_caught_on_a_copy_of_the_proof_design_and_the_committed_design_stays_passing(self):
        # SOL-PRE-ORDER-CHECK-DATED-RECORDS-MINIMUMS-AND-LIFECYCLE.C5: The on-demand seeded-fault proof introduces into a copy of a throwaway design, outside the tracked tree, a track-width minimum looser than its process's limit, a design whose process the record does not list, a design whose board rules record declares no outer copper weight, a record older than its max_age_days, a part whose lifecycle status is end of life and a part whose catalogue entry lacks its lifecycle mapping, and requires the check to fail each
        # OBL-VERIFICATION-DISCIPLINE-001.C9: A check is shown to fail on the defect it exists to catch rather than asserted to be capable of it
        faults = [fault for fault in board_prove.FAULTS if fault[1].startswith(MINIMUMS_FAULT_PREFIXES)]
        self.assertEqual(len(faults), 6)
        self.assertEqual({board_prove.target_of(fault) for fault in faults}, {(board_prove.DESIGN, board_prove.NAME)},
                         "seeded into a copy of the throwaway gate proof design")
        self.assertEqual({fault[2] for fault in faults}, set(MINIMUMS_RULES))
        wanted = {
            "min_track_width is 0.05 mm, looser than the manufacturer's": "board_minimums",
            "a process hardware/proof/manufacturer-limits.yaml does not list": "board_minimums",
            "fabrication lacks outer_copper_oz": "board_rules_record",
            "past the 30 days it allows itself": "manufacturer_limits_record",
            "has the lifecycle status 'end of life'": "parts_lifecycle",
            "has no lifecycle in the catalogue extract": "parts_lifecycle",
        }
        for words, rule in wanted.items():
            with self.subTest(fault=words):
                self.assertTrue(any(words in fault[3] and fault[2] == rule for fault in faults), words)
        self.assertCaught(*[fault[0] for fault in faults])

    def test_a_seeded_minimums_or_lifecycle_fault_names_the_fault_and_the_rule_in_the_record_of_the_run(self):
        # SOL-PRE-ORDER-CHECK-DATED-RECORDS-MINIMUMS-AND-LIFECYCLE.C5: the record of each seeded run naming the fault and the rule that caught it
        # SOL-PRE-ORDER-CHECK-DATED-RECORDS-MINIMUMS-AND-LIFECYCLE.C4: A failure of any rule in this leaf is reported with the rule's name, the design, and the offending item
        for fault in board_prove.FAULTS:
            if fault[1].startswith(MINIMUMS_FAULT_PREFIXES):
                caught, evidence = outcomes()[fault[0]]
                self.assertTrue(caught, evidence)
                self.assertIn(f" | {fault[2]} | ", evidence)
                self.assertIn("hardware/proof/gate-proof/gate-proof.kicad_pro", evidence)
                self.assertIn(fault[3], evidence)



class TheProofCopyCarriesTheSharedLimitsRecord(unittest.TestCase):
    def test_the_proof_copy_carries_the_shared_limits_record_so_it_is_held_to_it_as_the_committed_design_is(self):
        # SOL-PRE-ORDER-CHECK-DATED-RECORDS-MINIMUMS-AND-LIFECYCLE.C5: introduces into a copy of a throwaway design, outside the tracked tree; the committed proof design stays passing
        with tempfile.TemporaryDirectory(prefix="board-test-") as scratch:
            seed = board_prove.prepare(scratch)
            self.assertTrue(os.path.isfile(os.path.join(seed.root, "hardware", "proof", "manufacturer-limits.yaml")))
            self.assertNotIn("manufacturer-limits.yaml", seed.files, "the shared record sits above the design's folder")
            status, lines = board_prove.check(seed, KICAD_CLI)[:2]
        self.assertEqual(status, 0, lines)



class MinimumsCopy(Copy):
    """A fresh copy of the throwaway proof design, which the minimums and lifecycle rules are driven on directly."""

    def found(self, rule):
        status, lines = self.check()
        return [v for v in self.violations(lines) if v[2] == rule], lines



class TheMinimumsAndLifecycleRulesRunOnTheShippedCheck(MinimumsCopy):
    def test_a_custom_rule_that_sets_a_minimum_looser_than_the_limit_fails_naming_the_rule_and_its_line(self):
        # SOL-PRE-ORDER-CHECK-DATED-RECORDS-MINIMUMS-AND-LIFECYCLE.C1: The rule fails a board whose any minimum a custom rule sets is looser than its process's limit
        # SOL-PRE-ORDER-CHECK-DATED-RECORDS-MINIMUMS-AND-LIFECYCLE.C4: Every failure names the rule, the design and the offending item
        self.seed.write(".kicad_dru", self.seed.read(".kicad_dru") + '(rule "thin tracks"\n\t(constraint track_width (min 0.05mm)))\n')
        found, lines = self.found("board_minimums")
        self.assertEqual(len(found), 1, lines)
        self.assertEqual(found[0][1], "hardware/proof/gate-proof/gate-proof.kicad_pro")
        self.assertIn("gate-proof.kicad_dru rule 'thin tracks' at line", found[0][3])
        self.assertIn("sets a track_width minimum of 0.05 mm, looser than the manufacturer's", found[0][4])

    def test_a_net_class_looser_than_the_limit_fails_naming_the_class_and_the_figure(self):
        # SOL-PRE-ORDER-CHECK-DATED-RECORDS-MINIMUMS-AND-LIFECYCLE.C1: The rule fails a board whose each net class's clearance and track width is looser than its process's limit
        def loosen(data):
            next(c for c in data["net_settings"]["classes"] if c["name"] == "Default")["track_width"] = 0.05
        self.seed.project(loosen)
        found, lines = self.found("board_minimums")
        self.assertEqual(len(found), 1, lines)
        self.assertIn("net_settings.classes 'Default' track_width", found[0][3])
        self.assertIn("the net class Default has a track_width of 0.05 mm", found[0][4])

    def test_a_board_setup_minimum_the_record_bounds_that_the_project_does_not_state_fails_naming_the_key(self):
        # SOL-PRE-ORDER-CHECK-DATED-RECORDS-MINIMUMS-AND-LIFECYCLE.C1: The rule fails a board-setup minimum the record bounds that the project file does not state
        self.seed.project(lambda data: data["board"]["design_settings"]["rules"].pop("min_hole_to_hole"))
        found, lines = self.found("board_minimums")
        self.assertEqual(len(found), 1, lines)
        self.assertIn("board.design_settings.rules.min_hole_to_hole", found[0][3])
        self.assertIn("states no min_hole_to_hole", found[0][4])

    def test_a_synthetic_limits_record_applied_to_an_orderable_board_fails(self):
        # SOL-PRE-ORDER-CHECK-DATED-RECORDS-MINIMUMS-AND-LIFECYCLE.C1: The rule fails a synthetic record applied to an orderable board
        self.seed.project(lambda data: data["text_variables"].update(NOT_FOR_MANUFACTURE="false"))
        found, lines = self.found("manufacturer_limits_record")
        self.assertEqual(len(found), 1, lines)
        self.assertIn("manufacturer-limits.yaml synthetic", found[0][3])
        self.assertIn("a proof record cannot let it pass", found[0][4])

    def test_a_design_with_no_limits_record_in_any_folder_above_it_fails(self):
        # SOL-PRE-ORDER-CHECK-DATED-RECORDS-MINIMUMS-AND-LIFECYCLE.C1: The rule fails a design with no usable record
        os.remove(os.path.join(self.seed.root, "hardware", "proof", "manufacturer-limits.yaml"))
        found, lines = self.found("manufacturer_limits_record")
        self.assertEqual(len(found), 1, lines)
        self.assertIn("no manufacturer-limits.yaml in the design's folder or any folder above it", found[0][4])
        self.assertEqual([v for v in self.violations(lines) if v[2] == "board_minimums"], [], "no record, so nothing to compare is not judged twice")

    def test_a_placed_part_whose_status_is_not_recommended_for_new_designs_fails_naming_the_position(self):
        # SOL-PRE-ORDER-CHECK-DATED-RECORDS-MINIMUMS-AND-LIFECYCLE.C2: A part whose catalogue lifecycle is end of life, obsolete or not recommended for new designs fails
        self.seed.replace("catalogue-extract.yaml", "lifecycle:\n      status: active", "lifecycle:\n      status: not recommended for new designs")
        found, lines = self.found("parts_lifecycle")
        self.assertTrue(found, lines)
        self.assertTrue(all("lifecycle status 'not recommended for new designs'" in v[4] for v in found), found)



class EveryTrackedDesignPassesTheMinimumsAndLifecycleRules(unittest.TestCase):
    def test_no_design_the_repository_tracks_fails_either_rule_and_each_carries_the_records_they_read(self):
        # SOL-PRE-ORDER-CHECK-DATED-RECORDS-MINIMUMS-AND-LIFECYCLE.C6: Every design git tracks passes the board-minimums rule and the lifecycle rule, carrying the records they read, synthetic where the design is not for manufacture
        out = io.StringIO()
        board_check.run(board_prove.REPO, KICAD_CLI, out=out)
        lines = out.getvalue().splitlines()
        self.assertGreaterEqual(len([line for line in lines if line.startswith("DESIGN | ")]), 5)
        for rule in MINIMUMS_RULES + ("parts_record", "parts_catalogue"):
            self.assertEqual([line for line in lines if f" | {rule} | " in line], [], out.getvalue())
        yaml = board_check.require_yaml()
        with open(os.path.join(board_prove.REPO, "hardware", "proof", "manufacturer-limits.yaml"), encoding="utf-8") as handle:
            shared = yaml.safe_load(handle)
        self.assertIs(shared["synthetic"], True)
        self.assertEqual({(p["copper_layers"], p["outer_copper_oz"]) for p in shared["processes"]}, {(2, 1), (4, 1)})
        for path in __import__("glob").glob(os.path.join(board_prove.REPO, "hardware", "proof", "*", "board-rules.yaml")):
            with open(path, encoding="utf-8") as handle:
                record = yaml.safe_load(handle)
            self.assertEqual(record["fabrication"]["outer_copper_oz"], 1, path)
            self.assertTrue(record["fabrication"]["source"].strip(), path)
        for path in __import__("glob").glob(os.path.join(board_prove.REPO, "hardware", "proof", "*", "catalogue-extract.yaml")):
            with open(path, encoding="utf-8") as handle:
                entries = yaml.safe_load(handle)["entries"]
            self.assertTrue(all(set(entry["lifecycle"]) == {"status", "source", "read_on"} for entry in entries), path)

    def test_the_round_learns_a_change_to_the_limits_record_reaches_a_design_through_the_reads_listing(self):
        # SOL-PRE-ORDER-CHECK-DATED-RECORDS-MINIMUMS-AND-LIFECYCLE.C6: A change to a design's board files or to any record these rules read re-runs the board tier of the build round
        result = subprocess.run([sys.executable, os.path.join(TOOLS, "board_check.py"), "--root", board_prove.REPO, "--list-reads"],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        reads = result.stdout.splitlines()
        self.assertIn("hardware/proof/manufacturer-limits.yaml", reads)
        for design in ("gate-proof", "record-keys-proof", "review-proof", "method-proof", "circuit-review-proof"):
            self.assertIn(f"hardware/proof/{design}/catalogue-extract.yaml", reads)
            self.assertIn(f"hardware/proof/{design}/board-rules.yaml", reads)

    def test_the_reads_listings_description_names_the_manufacturer_limits_record(self):
        # SOL-PRE-ORDER-CHECK-DATED-RECORDS-MINIMUMS-AND-LIFECYCLE.C6: The board-reads listing's description names every record a design is held to, including the manufacturer limits record this leaf adds
        with open(os.path.join(board_prove.REPO, "Taskfile.yml"), encoding="utf-8") as handle:
            lines = handle.read().splitlines()
        start = lines.index("  hw:reads:")
        description = next(line for line in lines[start:] if line.strip().startswith("desc:"))
        for record in ("separation basis", "pin allocation", "parts specification", "catalogue extract", "derating policy", "pin-limit",
                       "board rules", "manufacturer limits"):
            self.assertIn(record, description)
