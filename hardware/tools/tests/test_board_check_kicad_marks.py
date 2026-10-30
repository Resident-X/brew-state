#!/usr/bin/env python3
"""The pre-order check against KiCad itself, on the throwaway proof design, here the barrier, paste and pour rules, decoupling and silkscreen, test pad courtyards, fiducials and polarity marks.

This is one of the files the check's KiCad tests are divided into by topic; the
shared setup, the seeded-fault proof's pooled outcomes and the exclusion of what
needs that proof are in board_kicad_fixtures.py.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest


TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)

import board_prove  # noqa: E402
from board_kicad_fixtures import load_tests, setUpModule  # noqa: E402,F401
from board_kicad_fixtures import Copy, KICAD_CLI, Proved, SharedCopy, outcomes  # noqa: E402



class TheBarrierPasteAndPourRules(Proved):
    # SOL-BOARD-REVIEW-PROOF-BASELINE-CLEAN.C3: Each rule the proof design's review adds fails on a fault seeded for it and passes the clean design
    """Copper under a part that bridges the mains barrier, solder paste over a
    via's hole and a pour stopping short of copper of its own net each fail on
    a fault seeded for it in a throwaway copy of the gate's proof design.
    """

    def test_each_rule_fails_on_its_seeded_fault(self):
        # SOL-BOARD-REVIEW-PROOF-BASELINE-CLEAN.C3: Each rule the proof design's review adds fails on a fault seeded for it and passes the clean design
        self.assertCaught("a track under a part that joins mains to low voltage", "a via drilled through the paste of a pad",
                          "a pour stopping short of a track of its own net")
        rules = {fault[2] for fault in board_prove.FAULTS if fault[1].startswith(("separation: no copper", "manufacture:"))}
        self.assertGreaterEqual(rules, {"mains_barrier", "paste_via", "pour_gap"})

    def test_a_missing_or_malformed_figure_of_either_measured_area_fails_by_name(self):
        # SOL-BOARD-REVIEW-PROOF-BASELINE-CLEAN.C3: Each rule the proof design's review adds fails on a fault seeded for it and passes the clean design
        self.assertCaught("a barrier rule with no figure", "a paste rule with a figure written with a unit")

    def test_a_part_the_barrier_rule_cannot_measure_and_a_missing_rule_each_fail_by_name(self):
        # SOL-BOARD-REVIEW-PROOF-BASELINE-CLEAN.C3: Each rule the proof design's review adds fails on a fault seeded for it and passes the clean design
        self.assertCaught("a part whose Mains-class and other pads overlap on both axes",
                          "a part whose only pads off the Mains class have no net",
                          "a crystal on a board whose rules file has no keep-clear",
                          "a crystal keep-clear that exempts every other part",
                          "a second crystal's keep-clear followed by a rule naming the first crystal as B with ==",
                          "a rule with A.Reference != the first crystal at 0mm on a board of two crystals",
                          "a ground class on a board whose rules file has no relief rule",
                          "a relief rule exempting a pad that is not an exposed pad")

    def test_a_no_connect_pad_and_a_pad_on_a_mains_net_with_no_number_leave_the_part_measured(self):
        # SOL-PRE-ORDER-CHECK-MAINS-BARRIER-IGNORES-PADS-THAT-CARRY-NO-NET.C12: The seeded-fault harness holds a row on the throwaway proof design's bridging part with a no-connect pad added beside a mains pad and copper under the part, and the check reports mains_barrier.
        # SOL-PRE-ORDER-CHECK-MAINS-BARRIER-IGNORES-PADS-THAT-CARRY-NO-NET.C13: The seeded-fault harness holds a row on the throwaway proof design's bridging part with a pad on a Mains-class net given no number and copper under the part, and the check reports mains_barrier.
        names = ("a no-connect pad beside a mains pad of a part with copper under it",
                 "a pad on a Mains-class net given no number with copper under the part")
        self.assertCaught(*names)
        found = outcomes()
        for name in names:
            with self.subTest(fault=name):
                self.assertEqual(found[name][1].split(" | ")[2], "mains_barrier")

    def test_each_failure_names_where_on_the_board_it_is(self):
        # SOL-BOARD-REVIEW-PROOF-BASELINE-CLEAN.C3: Each rule the proof design's review adds fails on a fault seeded for it and passes the clean design
        found = outcomes()
        for name in ("a track under a part that joins mains to low voltage", "a via drilled through the paste of a pad",
                     "a pour stopping short of a track of its own net"):
            with self.subTest(fault=name):
                caught, line = found[name]
                self.assertTrue(caught, line)
                self.assertRegex(line.split(" | ")[3], r"\(\d+(\.\d+)?, \d+(\.\d+)?\) mm")



class TheDecouplingAndSilkscreenRules(Proved):
    # SOL-BOARD-METHOD-FOLLOWABLE-AND-MACHINE-FREE.C3: Each rule the method proof design's review adds fails on a fault seeded for it and passes the clean design
    """A via between a decoupling capacitor and the pin it decouples, and a
    reference designator off the silkscreen each fail on a fault seeded for it
    in a throwaway copy of the gate's proof design.
    """

    FAULTS = {"a via between a decoupling capacitor's supply pad and the pin it decouples": "decoupling_via",
              "an integrated circuit with netted pads and no pad typed as a power pin on a design not marked not for manufacture": "decoupling_pintype",
              "an in-list category on an integrated circuit with a pad typed power input": "decoupling_pintype",
              "a category outside the list on an integrated circuit with netted pads and none typed power": "decoupling_pintype",
              "a reference designator on the fabrication layer": "reference_off_silkscreen",
              "a part with no reference text": "reference_off_silkscreen",
              "a reference designator inside a part's courtyard": "designator_astray"}

    def test_each_rule_fails_on_its_seeded_fault_and_names_where(self):
        # SOL-BOARD-REVIEW-LOOP-PROPORTIONATE.C5: Each of the three designs under hardware/proof passes the rule before it lands, and a seeded fault shows it fails.
        # SOL-BOARD-METHOD-FOLLOWABLE-AND-MACHINE-FREE.C3: Each rule the method proof design's review adds fails on a fault seeded for it and passes the clean design
        self.assertCaught(*self.FAULTS)
        found = outcomes()
        for name, rule in self.FAULTS.items():
            with self.subTest(fault=name):
                fields = found[name][1].split(" | ")
                self.assertEqual(fields[2], rule)
                self.assertRegex(fields[3], r"\(\d+(\.\d+)?, \d+(\.\d+)?\) mm")
        self.assertEqual({fault[2] for fault in board_prove.FAULTS if fault[0] in self.FAULTS}, set(self.FAULTS.values()))



class TheTestPadCourtyardRule(Proved):
    """A test point seeded inside a part's courtyard fails the rule in a throwaway copy of the gate's proof design."""

    FAULT = "a test point seeded inside a part's courtyard"

    def test_the_rule_fails_on_its_seeded_fault_and_names_the_test_point_the_part_and_the_distances(self):
        # SOL-PRE-ORDER-CHECK-TEST-POINT-COURTYARD-DISTANCE.C2: Show the rule fail on a test point seeded inside a part's courtyard and closer than the distance, in a throwaway design built outside the repository, and pass the clean design.
        self.assertCaught(self.FAULT)
        fields = outcomes()[self.FAULT][1].split(" | ")
        self.assertEqual(fields[2], "test_point_courtyard")
        self.assertEqual(fields[3], "pad 1 of TP9 at (20, 10) mm")
        for words in ("TEST-5", "test point TP9", "0 mm from the F.CrtYd courtyard of R1", "requires 1 mm", "move TP9 or R1"):
            self.assertIn(words, fields[4])
        self.assertEqual([fault[2] for fault in board_prove.FAULTS if fault[0] == self.FAULT], ["test_point_courtyard"])



class TheTrackedDesignsPassTheTestPadCourtyardRule(unittest.TestCase):
    """Every design the repository tracks passes the rule, and states its figure."""

    DESIGNS = ("circuit-review-proof", "gate-proof", "method-proof", "record-keys-proof", "review-proof")

    def test_every_tracked_design_passes_and_reports_the_figure(self):
        # SOL-PRE-ORDER-CHECK-TEST-POINT-COURTYARD-DISTANCE.C1: Every design the repository tracks passes it.
        tracked = set(subprocess.run(["git", "ls-files", "*.kicad_pro"], cwd=board_prove.REPO, capture_output=True,
                                     text=True, check=True).stdout.split())
        self.assertEqual(tracked, {f"hardware/proof/{name}/{name}.kicad_pro" for name in self.DESIGNS})
        for name in self.DESIGNS:
            with self.subTest(design=name), tempfile.TemporaryDirectory(prefix="board-test-") as scratch:
                seed = board_prove.prepare(scratch, f"hardware/proof/{name}", name)
                status, lines, stderr = board_prove.check(seed, KICAD_CLI)
                self.assertNotEqual(status, 2, stderr)
                self.assertFalse([line for line in lines if "test_point_courtyard" in line or "TEST_COURTYARD_MM" in line
                                  and line.startswith("VIOLATION")], lines)
                figure = [line for line in lines if line.startswith("FIGURE") and "TEST-5 test point to courtyard" in line]
                self.assertEqual(len(figure), 1, lines)
                self.assertIn("| TEST_COURTYARD_MM | 1 mm at least from a test point's pad to the courtyard of any other part", figure[0])



class TheFiducialAndPolarityMarkRules(Proved):
    """Each seeded in a throwaway copy of the gate's proof design, the faults fail the rule that names them."""

    FAULTS = {
        "a side with surface-mount parts and two fiducials": ("side_fiducials", "the front side (F.Cu)",
                                                             ("MFG-10", "the front side has 1 surface-mount parts and 2 fiducials", "add 1 or more")),
        "a polarised part with no mark at its first pin": ("polarity_mark", "R2 pad 1 at (45, 10) mm",
                                                          ("R2 is not marked at pad 1", "draws nothing on F.SilkS")),
        "a polarised capacitor named only by its symbol with no mark": ("polarity_mark", "R2 pad 1 at (45, 10) mm",
                                                                        ("R2 is not marked at pad 1", "draws nothing on F.SilkS")),
        "a plated through-hole polarised part with no mark": ("polarity_mark", "R2 pad 1 at (45, 10) mm",
                                                              ("R2 is not marked at pad 1", "draws nothing on F.SilkS")),
        "a plated through-hole polarised part with no pad numbered 1 and holes a turn maps onto themselves": (
            "polarity_mark", "R2 at (45, 10) mm", ("R2 has no pad numbered 1", "its holes map onto themselves when turned")),
        "a polarity mark on the wrong side of the part": ("polarity_mark", "R2 pad 1 at (45, 10) mm",
                                                         ("R2 is not marked at pad 1", "no graphic on F.SilkS nearer pad 1")),
        "a symmetric outline on a symmetric pad pattern": ("polarity_mark", "R2 pad 1 at (45, 10) mm",
                                                          ("the silkscreen of R2 looks the same", "so that pad 1 moves")),
    }

    def test_each_rule_fails_on_its_seeded_fault_and_names_the_rule_the_design_and_the_item(self):
        # SOL-PRE-ORDER-CHECK-FIDUCIALS-AND-POLARITY-MARKS.C4: The on-demand seeded-fault proof introduces into a copy of a throwaway design, outside the tracked tree, a side with surface-mount parts and fewer than three fiducials, a polarised part with no silkscreen mark nearer pad one, a polarised capacitor named only by its symbol with no mark, a mark on the wrong side of the part, and a part on a pad pattern with a symmetry whose silkscreen outline is unchanged by it, and requires the check to fail each
        # SOL-PRE-ORDER-CHECK-FIDUCIALS-AND-POLARITY-MARKS.C3: A failure of any rule in this leaf is reported with the rule's name, the design, and the offending item
        self.assertCaught(*self.FAULTS)
        for fault, (rule, item, words) in self.FAULTS.items():
            with self.subTest(fault=fault):
                fields = outcomes()[fault][1].split(" | ")
                self.assertEqual(fields[1], "hardware/proof/gate-proof/gate-proof.kicad_pro")
                self.assertEqual((fields[2], fields[3]), (rule, item))
                for word in words:
                    self.assertIn(word, fields[4])
                self.assertEqual([entry[2] for entry in board_prove.FAULTS if entry[0] == fault], [rule])


    HOLES_FAULT = "a plated through-hole polarised part with no pad numbered 1 and holes a turn maps onto themselves"

    def test_the_seeded_part_with_no_pad_numbered_one_and_self_mapping_holes_is_caught_with_its_reason(self):
        # SOL-PRE-ORDER-CHECK-POLARITY-MARK-SKIPS-A-PART-WHOSE-HOLES-FIX-ITS-ORIENTATION.C9: The seeded-fault harness holds a row on the throwaway proof design that renames a polarised through-hole part's pads from numbers to names so that no pad is numbered 1, on a part whose holes a turn maps onto themselves, and the check reports polarity_mark
        self.assertCaught(self.HOLES_FAULT)
        fields = outcomes()[self.HOLES_FAULT][1].split(" | ")
        self.assertEqual((fields[2], fields[3]), ("polarity_mark", "R2 at (45, 10) mm"))
        self.assertIn("its holes map onto themselves when turned", fields[4])
        self.assertEqual([entry[2] for entry in board_prove.FAULTS if entry[0] == self.HOLES_FAULT], ["polarity_mark"])


class AnUnparseableSchematicFailsTheDesignWhichSwitchesOffPolarisationBySymbol(Copy):
    def test_a_schematic_kicad_cannot_read_fails_the_design_naming_the_schematic(self):
        # SOL-PRE-ORDER-CHECK-FIDUCIALS-AND-POLARITY-MARKS.C2: The fiducial rule and the polarity-mark rule are added to the existing pre-order check as further rules, each reading only the design's files
        # Without the netlist the polarity rule knows no symbol or pin name, so the design must fail rather than pass on pads alone.
        self.seed.write(".kicad_sch", "(kicad_sch (version")
        status, lines = self.check()
        self.assertEqual(status, 1, lines)
        schematic = f"hardware/proof/gate-proof/{board_prove.NAME}.kicad_sch"
        self.assertTrue([v for v in self.violations(lines) if v[2] == "design_unreadable" and v[3] == schematic], lines)



class TheTrackedDesignsPassTheFiducialAndPolarityMarkRules(unittest.TestCase):
    """Every design the repository tracks passes the two rules, and the report states the fiducial rule's count."""

    DESIGNS = TheTrackedDesignsPassTheTestPadCourtyardRule.DESIGNS

    def test_every_tracked_design_passes_and_reports_the_count(self):
        # SOL-PRE-ORDER-CHECK-FIDUCIALS-AND-POLARITY-MARKS.C5: Every design git tracks passes the fiducial rule and the polarity-mark rule
        for name in self.DESIGNS:
            with self.subTest(design=name), tempfile.TemporaryDirectory(prefix="board-test-") as scratch:
                seed = board_prove.prepare(scratch, f"hardware/proof/{name}", name)
                status, lines, stderr = board_prove.check(seed, KICAD_CLI)
                self.assertNotEqual(status, 2, stderr)
                self.assertEqual([line for line in lines if line.startswith("VIOLATION") and (
                    "| side_fiducials |" in line or "| polarity_mark |" in line)], [])
                figure = [line for line in lines if line.startswith("FIGURE") and "MFG-10 fiducials on a side" in line]
                self.assertEqual(len(figure), 1, lines)
                self.assertIn("3 fiducials at least on each side that carries assembled surface-mount parts", figure[0])



class TheCleanDesignStatesTheFiguresOfTheDecouplingAndSilkscreenRules(SharedCopy):
    # SOL-BOARD-METHOD-FOLLOWABLE-AND-MACHINE-FREE.C3: Each rule the method proof design's review adds fails on a fault seeded for it and passes the clean design
    """The report states the two inherent zeros, and how much of the layout the decoupling rule measured."""

    def test_the_inherent_zeros_are_stated_and_the_clean_design_passes_the_two_rules(self):
        # SOL-BOARD-REVIEW-LOOP-PROPORTIONATE.C5: Each of the three designs under hardware/proof passes the rule before it lands, and a seeded fault shows it fails.
        # SOL-BOARD-METHOD-FOLLOWABLE-AND-MACHINE-FREE.C3: Each rule the method proof design's review adds fails on a fault seeded for it and passes the clean design
        status, lines = self.check()
        self.assertEqual(status, 0, lines)
        design = "hardware/proof/gate-proof/gate-proof.kicad_pro"
        self.assertIn(f"FIGURE | {design} | DECOUPLE-6 via in the decoupling path | none, inherent zero | 0 vias between a "
                      "decoupling capacitor's supply pad and the pin it decouples", lines)
        self.assertIn(f"FIGURE | {design} | MFG-7 reference on silkscreen | none, inherent zero | 0 references off a silkscreen "
                      "layer or hidden", lines)
        self.assertIn(f"FIGURE | {design} | MFG-9 designator beside its part | none, inherent zero | 0 designators inside a "
                      "part's courtyard or nearer another part than their own", lines)
        self.assertIn(f"FIGURE | {design} | DECOUPLE-6 decoupling paths measured | the layout's pad pin types | 0 paths of 0 "
                      "circuits with a supply pin", lines)
