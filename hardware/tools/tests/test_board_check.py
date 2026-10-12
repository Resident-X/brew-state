#!/usr/bin/env python3
"""The pre-order check's own decisions, driven on synthetic fixtures with no KiCad involved.

What is under test here is everything the check decides for itself rather than
asks KiCad: which files make up a design and which belong to none, whether a
separation basis record is signed and usable, whether a design's own Mains rule
is in the one form it may take, which clearance overrides would outrank the
signed figure, what a project file marks as excluded, and whether the tools it
needs are there. Each of these can be wrong while KiCad's checks still run and
report nothing, which is exactly the failure worth a test: a pass that is not
one. What KiCad itself finds is driven against the real tool in
test_board_check_kicad.py.
"""

from __future__ import annotations

import datetime
import io
import os
import stat
import subprocess
import sys
import tempfile
import types
import unittest
from unittest import mock

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)

import board_check  # noqa: E402
import sexpr  # noqa: E402

REPO = os.path.dirname(os.path.dirname(TOOLS))
TODAY = datetime.date(2026, 10, 12)

SIGNED_RECORD = """\
standard: synthetic
mains_to_low_voltage:
  clearance_mm: 3.0
  creepage_mm: 4.0
accepted_by: maintainer
accepted_on: 2026-10-01
"""

MAINS_RULE = """\
(version 1)
(rule "Mains separation"
	(condition "A.hasNetclass('Mains') && !B.hasNetclass('Mains')")
	(constraint clearance (min 3mm))
	(constraint creepage (min 4mm)))
"""


def write(root: str, path: str, text: str) -> str:
    full = os.path.join(root, path)
    os.makedirs(os.path.dirname(full) or root, exist_ok=True)
    with open(full, "w", encoding="utf-8") as handle:
        handle.write(text)
    return path


def schematic(*sheets: str) -> str:
    body = "".join(
        f'\t(sheet\n\t\t(at 0 0)\n\t\t(property "Sheetname" "s{i}")\n\t\t(property "Sheetfile" "{path}")\n\t)\n'
        for i, path in enumerate(sheets))
    return f'(kicad_sch\n\t(version 20250114)\n{body})\n'


def fake_tool(path: str, script: str) -> str:
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("#!/bin/sh\n" + script + "\n")
    os.chmod(path, os.stat(path).st_mode | stat.S_IEXEC)
    return path


class Tree(unittest.TestCase):
    """A synthetic repository in a temporary directory."""

    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory()
        self.addCleanup(self.scratch.cleanup)
        self.root = self.scratch.name

    def write(self, path: str, text: str = "") -> str:
        return write(self.root, path, text)


# --- The S-expression reader ---------------------------------------------------


class TheReaderKeepsWhatKiCadMeans(unittest.TestCase):
    """The rules, layout and schematic files are read as KiCad reads them.

    SOL-HW-BOARD-RULE-CHECK-GATE.C2: the layout check reads the design's rules
    from its project files as written. A reader that dropped a form, or read a
    quoted string as an atom, would let the check misjudge a rule KiCad enforces.
    """

    def test_round_trip_keeps_quoting_escapes_and_order(self):
        text = '(rule "a \\"b\\"" (condition "A.x == \'1\'") hide (layer outer) last)'
        tree = sexpr.parse(text)
        again = sexpr.parse(sexpr.dump(tree[0]))
        self.assertEqual(again, tree)
        self.assertIsInstance(tree[0][1], sexpr.Quoted)
        self.assertNotIsInstance(tree[0][3], sexpr.Quoted)
        self.assertEqual(tree[0][-1], "last")

    def test_comments_are_read_only_where_kicad_allows_them(self):
        rules = sexpr.parse('# a note (with a paren\n(version 1) # trailing\n(rule "r#1")', comments=True)
        self.assertEqual(rules, [["version", "1"], ["rule", "r#1"]])
        with self.assertRaises(sexpr.SexprError):
            sexpr.parse('# a note (with a paren\n(version 1)')

    def test_malformed_text_is_refused(self):
        for text in ("(rule", "(rule))", '(rule "open)', ""):
            with self.subTest(text=text), self.assertRaises(sexpr.SexprError):
                sexpr.parse_one(text)


# --- Discovery ------------------------------------------------------------------


class EveryDesignIsFoundBecauseItExists(Tree):
    """SOL-HW-BOARD-RULE-CHECK-GATE.C1: Every board design in the repository is checked because it exists, not because it is listed."""

    def test_a_design_anywhere_is_found_with_its_schematic_and_layout(self):
        files = [self.write(p) for p in ("boards/a/a.kicad_pro", "boards/a/a.kicad_pcb")]
        files.append(self.write("boards/a/a.kicad_sch", schematic()))
        files += [self.write(p) for p in ("deep/er/b/b.kicad_pro", "deep/er/b/b.kicad_pcb")]
        files.append(self.write("deep/er/b/b.kicad_sch", schematic()))
        designs, orphans, problems = board_check.discover(self.root, files)
        self.assertEqual([d.project for d in designs], ["boards/a/a.kicad_pro", "deep/er/b/b.kicad_pro"])
        self.assertEqual(orphans, [])
        self.assertEqual(problems, {"boards/a/a.kicad_pro": [], "deep/er/b/b.kicad_pro": []})

    def test_a_design_added_to_the_tree_is_checked_without_editing_any_list(self):
        subprocess.run(["git", "init", "-q", self.root], check=True)
        for path in ("x/x.kicad_pro", "x/x.kicad_pcb"):
            self.write(path)
        self.write("x/x.kicad_sch", schematic())
        subprocess.run(["git", "-C", self.root, "add", "-A"], check=True)
        designs, _, _ = board_check.discover(self.root, board_check.tracked_files("git", self.root))
        self.assertEqual([d.project for d in designs], ["x/x.kicad_pro"])
        self.write("y/new.kicad_pro"), self.write("y/new.kicad_pcb"), self.write("y/new.kicad_sch", schematic())
        subprocess.run(["git", "-C", self.root, "add", "-A"], check=True)
        designs, _, _ = board_check.discover(self.root, board_check.tracked_files("git", self.root))
        self.assertEqual([d.project for d in designs], ["x/x.kicad_pro", "y/new.kicad_pro"])

    def test_a_project_without_its_schematic_or_layout_fails_by_name(self):
        files = [self.write("a/a.kicad_pro"), self.write("a/a.kicad_sch", schematic()),
                 self.write("b/b.kicad_pro"), self.write("b/b.kicad_pcb")]
        _, _, problems = board_check.discover(self.root, files)
        self.assertEqual([(v.rule, v.location) for v in problems["a/a.kicad_pro"]],
                         [("design_discovery", "a/a.kicad_pcb")])
        self.assertIn("no layout beside it", problems["a/a.kicad_pro"][0].message)
        self.assertEqual([(v.rule, v.location) for v in problems["b/b.kicad_pro"]],
                         [("design_discovery", "b/b.kicad_sch")])

    def test_a_board_file_without_its_project_fails_by_name(self):
        files = [self.write("loose/board.kicad_pcb"), self.write("loose/board.kicad_sch", schematic()),
                 self.write("a/a.kicad_pro"), self.write("a/a.kicad_pcb"), self.write("a/a.kicad_sch", schematic()),
                 self.write("a/other.kicad_pcb")]
        _, orphans, _ = board_check.discover(self.root, files)
        self.assertEqual([(v.design, v.rule) for v in orphans],
                         [("a/other.kicad_pcb", "design_discovery"),
                          ("loose/board.kicad_pcb", "design_discovery"),
                          ("loose/board.kicad_sch", "design_discovery")])

    def test_hierarchical_sheets_belong_to_their_design_and_no_others(self):
        files = [self.write("a/a.kicad_pro"), self.write("a/a.kicad_pcb"),
                 self.write("a/a.kicad_sch", schematic("power.kicad_sch", "sub/io.kicad_sch")),
                 self.write("a/power.kicad_sch", schematic()),
                 self.write("a/sub/io.kicad_sch", schematic("../power.kicad_sch")),
                 self.write("a/unused.kicad_sch", schematic())]
        _, orphans, problems = board_check.discover(self.root, files)
        self.assertEqual([v.design for v in orphans], ["a/unused.kicad_sch"])
        self.assertEqual(problems["a/a.kicad_pro"], [])

    def test_a_schematic_that_cannot_be_read_fails_its_design(self):
        files = [self.write("a/a.kicad_pro"), self.write("a/a.kicad_pcb"), self.write("a/a.kicad_sch", "(kicad_sch (sheet")]
        _, _, problems = board_check.discover(self.root, files)
        self.assertEqual([v.rule for v in problems["a/a.kicad_pro"]], ["design_unreadable"])

    def test_untracked_files_are_not_designs(self):
        subprocess.run(["git", "init", "-q", self.root], check=True)
        self.write("a/a.kicad_pro"), self.write("a/a.kicad_pcb"), self.write("a/a.kicad_sch", schematic())
        self.assertEqual(board_check.tracked_files("git", self.root), [])


# --- The separation basis record ---------------------------------------------


class TheRecordMustBeSigned(Tree):
    """SOL-HW-BOARD-RULE-CHECK-GATE.C3: The separation basis is a written rule the layout check enforces at no less than the signed figure, and a mains-carrying design without it fails.

    These are the record's own failure conditions: missing, unparseable,
    lacking or misstating a figure, unsigned, or synthetic on an orderable board.
    """

    design = board_check.Design("hardware/m/board/board.kicad_pro")

    def record(self, text: str, not_for_manufacture: bool = False):
        self.write("hardware/m/separation-basis.yaml", text)
        found = board_check.find_record(self.root, self.design.directory)
        return board_check.read_record(board_check.require_yaml(), self.root, self.design, found,
                                       not_for_manufacture, TODAY)

    def assertFails(self, text: str, location_end: str, words: str, not_for_manufacture: bool = False):
        figures, problems = self.record(text, not_for_manufacture)
        self.assertIsNone(figures)
        self.assertTrue(any(v.rule == "separation_basis" and v.location.endswith(location_end) and words in v.message
                            for v in problems), problems)

    def test_a_signed_record_gives_its_figures(self):
        self.assertEqual(self.record(SIGNED_RECORD), ((3.0, 4.0), []))

    def test_the_nearest_record_at_or_above_the_design_is_the_one_used(self):
        self.write("separation-basis.yaml", SIGNED_RECORD.replace("3.0", "9.0"))
        self.write("hardware/m/board/separation-basis.yaml", SIGNED_RECORD.replace("3.0", "5.0"))
        self.assertEqual(board_check.find_record(self.root, self.design.directory), "hardware/m/board/separation-basis.yaml")
        self.assertEqual(board_check.find_record(self.root, "hardware/other"), "separation-basis.yaml")

    def test_a_missing_record_fails(self):
        figures, problems = board_check.read_record(board_check.require_yaml(), self.root, self.design, None, False, TODAY)
        self.assertIsNone(figures)
        self.assertEqual([v.rule for v in problems], ["separation_basis"])
        self.assertIn("no separation-basis.yaml", problems[0].message)

    def test_a_record_that_cannot_be_parsed_fails(self):
        self.assertFails("mains_to_low_voltage: [unclosed\n", "separation-basis.yaml", "cannot be parsed")
        self.assertFails("- a list\n- not a mapping\n", "separation-basis.yaml", "not a mapping")
        self.assertFails("", "separation-basis.yaml", "not a mapping")

    def test_a_record_lacking_or_misstating_a_figure_fails(self):
        self.assertFails(SIGNED_RECORD.replace("  creepage_mm: 4.0\n", ""), "creepage_mm", "lacks")
        self.assertFails(SIGNED_RECORD.replace("  clearance_mm: 3.0\n", ""), "clearance_mm", "lacks")
        self.assertFails(SIGNED_RECORD.replace("mains_to_low_voltage:", "other_pair:"), "mains_to_low_voltage", "lacks")
        for bad in ("0", "-3", "abc", "true", ".nan", ".inf", "'3'", "null"):
            with self.subTest(figure=bad):
                self.assertFails(SIGNED_RECORD.replace("clearance_mm: 3.0", f"clearance_mm: {bad}"), "clearance_mm",
                                 "not a positive number")

    def test_an_unsigned_record_fails(self):
        self.assertFails(SIGNED_RECORD.replace("accepted_by: maintainer\n", ""), "accepted_by", "missing")
        for placeholder in ("TBD", "unsigned", "Todo", "NONE", "placeholder", "<your name>", "'<name>'", "''", "42"):
            with self.subTest(accepted_by=placeholder):
                figures, problems = self.record(SIGNED_RECORD.replace("accepted_by: maintainer", f"accepted_by: {placeholder}"))
                self.assertIsNone(figures)
                self.assertEqual([v.location for v in problems], ["hardware/m/separation-basis.yaml accepted_by"])

    def test_an_acceptance_date_missing_invalid_or_in_the_future_fails(self):
        self.assertFails(SIGNED_RECORD.replace("accepted_on: 2026-10-01\n", ""), "accepted_on", "missing")
        for bad in ("'12/10/2026'", "'2026-02-30'", "2026-10-01T09:00:00", "yesterday", "20261001"):
            with self.subTest(accepted_on=bad):
                self.assertFails(SIGNED_RECORD.replace("accepted_on: 2026-10-01", f"accepted_on: {bad}"),
                                 "accepted_on", "not a valid calendar date")
        self.assertFails(SIGNED_RECORD.replace("2026-10-01", "2026-10-13"), "accepted_on", "later than today")

    def test_the_acceptance_date_may_be_today_and_may_be_quoted(self):
        self.assertEqual(self.record(SIGNED_RECORD.replace("2026-10-01", "2026-10-12"))[0], (3.0, 4.0))
        self.assertEqual(self.record(SIGNED_RECORD.replace("2026-10-01", "'2026-10-12'"))[0], (3.0, 4.0))

    def test_a_synthetic_record_passes_only_a_design_not_for_manufacture(self):
        for marking in ("synthetic: true", "synthetic: yes", "synthetic: 'true'", "synthetic: 1"):
            with self.subTest(marking=marking):
                self.assertFails(SIGNED_RECORD + marking + "\n", "synthetic", "marked synthetic")
                self.assertEqual(self.record(SIGNED_RECORD + marking + "\n", not_for_manufacture=True)[0], (3.0, 4.0))
        self.assertEqual(self.record(SIGNED_RECORD + "synthetic: false\n")[0], (3.0, 4.0))


# --- The design's own rules --------------------------------------------------


class TheMainsRuleHasOneForm(Tree):
    """SOL-HW-BOARD-RULE-CHECK-GATE.C3: The separation basis is a written rule the layout check enforces at no less than the signed figure, and a mains-carrying design without it fails."""

    design = board_check.Design("b/b.kicad_pro")

    def rules(self, text):
        if text is not None:
            self.write("b/b.kicad_dru", text)
        rules, hidden = board_check.read_rules(self.root, self.design)
        return rules, hidden

    def verdict(self, text, signed=(3.0, 4.0)):
        rules, _ = self.rules(text)
        return board_check.mains_rule(self.design, rules, signed)

    def assertOnly(self, found, words):
        self.assertEqual(len(found), 1, found)
        self.assertEqual(found[0].rule, "separation_rule")
        self.assertIn(words, found[0].message)

    def test_the_rule_in_its_form_at_or_above_the_record_passes(self):
        self.assertEqual(self.verdict(MAINS_RULE), [])
        self.assertEqual(self.verdict(MAINS_RULE.replace("3mm", "5mm").replace("4mm", "0.25in")), [])
        self.assertEqual(self.verdict(MAINS_RULE.replace("A.hasNetclass('Mains') && !B", "A.hasNetclass('Mains')&&!B")), [])

    def test_no_rules_file_or_no_rule_in_the_form_fails(self):
        self.assertOnly(self.verdict(None), "no custom rules file")
        self.assertOnly(self.verdict("(version 1)\n"), "no custom rule has the condition")
        self.assertOnly(self.verdict(MAINS_RULE.replace("!B.hasNetclass", "B.hasNetclass")), "narrowed by its condition")

    def test_a_rule_narrowed_by_layer_or_area_fails(self):
        self.assertOnly(self.verdict(MAINS_RULE.replace("(condition", "(layer outer)\n\t(condition")), "narrowed by layer")
        self.assertOnly(self.verdict(MAINS_RULE.replace("Mains')\"", "Mains') && A.intersectsArea('m')\"")),
                        "narrowed by its condition")

    def test_a_rule_holding_one_distance_or_split_in_two_fails(self):
        self.assertOnly(self.verdict(MAINS_RULE.replace("\t(constraint creepage (min 4mm))", "")), "no creepage")
        self.assertOnly(self.verdict(MAINS_RULE.replace("\t(constraint clearance (min 3mm))\n", "")), "no clearance")
        self.assertOnly(self.verdict(MAINS_RULE.replace("(min 3mm)", "(max 9mm)")), "cannot be read as a distance")
        split = MAINS_RULE.replace("\t(constraint creepage (min 4mm)))", ")") + MAINS_RULE.split("\n", 1)[1].replace(
            "\t(constraint clearance (min 3mm))\n", "")
        self.assertOnly(self.verdict(split), "more than one rule")

    def test_a_declared_figure_below_the_record_fails_in_any_unit(self):
        self.assertOnly(self.verdict(MAINS_RULE.replace("3mm", "2.9mm")), "clearance of 2.9 mm, below the signed 3 mm")
        self.assertOnly(self.verdict(MAINS_RULE.replace("4mm", "150mil")), "creepage of 3.81 mm, below the signed 4 mm")
        self.assertOnly(self.verdict(MAINS_RULE.replace("3mm", "2")), "clearance of 2 mm")

    def test_figures_are_not_compared_when_there_is_no_signed_basis(self):
        self.assertEqual(self.verdict(MAINS_RULE.replace("3mm", "0.1mm"), signed=None), [])


class RulesThatHideWhatTheyFind(Tree):
    """SOL-HW-BOARD-RULE-CHECK-GATE.C2: A design passes only if KiCad's own electrical and layout rule checks find no violation, including no layout-schematic disagreement."""

    design = board_check.Design("b/b.kicad_pro")

    def test_a_custom_rule_set_to_ignore_or_exclusion_fails(self):
        for level in ("ignore", "exclusion"):
            with self.subTest(severity=level):
                write(self.root, "b/b.kicad_dru", MAINS_RULE + f'(rule "quiet"\n\t(condition "A.Type == \'Via\'")\n\t(severity {level}))\n')
                _, hidden = board_check.read_rules(self.root, self.design)
                self.assertEqual([(v.rule, v.location) for v in hidden], [("ignored_check", "b/b.kicad_dru rule 'quiet'")])

    def test_a_rule_at_error_or_warning_is_not_flagged(self):
        write(self.root, "b/b.kicad_dru", MAINS_RULE + '(rule "w" (condition "A.Type == \'Via\'") (severity warning))\n')
        self.assertEqual(board_check.read_rules(self.root, self.design)[1], [])

    def test_a_rules_file_that_cannot_be_read_fails(self):
        write(self.root, "b/b.kicad_dru", MAINS_RULE + "(rule \"broken\"")
        rules, hidden = board_check.read_rules(self.root, self.design)
        self.assertEqual(rules, [])
        self.assertEqual([v.rule for v in hidden], ["custom_rules"])

    def test_exclusions_in_the_project_file_each_fail(self):
        project = {"board": {"design_settings": {"drc_exclusions": [
            "clearance|56185000|9000000|a|b", ["silk_overlap|1000000|2000000|c|d", "fine"]]}},
                   "erc": {"erc_exclusions": ["pin_not_connected|635000|812800|e|f|||"]}}
        found = board_check.exclusions(self.design, project)
        self.assertEqual([(v.rule, v.location) for v in found], [
            ("clearance", "b/b.kicad_pcb @ (56.185, 9) mm"),
            ("silk_overlap", "b/b.kicad_pcb @ (1, 2) mm"),
            ("pin_not_connected", "b/b.kicad_sch @ (63.5, 81.28) mm")])
        self.assertTrue(all("excluded" in v.message for v in found))
        self.assertEqual(board_check.exclusions(self.design, {}), [])

    def test_ignored_checks_kicad_reports_each_fail(self):
        report = {"ignored_checks": [{"key": "missing_courtyard", "description": "Footprint has no courtyard defined"}]}
        found = board_check.ignored(self.design, report, "board.design_settings.rule_severities")
        self.assertEqual([(v.rule, v.location) for v in found],
                         [("ignored_check", "b/b.kicad_pro board.design_settings.rule_severities.missing_courtyard")])
        self.assertEqual(board_check.ignored(self.design, {"ignored_checks": []}, "x"), [])

    def test_a_violation_kicad_reports_as_excluded_says_so(self):
        entry = {"type": "clearance", "severity": "exclusion", "description": "Clearance violation",
                 "items": [{"description": "Pad 1 of R1", "pos": {"x": 1.5, "y": 2.0}}]}
        found = board_check.kicad_violation(self.design, entry, "b/b.kicad_pcb")
        self.assertEqual(found.location, "Pad 1 of R1 @ (1.5, 2) mm")
        self.assertIn("excluded", found.message)


# --- Local overrides ---------------------------------------------------------


LAYOUT = """\
(kicad_pcb
	(footprint "proof:R"
		(at 15 10)
		(property "Reference" "R1")
		{fp}
		(pad "1" thru_hole circle (at 0 0) (net "/MAINS_L") {pad1})
		(pad "2" smd custom (at 10 0) (net "/LV_A") (options (clearance outline) (anchor rect)) {pad2})
	)
	(zone (net "{zone_net}") (layer "F.Cu") (connect_pads (clearance {zone}))
		(polygon (pts (xy 2 15) (xy 20 15))))
)
"""


class NoOverrideOutranksTheSignedFigure(unittest.TestCase):
    """SOL-HW-BOARD-RULE-CHECK-GATE.C3: The separation basis is a written rule the layout check enforces at no less than the signed figure, and a mains-carrying design without it fails.

    KiCad 10 ranks a pad's or footprint's local clearance override above every
    custom rule, taking the larger of the pair's two overrides, so one below the
    signed figure on either item of a mains/low-voltage pair wins over the
    appended signed rule. A zone's clearance does not outrank custom rules.
    """

    design = board_check.Design("b/b.kicad_pro")

    def found(self, fp="", pad1="", pad2="", zone="0.5", zone_net="/LV_B"):
        tree = sexpr.parse_one(LAYOUT.format(fp=fp, pad1=pad1, pad2=pad2, zone=zone, zone_net=zone_net))
        return [(v.rule, v.location) for v in board_check.overrides(self.design, tree, 3.0, {"/MAINS_L"})]

    def test_no_overrides_and_overrides_at_or_above_the_figure_pass(self):
        self.assertEqual(self.found(), [])
        self.assertEqual(self.found(fp="(clearance 3)", pad1="(clearance 5)", pad2="(clearance 3.0)", zone="3"), [])

    def test_a_pad_override_below_the_figure_fails_on_either_side_of_the_pair(self):
        self.assertEqual(self.found(pad1="(clearance 0.1)"),
                         [("local_clearance_override", "pad 1 [/MAINS_L] of R1 (footprint at (15, 10) mm)")])
        self.assertEqual(self.found(pad2="(clearance 0)"),
                         [("local_clearance_override", "pad 2 [/LV_A] of R1 (footprint at (15, 10) mm)")])

    def test_a_footprint_override_below_the_figure_fails(self):
        self.assertEqual(self.found(fp="(clearance 2.99)"),
                         [("local_clearance_override", "footprint R1 at (15, 10) mm")])

    def test_a_mains_zone_below_the_figure_fails_and_a_low_voltage_zone_does_not(self):
        self.assertEqual(self.found(zone="0.2", zone_net="/MAINS_L"),
                         [("local_clearance_override", "zone [/MAINS_L] with a corner at (2, 15) mm")])
        self.assertEqual(self.found(zone="0.2", zone_net="/LV_B"), [])

    def test_the_custom_pad_shape_option_is_not_read_as_an_override(self):
        self.assertEqual(self.found(), [])


# --- The tools ---------------------------------------------------------------


class AMissingToolStopsTheCheck(Tree):
    """SOL-HW-BOARD-RULE-CHECK-GATE.C4: One task-runner command runs the whole check with tools any reader can obtain."""

    def test_python_older_than_the_minimum_stops_naming_it(self):
        with self.assertRaises(board_check.CannotRun) as stop:
            board_check.require_python((3, 8, 18))
        self.assertIn("Python 3.9 or newer", str(stop.exception))
        self.assertIn("3.8.18", str(stop.exception))
        board_check.require_python((3, 9, 0))

    def test_missing_or_old_pyyaml_stops_naming_it(self):
        with mock.patch.dict(sys.modules, {"yaml": None}), self.assertRaises(board_check.CannotRun) as stop:
            board_check.require_yaml()
        self.assertIn("PyYAML 5.1 or newer", str(stop.exception))
        self.assertIn("pip install pyyaml", str(stop.exception))
        old = types.ModuleType("yaml")
        old.__version__ = "5.0.9"
        with mock.patch.dict(sys.modules, {"yaml": old}), self.assertRaises(board_check.CannotRun) as stop:
            board_check.require_yaml()
        self.assertIn("5.0.9", str(stop.exception))

    def test_a_missing_kicad_cli_stops_saying_how_to_point_at_it(self):
        with self.assertRaises(board_check.CannotRun) as stop:
            board_check.require_kicad(os.path.join(self.root, "no-such-kicad-cli"))
        message = str(stop.exception)
        for words in ("kicad-cli", "KiCad 10.0 or newer", "KICAD_CLI=", "hardware/README.md"):
            self.assertIn(words, message)

    def test_an_old_or_unrecognisable_kicad_stops_naming_it(self):
        old = fake_tool(os.path.join(self.root, "kicad9"), "echo 9.0.4")
        with self.assertRaises(board_check.CannotRun) as stop:
            board_check.require_kicad(old)
        self.assertIn("KiCad 9.0.4, older than the 10.0", str(stop.exception))
        broken = fake_tool(os.path.join(self.root, "broken"), "echo nonsense; exit 3")
        with self.assertRaises(board_check.CannotRun):
            board_check.require_kicad(broken)
        self.assertEqual(board_check.require_kicad(fake_tool(os.path.join(self.root, "k"), "echo 10.0.0")), "10.0.0")
        self.assertEqual(board_check.require_kicad(fake_tool(os.path.join(self.root, "k11"), "echo 11.1.2")), "11.1.2")

    def test_missing_git_or_no_work_tree_stops(self):
        with self.assertRaises(board_check.CannotRun) as stop:
            board_check.require_git(os.path.join(self.root, "no-git"), self.root)
        self.assertIn("git is needed", str(stop.exception))
        with self.assertRaises(board_check.CannotRun) as stop:
            board_check.require_git("git", self.root)
        self.assertIn("not inside a git work tree", str(stop.exception))

    def test_the_command_stops_with_status_2_and_reports_no_verdict(self):
        stderr = io.StringIO()
        with mock.patch("sys.stderr", stderr), mock.patch("sys.stdout", io.StringIO()) as stdout:
            status = board_check.main(["--root", REPO, "--kicad-cli", os.path.join(self.root, "absent")])
        self.assertEqual(status, 2)
        self.assertTrue(stderr.getvalue().startswith("CANNOT RUN | kicad-cli"))
        self.assertNotIn("PASS", stdout.getvalue())

    def test_the_tools_and_their_minimums_are_named_where_the_check_is_documented(self):
        with open(os.path.join(REPO, "hardware", "README.md"), encoding="utf-8") as handle:
            readme = handle.read()
        with open(os.path.join(REPO, "Taskfile.yml"), encoding="utf-8") as handle:
            taskfile = handle.read()
        verify = taskfile[taskfile.index("  hw:verify:"):]
        verify = verify[: verify.index("\n\n")]
        for text in (readme, verify):
            for words in ("KiCad 10.0", "Python 3.9", "PyYAML 5.1", "git", "KICAD_CLI"):
                self.assertIn(words, text)
        for location in ("/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli",
                         r"C:\Program Files\KiCad\10.0\bin\kicad-cli.exe", "/usr/bin/kicad-cli"):
            self.assertIn(location, readme)


# --- The report ------------------------------------------------------------------


class EachViolationIsOneLine(unittest.TestCase):
    """SOL-HW-BOARD-RULE-CHECK-GATE.C6: The check's report names each design, its verdict and every violation in terms a builder can act on."""

    def test_a_violation_is_one_line_of_five_fields_whatever_its_text(self):
        line = board_check.Violation("a/a.kicad_pro", "clearance", "pad 1 | of R1\n@ (1, 2)",
                                     "Clearance violation\n(rule 'x|y')").line()
        self.assertNotIn("\n", line)
        self.assertEqual(line.split(" | "),
                         ["VIOLATION", "a/a.kicad_pro", "clearance", "pad 1 / of R1 @ (1, 2)", "Clearance violation (rule 'x/y')"])


if __name__ == "__main__":
    unittest.main()
