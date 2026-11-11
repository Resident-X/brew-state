#!/usr/bin/env python3
"""The pre-order check against KiCad itself, on the throwaway proof design: the signed creepage is computed by one pass, not three.

The check runs KiCad's rule check on the board three times, with the design's
rules, with the mounting-hole rules and with the sensing rules. KiCad's creepage
test is the slow one on a poured board, and the second and third pass read no
creepage finding, so their rules hold none. This file runs the check on a design
that fails all three kinds of rule at once and asks what each pass was handed
and what came of it.

This is one of the files the check's KiCad tests are divided into by topic; the
shared setup is in board_kicad_fixtures.py. None of these tests needs the
seeded-fault proof's pooled outcomes, so none derives from Proved.
"""

from __future__ import annotations

import glob
import io
import os
import sys
import tempfile
import unittest
from unittest import mock

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)

import board_check  # noqa: E402
import board_prove  # noqa: E402
from board_kicad_fixtures import load_tests, setUpModule  # noqa: E402,F401
from board_kicad_fixtures import Copy, KICAD_CLI  # noqa: E402

#: The sensing track laid 2 mm beyond the Mains tracks' round ends: inside the signed 3 mm clearance and the signed 4 mm creepage
#: of both, and far inside the 0.5 mm declared for sensing only against a noisy class outside Mains, so it is a sensing finding.
SENSING_X = 24.69 + 2.0 + 0.125
SENSING_UUID = "0b0e5c1a-0000-4000-8000-000000001002"
#: A non-plated hole 3.4 mm from the Mains pad of U1 at (24.19, 18.92), inside the larger of the signed figures, 4 mm.
HOLE_AT = (30.0, 19.0)

#: Lines of the check's output that come from the passes whose rules lose their creepage, and from the pass that keeps it.
HOLE_AND_SENSING = ("mounting_hole", "sensing_clearance")


def seeded(seed) -> None:
    """The design with a creepage shortfall, a mounting hole and a sensing item all inside the signed distance of Mains."""
    seed.layout(lambda tree: (tree.insert(len(tree) - 1, board_prove.segment("/AMP_OUT", SENSING_X, 19, SENSING_X, 25, SENSING_UUID)),
                              tree.insert(len(tree) - 1, board_prove.seeded_hole("H9", *HOLE_AT, board_prove.FIXING_UUID))))


class Run:
    """One run of the check, in this process, on a seeded design: its output lines, and the rules text each KiCad pass was given."""

    def __init__(self, seed, strip=True, extra_creepage=0):
        board_prove.git(seed, "add", "-A")
        board_prove.git(seed, "commit", "-q", "--allow-empty", "-m", "seeded copy")
        self.rules = []
        self.reports = []
        real = board_check.run_report

        def spy(command, cwd):
            texts = []
            if "drc" in command and "pcb" in command:
                for path in glob.glob(os.path.join(cwd, "*.kicad_dru")):
                    with open(path, encoding="utf-8") as handle:
                        texts.append(handle.read())
            report, why = real(command, cwd)
            if report is not None and extra_creepage and "drc" in command and "pcb" in command:
                report = dict(report, violations=list(report.get("violations") or []) + [
                    {"type": "creepage", "description": f"Creepage violation (rule 'extra {n}'; minimum 10 mm; actual 1 mm)", "items": []}
                    for n in range(extra_creepage)])
            self.rules.append("\n".join(texts))
            self.reports.append(report)
            return report, why

        out = io.StringIO()
        patches = [mock.patch.object(board_check, "run_report", spy)]
        if not strip:
            patches.append(mock.patch.object(board_check, "without_creepage", lambda text: text))
        for patch in patches:
            patch.start()
        try:
            self.status = board_check.run(seed.root, KICAD_CLI, out=out)
        finally:
            for patch in patches:
                patch.stop()
        self.lines = out.getvalue().splitlines()

    def violations(self, *rules):
        """The violation lines of the given rules, or all, each with its items in a fixed order and the lines sorted.

        KiCad reports the two items of a violation, and the violations, in an order that differs from one run to
        the next, so a comparison of two runs reads each line's items as a set.
        """
        found = [line.split(" | ") for line in self.lines if line.startswith("VIOLATION | ")]
        found = [fields[:3] + ["; ".join(sorted(fields[3].split("; ")))] + fields[4:] for fields in found
                 if not rules or fields[2] in rules]
        return sorted(found)

    def pass_rules(self, rule_name):
        """The rules text of every KiCad pass whose rules name `rule_name`: the pass that holds that kind of rule."""
        return [text for text in self.rules if f'"{rule_name}' in text or f"'{rule_name}" in text]


class SensingCopy(Copy):
    """A fresh copy of the layout review proof design, the one with a sensing net class and Mains copper."""

    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory(prefix="board-test-")
        self.addCleanup(self.scratch.cleanup)
        self.seed = board_prove.prepare(self.scratch.name, *board_prove.SENSING_TARGET)


class CreepageIsComputedOnce(SensingCopy):
    def setUp(self):
        super().setUp()
        seeded(self.seed)

    def test_the_hole_and_sensing_findings_are_the_same_with_the_creepage_stripped_as_without_it_and_the_creepage_findings_stay(self):
        # SOL-PRE-ORDER-CHECK-CREEPAGE-IS-CHECKED-ONCE-PER-DESIGN.C3: A seeded design gives the same hole and sensing findings with the creepage taken out of their passes as with it left in
        stripped = Run(self.seed)
        kept = Run(self.seed, strip=False)
        for rule in HOLE_AND_SENSING:
            with self.subTest(rule=rule):
                self.assertTrue(stripped.violations(rule), stripped.lines)
                self.assertEqual(stripped.violations(rule), kept.violations(rule))
        # a finding carrying creepage: the one the first pass reports, under the signed rule, with the items it is between
        shortfalls = stripped.violations("creepage")
        self.assertTrue(shortfalls, stripped.lines)
        self.assertEqual(shortfalls, kept.violations("creepage"))
        self.assertEqual(stripped.status, kept.status)

    def test_the_rules_of_the_hole_and_sensing_passes_hold_no_creepage_and_those_of_the_first_pass_do(self):
        # SOL-PRE-ORDER-CHECK-CREEPAGE-IS-CHECKED-ONCE-PER-DESIGN.C2: The rules the mounting-hole pass and the sensing pass hand the rule engine hold no creepage constraint
        # SOL-PRE-ORDER-CHECK-CREEPAGE-IS-CHECKED-ONCE-PER-DESIGN.C1: The signed creepage is computed once per design check, by the first pass that holds the design's own rules
        run = Run(self.seed)
        holes = run.pass_rules(board_check.HOLE_RULE)
        sensing = run.pass_rules(board_check.SENSING_RULE)
        self.assertEqual(len(holes), 1, "one KiCad pass holds the mounting-hole rules")
        self.assertEqual(len(sensing), 1, "one KiCad pass holds the sensing rules")
        for name, text in (("mounting-hole", holes[0]), ("sensing", sensing[0])):
            with self.subTest(pass_=name):
                self.assertNotIn("creepage", text)
                self.assertIn("(constraint clearance (min 3mm))", text, "the signed clearance is still held")
                self.assertIn(f'(rule "{board_check.SIGNED_RULE}"', text)
                self.assertIn('(rule "Mains separation"', text, "the design's own rules are still there, less their creepage")
        first = [text for text in run.rules if f'"{board_check.SIGNED_RULE}"' in text
                 and text not in holes and text not in sensing]
        self.assertTrue(first)
        for text in first:
            self.assertIn(f"(constraint creepage (min 4mm))", text)
        # the design's own file, which the strip never writes back
        self.assertIn("(constraint creepage (min 4mm))", self.seed.read(".kicad_dru"))

    def test_the_creepage_stays_in_the_hole_and_sensing_rules_when_the_strip_is_taken_out_so_the_test_above_would_notice_it_missing(self):
        # SOL-PRE-ORDER-CHECK-CREEPAGE-IS-CHECKED-ONCE-PER-DESIGN.C2: The rules the mounting-hole pass and the sensing pass hand the rule engine hold no creepage constraint
        run = Run(self.seed, strip=False)
        for rule in (board_check.HOLE_RULE, board_check.SENSING_RULE):
            with self.subTest(rule=rule):
                texts = run.pass_rules(rule)
                self.assertEqual(len(texts), 1)
                self.assertIn("(constraint creepage (min 4mm))", texts[0])

    def test_a_report_full_of_creepage_findings_trips_neither_the_assertion_cut_off_nor_the_clearance_bound_of_the_sensing_pass(self):
        # SOL-PRE-ORDER-CHECK-CREEPAGE-IS-CHECKED-ONCE-PER-DESIGN.C3: A seeded design gives the same hole and sensing findings with the creepage taken out of their passes as with it left in
        plain = Run(self.seed)
        crowded = Run(self.seed, extra_creepage=board_check.REPORT_LIMIT * 3)
        self.assertEqual(crowded.violations(*HOLE_AND_SENSING), plain.violations(*HOLE_AND_SENSING))
        for rule in HOLE_AND_SENSING:
            self.assertTrue(plain.violations(rule))
        about_reports = [fields for fields in crowded.violations("sensing_clearance", "mounting_hole") if "cut short" in fields[4] or "as many as" in fields[4]]
        self.assertEqual(about_reports, [])


class TheCreepageFindingStaysWithTheFirstPass(SensingCopy):
    def test_a_creepage_shortfall_alone_is_still_reported_by_the_first_pass(self):
        # SOL-PRE-ORDER-CHECK-CREEPAGE-IS-CHECKED-ONCE-PER-DESIGN.C1: The signed creepage is computed once per design check, by the first pass that holds the design's own rules
        self.seed.layout(lambda tree: tree.insert(len(tree) - 1, board_prove.segment("/AMP_OUT", SENSING_X, 19, SENSING_X, 25, SENSING_UUID)))
        run = Run(self.seed)
        self.assertTrue(run.violations("creepage"), run.lines)
        self.assertEqual(run.status, 1)


if __name__ == "__main__":
    unittest.main()
