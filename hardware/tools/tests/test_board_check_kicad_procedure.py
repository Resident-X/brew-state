#!/usr/bin/env python3
"""The pre-order check against KiCad itself, on the throwaway proof design, here the procedures the check follows: the signed figure, net ties, isolation from the machine, the one command and the seeded-fault proof.

This is one of the files the check's KiCad tests are divided into by topic; the
shared setup, the seeded-fault proof's pooled outcomes and the exclusion of what
needs that proof are in board_kicad_fixtures.py.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest


TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)

import board_check  # noqa: E402
import board_prove  # noqa: E402
from board_kicad_fixtures import load_tests, setUpModule  # noqa: E402,F401
from board_kicad_fixtures import Copy, KICAD_CLI, Proved  # noqa: E402

REPO = os.path.dirname(os.path.dirname(TOOLS))



class TheSignedFigurePrevails(Copy):
    """SOL-HW-BOARD-RULE-CHECK-GATE.C3: The separation basis is a written rule the layout check enforces at no less than the signed figure, and a mains-carrying design without it fails."""

    def test_a_design_declaring_a_stricter_figure_is_held_to_the_record(self):
        self.seed.replace(".kicad_dru", "(min 3mm)", "(min 5mm)")
        self.seed.replace(".kicad_dru", "(min 4mm)", "(min 6mm)")
        x = 25.16 + 0.8 + 4.5 + 0.125
        self.seed.layout(lambda tree: tree.insert(len(tree) - 1, board_prove.segment(
            "/LV_A", x, 9, x, 11, "0b0e5c1a-0000-4000-8000-0000000000b1")))
        status, lines = self.check()
        separation = [v for v in self.violations(lines) if v[2] in ("clearance", "creepage")]
        self.assertEqual(separation, [], "4.5 mm meets the signed 3/4 mm, though not the design's own 5/6 mm")
        board_prove.encroach(self.seed)
        status, lines = self.check()
        clearance = [v for v in self.violations(lines) if v[2] == "clearance"]
        self.assertTrue(clearance and all(f"rule '{board_check.SIGNED_RULE}' clearance 3.0000 mm" in v[4] for v in clearance), lines)

    def test_kicad_ranks_pad_and_footprint_overrides_above_custom_rules(self):
        """The precedence the override guard rests on, measured rather than assumed.

        With the signed rule appended last, a 0.1 mm clearance override on the
        mains pad, or on the footprint carrying it, removes the clearance
        violation the encroaching track raises against that pad. That is why the
        check fails such an override outright rather than trusting the appended
        rule; the zone case follows below, and the net class case is a seeded fault.
        """
        board_prove.encroach(self.seed)
        self.seed.write(".kicad_dru", self.seed.read(".kicad_dru") + board_check.appended_rules((3.0, 4.0), "test"))
        layout = self.seed.read(".kicad_pcb")

        def clearance_against_r1():
            report = self.drc("--all-track-errors")
            return [v for v in report["violations"]
                    if v["type"] == "clearance" and any("of R1" in item["description"] for item in v["items"])]

        self.assertTrue(clearance_against_r1())
        for name, target in (("pad", lambda tree: board_prove.pad(tree, "R1", "2")),
                             ("footprint", lambda tree: board_prove.footprint(tree, "R1"))):
            with self.subTest(override=name):
                self.seed.write(".kicad_pcb", layout)
                self.seed.layout(lambda tree: target(tree).insert(-1, ["clearance", "0.1"]))
                self.assertEqual(clearance_against_r1(), [],
                                 f"KiCad no longer ranks a {name} override above custom rules")

    def test_a_zone_fill_keeps_the_signed_figure_whatever_its_own_clearance(self):
        Q = board_prove.sexpr.Quoted
        zone = ["zone", ["net", Q("/LV_A")], ["layer", Q("F.Cu")], ["uuid", Q("0b0e5c1a-0000-4000-8000-0000000000c1")],
                ["hatch", "edge", "0.5"], ["connect_pads", ["clearance", "0.2"]], ["min_thickness", "0.25"],
                ["fill", ["thermal_gap", "0.5"], ["thermal_bridge_width", "0.5"]],
                ["polygon", ["pts", ["xy", "1", "1"], ["xy", "59", "1"], ["xy", "59", "19"], ["xy", "1", "19"]]]]
        self.seed.layout(lambda tree: tree.insert(len(tree) - 1, zone))
        self.seed.write(".kicad_dru", self.seed.read(".kicad_dru") + board_check.appended_rules((3.0, 4.0), "test"))
        report = self.drc("--refill-zones")
        actual = [float(m) for v in report["violations"] if v["type"] == "creepage" and "Zone [/LV_A]" in json.dumps(v)
                  for m in re.findall(r"actual ([0-9.]+) mm", v["description"])]
        self.assertTrue(actual and min(actual) >= 3.0, report["violations"])
        self.assertFalse([v for v in report["violations"] if v["type"] == "clearance"])



class NetTiesAreExemptFromClearance(Copy):
    """SOL-HW-BOARD-RULE-CHECK-GATE.C3: The separation basis is a written rule the layout check enforces at no less than the signed figure, and a mains-carrying design without it fails.

    The premise the net-tie guard rests on, measured rather than assumed: KiCad
    reports no clearance violation between the pads a net tie joins, even with
    the signed rule appended, so only the check's own guard stops a tie from
    joining low-voltage copper to mains with the signed clearance unchecked.
    """

    def test_kicad_checks_no_clearance_between_tied_pads_and_the_check_fails_the_tie(self):
        # R1's third pad, on /LV_A, sits 0.2 mm from its mains pad 2.
        board_prove.net_tie("2, 3", True)(self.seed)
        self.seed.layout(lambda tree: board_prove.sexpr.child(board_prove.pad(tree, "R1", "3"), "at").__setitem__(
            slice(1, 3), ["12", "0"]))
        self.seed.write(".kicad_dru", self.seed.read(".kicad_dru") + board_check.appended_rules((3.0, 4.0), "test"))
        between = [v for v in self.drc()["violations"] if v["type"] == "clearance"
                   and sum(" of R1" in item["description"] for item in v["items"]) == 2]
        self.assertEqual(between, [], "KiCad now checks clearance between the pads a net tie joins")
        self.seed.write(".kicad_dru", self.seed.read(".kicad_dru").split("\n(rule \"pre-order check test")[0])
        status, lines = self.check()
        self.assertEqual(status, 1)
        self.assertIn("mains_net_tie", [v[2] for v in self.violations(lines)])



class NothingFromTheMachineRunningTheCheck(unittest.TestCase):
    """SOL-HW-BOARD-RULE-CHECK-GATE.C4: One task-runner command runs the whole check with tools any reader can obtain.

    A library named only by the KiCad tables of whoever runs the check is one
    KiCad, run as that user, finds without complaint; the check, which runs
    KiCad with a configuration of its own, fails it by name.
    """

    def test_kicad_run_as_the_user_finds_the_library_and_the_check_does_not(self):
        fault = next(fault for fault in board_prove.FAULTS if fault[4] is board_prove.machine_table_library)
        with tempfile.TemporaryDirectory(prefix="board-test-") as scratch:
            seed = board_prove.prepare(scratch)
            board_prove.machine_table_library(seed)
            status, lines, stderr = board_prove.check(seed, KICAD_CLI)
            out = os.path.join(scratch, "drc.json")
            subprocess.run([KICAD_CLI, "pcb", "drc", "--format", "json", "--severity-all", "-o", out,
                            board_prove.NAME + ".kicad_pcb"], cwd=seed.design, check=True, capture_output=True,
                           env={**os.environ, **seed.environment})
            with open(out, encoding="utf-8") as handle:
                as_the_user = json.load(handle)["violations"]
        self.assertEqual([v for v in as_the_user if v["type"].startswith("lib_footprint")], [],
                         "the seeded library was meant to be found by KiCad run as the user")
        self.assertEqual(status, 1, stderr)
        self.assertTrue(any(" | design_library | " in line and fault[3] in line for line in lines), lines)



class OneCommand(unittest.TestCase):
    """SOL-HW-BOARD-RULE-CHECK-GATE.C4: One task-runner command runs the whole check with tools any reader can obtain."""

    def task(self, *args):
        return subprocess.run(["task", *args], cwd=REPO, capture_output=True, text=True, timeout=1800)

    def test_the_task_runs_the_whole_check_on_the_repository(self):
        result = self.task("hw:verify", f"KICAD_CLI={KICAD_CLI}")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("DESIGN | hardware/proof/gate-proof/gate-proof.kicad_pro | PASS", result.stdout)
        self.assertIn("RESULT | PASS", result.stdout)

    def test_the_task_stops_naming_a_missing_kicad_rather_than_passing(self):
        result = self.task("hw:verify", "KICAD_CLI=/nonexistent/kicad-cli")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("CANNOT RUN | kicad-cli was not found", result.stderr)
        self.assertNotIn("RESULT | PASS", result.stdout)



def tree_digest(path: str) -> str:
    digest = hashlib.sha256()
    for directory, _, names in sorted(os.walk(path)):
        for name in sorted(names):
            full = os.path.join(directory, name)
            digest.update(os.path.relpath(full, path).encode())
            with open(full, "rb") as handle:
                digest.update(handle.read())
    return digest.hexdigest()



class TheSeededFaultProof(Proved):
    """SOL-HW-BOARD-RULE-CHECK-GATE.C5: Each check this leaf enforces is shown to fail on a fault seeded for it in a throwaway design."""

    def test_the_clean_design_passes_and_every_fault_is_caught_without_touching_the_tree(self):
        before = tree_digest(os.path.join(board_prove.REPO, board_prove.DESIGN))
        out = io.StringIO()
        sys_stdout, sys.stdout = sys.stdout, out
        try:
            status = board_prove.main(["--kicad-cli", KICAD_CLI])
        finally:
            sys.stdout = sys_stdout
        lines = out.getvalue().splitlines()
        self.assertEqual(status, 0, out.getvalue())
        self.assertTrue(lines[0].startswith("CLEAN | "), lines[0])
        self.assertEqual(sum(line.startswith("CAUGHT | ") for line in lines), len(board_prove.FAULTS))
        self.assertEqual(tree_digest(os.path.join(board_prove.REPO, board_prove.DESIGN)), before, "the proof touched the committed design")



class TheProofDesignAndItsFaults(unittest.TestCase):
    """SOL-HW-BOARD-RULE-CHECK-GATE.C5: Each check this leaf enforces is shown to fail on a fault seeded for it in a throwaway design.

    What the proof is made of, read without running it.
    """

    def test_the_proof_design_is_marked_not_for_manufacture_and_carries_a_synthetic_record(self):
        with open(os.path.join(board_prove.REPO, board_prove.DESIGN, "gate-proof.kicad_pro"), encoding="utf-8") as handle:
            variables = json.load(handle)["text_variables"]
        self.assertEqual(variables.get("NOT_FOR_MANUFACTURE"), "true")
        self.assertEqual(variables.get("MAINS"), "present")
        with open(os.path.join(board_prove.REPO, board_prove.DESIGN, "separation-basis.yaml"), encoding="utf-8") as handle:
            self.assertIs(board_check.require_yaml().safe_load(handle)["synthetic"], True)

    def test_every_rule_the_check_reports_of_its_own_has_a_seeded_fault(self):
        with open(os.path.join(TOOLS, "board_check.py"), encoding="utf-8") as handle:
            source = handle.read()
        own = set(re.findall(r'Violation\(\s*(?:[\w.]+|"[^"]*"),\s*"([a-z_]+)"', source))
        self.assertGreaterEqual(own, {"design_discovery", "design_unreadable", "ignored_check", "custom_rules",
                                      "mains_declaration", "mains_class", "design_library", "local_clearance_override",
                                      "project_file", "mains_net_tie", "separation_rule", "separation_basis"})
        seeded = {fault[2] for fault in board_prove.FAULTS}
        self.assertEqual(own - seeded, set(), "a rule the check reports of its own has no seeded fault proving it")
