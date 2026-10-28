#!/usr/bin/env python3
"""The pre-order check against KiCad itself, on the throwaway proof design, here the pin allocation record that declares no controller: the seeded cases and the report.

The unit tests of the same rules are in test_board_check_no_controller.py.
"""

from __future__ import annotations

import os
import sys
import unittest

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import board_prove  # noqa: E402
from board_kicad_fixtures import load_tests, setUpModule  # noqa: E402,F401
from board_kicad_fixtures import Copy, Proved, outcomes  # noqa: E402

DECLARED = (
    "synthetic: true\ncontroller: none\nchannels:\n"
    "  - channel: lv_a\n    net: LV_A\n    connector: J2\n    connector_pin: 1\n    far_channel: lv_a\n"
    "  - channel: lv_b\n    net: LV_B\n    connector: J2\n    connector_pin: 2\n    rail: signal_b\n")

NO_CONTROLLER_FAULTS = {
    "a controller placed under a no-controller declaration": ("controller_part", "the design places U1"),
    "a controller pin listed under a no-controller declaration": ("pin_allocation", "carries no controller_pin"),
    "a no-controller entry naming neither a far channel nor a rail": ("pin_allocation", "carries neither far_channel nor rail"),
    "a no-controller entry naming both a far channel and a rail": ("pin_allocation", "carries both far_channel and rail"),
    "a far channel that no other design's record lists": ("pin_allocation", "names far channel lv_a"),
    "a pin of a listed connector that a no-controller record omits": ("connectivity", "J2 pin 2, which the record does not list"),
}


class TheNoControllerFaultsAreSeeded(Proved):
    def test_each_way_the_declaration_can_be_abused_has_a_seeded_case_that_fails_the_check_naming_what_it_breaks(self):
        # SOL-HW-PRE-ORDER-CHECK-HOLDS-BOARD-WITHOUT-CONTROLLER.C6: There is a seeded case for a controller placed under a no-controller declaration, a controller pin under the declaration, an entry with neither or both of far channel and rail, a far channel no other record lists, and an unlisted pin on a listed connector, each failing when the check is run on it by hand. Running the proof in either gate is out of scope; it is run by hand.
        faults = {fault[0]: fault for fault in board_prove.FAULTS if fault[0] in NO_CONTROLLER_FAULTS}
        self.assertEqual(set(faults), set(NO_CONTROLLER_FAULTS))
        found = outcomes()
        for name, (rule, words) in NO_CONTROLLER_FAULTS.items():
            with self.subTest(fault=name):
                self.assertEqual(faults[name][2], rule)
                caught, evidence = found[name]
                self.assertTrue(caught, evidence)
                self.assertIn(words, evidence)


class TheDeclarationOnTheThrowawayDesign(Copy):
    def declare(self):
        self.seed.write("pin-allocation.yaml", DECLARED)

    def test_the_far_channel_case_runs_in_a_machine_folder_and_the_others_in_the_design_without_one(self):
        # SOL-HW-PRE-ORDER-CHECK-HOLDS-BOARD-WITHOUT-CONTROLLER.C6: There is a seeded case for a controller placed under a no-controller declaration, a controller pin under the declaration, an entry with neither or both of far channel and rail, a far channel no other record lists, and an unlisted pin on a listed connector, each failing when the check is run on it by hand. Running the proof in either gate is out of scope; it is run by hand.
        far = next(fault for fault in board_prove.FAULTS if fault[0] == "a far channel that no other design's record lists")
        self.assertEqual(board_prove.destination_of(far), "hardware/seeded-machine/gate-proof")
        self.assertIsNotNone(board_prove.committed(board_prove.target_of(far)[0]))
        self.assertIsNone(board_prove.destination_of(next(fault for fault in board_prove.FAULTS
                                                          if fault[0] == "a controller placed under a no-controller declaration")))

    def test_the_check_reports_the_rule_and_the_part_in_its_text_report(self):
        # SOL-HW-PRE-ORDER-CHECK-HOLDS-BOARD-WITHOUT-CONTROLLER.C5: The check's text report names, for each failing case of the pin allocation and connectivity rules, the rule and the channel or part, and a passing controller-less design reports no failure. The check has no machine-readable report, and none is added here. Failures of rules other than the pin allocation and connectivity rules are out of scope.
        self.declare()
        status, lines = self.check()
        self.assertEqual(status, 1)
        found = [v for v in self.violations(lines) if v[2] == "controller_part"]
        self.assertEqual(len(found), 1, lines)
        self.assertEqual(found[0][3], "hardware/proof/gate-proof/gate-proof.kicad_sch U1")
        self.assertTrue(found[0][4].startswith("the pin allocation record hardware/proof/gate-proof/pin-allocation.yaml "
                                               "declares controller: none, but the design places U1"), found[0][4])

    def test_a_design_with_no_machine_folder_is_not_held_to_the_far_channel_check(self):
        # SOL-HW-PRE-ORDER-CHECK-HOLDS-BOARD-WITHOUT-CONTROLLER.C3: A far channel must be a channel with a controller pin and a connector in another design's record in the same machine folder, and one that no record lists fails the design, naming the channel. A design with no machine folder is exempt from the check. Comparing the cable's pin map between the two headers is out of scope.
        self.declare()
        status, lines = self.check()
        self.assertEqual(status, 1)
        self.assertEqual([v for v in self.violations(lines) if v[2] == "pin_allocation"], [])
        self.assertFalse([line for line in lines if "far channel" in line], lines)

    def test_a_declared_design_that_places_a_controller_is_not_accepted(self):
        # SOL-HW-PRE-ORDER-CHECK-HOLDS-BOARD-WITHOUT-CONTROLLER.C1: The declaration fails a design that places a part with a port-named pin or a part whose catalogue number equals the machine's controller part record, naming the part, and a design that places no controller and carries no declaration fails as it does now. Comparing the cable between two headers pin for pin is out of scope.
        self.declare()
        status, lines = self.check()
        self.assertEqual(status, 1)
        self.assertTrue([v for v in self.violations(lines) if v[2] == "controller_part" and v[4].endswith("or take the part off the board")], lines)

    def test_the_design_as_committed_passes_and_a_rail_entry_beside_its_controller_channels_is_accepted(self):
        # SOL-HW-PRE-ORDER-CHECK-HOLDS-BOARD-WITHOUT-CONTROLLER.C4: A connector pin carrying a supply or return can be listed by a rail entry with no controller pin, and a rail entry whose net does not reach its connector pin fails, as for any channel. A rail entry's channel is a label unique within the record, and rail entries are exempt from the rule that a net is listed once, so a connector with several supply or several return pins is listed in full; each connector pin is still listed once. Entries that carry a controller pin are out of scope here and unchanged.
        status, lines = self.check()
        self.assertEqual(status, 0, lines)
        self.seed.replace("pin-allocation.yaml", "    connector_pin: 2\n",
                          "    connector_pin: 2\n  - channel: spare_return\n    net: LV_A\n    connector: J2\n"
                          "    connector_pin: 1\n    rail: signal_a\n")
        status, lines = self.check()
        self.assertEqual(status, 1)
        self.assertTrue([v for v in self.violations(lines) if v[2] == "pin_allocation" and "connector pin J2 pin 1 is listed" in v[4]], lines)


if __name__ == "__main__":
    unittest.main()
