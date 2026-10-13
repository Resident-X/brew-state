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

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)

import board_check  # noqa: E402
import board_prove  # noqa: E402

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
        schematic or layout, and a board file without its project each fail.
        """
        self.assertCaught("an empty tree", "a layout that cannot be opened", "a schematic that cannot be opened",
                          "a project file that cannot be read", "a project missing its schematic",
                          "a project missing its layout", "a layout committed without its project",
                          "a schematic committed without its project",
                          "a sheet left out of the commit of the schematic naming it",
                          "a library the design's table names that git does not track", "a library table git does not track",
                          "a library named outside the repository", "a library named by an absolute path",
                          "a library reached through one machine's own path variable")


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
        """SOL-HW-BOARD-RULE-CHECK-GATE.C2: A design passes only if KiCad's own electrical and layout rule checks find no violation, including no layout-schematic disagreement."""
        self.assertCaught("an electrical rule violation", "a layout clearance violation", "layout-schematic disagreement",
                          "a violation marked as excluded", "a custom rule marking its violations excluded",
                          "a layout rule set to ignore", "an electrical rule set to ignore",
                          "a rule left at KiCad's own default of ignore", "a custom rule set to ignore",
                          "a rules file KiCad declines to load", "a rules file that is not well-formed",
                          "a rules file without its version header",
                          "an untracked custom rules file", "a design rule taking a name reserved for the check's own rules")

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
        self.assertEqual(found[0][3], "hardware/proof/gate-proof/gate-proof.kicad_dru rule 'typo' at line 10")
        self.assertIn("this is the rule it rejects", found[0][4])

    def test_a_form_that_is_not_a_rule_is_named(self):
        found = self.rejected(self.seed.read(".kicad_dru") + "(rules \"x\")\n")
        self.assertEqual(found[0][3], "hardware/proof/gate-proof/gate-proof.kicad_dru the rules form at line 9")


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
        with open(os.path.join(board_prove.PROOF, "gate-proof.kicad_pro"), encoding="utf-8") as handle:
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


# --- C4 -----------------------------------------------------------------------


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
        before = tree_digest(board_prove.PROOF)
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
        self.assertEqual(tree_digest(board_prove.PROOF), before, "the proof touched the committed design")

    def test_the_proof_design_is_marked_not_for_manufacture_and_carries_a_synthetic_record(self):
        with open(os.path.join(board_prove.PROOF, "gate-proof.kicad_pro"), encoding="utf-8") as handle:
            variables = json.load(handle)["text_variables"]
        self.assertEqual(variables.get("NOT_FOR_MANUFACTURE"), "true")
        self.assertEqual(variables.get("MAINS"), "present")
        with open(os.path.join(board_prove.PROOF, "separation-basis.yaml"), encoding="utf-8") as handle:
            self.assertIs(board_check.require_yaml().safe_load(handle)["synthetic"], True)

    def test_every_rule_the_check_reports_of_its_own_has_a_seeded_fault(self):
        with open(os.path.join(TOOLS, "board_check.py"), encoding="utf-8") as handle:
            source = handle.read()
        own = set(re.findall(r'Violation\(\s*(?:[\w.]+|"[^"]*"),\s*"([a-z_]+)"', source))
        self.assertGreaterEqual(own, {"design_discovery", "design_unreadable", "ignored_check", "custom_rules",
                                      "mains_declaration", "mains_class", "design_library", "local_clearance_override"})
        seeded = {fault[2] for fault in board_prove.FAULTS}
        self.assertEqual(own - seeded, set(), "a rule the check reports of its own has no seeded fault proving it")


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
        self.assertEqual(lines[1:], ["DESIGN | hardware/proof/gate-proof/gate-proof.kicad_pro | PASS",
                                     "RESULT | PASS | all 1 designs passed"])


if __name__ == "__main__":
    unittest.main()
