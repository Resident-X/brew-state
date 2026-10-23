#!/usr/bin/env python3
"""The pre-order check against KiCad itself, on the throwaway proof design: how the check finds designs, reports a forged or rejected rule and refills zones.

This is one of the files the check's KiCad tests are divided into by topic; the
shared setup, the seeded-fault proof's pooled outcomes and the exclusion of what
needs that proof are in board_kicad_fixtures.py.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import unittest


TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)

import board_prove  # noqa: E402
from board_kicad_fixtures import load_tests, setUpModule  # noqa: E402,F401
from board_kicad_fixtures import Copy, KICAD_CLI, Proved  # noqa: E402



class Discovery(Proved):
    def test_every_discovery_failure_fails_by_name(self):
        """SOL-HW-BOARD-RULE-CHECK-GATE.C1: Every board design in the repository is checked because it exists, not because it is listed.

        An empty tree, a design that cannot be opened, a project missing its
        schematic or layout, a board file without its project, a sheet or
        library the design reaches that the repository does not hold, and a
        library table not in the form KiCad writes each fail.
        """
        discovery = [fault[0] for fault in board_prove.FAULTS if fault[1].startswith("discovery:")]
        self.assertGreaterEqual(len(discovery), 22)
        self.assertCaught(*discovery)



class OnlyWhatTheRepositoryHoldsIsChecked(Copy):
    """SOL-HW-BOARD-RULE-CHECK-GATE.C1: Every board design in the repository is checked because it exists, not because it is listed.

    KiCad is given only the files git tracks, so a library, sheet or rules file
    left uncommitted beside a design cannot make the design pass here while the
    repository's copy of it would not.
    """

    def test_a_footprint_library_left_out_of_the_commit_is_not_used(self):
        board_prove.untracked_library(self.seed)
        status, lines = self.check()
        self.assertEqual(status, 1, lines)
        rules = [v[2] for v in self.violations(lines)]
        self.assertIn("design_library", rules)
        self.assertIn("lib_footprint_issues", rules)

    def test_libraries_and_sheets_above_the_designs_folder_are_checked_with_it(self):
        # The libraries move to a folder beside the design's and a sheet to the
        # folder above it; a copy of the design's folder alone would lose all
        # three, and KiCad would report the missing symbols, footprints and sheet.
        shared = os.path.join(os.path.dirname(self.seed.design), "lib")
        os.makedirs(shared)
        for name in ("proof.pretty", "proof.kicad_sym"):
            shutil.move(self.seed.path(name), os.path.join(shared, name))
        self.seed.replace("fp-lib-table", "${KIPRJMOD}/proof.pretty", "${KIPRJMOD}/../lib/proof.pretty")
        self.seed.replace("sym-lib-table", "${KIPRJMOD}/proof.kicad_sym", "${KIPRJMOD}/../lib/proof.kicad_sym")
        Q = board_prove.sexpr.Quoted
        with open(os.path.join(os.path.dirname(self.seed.design), "notes.kicad_sch"), "w", encoding="utf-8") as handle:
            handle.write('(kicad_sch\n\t(version 20250114)\n\t(generator "eeschema")\n\t(uuid "0b0e5c1a-0000-4000-8000-0000000000f0")\n'
                         '\t(paper "A4")\n)\n')
        sheet = ["sheet", ["at", "200", "100"], ["size", "20", "10"], ["uuid", Q("0b0e5c1a-0000-4000-8000-0000000000f1")],
                 ["property", Q("Sheetname"), Q("notes"), ["at", "200", "99", "0"]],
                 ["property", Q("Sheetfile"), Q("../notes.kicad_sch"), ["at", "200", "111", "0"]]]
        self.seed.schematic(lambda tree: tree.insert(len(tree) - 1, sheet))
        status, lines = self.check()
        self.assertEqual(status, 0, lines)



class RuleChecks(Proved):
    def test_kicad_violations_parity_exclusions_and_ignored_checks_each_fail(self):
        """SOL-HW-BOARD-RULE-CHECK-GATE.C2: A design passes only if KiCad's own electrical and layout rule checks find no violation, including no layout-schematic disagreement.

        KiCad's own findings, schematic parity, exclusions, ignored checks, a
        stale zone fill, rules files KiCad declines or reads differently from
        the check, and project files not in KiCad's form each fail.
        """
        rule_checks = [fault[0] for fault in board_prove.FAULTS if fault[1].startswith("rule checks:")]
        self.assertGreaterEqual(len(rule_checks), 21)
        self.assertCaught(*rule_checks)



class AForgedRuleIsReported(unittest.TestCase):
    """Driven directly on a copy of its own, so it needs no seeded-fault proof."""

    def test_a_rule_written_to_look_like_the_checks_own_has_its_findings_reported(self):
        """SOL-HW-BOARD-RULE-CHECK-GATE.C2: A design passes only if KiCad's own electrical and layout rule checks find no violation, including no layout-schematic disagreement.

        A design rule named as the check's marker once was is not taken for it:
        its assertion failures on every pad are reported, not set aside.
        """
        with tempfile.TemporaryDirectory(prefix="board-test-") as scratch:
            seed = board_prove.prepare(scratch)
            board_prove.forged_rule(seed)
            status, lines, stderr = board_prove.check(seed, KICAD_CLI)
        self.assertEqual(status, 1, stderr)
        forged = [line for line in lines if " | assertion_failure | " in line and "pre-order check: rules loaded" in line]
        self.assertEqual(len(forged), 10, lines)



class TheRejectedRuleIsNamed(Copy):
    """SOL-HW-BOARD-RULE-CHECK-GATE.C6: The check's report names each design, its verdict and every violation in terms a builder can act on.

    When KiCad drops a rules file, the report names the first form it rejects
    and its line, found with KiCad alone, so the builder need not open the
    editor to learn what is wrong.
    """

    def rejected(self, text: str):
        self.seed.write(".kicad_dru", text)
        status, lines = self.check()
        self.assertEqual(status, 1, lines)
        return [v for v in self.violations(lines) if v[2] == "custom_rules"]

    def test_the_first_rejected_rule_is_named_wherever_it_sits(self):
        rules = self.seed.read(".kicad_dru")
        bad = "(rule \"bad {0}\"\n\t(condition \"A.Type == \")\n\t(constraint clearance (min 1mm)))\n"
        typo = "(rule \"typo\"\n\t(condition \"A.Type == 'Pad'\")\n\t(constraint clearence (min 1mm)))\n"
        found = self.rejected(rules.replace("(rule \"Mains", bad.format(1) + typo + "(rule \"Mains", 1))
        self.assertEqual(len(found), 1, found)
        self.assertEqual(found[0][3], "hardware/proof/gate-proof/gate-proof.kicad_dru rule 'bad 1' at line 5")
        found = self.rejected(rules + "(rule \"fine\" (condition \"A.Type == 'Via'\") (constraint clearance (min 0.2mm)))\n"
                              + typo + bad.format(2))
        self.assertEqual(found[0][3], "hardware/proof/gate-proof/gate-proof.kicad_dru rule 'typo' at line 19")
        self.assertIn("this is the rule it rejects", found[0][4])

    def test_a_form_that_is_not_a_rule_is_named(self):
        found = self.rejected(self.seed.read(".kicad_dru") + "(rules \"x\")\n")
        self.assertEqual(found[0][3], "hardware/proof/gate-proof/gate-proof.kicad_dru the rules form at line 18")



class ZonesAreRefilled(Copy):
    """SOL-HW-BOARD-RULE-CHECK-GATE.C2: A design passes only if KiCad's own electrical and layout rule checks find no violation, including no layout-schematic disagreement.

    The layout check refills copper zones first, so a stale saved fill can
    neither hide nor invent a violation.
    """

    def add_zone(self, net: str, corners, clearance: str = "0.2"):
        Q = board_prove.sexpr.Quoted
        zone = ["zone", ["net", Q(net)], ["layer", Q("F.Cu")], ["uuid", Q("0b0e5c1a-0000-4000-8000-0000000000a1")],
                ["hatch", "edge", "0.5"], ["connect_pads", ["clearance", clearance]], ["min_thickness", "0.25"],
                ["fill", ["thermal_gap", "0.5"], ["thermal_bridge_width", "0.5"]],
                ["polygon", ["pts", *[["xy", str(x), str(y)] for x, y in corners]]]]
        self.seed.layout(lambda tree: tree.insert(len(tree) - 1, zone))

    def test_a_stale_fill_closer_than_the_signed_figure_does_not_fail_a_design_whose_refill_is_clean(self):
        # A low-voltage pour around R1, filled while the rules file held nothing:
        # its saved copper then sits within the Mains net class's 0.5 mm of the
        # mains pads, well inside the signed 3 mm.
        self.add_zone("/LV_A", [(1, 1), (59, 1), (59, 19), (1, 19)])
        rules = self.seed.read(".kicad_dru")
        self.seed.write(".kicad_dru", "(version 1)\n")
        self.drc("--refill-zones", "--save-board")
        self.seed.write(".kicad_dru", rules)
        stale = self.drc()
        self.assertTrue(any(v["type"] == "clearance" and "Zone [/LV_A]" in json.dumps(v) for v in stale["violations"]),
                        "the seeded fill was meant to be stale against the signed figure")
        status, lines = self.check()
        clearance = [v for v in self.violations(lines) if v[2] == "clearance"]
        self.assertEqual(clearance, [], lines)

    def test_an_unfilled_zone_is_filled_before_it_is_judged(self):
        # A pour on a net with no pad inside it is isolated copper once filled.
        # Saved unfilled, a check that did not refill would never see it.
        self.add_zone("/LV_B", [(30, 15), (36, 15), (36, 19), (30, 19)])
        self.assertFalse(any(v["type"] == "isolated_copper" for v in self.drc()["violations"]))
        status, lines = self.check()
        self.assertEqual(status, 1)
        self.assertIn("isolated_copper", [v[2] for v in self.violations(lines)])
