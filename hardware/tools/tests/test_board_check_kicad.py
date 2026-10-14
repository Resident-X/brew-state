#!/usr/bin/env python3
"""The pre-order check against KiCad itself, on the throwaway proof design.

These run the shipped check, through the shipped command where it matters, on
copies of hardware/proof/gate-proof in temporary git work trees outside the
repository, with the real kicad-cli named by KICAD_CLI (or found on the search
path). Nothing is skipped when KiCad is absent: a missing tool fails the run,
because a check that cannot be exercised has not been shown to work.

Every seeded fault is proved once for the whole module and shared, since each
costs two KiCad runs; the tests below then ask of those outcomes what each
criterion needs. A few behaviours are not faults but procedures the check must
follow -- refilling zones, holding a stricter design to the signed figure, the
report's shape across several designs -- and those are driven directly.
"""

from __future__ import annotations

import concurrent.futures
import datetime
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from typing import Tuple
from unittest import mock

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)

import board_check  # noqa: E402
import board_geometry  # noqa: E402
import board_prove  # noqa: E402
import board_views  # noqa: E402
import locked_copper  # noqa: E402
import sexpr  # noqa: E402

REPO = os.path.dirname(os.path.dirname(TOOLS))
KICAD_CLI = os.environ.get("KICAD_CLI") or "kicad-cli"

_OUTCOMES = {}


def setUpModule():
    board_check.require_kicad(KICAD_CLI)


def outcomes():
    """Every seeded fault's outcome, proved once: name -> (caught, evidence)."""
    if not _OUTCOMES:
        with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, min(8, (os.cpu_count() or 2) // 2))) as pool:
            results = pool.map(lambda fault: board_prove.prove(fault, KICAD_CLI), board_prove.FAULTS)
            for fault, result in zip(board_prove.FAULTS, results):
                _OUTCOMES[fault[0]] = result
    return _OUTCOMES


class Proved(unittest.TestCase):
    def assertCaught(self, *names: str):
        found = outcomes()
        for name in names:
            with self.subTest(fault=name):
                self.assertIn(name, found, "no such seeded fault")
                caught, evidence = found[name]
                self.assertTrue(caught, evidence)


class Copy(unittest.TestCase):
    """A fresh copy of the proof design in its own git work tree."""

    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory(prefix="board-test-")
        self.addCleanup(self.scratch.cleanup)
        self.seed = board_prove.prepare(self.scratch.name)

    def check(self):
        status, lines, stderr = board_prove.check(self.seed, KICAD_CLI)
        self.assertNotEqual(status, 2, stderr)
        return status, lines

    def violations(self, lines):
        return [line.split(" | ") for line in lines if line.startswith("VIOLATION | ")]

    def drc(self, *flags):
        """KiCad's own DRC report on the copy as it stands, without the check in between."""
        out = os.path.join(self.scratch.name, "drc.json")
        subprocess.run([KICAD_CLI, "pcb", "drc", "--format", "json", "--severity-all", *flags, "-o", out,
                        board_prove.NAME + ".kicad_pcb"], cwd=self.seed.design, check=True, capture_output=True)
        with open(out, encoding="utf-8") as handle:
            return json.load(handle)


# --- C1 -----------------------------------------------------------------------


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


# --- C2 -----------------------------------------------------------------------


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
        self.assertEqual(len(forged), 8, lines)


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


# --- C3 -----------------------------------------------------------------------


class Separation(Proved):
    def test_every_separation_failure_fails(self):
        """SOL-HW-BOARD-RULE-CHECK-GATE.C3: The separation basis is a written rule the layout check enforces at no less than the signed figure, and a mains-carrying design without it fails."""
        self.assertCaught(*[fault[0] for fault in board_prove.FAULTS if fault[1].startswith("separation:")])


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


# --- C4 -----------------------------------------------------------------------


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


# --- C5 -----------------------------------------------------------------------


def tree_digest(path: str) -> str:
    digest = hashlib.sha256()
    for directory, _, names in sorted(os.walk(path)):
        for name in sorted(names):
            full = os.path.join(directory, name)
            digest.update(os.path.relpath(full, path).encode())
            with open(full, "rb") as handle:
                digest.update(handle.read())
    return digest.hexdigest()


class TheSeededFaultProof(unittest.TestCase):
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


# --- Workmanship ---------------------------------------------------------------------


class TheWorkmanshipRules(Proved):
    # SOL-BOARD-LAYOUT-WORKMANSHIP-ITEMS.C2: The pre-order check measures every rule-kind workmanship item and fails a board that breaks one
    """Each rule, KiCad's and measured alike, fails on a fault seeded for it in a
    throwaway copy of the gate's proof design outside the repository, and the
    clean copy passes with every rule in force.
    """

    def test_every_workmanship_rule_fails_on_its_seeded_fault(self):
        workmanship = [fault[0] for fault in board_prove.FAULTS if fault[1].startswith("workmanship:")]
        self.assertCaught(*workmanship)
        rules = {fault[2] for fault in board_prove.FAULTS if fault[1].startswith("workmanship:")}
        # Every KiCad check a workmanship item rests on, every measured rule, and the figures and rules the design must carry.
        self.assertGreaterEqual(rules, {"track_angle", "track_segment_length", "track_dangling", "via_dangling", "workmanship_pad_corner",
                                        "workmanship_detour", "workmanship_direction", "workmanship_pad_entry",
                                        "workmanship_width", "workmanship_pad_copper", "workmanship_rule", "workmanship_figure"})

    def test_each_kicad_finding_and_measured_failure_names_the_item(self):
        found = outcomes()
        for name, item in (("a right-angled corner", "WORK-4"), ("a short jog", "WORK-5"), ("an unneeded via", "WORK-7"),
                           ("a short stub", "WORK-6"), ("a route wandering the long way round", "WORK-2"),
                           ("a route narrowed partway along", "WORK-8"),
                           ("a track off the board's edges and the 45 degrees to them", "WORK-9"),
                           ("a track entering a long pad from its side", "WORK-10")):
            with self.subTest(fault=name):
                caught, line = found[name]
                self.assertTrue(caught, line)
                self.assertIn(item, line)
                self.assertRegex(line.split(" | ")[3], r"\(\d+(\.\d+)?, \d+(\.\d+)?\) mm", "a failure names where on the board it is")


class KiCadComparesTracksEverywhereButAtAPad(Copy):
    # SOL-BOARD-LAYOUT-WORKMANSHIP-ITEMS.C2: The pre-order check measures every rule-kind workmanship item and fails a board that breaks one
    """The method tells a designer to branch a route at a pad because KiCad's
    corner rule compares every two tracks meeting on one layer anywhere else;
    this holds that to what the installed KiCad does.
    """

    def test_a_branch_at_a_pad_passes_and_one_off_a_track_or_a_via_fails(self):
        at_pad = board_prove.reroute("/LV_A", (board_prove.LV_A_ENDS,), [(40, 10), (45, 10), (45, 7)])
        at_pad(self.seed)
        drc = self.drc()
        self.assertFalse([v for v in drc["violations"] if v["type"] == "track_angle"], drc["violations"])
        self.setUp()
        board_prove.reroute("/LV_A", (board_prove.LV_A_ENDS,), [(40, 10), (42, 10), (45, 10)])(self.seed)
        self.seed.layout(lambda tree: tree.insert(len(tree) - 1, board_prove.segment("/LV_A", 42, 10, 42, 6, "0b0e5c1a-0000-4000-8000-0000000002ff")))
        angles = [v for v in self.drc()["violations"] if v["type"] == "track_angle"]
        self.assertTrue(angles, "a branch off the middle of a route is compared with each side of it")
        self.assertIn("actual 90.000", angles[0]["description"])


class KiCadReportsATrackEndingFreeUnaided(Copy):
    # SOL-BOARD-LAYOUT-WORKMANSHIP-ITEMS.C2: The pre-order check measures every rule-kind workmanship item and fails a board that breaks one
    """The stub item rests on KiCad's own unconnected-track-end check, with no
    rule and no figure of the check's own, so this holds that to what the
    installed KiCad does for a stub wherever it leaves the route, and to the
    check failing the design on it.
    """

    def test_a_stub_off_a_pad_off_a_track_or_lying_loose_is_reported_and_fails_the_design(self):
        stubs = {
            "off a pad": [("/LV_A", 45, 10, 45, 8.5)],
            "off the middle of a track": [("/LV_A", 42, 10, 42, 8.5)],
            "lying loose": [("/LV_A", 47, 6, 49, 6)],
        }
        for where, tracks in stubs.items():
            with self.subTest(stub=where):
                self.setUp()
                self.seed.layout(lambda tree: [tree.insert(len(tree) - 1, board_prove.segment(*track, f"0b0e5c1a-0000-4000-8000-0000000005{index:02d}"))
                                               for index, track in enumerate(tracks)])
                if where == "off the middle of a track":
                    board_prove.reroute("/LV_A", (board_prove.LV_A_ENDS,), [(40, 10), (42, 10), (45, 10)])(self.seed)
                dangling = [v for v in self.drc()["violations"] if v["type"] == "track_dangling"]
                self.assertTrue(dangling, f"KiCad reports no stub {where}")
                status, lines = self.check()
                self.assertEqual(status, 1, lines)
                self.assertTrue([line for line in lines if " | track_dangling | " in line and "workmanship item WORK-6" in line], lines)


class TheCheckReadsATrackMeetingAPadAsKiCadDoes(Copy):
    # SOL-BOARD-LAYOUT-WORKMANSHIP-ITEMS.C2: The pre-order check measures every rule-kind workmanship item and fails a board that breaks one
    """Every measure that asks whether a track meets a pad rests on
    board_geometry's contact rule, so this holds that rule to the installed
    KiCad's own connectivity: /LV_A is redrawn as one track meeting R2's
    1.6 mm round pad 1 just so or just missing it, and the rule must join the
    two exactly when KiCad reports no unconnected item between them.
    """

    CASES = (
        ("an end cap reaching the pad's edge by 0.025 mm", [(40, 10), (44.1, 10)], True),
        ("an end cap stopping 0.025 mm short of it", [(40, 10), (44.05, 10)], False),
        ("copper running over the pad 0.025 mm deep, off its centre, neither end on it", [(40, 10.9), (48, 10.9)], True),
        ("copper running past the pad 0.025 mm clear of it", [(40, 10.95), (48, 10.95)], False),
    )

    def test_the_contact_rule_joins_a_track_to_a_pad_exactly_when_kicad_does(self):
        for what, points, joined in self.CASES:
            with self.subTest(track=what):
                self.setUp()
                board_prove.reroute("/LV_A", (board_prove.LV_A_ENDS,), points)(self.seed)
                report = self.drc()
                kicad = not any("pad 1 [/LV_A] of R2" in item["description"]
                                for unconnected in report["unconnected_items"] for item in unconnected["items"])
                self.assertEqual(kicad, joined, f"KiCad was expected {'to join' if joined else 'not to join'} {what}")
                layout = board_check.Layout(sexpr.parse_one(self.seed.read(".kicad_pcb")))
                pad = next(pad for pad in layout.pads if pad.name() == "pad 1 of R2")
                ours = any(board_geometry.joins(pad, copper.points(), copper.width) for copper in layout.copper if copper.net == "/LV_A")
                self.assertEqual(ours, kicad, f"the contact rule and KiCad disagree on {what}")


# --- C6 -----------------------------------------------------------------------


class TheReport(Copy):
    """SOL-HW-BOARD-RULE-CHECK-GATE.C6: The check's report names each design, its verdict and every violation in terms a builder can act on."""

    def test_each_design_gets_a_verdict_each_violation_one_line_and_the_exit_status_matches(self):
        second = os.path.join(self.seed.root, "hardware", "other", "board")
        shutil.copytree(self.seed.design, second)
        for name in os.listdir(second):
            if name.startswith(board_prove.NAME):
                os.rename(os.path.join(second, name), os.path.join(second, name.replace(board_prove.NAME, "board")))
        board_prove.crowd(self.seed)
        status, lines = self.check()
        self.assertEqual(status, 1)
        self.assertIn("DESIGN | hardware/other/board/board.kicad_pro | PASS", lines)
        failing = "hardware/proof/gate-proof/gate-proof.kicad_pro"
        verdict = [line for line in lines if line.startswith(f"DESIGN | {failing} | FAIL | ")]
        self.assertEqual(len(verdict), 1, lines)
        self.assertEqual(lines[-1], "RESULT | FAIL | 1 of 2 designs failed")
        violations = self.violations(lines)
        self.assertTrue(violations)
        for fields in violations:
            self.assertEqual(len(fields), 5, fields)
            self.assertEqual(fields[1], failing)
            self.assertTrue(all(fields[2:]), fields)
        count = int(re.search(r"FAIL \| (\d+) violation", verdict[0]).group(1))
        self.assertEqual(count, len(violations))
        clearance = [v for v in violations if v[2] == "clearance"][0]
        self.assertIn("PTH pad 2 [/LV_B] of R2 @ (55.16, 10) mm", clearance[3])
        self.assertIn("Clearance violation (netclass 'Default' clearance 0.2000 mm; actual 0.1000 mm)", clearance[4])

    def test_a_clean_tree_reports_every_design_passing_and_exits_zero(self):
        status, lines = self.check()
        self.assertEqual(status, 0, lines)
        self.assertEqual(lines[1], "DESIGN | hardware/proof/gate-proof/gate-proof.kicad_pro | PASS")
        self.assertIn("FIGURE | hardware/proof/gate-proof/gate-proof.kicad_pro | WORK-4 corner at a pad | the rules file's "
                      "track_angle | 135 degrees at least between two tracks of a net that meet at a pad, as at any other joint", lines)
        self.assertEqual([line for line in lines[2:] if not line.startswith("FIGURE | ")],
                         ["RESULT | PASS | all 1 designs passed"])


# --- Class membership on a board of any size -----------------------------------


#: Ten Mains nets, nine in the class by the project file's pattern and one by
#: its name, each carrying 22 tracks: 220 items between them, more than KiCad
#: reports failures of one kind. Thirty low-voltage nets of three tracks each
#: bring the board to 310 items.
MAINS_NETS = {f"/MAINS_{index}" for index in range(9)} | {"/LIVE_FEED"}
LV_NETS = {f"/LV_{index:02d}" for index in range(30)}

LAYERS = ('\t(layers\n\t\t(0 "F.Cu" signal)\n\t\t(2 "B.Cu" signal)\n\t\t(13 "F.Paste" user)\n\t\t(15 "B.Paste" user)\n'
          '\t\t(5 "F.SilkS" user "F.Silkscreen")\n\t\t(7 "B.SilkS" user "B.Silkscreen")\n\t\t(1 "F.Mask" user)\n'
          '\t\t(3 "B.Mask" user)\n\t\t(25 "Edge.Cuts" user)\n\t)\n')


def tracks_board(path: str, tracks) -> None:
    """A KiCad 10 board at `path` holding nothing but the given (net, count) tracks, each a 1 mm segment, inside an outline."""
    body = ""
    for row, (net, count) in enumerate(tracks):
        for column in range(count):
            body += (f'\t(segment (start {2 * column} {3 * row}) (end {2 * column + 1} {3 * row}) (width 0.25) '
                     f'(layer "F.Cu") (net {board_check.quoted(net)}) (uuid "00000000-0000-4000-8000-{row:06d}{column:06d}"))\n')
    with open(path, "w", encoding="utf-8") as handle:
        handle.write('(kicad_pcb\n\t(version 20260206)\n\t(generator "pcbnew")\n\t(generator_version "10.0")\n'
                     '\t(general (thickness 1.6))\n\t(paper "A4")\n' + LAYERS
                     + '\t(gr_rect (start -5 -5) (end 600 1000) (stroke (width 0.1) (type solid)) (fill no) '
                       '(layer "Edge.Cuts") (uuid "00000000-0000-4000-8000-ffffffffffff"))\n' + body + ")\n")


def over_limit_design(folder: str) -> Tuple[str, str]:
    """The over-limit board and its project file, b.kicad_pcb and b.kicad_pro in `folder`."""
    os.makedirs(folder, exist_ok=True)
    board, project = os.path.join(folder, "b.kicad_pcb"), os.path.join(folder, "b.kicad_pro")
    tracks_board(board, [(net, 22) for net in sorted(MAINS_NETS)] + [(net, 3) for net in sorted(LV_NETS)])
    with open(os.path.join(board_prove.REPO, board_prove.DESIGN, "gate-proof.kicad_pro"), encoding="utf-8") as handle:
        data = json.load(handle)
    data["net_settings"]["netclass_assignments"] = {"/LIVE_FEED": "Mains"}
    data["board"]["design_settings"].setdefault("rules", {}).update(min_track_width=0.2, min_clearance=0.2)
    with open(project, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=1)
    return board, project


class TheReportLimitIsKiCads(unittest.TestCase):
    """The report limit the class read is batched against is the one the installed KiCad keeps to."""

    def test_an_assertion_every_item_fails_is_reported_exactly_the_limit_times(self):
        # SOL-HW-BOARD-CLASS-READ-ANY-SIZE.C1: A net class's membership is read completely and identically on every run, on a board of any size
        with tempfile.TemporaryDirectory(prefix="board-test-") as scratch:
            tracks_board(os.path.join(scratch, "b.kicad_pcb"), [("/N", board_check.REPORT_LIMIT + 50)])
            with open(os.path.join(scratch, "b.kicad_dru"), "w", encoding="utf-8") as handle:
                handle.write("(version 1)\n" + board_check.marker("limit"))
            report, why = board_check.run_report([KICAD_CLI, "pcb", "drc", "--format", "json", "--severity-all",
                                                  "b.kicad_pcb"], scratch)
        self.assertIsNotNone(report, why)
        self.assertEqual(len(board_check.fired(report, board_check.marker_rule("limit"))), board_check.REPORT_LIMIT)


class AClassIsReadWholeOnABoardOfAnySize(unittest.TestCase):
    """On a board whose Mains nets alone carry more items than KiCad reports, the class read and every reader of it see the class whole."""

    @classmethod
    def setUpClass(cls):
        cls.scratch = tempfile.TemporaryDirectory(prefix="board-test-")
        cls.folder = os.path.join(cls.scratch.name, "repository", "over")
        cls.board, cls.project = over_limit_design(cls.folder)
        cls.layout = locked_copper.read_layout(cls.board)

    @classmethod
    def tearDownClass(cls):
        cls.scratch.cleanup()

    def test_the_board_is_past_the_limit_on_its_mains_nets_alone(self):
        # SOL-HW-BOARD-CLASS-READ-ANY-SIZE.C1: A net class's membership is read completely and identically on every run, on a board of any size
        items = board_check.net_items(self.layout)
        self.assertGreater(sum(len(items[net]) for net in MAINS_NETS), board_check.REPORT_LIMIT)
        self.assertEqual(set(items), MAINS_NETS | LV_NETS)

    def test_the_mains_class_is_read_exactly_on_every_run(self):
        # SOL-HW-BOARD-CLASS-READ-ANY-SIZE.C1: A net class's membership is read completely and identically on every run, on a board of any size
        for run in range(3):
            with self.subTest(run=run), tempfile.TemporaryDirectory(prefix="board-test-") as work:
                found, why = board_check.class_members(KICAD_CLI, work, self.project, ["Mains"],
                                                       board_check.layout_nets(self.layout), f"run{run}",
                                                       board_check.layout_version(self.layout),
                                                       board_check.class_blocks(self.layout))
                self.assertEqual(found, {"Mains": MAINS_NETS}, why)

    def test_the_pre_order_check_sees_that_set(self):
        # SOL-HW-BOARD-CLASS-READ-ANY-SIZE.C1: A net class's membership is read completely and identically on every run, on a board of any size
        root = os.path.dirname(self.folder)
        with open(os.path.join(self.folder, "b.kicad_sch"), "w", encoding="utf-8") as handle:
            handle.write('(kicad_sch\n\t(version 20250114)\n\t(generator "eeschema")\n'
                         '\t(uuid "0b0e5c1a-0000-4000-8000-0000000000f0")\n\t(paper "A4")\n)\n')
        repository = board_check.Repository(root, ["over/b.kicad_pro", "over/b.kicad_sch", "over/b.kicad_pcb"])
        found = board_check.check_design(board_check.Design("over/b.kicad_pro"), repository, KICAD_CLI,
                                         board_check.require_yaml(), datetime.date.today(), [])
        # The schematic holds no net, so each net the layout and the project
        # file put in Mains is named as missing from the schematic alone.
        said = {}
        for violation in found:
            match = re.match(r"net (\S+) is in the Mains net class (.*?) but not (.*?); ", violation.message)
            if violation.rule == "mains_class" and match:
                said[match.group(1)] = (match.group(2), match.group(3))
        self.assertEqual(said, {net: ("on the layout and in the project file's net settings", "in the schematic")
                                for net in MAINS_NETS}, found)
        self.assertFalse([v for v in found if v.rule in ("mains_declaration", "design_unreadable")], found)

    def test_the_locked_copper_reading_sees_that_set(self):
        # SOL-HW-BOARD-CLASS-READ-ANY-SIZE.C1: A net class's membership is read completely and identically on every run, on a board of any size
        self.assertEqual(locked_copper.members(KICAD_CLI, self.board, self.project, self.layout, ["Mains"]),
                         {"Mains": MAINS_NETS})

    def test_the_review_views_see_that_set(self):
        # SOL-HW-BOARD-CLASS-READ-ANY-SIZE.C1: A net class's membership is read completely and identically on every run, on a board of any size
        # The views read every class the design defines, Default too, with
        # Mains alone carrying more items than KiCad's report limit; the render
        # is stopped once the membership it draws from has been read.
        seen = {}
        members = locked_copper.members

        class Read(Exception):
            pass

        def spy(*args):
            seen.update(members(*args))
            raise Read()

        with tempfile.TemporaryDirectory(prefix="board-test-") as out, \
                mock.patch.object(locked_copper, "members", side_effect=spy):
            with self.assertRaises(Read):
                board_views.views(self.board, self.project, ["Mains"], os.path.join(out, "views"), KICAD_CLI,
                                  "resvg", io.StringIO())
        self.assertEqual(seen["Mains"], MAINS_NETS)
        self.assertEqual(seen["Default"], LV_NETS)


class AReportCutShortFailsTheCheck(unittest.TestCase):
    """A design whose own assertion rules fail on more items than KiCad reports fails, rather than passing on what was left."""

    def test_a_design_rule_failing_on_more_items_than_the_limit_fails_saying_the_report_was_cut_short(self):
        # SOL-HW-BOARD-CLASS-READ-ANY-SIZE.C1: A net class's membership is read completely and identically on every run, on a board of any size
        with tempfile.TemporaryDirectory(prefix="board-test-") as scratch:
            seed = board_prove.prepare(scratch)
            seed.write(".kicad_dru", seed.read(".kicad_dru") + '(rule "no tracks"\n\t(condition "A.Type == \'Track\'")\n'
                                                               '\t(constraint assertion "false"))\n')

            def crowd_with_tracks(tree):
                for index in range(board_check.REPORT_LIMIT + 20):
                    x, y = 2 * (index % 25), 40 + 2 * (index // 25)
                    tree.insert(len(tree) - 1, board_prove.segment("/LV_B", x, y, x + 1, y,
                                                                   f"0b0e5c1a-0000-4000-8000-{index:012d}"))

            seed.layout(crowd_with_tracks)
            status, lines, stderr = board_prove.check(seed, KICAD_CLI)
        self.assertEqual(status, 1, stderr)
        cut = [line for line in lines if " | custom_rules | " in line and "KiCad's report was cut short" in line]
        self.assertEqual(len(cut), 1, lines)
        self.assertFalse([line for line in lines if "did not load" in line], lines)


if __name__ == "__main__":
    unittest.main()
