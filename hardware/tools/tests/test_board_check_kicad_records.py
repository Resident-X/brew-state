#!/usr/bin/env python3
"""The pre-order check against KiCad itself, on the throwaway proof design, here the records a design is held to: separation, parts, names, record keys, voltage and pin coverage.

This is one of the files the check's KiCad tests are divided into by topic; the
shared setup, the seeded-fault proof's pooled outcomes and the exclusion of what
needs that proof are in board_kicad_fixtures.py.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest


TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)

import board_check  # noqa: E402
import board_prove  # noqa: E402
from board_kicad_fixtures import load_tests, setUpModule  # noqa: E402,F401
from board_kicad_fixtures import KICAD_CLI, Proved, outcomes  # noqa: E402



class Separation(Proved):
    def test_every_separation_failure_fails(self):
        """SOL-HW-BOARD-RULE-CHECK-GATE.C3: The separation basis is a written rule the layout check enforces at no less than the signed figure, and a mains-carrying design without it fails."""
        self.assertCaught(*[fault[0] for fault in board_prove.FAULTS if fault[1].startswith("separation:")])



class Parts(Proved):
    def test_every_parts_failure_fails_and_is_named(self):
        # SOL-HW-PARTS-CHECK.C4: Each parts fault is shown to fail the check on a seeded copy of the throwaway design
        faults = [fault for fault in board_prove.FAULTS if fault[1].startswith("parts:")]
        names = {fault[0] for fault in faults}
        for required in ("a part whose value differs from the specification record", "a part with no LCSC field",
                         "a part whose number is absent from the extract", "a part the extract shows out of stock",
                         "an extract past its age limit", "an extract dated later than the day of the check",
                         "an extract entry whose stock is not a whole number",
                         "two extract entries carrying one catalogue number", "two symbols carrying one reference",
                         "a placed position the specification record omits"):
            self.assertIn(required, names)
        self.assertEqual({fault[2] for fault in faults}, {"parts_record", "parts_part", "parts_catalogue"})
        self.assertCaught(*names)

    def test_the_unmodified_throwaway_design_passes_the_parts_check(self):
        # SOL-HW-PARTS-CHECK.C4: Each parts fault is shown to fail the check on a seeded copy of the throwaway design
        found = outcomes()
        self.assertIn("a part whose value differs from the specification record", found)
        with tempfile.TemporaryDirectory(prefix="board-test-") as scratch:
            seed = board_prove.prepare(scratch)
            status, lines = board_prove.check(seed, KICAD_CLI)[:2]
        self.assertEqual(status, 0, lines)
        self.assertEqual([line for line in lines if line.startswith("VIOLATION") and "| parts_" in line], [])



class Names(Proved):
    def test_a_tool_named_net_and_each_unnamed_sheet_fail_by_name_beside_a_pin_nothing_joins(self):
        # SOL-PRE-ORDER-CHECK-REFUSES-TOOL-NAMED-NETS-AND-UNNAMED-SHEETS.C2: Each refusal is shown to fail on a fault seeded for it in a copy of the throwaway design
        faults = [fault for fault in board_prove.FAULTS if fault[1].startswith("names:")]
        self.assertEqual({fault[2] for fault in faults}, {"tool_named_net", "unnamed_sheet"})
        self.assertGreaterEqual(len([fault for fault in faults if fault[2] == "unnamed_sheet"]), 3)
        net = next(fault for fault in faults if fault[2] == "tool_named_net")
        self.assertEqual(net[6], "unconnected-(")
        self.assertCaught(*[fault[0] for fault in faults])



class NamesRunDirectly(unittest.TestCase):
    def test_the_seeded_net_run_carries_a_pin_nothing_joins_and_names_none_of_them_in_a_failure(self):
        # SOL-PRE-ORDER-CHECK-REFUSES-TOOL-NAMED-NETS-AND-UNNAMED-SHEETS.C2: Each refusal is shown to fail on a fault seeded for it in a copy of the throwaway design
        fault = next(fault for fault in board_prove.FAULTS if fault[2] == "tool_named_net")
        with tempfile.TemporaryDirectory(prefix="board-test-") as scratch:
            seed = board_prove.prepare(scratch)
            fault[4](seed)
            status, lines = board_prove.check(seed, KICAD_CLI)[:2]
        self.assertEqual(status, 1, lines)
        self.assertTrue(any("| tool_named_net |" in line for line in lines), lines)
        self.assertTrue(any("Pin not connected" in line for line in lines), "the run seeds no pin nothing joins")
        self.assertEqual([line for line in lines if line.startswith("VIOLATION") and "unconnected-(" in line], [])

    def test_the_proof_fails_a_fault_whose_run_names_what_the_check_must_leave_alone(self):
        # SOL-PRE-ORDER-CHECK-REFUSES-TOOL-NAMED-NETS-AND-UNNAMED-SHEETS.C2: Each refusal is shown to fail on a fault seeded for it in a copy of the throwaway design
        fault = next(fault for fault in board_prove.FAULTS if fault[2] == "tool_named_net")
        spared = (*fault[:6], "Net-(R1-Pad1)")
        caught, evidence = board_prove.prove(spared, KICAD_CLI)
        self.assertFalse(caught)
        self.assertIn("must leave alone", evidence)

    def test_the_unmodified_throwaway_design_passes_the_name_refusals(self):
        # SOL-PRE-ORDER-CHECK-REFUSES-TOOL-NAMED-NETS-AND-UNNAMED-SHEETS.C3: Every tracked design passes the refusals, which run in the build round for board changes and nightly on main
        with tempfile.TemporaryDirectory(prefix="board-test-") as scratch:
            seed = board_prove.prepare(scratch)
            status, lines = board_prove.check(seed, KICAD_CLI)[:2]
        self.assertEqual(status, 0, lines)
        self.assertEqual([line for line in lines if "| tool_named_net |" in line or "| unnamed_sheet |" in line], [])



class RecordKeys(Proved):
    def test_a_misspelt_key_in_each_kind_of_record_fails_and_is_named(self):
        # SOL-PRE-ORDER-CHECK-READS-RECORD-KEYS.C1: The check accepts and reads every key the record decisions define, fails one they do not, and is shown to on a seeded copy
        faults = [fault for fault in board_prove.FAULTS if fault[1].startswith("record keys:")]
        self.assertEqual({fault[2] for fault in faults},
                         {"separation_basis", "derating_record", "pin_limits_record", "parts_record"})
        self.assertEqual({board_prove.target_of(fault) for fault in faults}, {board_prove.KEYS_TARGET})
        self.assertCaught(*[fault[0] for fault in faults])



class VoltageRulesProof(Proved):
    def test_each_voltage_rule_fault_is_caught_on_a_copy_of_the_throwaway_design_and_the_committed_design_stays_passing(self):
        # SOL-PRE-ORDER-CHECK-DERATED-VOLTAGE-AND-PIN-LIMITS.C5: The on-demand seeded-fault proof introduces into a copy of a throwaway design, outside the tracked tree, a part whose net exceeds the policy's voltage share of its rating, a position without its class, a position naming a class the policy lacks, a pin whose net exceeds absolute_max_v, a pin whose net falls below absolute_min_v, a pin driven from another domain while its own is unpowered, and an integrated circuit the pin-limit record omits, and requires the check to fail each
        faults = [fault for fault in board_prove.FAULTS if fault[1].startswith(("derated voltage:", "pin limits:"))]
        self.assertEqual(len(faults), 9)
        self.assertEqual(sorted(fault[2] for fault in faults), ["derated_voltage"] * 4 + ["pin_limit"] * 5)
        self.assertEqual({board_prove.target_of(fault) for fault in faults}, {board_prove.KEYS_TARGET})
        for words in ("working voltage of 353.553 V", "has no class", "names the class 'ghost'", "can reach 3.3 V, above the pin's absolute_max_v 3",
                      "can fall to 0 V, below the pin's absolute_min_v 0.5", "driven from the domain sense", "omits the integrated circuit U1",
                      "names the class none and the parts specification record gives '50V 0.25W'",
                      "which the part U1 does not have"):
            self.assertTrue(any(words in fault[3] for fault in faults), words)
        self.assertCaught(*[fault[0] for fault in faults])

    def test_a_seeded_fault_names_the_fault_and_the_rule_in_the_proofs_record_of_the_run(self):
        # SOL-PRE-ORDER-CHECK-DERATED-VOLTAGE-AND-PIN-LIMITS.C5: ... the record of each seeded run naming the fault and the rule that caught it
        for fault in board_prove.FAULTS:
            if fault[1].startswith(("derated voltage:", "pin limits:")):
                caught, evidence = outcomes()[fault[0]]
                self.assertTrue(caught, evidence)
                self.assertIn(f" | {fault[2]} | ", evidence)
                self.assertIn(fault[3], evidence)



class PinCoverageProof(Proved):
    def test_a_pin_left_out_of_a_listed_parts_entry_is_caught_on_a_copy_of_the_throwaway_design_that_spares_its_listed_pins(self):
        # SOL-PRE-ORDER-CHECK-EVERY-CONNECTED-PIN-LISTED.C4: The on-demand seeded-fault proof removes from a copy of a throwaway design, outside the tracked tree, the entry of one connected pin of a listed part that keeps its other pins listed and requires the check to fail it, the record of the seeded run naming the fault and the rule that caught it
        # OBL-VERIFICATION-DISCIPLINE-001.C9: A check is shown to fail on the defect it exists to catch rather than asserted to be capable of it
        faults = [fault for fault in board_prove.FAULTS if fault[1].startswith("pin coverage:")]
        self.assertEqual(len(faults), 1)
        fault = faults[0]
        self.assertEqual(fault[2], "pin_limit")
        self.assertEqual(board_prove.target_of(fault), board_prove.KEYS_TARGET)
        self.assertEqual(fault[6], "U1 pin 2")
        self.assertCaught(fault[0])
        caught, evidence = outcomes()[fault[0]]
        self.assertTrue(caught, evidence)
        self.assertIn(" | pin_limit | ", evidence)
        self.assertIn("omits U1 pin 1, which is connected on net /LV_A", evidence)
        self.assertIn("C9000005", evidence)



class PinCoverageSparesUnconnectedPins(Proved):
    def test_a_pin_on_no_other_pin_and_no_rail_is_not_failed_beside_a_connected_pin_left_out_and_the_proof_notices_if_it_were(self):
        # SOL-PRE-ORDER-CHECK-EVERY-CONNECTED-PIN-LISTED.C4: ... a pin on no other pin and no rail is shown not to be failed.
        faults = [fault for fault in board_prove.FAULTS if fault[1].startswith("pin coverage:") and "on no other pin" in fault[1]]
        self.assertEqual(len(faults), 1)
        fault = faults[0]
        self.assertEqual(board_prove.target_of(fault), (board_prove.REVIEW_DESIGN, board_prove.REVIEW_NAME))
        self.assertEqual(fault[6], "U4 pin 5")
        self.assertCaught(fault[0])
        caught, evidence = outcomes()[fault[0]]
        self.assertTrue(caught, evidence)
        self.assertIn(" | pin_limit | ", evidence)
        self.assertIn("omits U4 pin 13, which is connected on net /WDI", evidence)
        self.assertNotIn("U4 pin 5", evidence)
        # the same run, told to leave alone the connected pin it does fail, is a missed proof: the spared pin is what the proof watches
        named = (*fault[:6], "U4 pin 13")
        caught, evidence = board_prove.prove(named, KICAD_CLI)
        self.assertFalse(caught)
        self.assertIn("must leave alone", evidence)



class PinCoverageSparesListedPins(unittest.TestCase):
    def test_the_proof_fails_a_run_that_names_the_listed_pin_it_must_leave_alone(self):
        # SOL-PRE-ORDER-CHECK-EVERY-CONNECTED-PIN-LISTED.C4: ... the entry of one connected pin of a listed part that keeps its other pins listed ... requires the check to fail it; the listed pins it keeps are not failed (the pin on no other pin and no rail is shown in PinCoverageSparesUnconnectedPins).
        fault = next(fault for fault in board_prove.FAULTS if fault[1].startswith("pin coverage:"))
        spared = (*fault[:6], "U1 pin 1")
        caught, evidence = board_prove.prove(spared, KICAD_CLI)
        self.assertFalse(caught)
        self.assertIn("must leave alone", evidence)



class TheRecordKeysProofDesignPasses(unittest.TestCase):
    def test_the_record_keys_proof_design_with_every_key_passes_the_check(self):
        # SOL-PRE-ORDER-CHECK-READS-RECORD-KEYS.C1: The check accepts and reads every key the record decisions define, fails one they do not, and is shown to on a seeded copy
        with tempfile.TemporaryDirectory(prefix="board-test-") as scratch:
            seed = board_prove.prepare(scratch, *board_prove.KEYS_TARGET)
            for name in ("separation-basis.yaml", "derating-policy.yaml", "pin-limits.yaml", "catalogue-extract.yaml"):
                self.assertIn(name, seed.files)
            status, lines = board_prove.check(seed, KICAD_CLI)[:2]
        self.assertEqual(status, 0, lines)
        self.assertEqual([line for line in lines if line.startswith("VIOLATION")], [])



class TheProjectFilesNetClassesAreResolvedByKiCad(unittest.TestCase):
    """SOL-HW-BOARD-RULE-CHECK-GATE.C3: The separation basis is a written rule the layout check enforces at no less than the signed figure, and a mains-carrying design without it fails.

    The project file's Mains nets are read as KiCad resolves its assignments
    and patterns, for every net name given, whether or not any copper carries it.
    """

    def test_assignments_and_patterns_resolve_as_kicad_matches_them(self):
        with open(os.path.join(board_prove.REPO, board_prove.DESIGN, "gate-proof.kicad_pro"), encoding="utf-8") as handle:
            project = json.load(handle)
        settings = project["net_settings"]
        settings["netclass_assignments"] = {"/GHOST": "Mains", "/LV_A": ["Default", "Mains"], "/LV_B": "Default"}
        settings["netclass_patterns"].append({"netclass": "Mains", "pattern": "/re_[0-9]+"})
        names = {"/MAINS_L", "/MAINS_N", "/mains_l", "/LV_A", "/LV_B", "/GHOST", "/re_12", "/RE_12", 'odd "name"'}
        with tempfile.TemporaryDirectory(prefix="board-test-") as scratch:
            path = os.path.join(scratch, "p.kicad_pro")
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(project, handle)
            found, why = board_check.project_mains(KICAD_CLI, scratch, path, names, "test")
            self.assertEqual(found, {"/MAINS_L", "/MAINS_N", "/LV_A", "/GHOST", "/re_12"}, why)
            settings["netclass_assignments"], settings["netclass_patterns"] = None, []
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(project, handle)
            self.assertEqual(board_check.project_mains(KICAD_CLI, scratch, path, names, "test2"), (set(), ""))
