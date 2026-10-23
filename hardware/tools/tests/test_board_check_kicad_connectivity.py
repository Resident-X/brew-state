#!/usr/bin/env python3
"""The pre-order check against KiCad itself, on the throwaway proof design, here the connectivity check, the separation floor and the mounting holes: the connectivity part.

One of the files the original test file is divided into by topic; the tests are unchanged and only live elsewhere.
"""

from __future__ import annotations

import io
import os
import sys
import unittest

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import board_check  # noqa: E402
import board_prove  # noqa: E402
from board_kicad_fixtures import load_tests, setUpModule  # noqa: E402,F401
from board_kicad_fixtures import Copy, KICAD_CLI, Proved, outcomes  # noqa: E402


class Connectivity(Proved):
    """The connectivity check against the real KiCad, on the throwaway design and on a copy with each fault seeded."""

    def connectivity_faults(self):
        return [fault for fault in board_prove.FAULTS if fault[1].startswith("connectivity:")]

    def test_the_four_connectivity_faults_are_each_seeded_and_caught_naming_what_they_break(self):
        # SOL-HW-CONNECTIVITY-CHECK.C4: Each connectivity fault is shown to fail the check on a seeded copy of the throwaway design
        faults = {fault[0]: fault for fault in self.connectivity_faults()}
        self.assertEqual(set(faults), {"a channel's net moved to the other controller pin",
                                       "a channel's net moved to the other pin of its connector",
                                       "a channel on the wrong connector",
                                       "a listed channel removed from the design",
                                       "a channel on pins the record omits"})
        self.assertEqual({fault[2] for fault in faults.values()}, {"connectivity"})
        self.assertCaught(*faults)

    def test_each_connectivity_fault_is_caught_with_the_line_that_names_it(self):
        # SOL-HW-CONNECTIVITY-CHECK.C1: A channel whose net does not reach the pin and connector its record entry names fails the check
        found = outcomes()
        for name in ("a channel's net moved to the other controller pin", "a channel's net moved to the other pin of its connector",
                     "a channel on the wrong connector"):
            with self.subTest(fault=name):
                caught, evidence = found[name]
                self.assertTrue(caught, evidence)
                self.assertIn("channel lv_a: net /LV_A reaches", evidence)
                self.assertIn("where the record names", evidence)

    def test_a_channel_the_design_lacks_and_a_pin_the_record_omits_are_each_caught_by_name(self):
        # SOL-HW-CONNECTIVITY-CHECK.C2: A channel the record lists and the design lacks, and a net on a pin the record omits, each fail the check
        found = outcomes()
        caught, evidence = found["a listed channel removed from the design"]
        self.assertTrue(caught, evidence)
        self.assertIn("channel lv_b: the record lists net LV_B", evidence)
        caught, evidence = found["a channel on pins the record omits"]
        self.assertTrue(caught, evidence)
        self.assertIn("net /LV_B is on connector pin J2 pin 2", evidence)

    def test_every_pin_allocation_record_failure_fails(self):
        # SOL-HW-CONNECTIVITY-CHECK.C3: A design with no usable pin allocation record fails, and a synthetic record passes only a design not for manufacture
        faults = [fault[0] for fault in board_prove.FAULTS if fault[1].startswith("pin allocation:")]
        self.assertGreaterEqual(len(faults), 6)
        self.assertCaught(*faults)


class TheUnmodifiedProofDesignPassesTheConnectivityCheck(Copy):
    def test_the_throwaway_design_as_committed_passes_with_its_synthetic_record(self):
        # SOL-HW-CONNECTIVITY-CHECK.C4: Each connectivity fault is shown to fail the check on a seeded copy of the throwaway design
        status, lines = self.check()
        self.assertEqual(status, 0, lines)
        self.assertEqual([v for v in self.violations(lines) if v[2] in ("connectivity", "pin_allocation")], [])
        self.assertIn("synthetic: true", self.seed.read("pin-allocation.yaml"))

    def test_a_net_moved_off_its_controller_pin_is_caught_on_the_real_netlist(self):
        # SOL-HW-CONNECTIVITY-CHECK.C1: A channel whose net does not reach the pin and connector its record entry names fails the check
        self.seed.replace(".kicad_sch", '(label "LV_B"\n\t\t(at 96.52 78.74 0)', '(label "LV_A"\n\t\t(at 96.52 78.74 0)')
        status, lines = self.check()
        self.assertEqual(status, 1)
        found = [v[4] for v in self.violations(lines) if v[2] == "connectivity"]
        self.assertEqual(found, ["channel lv_b: net /LV_B reaches no controller pin, where the record names controller pin PA1"])


class EveryTrackedDesignPassesTheConnectivityCheck(unittest.TestCase):
    def test_every_design_the_repository_tracks_is_held_to_a_record_and_passes(self):
        # SOL-HW-CONNECTIVITY-CHECK.C5: Every tracked design passes the connectivity check, and a change to a pin allocation record re-runs the board tier in the build round
        out = io.StringIO()
        status = board_check.run(board_prove.REPO, KICAD_CLI, out=out)
        lines = out.getvalue().splitlines()
        self.assertEqual(status, 0, out.getvalue())
        designs = [line for line in lines if line.startswith("DESIGN | ")]
        self.assertGreaterEqual(len(designs), 2)
        self.assertTrue(all(line.endswith(" | PASS") for line in designs), designs)
        self.assertFalse([line for line in lines if " | connectivity | " in line or " | pin_allocation | " in line], lines)
        # SOL-PRE-ORDER-CHECK-DERATED-VOLTAGE-AND-PIN-LIMITS.C6: Every design git tracks passes the derated-voltage rule and the pin-limit rule, carrying the records they read, synthetic where the design is not for manufacture.
        # SOL-PRE-ORDER-CHECK-EVERY-CONNECTED-PIN-LISTED.C5: Every design git tracks passes the coverage rule, its pin-limit record carrying an entry for every connected pin of every semiconductor and integrated circuit it places, through the board gate the pre-order check already uses.
        self.assertFalse([line for line in lines if " | derated_voltage | " in line or " | pin_limit | " in line], lines)
