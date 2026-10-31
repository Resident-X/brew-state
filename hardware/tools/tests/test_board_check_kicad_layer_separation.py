#!/usr/bin/env python3
"""The pre-order check against KiCad itself, on the throwaway proof design, here the rule holding Mains-class copper apart from low-voltage copper on every layer.

This is one of the files the check's KiCad tests are divided into by topic; the
shared setup, the seeded-fault proof's pooled outcomes and the exclusion of what
needs that proof are in board_kicad_fixtures.py.
"""

from __future__ import annotations

import io
import math
import os
import subprocess
import sys
import tempfile
import time
import unittest

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)

import board_check  # noqa: E402
import board_prove  # noqa: E402
import sexpr  # noqa: E402
from board_kicad_fixtures import KICAD_CLI, load_tests, setUpModule  # noqa: E402,F401
from board_kicad_fixtures import Copy, Proved, outcomes  # noqa: E402

Q = sexpr.Quoted
#: The most the rule's own computation may take, in seconds, on a fill of 50,000 vertices with 360 pieces of mains copper over it.
FIFTY_THOUSAND_VERTEX_BOUND_S = 30


def brief(lines: list) -> list:
    """The failures of a report, each cut short, for a message."""
    return [line[:260] for line in lines if line.startswith(("VIOLATION", "RESULT"))]


def pour(net: str, layer: str, box: tuple, uuid: str, clearance: float = 0.2) -> list:
    """A pour of `net` on `layer` over a box, as (left, top, right, bottom), whose own clearance is `clearance`."""
    left, top, right, bottom = box
    return ["zone", ["net", Q(net)], ["layer", Q(layer)], ["uuid", Q(uuid)], ["hatch", "edge", "0.5"],
            ["connect_pads", ["clearance", f"{clearance:g}"]], ["min_thickness", "0.25"],
            ["fill", ["thermal_gap", "0.5"], ["thermal_bridge_width", "0.5"]],
            ["polygon", ["pts", ["xy", f"{left}", f"{top}"], ["xy", f"{right}", f"{top}"], ["xy", f"{right}", f"{bottom}"],
                         ["xy", f"{left}", f"{bottom}"]]]]


def four_layers_with_pours(seed) -> None:
    """The proof layout with four copper layers and a pour on each: /MAINS_N on the front and In2.Cu round R1 pad 2, and /LV_B on
    In1.Cu and the back round J2 pad 2, the two sets 14 mm apart in plan view."""
    def edit(tree: list) -> None:
        board_prove.four_layers(tree)
        for index, (net, layer, box, clearance) in enumerate((("/MAINS_N", "F.Cu", (23, 4, 28.5, 11), 3), ("/LV_B", "In1.Cu", (38, 12, 46, 18), 0.2),
                                                               ("/MAINS_N", "In2.Cu", (23, 4, 28.5, 11), 3), ("/LV_B", "B.Cu", (38, 12, 46, 18), 0.2))):
            tree.insert(len(tree) - 1, pour(net, layer, box, f"0b0e5c1a-0000-4000-8000-000000001b0{index}", clearance))
    seed.layout(edit)


class TheLayerSeparationRuleRunsDirectly(Copy):
    def rule(self, lines):
        return [v for v in self.violations(lines) if v[2] == board_check.LAYER_RULE]

    def test_a_pair_at_or_above_the_figures_passes_and_the_same_pair_under_them_fails_naming_both(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-APART-FROM-LOW-VOLTAGE-COPPER-ON-EVERY-LAYER.C1: On a throwaway copy of a proof design that declares MAINS present, a low-voltage item on one copper layer (a pour, a track, a via or a pad) whose straight-line plan-view distance to a Mains-class item on a different copper layer is less than the record's mains_to_low_voltage clearance_mm fails as mains_layer_separation naming both items, their layers and nets, and the distance; the same pair at or above the figure passes. Out of scope is a pair on the same layer that KiCad's own rule already reports.
        board_prove.inner_copper_beside_mains(self.seed)
        status, lines = self.check()
        self.assertEqual(status, 1, brief(lines))
        (clearance,) = [v for v in self.rule(lines) if "; clearance" in v[3]]
        for words in ("Track [/MAINS_N] on F.Cu", "Track [/LV_A] on In1.Cu", "2.250 mm", "3 mm"):
            self.assertIn(words, clearance[4])
        self.assertIn("gate-proof.kicad_pro | FAIL", "\n".join(lines))

    def test_the_same_pair_at_the_figures_passes(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-APART-FROM-LOW-VOLTAGE-COPPER-ON-EVERY-LAYER.C1: On a throwaway copy of a proof design that declares MAINS present, a low-voltage item on one copper layer (a pour, a track, a via or a pad) whose straight-line plan-view distance to a Mains-class item on a different copper layer is less than the record's mains_to_low_voltage clearance_mm fails as mains_layer_separation naming both items, their layers and nets, and the distance; the same pair at or above the figure passes. Out of scope is a pair on the same layer that KiCad's own rule already reports.
        def edit(tree: list) -> None:
            board_prove.four_layers(tree)
            tree.insert(len(tree) - 1, board_prove.segment("/MAINS_N", 30, 1.5, 36, 1.5, board_prove.LAYER_MAINS_UUID))
            tree.insert(len(tree) - 1, board_prove.segment("/LV_A", 30, 6, 36, 6, board_prove.LAYER_OTHER_UUID, "In1.Cu"))
        self.seed.layout(edit)
        status, lines = self.check()
        self.assertEqual(self.rule(lines), [], brief(lines))

    def test_a_same_layer_pair_is_reported_once_by_kicad_and_not_by_the_rule(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-APART-FROM-LOW-VOLTAGE-COPPER-ON-EVERY-LAYER.C1: On a throwaway copy of a proof design that declares MAINS present, a low-voltage item on one copper layer (a pour, a track, a via or a pad) whose straight-line plan-view distance to a Mains-class item on a different copper layer is less than the record's mains_to_low_voltage clearance_mm fails as mains_layer_separation naming both items, their layers and nets, and the distance; the same pair at or above the figure passes. Out of scope is a pair on the same layer that KiCad's own rule already reports.
        def edit(tree: list) -> None:
            board_prove.four_layers(tree)
            tree.insert(len(tree) - 1, board_prove.segment("/MAINS_N", 12, 2.5, 18, 2.5, board_prove.LAYER_MAINS_UUID))
            tree.insert(len(tree) - 1, board_prove.segment("/LV_A", 12, 5, 18, 5, board_prove.LAYER_OTHER_UUID))
        self.seed.layout(edit)
        status, lines = self.check()
        self.assertEqual(status, 1, brief(lines))
        self.assertEqual(self.rule(lines), [], brief(lines))
        self.assertTrue([v for v in self.violations(lines) if v[2] == "clearance"], brief(lines))

    def test_an_exception_accepts_the_clearance_of_its_pair_at_or_above_its_distance_and_leaves_the_creepage(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-APART-FROM-LOW-VOLTAGE-COPPER-ON-EVERY-LAYER.C6: On a throwaway copy of a proof design with a synthetic signed record, a cross-layer shortfall between the two pads or nets a between entry of pair mains_to_low_voltage names is accepted and reported when its distance is at least accepted_mm and fails as spacing_exception naming the entry when less, a shortfall between any other pair stays a mains_layer_separation failure, and an entry that no shortfall uses fails. Out of scope is the signing of any entry.
        board_prove.inner_copper_beside_mains(self.seed)
        board_prove.exceptions(board_prove.exception_entry("mains_to_low_voltage", "clearance", ("/MAINS_N", "/LV_A"), 2.0))(self.seed)
        status, lines = self.check()
        accepted = [line for line in lines if line.startswith("ACCEPTED | ")]
        self.assertEqual(len(accepted), 1, brief(lines))
        self.assertIn("mains_to_low_voltage clearance between /MAINS_N and /LV_A", accepted[0])
        self.assertIn("measures 2.25 mm", accepted[0])
        self.assertEqual([v for v in self.violations(lines) if v[2] == "spacing_exception"], [], brief(lines))
        self.assertEqual([v[3].rsplit("; ", 1)[1] for v in self.rule(lines)], ["creepage"])

    def test_an_entry_that_no_shortfall_uses_fails_and_a_pair_it_does_not_name_stays_a_layer_failure(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-APART-FROM-LOW-VOLTAGE-COPPER-ON-EVERY-LAYER.C6: On a throwaway copy of a proof design with a synthetic signed record, a cross-layer shortfall between the two pads or nets a between entry of pair mains_to_low_voltage names is accepted and reported when its distance is at least accepted_mm and fails as spacing_exception naming the entry when less, a shortfall between any other pair stays a mains_layer_separation failure, and an entry that no shortfall uses fails. Out of scope is the signing of any entry.
        board_prove.inner_copper_beside_mains(self.seed)
        board_prove.exceptions(board_prove.exception_entry("mains_to_low_voltage", "clearance", ("/MAINS_L", "/LV_B"), 2.0))(self.seed)
        status, lines = self.check()
        self.assertEqual(status, 1, brief(lines))
        self.assertEqual([line for line in lines if line.startswith("ACCEPTED | ")], [])
        (unused,) = [v for v in self.violations(lines) if v[2] == "spacing_exception"]
        self.assertIn("reports no shortfall", unused[4])
        self.assertEqual(sorted(v[3].rsplit("; ", 1)[1] for v in self.rule(lines)), ["clearance", "creepage"])

    def test_a_record_with_no_mapping_fails_under_its_own_name_and_the_rule_does_not_pass_it(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-APART-FROM-LOW-VOLTAGE-COPPER-ON-EVERY-LAYER.C7: On throwaway proof designs, a design that declares MAINS present and whose record has no mains_to_low_voltage mapping, or whose Mains net class cannot be resolved from the project, fails under the existing names and is not passed by the new rule; a design that declares no MAINS is not held by the rule. Out of scope is the wording of the existing failures.
        board_prove.inner_copper_beside_mains(self.seed)
        board_prove.record("mains_to_low_voltage:\n  clearance_mm: 3.0\n  creepage_mm: 4.0\n", "")(self.seed)
        status, lines = self.check()
        self.assertEqual(status, 1, brief(lines))
        self.assertTrue([v for v in self.violations(lines) if v[2] == "separation_basis"], brief(lines))
        self.assertEqual(self.rule(lines), [])

    def test_a_mains_class_with_no_net_fails_under_its_own_name_and_the_rule_has_nothing_to_hold(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-APART-FROM-LOW-VOLTAGE-COPPER-ON-EVERY-LAYER.C7: On throwaway proof designs, a design that declares MAINS present and whose record has no mains_to_low_voltage mapping, or whose Mains net class cannot be resolved from the project, fails under the existing names and is not passed by the new rule; a design that declares no MAINS is not held by the rule. Out of scope is the wording of the existing failures.
        board_prove.inner_copper_beside_mains(self.seed)
        self.seed.project(lambda data: board_prove.no_mains_patterns(data))
        status, lines = self.check()
        self.assertEqual(status, 1, brief(lines))
        self.assertTrue([v for v in self.violations(lines) if v[2] == "mains_declaration"], brief(lines))
        self.assertEqual(self.rule(lines), [])

    def test_a_design_that_declares_no_mains_is_not_held_by_the_rule(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-APART-FROM-LOW-VOLTAGE-COPPER-ON-EVERY-LAYER.C7: On throwaway proof designs, a design that declares MAINS present and whose record has no mains_to_low_voltage mapping, or whose Mains net class cannot be resolved from the project, fails under the existing names and is not passed by the new rule; a design that declares no MAINS is not held by the rule. Out of scope is the wording of the existing failures.
        board_prove.inner_copper_beside_mains(self.seed)
        board_prove.variables(lambda values: values.update(MAINS="none"))(self.seed)
        status, lines = self.check()
        self.assertEqual(self.rule(lines), [], brief(lines))

    def test_the_rule_adds_no_kicad_run_and_passes_a_board_poured_on_four_layers(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-APART-FROM-LOW-VOLTAGE-COPPER-ON-EVERY-LAYER.C9: On a throwaway proof design carrying filled ground and mains pours on four copper layers, the check including the new rule adds no KiCad run to the existing one, the rule's own computation finishes within a stated time bound on a synthetic fill of 50,000 vertices, and the existing test that a hung KiCad run still fails the design stands. Out of scope is the limit's value.
        four_layers_with_pours(self.seed)
        board_prove.git(self.seed, "add", "-A")
        board_prove.git(self.seed, "commit", "-q", "--allow-empty", "-m", "seeded copy")
        counts = {"run_kicad": 0, "run_report": 0}
        real = {name: getattr(board_check, name) for name in counts}
        real_rule = board_check.layer_separation
        ran = []

        def counted(name):
            def run(*args, **kwargs):
                counts[name] += 1
                return real[name](*args, **kwargs)
            return run

        def run_check(rule):
            for name in counts:
                counts[name] = 0
                setattr(board_check, name, counted(name))
            board_check.layer_separation = rule
            out = io.StringIO()
            try:
                status = board_check.run(self.seed.root, KICAD_CLI, out=out)
            finally:
                for name in counts:
                    setattr(board_check, name, real[name])
                board_check.layer_separation = real_rule
            return status, out.getvalue().splitlines(), dict(counts)

        def watched(*args, **kwargs):
            ran.append(args)
            return real_rule(*args, **kwargs)

        status, lines, with_rule = run_check(watched)
        self.assertTrue(ran, "the rule did not run")
        _, _, without = run_check(lambda *args, **kwargs: board_check.LayerResult())
        self.assertEqual(with_rule, without)
        self.assertGreater(with_rule["run_report"], 0)
        self.assertEqual(status, 0, brief(lines))

    def test_the_rule_finishes_within_its_bound_on_a_fill_of_fifty_thousand_vertices(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-APART-FROM-LOW-VOLTAGE-COPPER-ON-EVERY-LAYER.C9: On a throwaway proof design carrying filled ground and mains pours on four copper layers, the check including the new rule adds no KiCad run to the existing one, the rule's own computation finishes within a stated time bound on a synthetic fill of 50,000 vertices, and the existing test that a hung KiCad run still fails the design stands. Out of scope is the limit's value.
        count = 50000
        ring = " ".join(f"(xy {50 + 40 * math.cos(2 * math.pi * i / count):.4f} {50 + 40 * math.sin(2 * math.pi * i / count):.4f})"
                        for i in range(count))
        fill = (f'(zone (net "/LV_B") (layer "In1.Cu") (polygon (pts (xy 0 0) (xy 100 0) (xy 100 100) (xy 0 100))) '
                f'(filled_polygon (layer "In1.Cu") (pts {ring})))')
        tracks = " ".join(
            f'(segment (start {5 + 0.5 * i} {y}) (end {5.4 + 0.5 * i} {y + 0.3}) (width 0.25) (layer "{layer}") (net "/MAINS_N"))'
            for i in range(180) for y, layer in ((50, "F.Cu"), (48, "B.Cu")))
        tree = sexpr.parse_one(f'(kicad_pcb (version 20260206) (layers (0 "F.Cu" signal) (4 "In1.Cu" signal) (6 "In2.Cu" signal) '
                               f'(2 "B.Cu" signal)) {fill} {tracks})')
        started = time.monotonic()
        result = board_check.layer_separation(tree, {"/MAINS_N"}, 3.0, 4.0)
        elapsed = time.monotonic() - started
        self.assertTrue(result.findings)
        self.assertLess(elapsed, FIFTY_THOUSAND_VERTEX_BOUND_S)


class TheLayerSeparationRows(Proved):
    """Each failure of the rule fails on a fault seeded for it in a throwaway copy of the proof design."""

    #: The seeded faults the proof must hold, each with the rule that must report it and the words its line must carry.
    FAULTS = {
        "a low-voltage track on an inner layer within the clearance in plan view of a mains track on the front":
            ("mains_layer_separation", ("clearance: Track [/MAINS_N] on F.Cu", "Track [/LV_A] on In1.Cu", "2.250 mm")),
        "a path round a slot between mains copper and low-voltage copper on other layers under the creepage":
            ("mains_layer_separation", ("creepage: the shortest path", "round 1 slot", "Track [/LV_A] on B.Cu")),
        "inner-layer copper within 1.5 mm of a slot wall":
            ("mains_layer_separation", ("pull-back: Track [/LV_A] on In1.Cu", "0.875 mm", "the wall of the cut-out")),
        "a low-voltage pour on an inner layer under a mains track on the front":
            ("mains_layer_separation", ("overlap: Track [/MAINS_N] on F.Cu", "Zone [/LV_A] on In1.Cu")),
        "an excepted pair below the distance its exception accepts":
            ("spacing_exception", ("accepts mains_to_low_voltage clearance between /MAINS_N and /LV_A down to 2.4 mm", "leaves 2.25 mm")),
    }

    def test_each_failure_is_caught_on_a_seeded_fault_under_the_rule_named_for_it(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-APART-FROM-LOW-VOLTAGE-COPPER-ON-EVERY-LAYER.C8: The seeded-fault rows of the proof run gain one fault for each of the plan-view clearance across layers, the creepage round a slot, the slot-wall pull-back, the overlap and the excepted-pair shortfall below its accepted distance, each run on a throwaway copy of a proof design and shown to fail the check by name, with the unseeded copy passing. Out of scope is a seeded fault on any tracked design.
        self.assertCaught(*self.FAULTS)
        found = outcomes()
        for name, (rule, words) in self.FAULTS.items():
            with self.subTest(fault=name):
                fields = found[name][1].split(" | ")
                self.assertEqual((fields[1], fields[2]), ("hardware/proof/gate-proof/gate-proof.kicad_pro", rule))
                for word in words:
                    self.assertIn(word, found[name][1])
                self.assertEqual([entry[2] for entry in board_prove.FAULTS if entry[0] == name], [rule])


class TheLayerSeparationRowsOfTheProof(unittest.TestCase):
    """The rows the proof holds for the rule, read without running it."""

    def test_the_proof_holds_one_row_for_each_of_the_five_failures_and_leaves_the_other_rules_their_rows(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-APART-FROM-LOW-VOLTAGE-COPPER-ON-EVERY-LAYER.C8: The seeded-fault rows of the proof run gain one fault for each of the plan-view clearance across layers, the creepage round a slot, the slot-wall pull-back, the overlap and the excepted-pair shortfall below its accepted distance, each run on a throwaway copy of a proof design and shown to fail the check by name, with the unseeded copy passing. Out of scope is a seeded fault on any tracked design.
        rows = [fault for fault in board_prove.FAULTS if fault[1].startswith("layer separation:")]
        self.assertEqual(sorted(fault[0] for fault in rows), sorted(TheLayerSeparationRows.FAULTS))
        self.assertEqual(len(rows), 5)
        self.assertEqual({board_prove.target_of(fault) for fault in rows}, {(board_prove.DESIGN, board_prove.NAME)})
        for prefix, count in (("mounting holes:", 5), ("separation floor:", 4), ("mains to mains:", 8)):
            with self.subTest(prefix=prefix):
                self.assertEqual(len([fault for fault in board_prove.FAULTS if fault[1].startswith(prefix)]), count)

    def test_every_row_seeds_a_copy_and_the_tracked_design_gains_no_inner_layer(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-APART-FROM-LOW-VOLTAGE-COPPER-ON-EVERY-LAYER.C8: The seeded-fault rows of the proof run gain one fault for each of the plan-view clearance across layers, the creepage round a slot, the slot-wall pull-back, the overlap and the excepted-pair shortfall below its accepted distance, each run on a throwaway copy of a proof design and shown to fail the check by name, with the unseeded copy passing. Out of scope is a seeded fault on any tracked design.
        with tempfile.TemporaryDirectory(prefix="board-test-") as scratch:
            seed = board_prove.prepare(scratch)
            board_prove.inner_copper_beside_mains(seed)
            tree = sexpr.parse_one(seed.read(".kicad_pcb"))
            self.assertEqual(board_check.copper_layers(tree), ["F.Cu", "In1.Cu", "In2.Cu", "B.Cu"])
        with open(os.path.join(board_prove.REPO, board_prove.DESIGN, "gate-proof.kicad_pcb"), encoding="utf-8") as handle:
            self.assertNotIn("In1.Cu", handle.read())


class TheRuleKeepsEveryTrackedDesignPassing(unittest.TestCase):
    """Every design the repository tracks is run through the rule, and none is excused by anything in the rule's code."""

    def test_every_tracked_design_passes_the_rule_and_the_report_lists_none_it_fails(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-APART-FROM-LOW-VOLTAGE-COPPER-ON-EVERY-LAYER.C11: The rule runs in the board tier on every tracked design that declares MAINS present, each passes, and the build report names each design the rule fails with the pairs it reports, none being silenced by an exception in the rule's code. Out of scope is correcting a failing layout, which the owning layout leaf does.
        tracked = sorted(subprocess.run(["git", "ls-files", "*.kicad_pro"], cwd=board_prove.REPO, capture_output=True,
                                        text=True, check=True).stdout.split())
        self.assertTrue(tracked)
        for project in tracked:
            design = os.path.dirname(project)
            name = os.path.basename(design)
            with self.subTest(design=name), tempfile.TemporaryDirectory(prefix="board-test-") as scratch:
                seed = board_prove.prepare(scratch, design, name)
                status, lines, stderr = board_prove.check(seed, KICAD_CLI)
                self.assertNotEqual(status, 2, stderr)
                self.assertEqual([line for line in lines if board_check.LAYER_RULE in line], [], brief(lines))
                self.assertEqual(status, 0, brief(lines))

    def test_a_design_the_rule_fails_is_listed_by_name_with_its_pair_though_it_is_a_fixture(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-APART-FROM-LOW-VOLTAGE-COPPER-ON-EVERY-LAYER.C11: The rule runs in the board tier on every tracked design that declares MAINS present, each passes, and the build report names each design the rule fails with the pairs it reports, none being silenced by an exception in the rule's code. Out of scope is correcting a failing layout, which the owning layout leaf does.
        with tempfile.TemporaryDirectory(prefix="board-test-") as scratch:
            seed = board_prove.prepare(scratch)
            board_prove.pour_under_mains(seed)
            status, lines, stderr = board_prove.check(seed, KICAD_CLI)
        self.assertEqual(status, 1, stderr)
        self.assertIn("DESIGN | hardware/proof/gate-proof/gate-proof.kicad_pro | FAIL", "\n".join(lines))
        (overlap,) = [line for line in lines if board_check.LAYER_RULE in line and "overlap:" in line]
        self.assertIn("Track [/MAINS_N] on F.Cu", overlap)
        self.assertIn("Zone [/LV_A] on In1.Cu", overlap)


if __name__ == "__main__":
    unittest.main()
