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

import contextlib
import datetime
import inspect
import io
import json
import math
import os
import re
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
import board_geometry  # noqa: E402
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

#: The figure of every measured workmanship rule, as a design sets them in its project text variables.
FIGURES = {"WORK_DETOUR_RATIO": "1.5", "WORK_NECK_MM": "1", "WORK_ANGLE_TOLERANCE_DEG": "0.1",
           "WORK_PAD_ENTRY_RATIO": "2", "WORK_PAD_ANGLE_DEG": "90", "BARRIER_COPPER_MM2": "0", "PASTE_OVER_VIA_MM2": "0"}

#: Those figures as the check reads them.
FIGURES_READ = {name: float(value) for name, value in FIGURES.items()}

#: The workmanship custom rules every design's rules file holds.
WORKMANSHIP = """\
(rule "Corners"
	(constraint track_angle (min 135)))
(rule "Jogs"
	(constraint track_segment_length (min 0.5mm)))
"""


def none_project(**more) -> str:
    """A project file declaring no mains, carrying every workmanship figure."""
    return json.dumps({"text_variables": {"MAINS": "none", **FIGURES, **more}})


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


def fake_tool(path: str, script: str, interpreter: str = "/bin/sh") -> str:
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(f"#!{interpreter}\n" + script + "\n")
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

    def everything(self) -> board_check.Repository:
        """The tree as a repository tracking every file in it."""
        files = [os.path.relpath(os.path.join(d, n), self.root).replace(os.sep, "/")
                 for d, _, names in os.walk(self.root) for n in names]
        return board_check.Repository(self.root, files)

    def git(self, *args: str) -> None:
        subprocess.run(["git", "-C", self.root, "-c", "user.name=t", "-c", "user.email=t@invalid", *args],
                       check=True, capture_output=True)


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

    def test_each_top_level_form_is_located_as_written(self):
        text = '(version 1)\n# note\n(rule "a"\n\t(condition "x"))\n  bare (rule "b (c")\n'
        spans = []
        forms = sexpr.parse(text, comments=True, spans=spans)
        self.assertEqual(len(spans), len(forms))
        self.assertEqual([text[start:end] for start, end, _ in spans],
                         ["(version 1)", '(rule "a"\n\t(condition "x"))', "bare", '(rule "b (c")'])
        self.assertEqual([line for _, _, line in spans], [1, 3, 5, 5])
        with self.assertRaisesRegex(sexpr.SexprError, "starting at line 2"):
            sexpr.parse('(a)\n(b "open\n\n')

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

    def test_a_sheet_the_schematic_names_but_git_does_not_track_fails_by_name(self):
        self.write("a/power.kicad_sch", schematic())
        files = [self.write("a/a.kicad_pro"), self.write("a/a.kicad_pcb"),
                 self.write("a/a.kicad_sch", schematic("power.kicad_sch", "gone.kicad_sch"))]
        _, orphans, problems = board_check.discover(self.root, files)
        self.assertEqual(orphans, [])
        self.assertEqual([(v.rule, v.location) for v in problems["a/a.kicad_pro"]],
                         [("design_discovery", "a/power.kicad_sch"), ("design_discovery", "a/gone.kicad_sch")])
        self.assertIn("a/a.kicad_sch names the sheet a/power.kicad_sch, which is not tracked",
                      problems["a/a.kicad_pro"][0].message)

    def test_a_sheet_not_naming_exactly_one_file_fails_by_name(self):
        cases = {
            '(sheet (property "Sheetname" "s"))': "has no Sheetfile property",
            '(sheet (property "Sheetname" "s") (property "Sheet file" "a.kicad_sch"))': "has no Sheetfile property",
            '(sheet (property "Sheetname" "s") (property "Sheetfile"))': "has a Sheetfile property naming no file",
            '(sheet (property "Sheetname" "s") (property "Sheetfile" "a.kicad_sch") (property "Sheetfile" "b.kicad_sch"))':
                "has 2 Sheetfile properties",
        }
        for sheet, words in cases.items():
            with self.subTest(sheet=sheet):
                self.write("d/d.kicad_pro", "{}")
                self.write("d/d.kicad_pcb", "(kicad_pcb)")
                self.write("d/a.kicad_sch", schematic())
                self.write("d/b.kicad_sch", schematic())
                self.write("d/d.kicad_sch", f"(kicad_sch (version 20250114) {sheet})")
                _, _, problems = board_check.discover(self.root, sorted(self.everything().tracked))
                self.assertEqual([(v.rule, v.location) for v in problems["d/d.kicad_pro"]],
                                 [("design_discovery", "d/d.kicad_sch sheet 's'")])
                self.assertIn(words, problems["d/d.kicad_pro"][0].message)

    def test_a_schematic_that_cannot_be_read_fails_its_design(self):
        files = [self.write("a/a.kicad_pro"), self.write("a/a.kicad_pcb"), self.write("a/a.kicad_sch", "(kicad_sch (sheet")]
        _, _, problems = board_check.discover(self.root, files)
        self.assertEqual([v.rule for v in problems["a/a.kicad_pro"]], ["design_unreadable"])

    def test_untracked_files_are_not_designs(self):
        subprocess.run(["git", "init", "-q", self.root], check=True)
        self.write("a/a.kicad_pro"), self.write("a/a.kicad_pcb"), self.write("a/a.kicad_sch", schematic())
        self.assertEqual(board_check.tracked_files("git", self.root), [])


def library_table(kind: str, *entries) -> str:
    rows = "".join(f'\t(lib (name "{name}")(type "KiCad")(uri "{uri}")(options "")(descr ""))\n' for name, uri in entries)
    return f"({kind}\n\t(version 7)\n{rows})\n"


class WhatADesignReachesIsCheckedWithIt(Tree):
    """SOL-HW-BOARD-RULE-CHECK-GATE.C1: Every board design in the repository is checked because it exists, not because it is listed.

    KiCad is given a copy of the design holding every tracked file it reads,
    each in its place in the repository, so a sheet or a library above the
    design's own folder is checked rather than missing; and a library the
    repository does not hold fails by name rather than being loaded from
    wherever one machine keeps it.
    """

    design = board_check.Design("hw/m/board/board.kicad_pro")

    def setUp(self):
        super().setUp()
        for path in ("hw/m/board/board.kicad_pro", "hw/m/board/board.kicad_pcb", "hw/m/board/notes.txt",
                     "hw/m/shared.pretty/R.kicad_mod", "hw/m/shared.kicad_sym", "hw/m/power.kicad_sch", "elsewhere/x.txt"):
            self.write(path, schematic() if path.endswith(".kicad_sch") else "")
        self.write("hw/m/board/board.kicad_sch", schematic("../power.kicad_sch"))

    def reach(self, *tables):
        for kind, entries in tables:
            self.write(f"hw/m/board/{'sym' if kind == 'sym_lib_table' else 'fp'}-lib-table", library_table(kind, *entries))
        return board_check.design_files(self.design, self.everything())

    def test_the_design_folder_its_sheets_and_its_libraries_above_it_are_all_copied(self):
        files, found = self.reach(("fp_lib_table", [("shared", "${KIPRJMOD}/../shared.pretty")]),
                                  ("sym_lib_table", [("syms", "${KIPRJMOD}/../shared.kicad_sym"),
                                                     ("kicad", "${KICAD10_SYMBOL_DIR}/Device.kicad_sym")]))
        self.assertEqual(found, [])
        self.assertEqual(files, ["hw/m/board/board.kicad_pcb", "hw/m/board/board.kicad_pro", "hw/m/board/board.kicad_sch",
                                 "hw/m/board/fp-lib-table", "hw/m/board/notes.txt", "hw/m/board/sym-lib-table",
                                 "hw/m/power.kicad_sch", "hw/m/shared.kicad_sym", "hw/m/shared.pretty/R.kicad_mod"])

    def test_a_library_the_repository_does_not_hold_fails_by_name(self):
        cases = {
            "${KIPRJMOD}/../missing.pretty": "git tracks nothing there",
            "${KIPRJMOD}/../../../../outside.pretty": "it lies outside the repository",
            "/opt/kicad-libs/R.pretty": "absolute path",
            "C:/libs/R.pretty": "absolute path",
            "${MY_LIBS}/R.pretty": "reached through ${MY_LIBS}",
            "${KICAD10_3RD_PARTY}/R.pretty": "reached through ${KICAD10_3RD_PARTY}",
        }
        for uri, why in cases.items():
            with self.subTest(uri=uri):
                files, found = self.reach(("fp_lib_table", [("lib", uri)]))
                self.assertEqual([(v.rule, v.location) for v in found],
                                 [("design_library", "hw/m/board/fp-lib-table library 'lib'")])
                self.assertIn(why, found[0].message)
                self.assertIn(uri, found[0].message)

    def test_a_library_table_git_does_not_track_fails_by_name(self):
        self.git("init", "-q")
        self.write("hw/m/board/fp-lib-table", library_table("fp_lib_table", ("shared", "${KIPRJMOD}/../shared.pretty")))
        repository = board_check.Repository(self.root, [p for p in self.everything().tracked if not p.endswith("fp-lib-table")])
        files, found = board_check.design_files(self.design, repository)
        self.assertEqual([(v.rule, v.location) for v in found], [("design_library", "hw/m/board/fp-lib-table")])
        self.assertIn("library table is not tracked in the repository", found[0].message)
        self.assertNotIn("hw/m/shared.pretty/R.kicad_mod", files)

    def test_a_library_table_is_read_only_in_the_form_kicad_writes(self):
        good = '(lib (name "a")(type "KiCad")(uri "${KIPRJMOD}/../shared.pretty")(options "")(descr ""))'
        cases = {
            "(sym_lib_table\n" + good + ")": ("hw/m/board/fp-lib-table", "headed (sym_lib_table ...), not (fp_lib_table ...)"),
            "(fp_lib_table (version 7) (version 7)\n" + good + ")": ("hw/m/board/fp-lib-table", "(version ...) more than once"),
            "(fp_lib_table\n" + good + " (nickname \"x\"))": ("hw/m/board/fp-lib-table", "a (nickname ...) form, which is not a library entry"),
            "(fp_lib_table\n" + good.replace('(descr "")', '(descr "")(priority 1)') + ")": ("hw/m/board/fp-lib-table library 'a'", "a (priority ...) clause"),
            "(fp_lib_table\n" + good.replace('(type "KiCad")', '(type "Legacy")') + ")": ("hw/m/board/fp-lib-table library 'a'", "the type 'Legacy'"),
            "(fp_lib_table\n" + good.replace('(type "KiCad")', '') + ")": ("hw/m/board/fp-lib-table library 'a'", "no (type ...) clause"),
            "(fp_lib_table\n" + good.replace('(uri', '(uri "/elsewhere")(uri') + ")": ("hw/m/board/fp-lib-table library 'a'", "2 (uri ...) clauses"),
            "(fp_lib_table\n" + good.replace('(name "a")', '(name "a" "b")') + ")": ("hw/m/board/fp-lib-table library 'a'", "a (name ...) clause holding something other than one value"),
            "(fp_lib_table\n" + good + "\n" + good.replace("shared.pretty", "other.pretty") + ")": ("hw/m/board/fp-lib-table library 'a'", "the nickname 'a', which an earlier entry already takes"),
        }
        for text, (where, words) in cases.items():
            with self.subTest(table=text):
                self.write("hw/m/board/fp-lib-table", text)
                _, found = board_check.design_files(self.design, self.everything())
                self.assertIn(("design_library", where), [(v.rule, v.location) for v in found])
                self.assertTrue(any(words in v.message for v in found), found)

    def test_the_flags_kicad_writes_on_an_entry_are_read_without_complaint(self):
        self.write("hw/m/board/fp-lib-table", '(fp_lib_table (version 7)\n(lib (name "a")(type "KiCad")'
                   '(uri "${KIPRJMOD}/../shared.pretty")(options "")(descr "")(disabled)(hidden)))')
        files, found = board_check.design_files(self.design, self.everything())
        self.assertEqual(found, [])
        self.assertIn("hw/m/shared.pretty/R.kicad_mod", files)

    def test_a_library_table_that_cannot_be_read_fails(self):
        self.write("hw/m/board/sym-lib-table", "(sym_lib_table (lib")
        _, found = board_check.design_files(self.design, self.everything())
        self.assertEqual([(v.rule, v.location) for v in found], [("design_unreadable", "hw/m/board/sym-lib-table")])


# --- The separation basis record ---------------------------------------------


class RecordTree(Tree):
    """A record beside a design two folders down, read as the check reads it."""

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


class TheRecordMustBeSigned(RecordTree):
    """SOL-HW-BOARD-RULE-CHECK-GATE.C3: The separation basis is a written rule the layout check enforces at no less than the signed figure, and a mains-carrying design without it fails.

    These are the record's own failure conditions: missing, unparseable,
    lacking or misstating a figure, unsigned, or synthetic on an orderable board.
    """

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
        for marking in ("synthetic: true", "synthetic: yes", "synthetic: True"):
            with self.subTest(marking=marking):
                self.assertFails(SIGNED_RECORD + marking + "\n", "synthetic", "marked synthetic")
                self.assertEqual(self.record(SIGNED_RECORD + marking + "\n", not_for_manufacture=True)[0], (3.0, 4.0))
        self.assertEqual(self.record(SIGNED_RECORD + "synthetic: false\n")[0], (3.0, 4.0))


class TheRecordIsReadInItsOneForm(RecordTree):
    """SOL-HW-BOARD-RULE-CHECK-GATE.C3: The separation basis is a written rule the layout check enforces at no less than the signed figure, and a mains-carrying design without it fails.

    The record is read only in the form its decision fixes: its own keys, any
    further pair of distances for readers, each key once, no merge key, and a
    synthetic mark that is true or false. Anything else fails by name rather
    than being read past, so a record cannot say one thing to a reader and
    another to the check.
    """

    def test_a_further_pair_of_distances_for_readers_is_accepted(self):
        text = SIGNED_RECORD + "mains_to_earthed_metal:\n  clearance_mm: 2.0\n  creepage_mm: 2.5\n"
        self.assertEqual(self.record(text), ((3.0, 4.0), []))

    def test_every_key_the_decision_names_is_accepted(self):
        text = SIGNED_RECORD + ("supply: 230 V 50 Hz\nworking_voltage: 250 V\npollution_degree: 2\nmaterial_group: IIIb\n"
                                "environment: indoor\nbarriers: []\nsynthetic: false\n")
        self.assertEqual(self.record(text), ((3.0, 4.0), []))

    def test_a_key_the_record_does_not_have_fails_naming_it(self):
        for extra in ("acceptd_by: someone\n", "other_pair:\n  clearance_mm: 1.0\n", "notes:\n  creepage_mm: 1.0\n  clearance_mm: 1\n  extra: 2\n", "7: seven\n"):
            with self.subTest(extra=extra):
                key = extra.split(":")[0]
                self.assertFails(SIGNED_RECORD + extra, f"separation-basis.yaml {key}", f"holds the key '{key}'")

    def test_a_key_the_figure_pair_does_not_have_fails_naming_it(self):
        self.assertFails(SIGNED_RECORD.replace("  creepage_mm: 4.0\n", "  creepage_mm: 4.0\n  creepage_mm_rms: 1\n"),
                         "mains_to_low_voltage.creepage_mm_rms", "holds 'creepage_mm_rms'")

    def test_a_key_given_twice_fails_wherever_it_is(self):
        self.assertFails(SIGNED_RECORD + "accepted_by: TBD\n", "separation-basis.yaml", "gives the key 'accepted_by' more than once")
        self.assertFails(SIGNED_RECORD.replace("  clearance_mm: 3.0\n", "  clearance_mm: 1.0\n  clearance_mm: 3.0\n"),
                         "separation-basis.yaml", "gives the key 'clearance_mm' more than once (again at line 4)")

    def test_a_merge_key_fails(self):
        text = SIGNED_RECORD.replace("mains_to_low_voltage:\n", "base: &f\n  clearance_mm: 1.0\n  creepage_mm: 1.0\nmains_to_low_voltage:\n  <<: *f\n")
        self.assertFails(text, "separation-basis.yaml", "merge key (<<) at line 6")

    def test_a_synthetic_mark_that_is_not_true_or_false_fails_whatever_the_design(self):
        for marking in ("synthetic: 'true'", "synthetic: 1", "synthetic: maybe", "synthetic: null"):
            for not_for_manufacture in (False, True):
                with self.subTest(marking=marking, not_for_manufacture=not_for_manufacture):
                    self.assertFails(SIGNED_RECORD + marking + "\n", "synthetic", "write true or false", not_for_manufacture)


#: A separation basis record carrying every key the separation basis decision defines.
KEYED_RECORD = SIGNED_RECORD + """\
overvoltage_category: 2
altitude_m: 2000
barriers:
  - inlet
  - split
barrier_types:
  - barrier: inlet
    insulation: reinforced
    earth_bonded: false
    touchable:
      - connector J2
    formed_by: the slot under J1
  - barrier: split
    insulation: basic
    earth_bonded: true
    touchable: []
    formed_by: the spacing between two tracks
table_rows:
  - citation:
      document: synthetic table
      edition: none
      locator: row 1
    inputs:
      working_voltage_v: 250
      insulation: reinforced
      overvoltage_category: 2
      pollution_degree: 2
      material_group: IIIb
      altitude_m: 2000
    figure:
      clearance_mm: 3.0
      creepage_mm: 4.0
  - citation:
      document: synthetic table
      edition: none
      locator: row 2
    inputs:
      working_voltage_v: 250
    figure:
      creepage_mm: 4.0
"""


class TheInputsOfTheFiguresAreRead(RecordTree):
    """The keys the separation basis decision adds beside the existing ones: each optional on a record, each read
    in the form the decision fixes, and any other key inside them refused by name."""

    def changed(self, old: str, new: str) -> str:
        self.assertIn(old, KEYED_RECORD)
        return KEYED_RECORD.replace(old, new, 1)

    def test_a_record_carrying_every_key_is_accepted_and_gives_its_figures(self):
        # SOL-PRE-ORDER-CHECK-READS-RECORD-KEYS.C1: The check accepts and reads every key the record decisions define, fails one they do not, and is shown to on a seeded copy
        self.assertEqual(self.record(KEYED_RECORD), ((3.0, 4.0), []))

    def test_a_record_without_the_new_keys_is_accepted_as_before(self):
        # SOL-PRE-ORDER-CHECK-READS-RECORD-KEYS.C1: The check accepts and reads every key the record decisions define, fails one they do not, and is shown to on a seeded copy
        self.assertEqual(self.record(SIGNED_RECORD), ((3.0, 4.0), []))

    def test_each_new_key_is_optional_on_its_own(self):
        # SOL-PRE-ORDER-CHECK-READS-RECORD-KEYS.C1: The check accepts and reads every key the record decisions define, fails one they do not, and is shown to on a seeded copy
        for extra in ("overvoltage_category: 4\n", "altitude_m: 0.5\n", "barrier_types: []\n",
                      "table_rows: []\n", "barriers: [a]\nbarrier_types:\n  - {barrier: a, insulation: basic, "
                      "earth_bonded: false, touchable: [], formed_by: x}\n"):
            with self.subTest(extra=extra):
                self.assertEqual(self.record(SIGNED_RECORD + extra), ((3.0, 4.0), []))

    def test_an_overvoltage_category_outside_one_to_four_or_not_a_whole_number_fails(self):
        # SOL-PRE-ORDER-CHECK-READS-RECORD-KEYS.C1: The check accepts and reads every key the record decisions define, fails one they do not, and is shown to on a seeded copy
        for bad in ("0", "5", "2.5", "'2'", "true", "null", "[2]"):
            with self.subTest(overvoltage_category=bad):
                self.assertFails(self.changed("overvoltage_category: 2\n", f"overvoltage_category: {bad}\n"),
                                 "separation-basis.yaml overvoltage_category", "whole number from 1 to 4")
        for good in (1, 2, 3, 4):
            self.assertEqual(self.record(self.changed("overvoltage_category: 2\n", f"overvoltage_category: {good}\n"))[0], (3.0, 4.0))

    def test_an_altitude_that_is_not_a_positive_number_fails(self):
        # SOL-PRE-ORDER-CHECK-READS-RECORD-KEYS.C1: The check accepts and reads every key the record decisions define, fails one they do not, and is shown to on a seeded copy
        for bad in ("0", "-100", "'2000'", "true", ".nan", ".inf", "null"):
            with self.subTest(altitude_m=bad):
                self.assertFails(self.changed("altitude_m: 2000\n", f"altitude_m: {bad}\n"),
                                 "separation-basis.yaml altitude_m", "not a positive number")

    def test_a_barrier_entry_is_read_in_the_form_the_decision_fixes(self):
        # SOL-PRE-ORDER-CHECK-READS-RECORD-KEYS.C1: The check accepts and reads every key the record decisions define, fails one they do not, and is shown to on a seeded copy
        for bad in ("double", "Basic", "'true'", "null", "[basic]"):
            with self.subTest(insulation=bad):
                self.assertFails(self.changed("insulation: reinforced", f"insulation: {bad}"),
                                 "barrier_types[0].insulation", "basic or reinforced")
        for bad in ("'true'", "1", "null", "'no'"):
            with self.subTest(earth_bonded=bad):
                self.assertFails(self.changed("earth_bonded: false", f"earth_bonded: {bad}"),
                                 "barrier_types[0].earth_bonded", "true or false")
        for bad in ("connector J2", "{a: b}", "null"):
            with self.subTest(touchable=bad):
                self.assertFails(self.changed("touchable:\n      - connector J2", f"touchable: {bad}"),
                                 "barrier_types[0].touchable", "not a list of parts")
        self.assertFails(self.changed("      - connector J2", "      - ''"), "barrier_types[0].touchable[0]", "non-empty string")
        self.assertFails(self.changed("formed_by: the slot under J1", "formed_by: ''"), "barrier_types[0].formed_by", "non-empty string")
        self.assertFails(self.changed("    formed_by: the slot under J1\n", ""), "barrier_types[0].formed_by", "lacks formed_by")
        self.assertFails(self.changed("    insulation: reinforced\n", ""), "barrier_types[0].insulation", "lacks insulation")
        self.assertFails(self.changed("barrier_types:\n  - barrier", "barrier_types:\n  - nonsense\n  - barrier"),
                         "barrier_types[0]", "not a mapping")
        self.assertFails(self.changed("barrier_types:", "barrier_types: {}\nunused:"), "barrier_types", "not a list")

    def test_each_barrier_has_exactly_one_entry_naming_a_barrier_the_record_lists(self):
        # SOL-PRE-ORDER-CHECK-READS-RECORD-KEYS.C1: The check accepts and reads every key the record decisions define, fails one they do not, and is shown to on a seeded copy
        self.assertFails(self.changed("barrier: split", "barrier: elsewhere"), "barrier_types[1].barrier",
                         "'elsewhere', which barriers does not list")
        self.assertFails(self.changed("barrier: split", "barrier: elsewhere"), "barrier_types",
                         "lists 'split' and barrier_types holds no entry for it")
        self.assertFails(self.changed("barrier: split", "barrier: inlet"), "barrier_types[1].barrier",
                         "already describes")
        self.assertFails(self.changed("  - split\n", "  - split\n  - third\n"), "barrier_types",
                         "lists 'third' and barrier_types holds no entry for it")
        self.assertFails(self.changed("barriers:\n  - inlet\n  - split\n", "barriers: []\n"), "barrier_types[0].barrier",
                         "which barriers does not list")
        self.assertFails(self.changed("barriers:\n  - inlet\n  - split\n", "barriers: not-a-list\n"), "barriers",
                         "not a list of the barriers' names")
        self.assertFails(self.changed("barrier: inlet", "barrier: ''"), "barrier_types[0].barrier", "non-empty string")

    def test_a_table_row_is_read_in_the_form_the_decision_fixes(self):
        # SOL-PRE-ORDER-CHECK-READS-RECORD-KEYS.C1: The check accepts and reads every key the record decisions define, fails one they do not, and is shown to on a seeded copy
        for bad in ("0", "-250", "'250'", "true"):
            with self.subTest(working_voltage_v=bad):
                self.assertFails(self.changed("working_voltage_v: 250\n      insulation", f"working_voltage_v: {bad}\n      insulation"),
                                 "table_rows[0].inputs.working_voltage_v", "not a positive number")
        self.assertFails(self.changed("      insulation: reinforced\n      overvoltage", "      insulation: triple\n      overvoltage"),
                         "table_rows[0].inputs.insulation", "basic or reinforced")
        self.assertFails(self.changed("      overvoltage_category: 2\n      pollution", "      overvoltage_category: 7\n      pollution"),
                         "table_rows[0].inputs.overvoltage_category", "whole number from 1 to 4")
        self.assertFails(self.changed("      pollution_degree: 2\n      material", "      pollution_degree: 0\n      material"),
                         "table_rows[0].inputs.pollution_degree", "whole number from 1 to 4")
        self.assertFails(self.changed("material_group: IIIb", "material_group: ''"), "table_rows[0].inputs.material_group", "non-empty string")
        self.assertFails(self.changed("altitude_m: 2000\n    figure", "altitude_m: -1\n    figure"),
                         "table_rows[0].inputs.altitude_m", "not a positive number")
        self.assertFails(self.changed("      clearance_mm: 3.0\n      creepage_mm: 4.0\n  - citation", "      clearance_mm: 0\n      creepage_mm: 4.0\n  - citation"),
                         "table_rows[0].figure.clearance_mm", "not a positive number")
        self.assertFails(self.changed("      creepage_mm: 4.0\n  - citation", "      creepage_mm: -4\n  - citation"),
                         "table_rows[0].figure.creepage_mm", "not a positive number")
        self.assertFails(self.changed("      locator: row 1\n", ""), "table_rows[0].citation.locator", "lacks locator")
        self.assertFails(self.changed("document: synthetic table\n      edition: none\n      locator: row 1",
                                      "document: ''\n      edition: none\n      locator: row 1"),
                         "table_rows[0].citation.document", "non-empty string")
        self.assertFails(self.changed("    figure:\n      creepage_mm: 4.0\n", ""), "table_rows[1].figure", "lacks figure")
        self.assertFails(self.changed("    inputs:\n      working_voltage_v: 250\n    figure:\n      creepage",
                                      "    figure:\n      creepage"), "table_rows[1].inputs", "lacks inputs")
        self.assertFails(self.changed("table_rows:", "table_rows: 3\nunused:"), "table_rows", "not a list")
        self.assertFails(self.changed("table_rows:\n  - citation", "table_rows:\n  - 7\n  - citation"), "table_rows[0]", "not a mapping")

    def test_an_empty_inputs_mapping_and_an_empty_figure_mapping_fail(self):
        # SOL-PRE-ORDER-CHECK-READS-RECORD-KEYS.C1: The check accepts and reads every key the record decisions define, fails one they do not, and is shown to on a seeded copy
        self.assertFails(self.changed("    inputs:\n      working_voltage_v: 250\n    figure:\n      creepage_mm: 4.0\n",
                                      "    inputs: {}\n    figure:\n      creepage_mm: 4.0\n"), "table_rows[1].inputs", "is empty")
        self.assertFails(self.changed("    figure:\n      creepage_mm: 4.0\n", "    figure: {}\n").replace(
            "    figure:\n      clearance_mm: 3.0\n      creepage_mm: 4.0\n  - citation", "    figure: {}\n  - citation"),
            "table_rows[0].figure", "is empty")
        self.assertFails(self.changed("    figure:\n      creepage_mm: 4.0\n", "    figure: {}\n"), "table_rows[1].figure", "is empty")

    def test_a_key_the_decision_does_not_name_is_refused_by_name_at_every_depth(self):
        # SOL-PRE-ORDER-CHECK-READS-RECORD-KEYS.C1: The check accepts and reads every key the record decisions define, fails one they do not, and is shown to on a seeded copy
        misspelt = [
            ("overvoltage_category:", "overvoltage_categry:", "separation-basis.yaml overvoltage_categry"),
            ("altitude_m:", "altitude:", "separation-basis.yaml altitude"),
            ("barrier_types:", "barrier_type:", "separation-basis.yaml barrier_type"),
            ("table_rows:", "table_row:", "separation-basis.yaml table_row"),
            ("    formed_by: the slot", "    formd_by: the slot", "barrier_types[0].formd_by"),
            ("    touchable:\n      - connector J2", "    touchables:\n      - connector J2", "barrier_types[0].touchables"),
            ("      document: synthetic table\n      edition: none\n      locator: row 1",
             "      document: synthetic table\n      edition: none\n      locater: row 1", "table_rows[0].citation.locater"),
            ("  - citation:\n      document: synthetic table\n      edition: none\n      locator: row 1",
             "  - citations:\n      document: synthetic table\n      edition: none\n      locator: row 1", "table_rows[0].citations"),
            ("      working_voltage_v: 250\n      insulation", "      working_volts: 250\n      insulation", "table_rows[0].inputs.working_volts"),
            ("      clearance_mm: 3.0\n      creepage_mm: 4.0\n  - citation", "      clearence_mm: 3.0\n      creepage_mm: 4.0\n  - citation",
             "table_rows[0].figure.clearence_mm"),
            ("    figure:\n      creepage_mm: 4.0\n", "    figure:\n      creepage_mm: 4.0\n      creepage_mm_rms: 1\n", "table_rows[1].figure.creepage_mm_rms"),
        ]
        for old, new, where in misspelt:
            with self.subTest(where=where):
                figures, problems = self.record(self.changed(old, new))
                self.assertIsNone(figures)
                key = where.rsplit(".", 1)[-1] if "." in where.split(" ")[-1] else where.split(" ")[-1]
                named = [v for v in problems if v.location == f"hardware/m/{where if ' ' in where else 'separation-basis.yaml ' + where}"
                         and f"holds the key '{key}'" in v.message]
                self.assertTrue(named, [(v.location, v.message) for v in problems])

    def test_an_unknown_key_is_reported_in_the_one_violation_line_form(self):
        # SOL-PRE-ORDER-CHECK-READS-RECORD-KEYS.C1: The check accepts and reads every key the record decisions define, fails one they do not, and is shown to on a seeded copy
        figures, problems = self.record(self.changed("    formed_by: the slot", "    formd_by: the slot"))
        self.assertIsNone(figures)
        lines = [v.line() for v in problems if "formd_by" in v.location]
        self.assertEqual(len(lines), 1)
        self.assertTrue(lines[0].startswith("VIOLATION | hardware/m/board/board.kicad_pro | separation_basis | "
                                            "hardware/m/separation-basis.yaml barrier_types[0].formd_by | "
                                            "barrier_types[0] holds the key 'formd_by', which is not one a barrier entry has"), lines[0])
        self.assertIn("its keys are barrier, earth_bonded, formed_by, insulation, touchable", lines[0])

    def test_the_top_level_refusal_lists_the_new_keys_among_those_a_record_has(self):
        # SOL-PRE-ORDER-CHECK-READS-RECORD-KEYS.C1: The check accepts and reads every key the record decisions define, fails one they do not, and is shown to on a seeded copy
        figures, problems = self.record(SIGNED_RECORD + "overvoltage_categry: 2\n")
        self.assertIsNone(figures)
        self.assertIn("altitude_m, barrier_types, barriers", problems[0].message.replace("accepted_by, ", "").replace("accepted_on, ", ""))
        self.assertIn("overvoltage_category", problems[0].message)
        self.assertIn("table_rows", problems[0].message)

    def test_a_synthetic_record_with_the_new_keys_still_passes_only_a_design_not_for_manufacture(self):
        # SOL-PRE-ORDER-CHECK-READS-RECORD-KEYS.C1: The check accepts and reads every key the record decisions define, fails one they do not, and is shown to on a seeded copy
        self.assertFails(KEYED_RECORD + "synthetic: true\n", "synthetic", "marked synthetic")
        self.assertEqual(self.record(KEYED_RECORD + "synthetic: true\n", not_for_manufacture=True)[0], (3.0, 4.0))


class TheRecordIsTheCommittedOne(Tree):
    """SOL-HW-BOARD-RULE-CHECK-GATE.C3: The separation basis is a written rule the layout check enforces at no less than the signed figure, and a mains-carrying design without it fails.

    The commit that adds or changes a record is its audit trail, so a record
    that is untracked, ignored, staged, edited or deleted since its commit
    gives no signed basis, and a nearer uncommitted record is not passed over
    for a committed one further up.
    """

    design = board_check.Design("hardware/m/board/board.kicad_pro")

    def setUp(self):
        super().setUp()
        subprocess.run(["git", "init", "-q", self.root], check=True)
        self.write("hardware/m/separation-basis.yaml", SIGNED_RECORD)
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "record")

    def repository(self) -> board_check.Repository:
        return board_check.Repository(self.root, board_check.tracked_files("git", self.root))

    def state(self, path: str = "hardware/m/separation-basis.yaml"):
        return self.repository().uncommitted(path)

    def test_a_record_committed_as_it_stands_is_read(self):
        self.assertIsNone(self.state())
        record = board_check.find_record(self.root, self.design.directory, self.repository().tracked)
        self.assertEqual(board_check.read_record(board_check.require_yaml(), self.root, self.design, record, False,
                                                 TODAY, self.state(record)), ((3.0, 4.0), []))

    def test_every_way_a_record_can_differ_from_its_commit_is_named(self):
        self.write("hardware/m/separation-basis.yaml", SIGNED_RECORD.replace("3.0", "5.0"))
        self.assertEqual(self.state(), "has changes that are not committed")
        self.git("add", "-A")
        self.assertEqual(self.state(), "has changes that are not committed")
        os.remove(os.path.join(self.root, "hardware/m/separation-basis.yaml"))
        self.assertEqual(self.state(), "is deleted in the working tree but not in the last commit")
        self.write("hardware/n/separation-basis.yaml", SIGNED_RECORD)
        self.assertEqual(self.state("hardware/n/separation-basis.yaml"), "is not tracked in the repository")
        self.git("add", "hardware/n/separation-basis.yaml")
        self.assertEqual(self.state("hardware/n/separation-basis.yaml"), "is staged but has never been committed")
        self.write(".gitignore", "hardware/o/\n")
        self.write("hardware/o/separation-basis.yaml", SIGNED_RECORD)
        self.assertEqual(self.state("hardware/o/separation-basis.yaml"), "is ignored by git")

    def test_a_nearer_uncommitted_record_is_found_and_fails_rather_than_being_passed_over(self):
        self.write("hardware/m/board/separation-basis.yaml", SIGNED_RECORD)
        repository = self.repository()
        record = board_check.find_record(self.root, self.design.directory, repository.tracked)
        self.assertEqual(record, "hardware/m/board/separation-basis.yaml")
        figures, problems = board_check.read_record(board_check.require_yaml(), self.root, self.design, record,
                                                    False, TODAY, repository.uncommitted(record))
        self.assertIsNone(figures)
        self.assertEqual([(v.rule, v.location) for v in problems],
                         [("separation_basis", "hardware/m/board/separation-basis.yaml")])
        self.assertIn("record is not tracked in the repository", problems[0].message)

    def test_a_tracked_record_deleted_from_disk_is_still_found(self):
        os.remove(os.path.join(self.root, "hardware/m/separation-basis.yaml"))
        self.assertEqual(board_check.find_record(self.root, self.design.directory, self.repository().tracked),
                         "hardware/m/separation-basis.yaml")


# --- The separation floor and the mounting holes ------------------------------

FLOOR_PATH = "hardware/m/separation-basis.yaml"


def floor_row(inputs: dict, **figure) -> dict:
    return {"citation": {"document": "synthetic table", "edition": "none", "locator": "row"}, "inputs": inputs, "figure": figure}


def floor_barrier(name: str, insulation: str) -> dict:
    return {"barrier": name, "insulation": insulation, "earth_bonded": False, "touchable": [], "formed_by": "a slot"}


def floor_basis(**changes) -> dict:
    """A record whose rows give exactly its signed figures, with `changes` set over it and a key set to None left out."""
    basis = {"standard": "synthetic", "working_voltage": "250 V rms", "pollution_degree": 2, "material_group": "IIIb",
             "overvoltage_category": 2, "altitude_m": 2000, "barriers": [], "barrier_types": [],
             "mains_to_low_voltage": {"clearance_mm": 3.0, "creepage_mm": 4.0},
             "table_rows": [floor_row({"working_voltage_v": 250, "overvoltage_category": 2}, clearance_mm=3.0),
                            floor_row({"working_voltage_v": 250, "pollution_degree": 2, "material_group": "IIIb"}, creepage_mm=4.0)],
             "accepted_by": "maintainer", "accepted_on": "2026-10-01", "synthetic": True}
    basis.update(changes)
    return {key: value for key, value in basis.items() if value is not None}


class FloorTree(RecordTree):
    """A record read as the check reads it, and then held to its own floor."""

    def floor(self, **changes):
        yaml = board_check.require_yaml()
        signed, problems = self.record(yaml.safe_dump(floor_basis(**changes)), True)
        self.assertEqual(problems, [])
        return signed, board_check.separation_floor(self.design, FLOOR_PATH, signed)

    def failures(self, **changes):
        return [(v.rule, v.location.split(" ")[-1]) for v in self.floor(**changes)[1]]


class ASignedFigureBelowItsFloorFails(FloorTree):
    """SOL-PRE-ORDER-CHECK-SEPARATION-FLOOR-AND-MOUNTING-HOLES.C1: A signed separation figure below the floor its own inputs give fails."""

    def test_a_record_whose_rows_give_its_figures_passes(self):
        # SOL-PRE-ORDER-CHECK-SEPARATION-FLOOR-AND-MOUNTING-HOLES.C1: A signed mains_to_low_voltage figure is compared with the floor its own table_rows give
        self.assertEqual(self.failures(), [])

    def test_a_signed_clearance_below_its_floor_fails_naming_the_figure_the_floor_and_the_row(self):
        # SOL-PRE-ORDER-CHECK-SEPARATION-FLOOR-AND-MOUNTING-HOLES.C1: The rule fails a signed clearance or creepage below its floor
        rows = floor_basis()["table_rows"]
        rows[0]["figure"]["clearance_mm"] = 3.5
        found = self.floor(table_rows=rows)[1]
        self.assertEqual([(v.rule, v.location) for v in found], [("separation_floor", f"{FLOOR_PATH} mains_to_low_voltage.clearance_mm")])
        self.assertEqual(found[0].design, "hardware/m/board/board.kicad_pro")
        for words in ("clearance_mm is 3 mm", "3.5 mm floor", "table_rows[0]"):
            self.assertIn(words, found[0].message)

    def test_a_signed_creepage_below_its_floor_fails_and_the_clearance_beside_it_does_not(self):
        # SOL-PRE-ORDER-CHECK-SEPARATION-FLOOR-AND-MOUNTING-HOLES.C1: The rule fails a signed clearance or creepage below its floor
        rows = floor_basis()["table_rows"]
        rows[1]["figure"]["creepage_mm"] = 4.5
        self.assertEqual(self.failures(table_rows=rows), [("separation_floor", "mains_to_low_voltage.creepage_mm")])

    def test_the_floor_is_the_largest_figure_over_the_applicable_rows_only(self):
        # SOL-PRE-ORDER-CHECK-SEPARATION-FLOOR-AND-MOUNTING-HOLES.C1: The floor is the largest clearance_mm and the largest creepage_mm over the applicable rows
        rows = floor_basis()["table_rows"] + [floor_row({"working_voltage_v": 250}, clearance_mm=3.2),
                                              floor_row({"working_voltage_v": 200}, clearance_mm=9.0)]
        self.assertEqual(self.failures(table_rows=rows), [("separation_floor", "mains_to_low_voltage.clearance_mm")])
        found = self.floor(table_rows=rows)[1]
        self.assertIn("3.2 mm floor", found[0].message)
        self.assertIn("table_rows[2]", found[0].message)

    def test_a_row_applies_when_its_voltage_and_altitude_are_at_or_above_the_basis_and_not_below(self):
        # SOL-PRE-ORDER-CHECK-SEPARATION-FLOOR-AND-MOUNTING-HOLES.C1: A row applies when its working_voltage_v and altitude_m are at or above the basis values
        def with_row(**inputs):
            return floor_basis()["table_rows"] + [floor_row(inputs, clearance_mm=5.0)]
        self.assertEqual(self.failures(table_rows=with_row(working_voltage_v=250, altitude_m=2000)), [("separation_floor", "mains_to_low_voltage.clearance_mm")])
        self.assertEqual(self.failures(table_rows=with_row(working_voltage_v=300)), [("separation_floor", "mains_to_low_voltage.clearance_mm")])
        self.assertEqual(self.failures(table_rows=with_row(altitude_m=3000)), [("separation_floor", "mains_to_low_voltage.clearance_mm")])
        self.assertEqual(self.failures(table_rows=with_row(working_voltage_v=249.9)), [])
        self.assertEqual(self.failures(table_rows=with_row(altitude_m=1999)), [])

    def test_a_row_applies_only_at_the_basis_category_pollution_degree_and_material_group(self):
        # SOL-PRE-ORDER-CHECK-SEPARATION-FLOOR-AND-MOUNTING-HOLES.C1: its overvoltage_category, pollution_degree and material_group equal the basis values
        def with_row(**inputs):
            return floor_basis()["table_rows"] + [floor_row(inputs, clearance_mm=5.0, creepage_mm=6.0)]
        for equal in ({"overvoltage_category": 2}, {"pollution_degree": 2}, {"material_group": "IIIb"}):
            with self.subTest(equal=equal):
                self.assertEqual(len(self.failures(table_rows=with_row(**equal))), 2)
        for other in ({"overvoltage_category": 3}, {"overvoltage_category": 1}, {"pollution_degree": 3}, {"material_group": "II"}):
            with self.subTest(other=other):
                self.assertEqual(self.failures(table_rows=with_row(**other)), [])

    def test_a_row_that_states_an_input_the_basis_does_not_state_does_not_apply(self):
        # SOL-PRE-ORDER-CHECK-SEPARATION-FLOOR-AND-MOUNTING-HOLES.C1: an input a row omits does not constrain whether it applies
        rows = [floor_row({"working_voltage_v": 250}, clearance_mm=3.0, creepage_mm=4.0),
                floor_row({"pollution_degree": 2}, clearance_mm=5.0)]
        self.assertEqual(self.failures(table_rows=rows, pollution_degree=None), [])
        self.assertEqual(self.failures(table_rows=rows), [("separation_floor", "mains_to_low_voltage.clearance_mm")])

    def test_a_row_applies_at_the_strongest_insulation_among_the_barriers_and_no_other(self):
        # SOL-PRE-ORDER-CHECK-SEPARATION-FLOOR-AND-MOUNTING-HOLES.C1: its insulation equals the strongest insulation among barrier_types
        both = {"barriers": ["a", "b"], "barrier_types": [floor_barrier("a", "basic"), floor_barrier("b", "reinforced")]}
        basic = {"barriers": ["a"], "barrier_types": [floor_barrier("a", "basic")]}
        extra = [floor_row({"insulation": "reinforced"}, clearance_mm=5.0), floor_row({"insulation": "basic"}, clearance_mm=3.5)]
        rows = floor_basis()["table_rows"] + extra
        self.assertIn("5 mm floor", self.floor(table_rows=rows, **both)[1][0].message)
        self.assertIn("3.5 mm floor", self.floor(table_rows=rows, **basic)[1][0].message)

    def test_an_explicit_none_for_barriers_leaves_out_a_row_stating_an_insulation_and_keeps_one_that_does_not(self):
        # SOL-PRE-ORDER-CHECK-SEPARATION-FLOOR-AND-MOUNTING-HOLES.C1: a row that states an insulation does not apply when barrier_types is an explicit none
        stated = floor_basis()["table_rows"] + [floor_row({"insulation": "reinforced"}, clearance_mm=5.0)]
        self.assertEqual(self.failures(table_rows=stated, barrier_types=[]), [])
        only_stated = [floor_row({"insulation": "reinforced"}, clearance_mm=3.0, creepage_mm=4.0)]
        self.assertEqual(self.failures(table_rows=only_stated, barrier_types=[]),
                         [("separation_floor", "mains_to_low_voltage.clearance_mm"), ("separation_floor", "mains_to_low_voltage.creepage_mm")])

    def test_a_row_giving_one_figure_counts_for_that_figure_only(self):
        # SOL-PRE-ORDER-CHECK-SEPARATION-FLOOR-AND-MOUNTING-HOLES.C1: The floor is the largest clearance_mm and the largest creepage_mm over the applicable rows
        rows = [floor_row({"working_voltage_v": 250}, clearance_mm=3.0), floor_row({"working_voltage_v": 250}, creepage_mm=4.0)]
        self.assertEqual(self.failures(table_rows=rows), [])
        rows = [floor_row({"working_voltage_v": 250}, clearance_mm=3.0)]
        self.assertEqual(self.failures(table_rows=rows), [("separation_floor", "mains_to_low_voltage.creepage_mm")])

    def test_a_mains_present_basis_with_no_applicable_row_for_a_figure_fails_for_that_figure(self):
        # SOL-PRE-ORDER-CHECK-SEPARATION-FLOOR-AND-MOUNTING-HOLES.C1: The rule fails a design that declares mains present with no applicable row for either figure
        both = [("separation_floor", "mains_to_low_voltage.clearance_mm"), ("separation_floor", "mains_to_low_voltage.creepage_mm")]
        self.assertEqual(self.failures(table_rows=[]), both)
        self.assertEqual(self.failures(table_rows=None), both)
        self.assertEqual(self.failures(working_voltage="300 V rms"), both)
        self.assertIn("no table row of the record gives a clearance_mm", self.floor(table_rows=[])[1][0].message)

    def test_a_basis_lacking_a_required_key_fails_naming_the_key(self):
        # SOL-PRE-ORDER-CHECK-SEPARATION-FLOOR-AND-MOUNTING-HOLES.C1: The basis keys overvoltage_category, altitude_m and barrier_types are required when the design declares mains present
        for key in ("overvoltage_category", "altitude_m", "barrier_types"):
            with self.subTest(key=key):
                found = self.floor(**{key: None, "barriers": []})[1]
                self.assertEqual([(v.rule, v.location) for v in found], [("separation_floor", f"{FLOOR_PATH} {key}")])
                self.assertIn(f"lacks {key}", found[0].message)

    def test_the_working_voltage_is_the_leading_number_of_the_basis_text_in_volts(self):
        # SOL-PRE-ORDER-CHECK-SEPARATION-FLOOR-AND-MOUNTING-HOLES.C1: working_voltage_v is the leading number of the basis working_voltage, in volts rms
        for text in ("250 V rms", 250, "250.0V", "  250 V rms at the top of the span"):
            with self.subTest(text=text):
                self.assertEqual(self.failures(working_voltage=text), [])
        self.assertEqual(self.failures(working_voltage="251 V rms"),
                         [("separation_floor", "mains_to_low_voltage.clearance_mm"), ("separation_floor", "mains_to_low_voltage.creepage_mm")])
        for text in ("about 250 V", "", 0, -5, True, None):
            with self.subTest(unreadable=text):
                self.assertEqual(self.failures(working_voltage=text), [("separation_floor", "working_voltage")])

    def test_a_record_that_cannot_be_read_is_not_held_to_a_floor_and_fails_as_the_record(self):
        # SOL-PRE-ORDER-CHECK-SEPARATION-FLOOR-AND-MOUNTING-HOLES.C1: the rule reads the figures the record gives
        rows = floor_basis()["table_rows"]
        del rows[0]["figure"]
        yaml = board_check.require_yaml()
        signed, problems = self.record(yaml.safe_dump(floor_basis(table_rows=rows)), True)
        self.assertIsNone(signed)
        self.assertTrue(any(v.rule == "separation_basis" for v in problems))


class TheReaderReturnsTheInputsAndRows(FloorTree):
    """SOL-PRE-ORDER-CHECK-SEPARATION-FLOOR-AND-MOUNTING-HOLES.C3: The rules extend the existing pre-order check and its record reader."""

    def test_the_reader_returns_the_signed_figures_with_the_inputs_and_rows_it_read(self):
        # SOL-PRE-ORDER-CHECK-SEPARATION-FLOOR-AND-MOUNTING-HOLES.C3: this leaf extends it to return those inputs and rows to the rules
        signed, found = self.floor()
        self.assertEqual(signed, (3.0, 4.0))
        self.assertEqual((signed[0], signed[1]), (3.0, 4.0))
        self.assertEqual(signed.basis["overvoltage_category"], 2)
        self.assertEqual(signed.basis["altitude_m"], 2000)
        self.assertEqual(signed.basis["barrier_types"], [])
        self.assertEqual(len(signed.basis["table_rows"]), 2)
        self.assertEqual(found, [])

    def test_the_reader_still_fails_a_key_the_decisions_do_not_define(self):
        # SOL-PRE-ORDER-CHECK-SEPARATION-FLOOR-AND-MOUNTING-HOLES.C3: the reader still fails a key the decisions do not define
        yaml = board_check.require_yaml()
        misspelt = floor_basis()
        misspelt["overvoltage_categry"] = misspelt.pop("overvoltage_category")
        self.assertFails(yaml.safe_dump(misspelt), "overvoltage_categry", "not one a separation basis record has", True)
        rows = floor_basis()["table_rows"]
        rows[0]["inputs"]["altitude"] = 5
        self.assertFails(yaml.safe_dump(floor_basis(table_rows=rows)), "table_rows[0].inputs.altitude", "altitude", True)

    def test_a_record_without_the_new_keys_is_still_read_and_only_the_floor_asks_for_them(self):
        # SOL-PRE-ORDER-CHECK-SEPARATION-FLOOR-AND-MOUNTING-HOLES.C3: The check's record reader already accepts the separation basis keys
        signed, problems = self.record(SIGNED_RECORD)
        self.assertEqual((signed, problems), ((3.0, 4.0), []))
        found = board_check.separation_floor(self.design, FLOOR_PATH, signed)
        self.assertEqual(sorted(v.location.split(" ")[-1] for v in found), ["altitude_m", "barrier_types", "overvoltage_category", "working_voltage"])


class AFloorFailureIsReportedWithItsRuleDesignAndItem(FloorTree):
    """SOL-PRE-ORDER-CHECK-SEPARATION-FLOOR-AND-MOUNTING-HOLES.C4: Every failure names the rule, the design and the offending item."""

    def test_the_report_line_names_the_rule_the_design_the_record_key_and_the_figure(self):
        # SOL-PRE-ORDER-CHECK-SEPARATION-FLOOR-AND-MOUNTING-HOLES.C4: reported with the rule's name, the design, and the offending item (record key or figure)
        rows = floor_basis()["table_rows"]
        rows[0]["figure"]["clearance_mm"] = 3.5
        line = self.floor(table_rows=rows)[1][0].line()
        fields = [field.strip() for field in line.split("|")]
        self.assertEqual(fields[:4], ["VIOLATION", "hardware/m/board/board.kicad_pro", "separation_floor",
                                      f"{FLOOR_PATH} mains_to_low_voltage.clearance_mm"])
        self.assertIn("3.5 mm", fields[4])
        missing = self.floor(altitude_m=None)[1][0].line()
        self.assertIn(f"| separation_floor | {FLOOR_PATH} altitude_m |", missing)


HOLE_LAYOUT = """(kicad_pcb (version 20241229)
 (net 0 "") (net 1 "/MAINS_L") (net 2 "/LV_A")
 (footprint "a:Hole" (layer "F.Cu") (at 3 3) (property "Reference" "H1" (at 0 0 0))
  (pad "" np_thru_hole circle (at 0 0) (size 3.2 3.2) (drill 3.2) (layers "*.Cu")))
 (footprint "a:Screw" (layer "F.Cu") (at 9 3) (property "Reference" "H2" (at 0 0 0))
  (pad "" np_thru_hole circle (at 0 0) (size 3.2 3.2) (drill 3.2) (layers "*.Cu"))
  (pad "1" thru_hole circle (at 0 4) (size 4 4) (drill 3.2) (layers "*.Cu") (net "/LV_A")))
 (footprint "a:Part" (layer "F.Cu") (at 20 3) (property "Reference" "R1" (at 0 0 0))
  (pad "1" thru_hole circle (at 0 0) (size 1.6 1.6) (drill 0.8) (layers "*.Cu") (net "/MAINS_L"))
  (pad "2" thru_hole circle (at 3 0) (size 1.6 1.6) (drill 0.8) (layers "*.Cu") (net "/LV_A")))
 (footprint "a:Plain" (layer "F.Cu") (at 30 3) (property "Reference" "R2" (at 0 0 0)))
 (footprint "a:Q" (layer "F.Cu") (at 40 3) (property "Reference" "H'3" (at 0 0 0))
  (pad "" np_thru_hole circle (at 0 0) (size 3.2 3.2) (drill 3.2) (layers "*.Cu"))))
"""


class AMountingHoleIsFoundAndHeldToTheLargerSignedFigure(unittest.TestCase):
    """SOL-PRE-ORDER-CHECK-SEPARATION-FLOOR-AND-MOUNTING-HOLES.C2: A mounting hole that breaches the separation from mains fails."""

    def setUp(self):
        self.tree = sexpr.parse_one(HOLE_LAYOUT)

    def test_a_mounting_hole_is_a_footprint_whose_pads_are_all_non_plated_holes(self):
        # SOL-PRE-ORDER-CHECK-SEPARATION-FLOOR-AND-MOUNTING-HOLES.C2: A mounting hole is a footprint whose pads are all holes and every non-plated hole
        self.assertEqual(board_check.hole_footprints(self.tree), ["H'3", "H1"])

    def test_the_footprints_the_courtyard_is_held_to_are_those_with_a_pad_on_a_mains_net_bar_the_holes(self):
        # SOL-PRE-ORDER-CHECK-SEPARATION-FLOOR-AND-MOUNTING-HOLES.C2: courtyard distance to the Mains class
        self.assertEqual(board_check.mains_footprints(self.tree, {"/MAINS_L"}, {"H1"}), ["R1"])
        self.assertEqual(board_check.mains_footprints(self.tree, {"/LV_A"}, {"H1"}), ["H2", "R1"])
        self.assertEqual(board_check.mains_footprints(self.tree, set(), set()), [])

    def test_the_rules_hold_the_larger_of_the_two_signed_figures_and_name_each_hole_and_part(self):
        # SOL-PRE-ORDER-CHECK-SEPARATION-FLOOR-AND-MOUNTING-HOLES.C2: rules holding the hole clearance and courtyard distance to the Mains class at no less than the larger of the signed clearance and the signed creepage
        text = board_check.hole_rules(4.0, ["H1"], ["R1", "H1"])
        self.assertEqual(text.count("(min 4mm)"), 4)
        self.assertIn("hole_clearance", text)
        self.assertIn("physical_clearance", text)
        self.assertIn("A.Reference == 'H1' && (B.Reference == 'R1')", text)
        self.assertNotIn("B.Reference == 'H1'", text)
        self.assertIn("A.Pad_Type == 'NPTH, mechanical' && B.hasNetclass('Mains')", text)
        self.assertIn("!A.hasNetclass('Mains') && B.hasNetclass('Mains')", text)
        self.assertNotIn("(min 3mm)", board_check.hole_rules(4.0, ["H1"], ["R1"]))

    def test_a_design_with_no_hole_and_no_mains_part_is_given_no_courtyard_rule(self):
        # SOL-PRE-ORDER-CHECK-SEPARATION-FLOOR-AND-MOUNTING-HOLES.C2: A design with no mounting hole is not failed for that
        self.assertNotIn("courtyard_clearance", board_check.hole_rules(4.0, [], ["R1"]))
        self.assertNotIn("courtyard_clearance", board_check.hole_rules(4.0, ["H1"], []))
        self.assertEqual(board_check.hole_footprints(sexpr.parse_one('(kicad_pcb (version 1) (net 0 ""))')), [])

    def test_the_hole_rules_come_after_the_signed_rule_so_that_the_signed_rule_is_not_the_last_word_on_a_hole(self):
        # SOL-PRE-ORDER-CHECK-SEPARATION-FLOOR-AND-MOUNTING-HOLES.C2: After the signed Mains rule the check appends rules
        appended = board_check.appended_rules((3.0, 4.0), "nonce") + board_check.hole_rules(4.0, ["H1"], ["R1"])
        self.assertLess(appended.index(board_check.SIGNED_RULE), appended.index(board_check.HOLE_RULE))
        self.assertLess(appended.index(board_check.SIGNED_RULE), appended.index(board_check.PLATED_RULE))
        self.assertLess(appended.index(board_check.SIGNED_RULE), appended.index(board_check.FIXING_RULE))
        self.assertIn(board_check.RESERVED, board_check.HOLE_RULE)

    def test_a_reference_that_cannot_be_written_into_a_rule_fails_naming_the_part_without_running_kicad(self):
        # SOL-PRE-ORDER-CHECK-SEPARATION-FLOOR-AND-MOUNTING-HOLES.C4: reported with the rule's name, the design, and the offending item (part reference)
        design = board_check.Design("hardware/m/board/board.kicad_pro")
        with tempfile.TemporaryDirectory() as scratch:
            found = board_check.mounting_holes("kicad-cli-that-is-not-there", design, scratch, "board.kicad_pcb",
                                               os.path.join(scratch, "board.kicad_dru"), "(version 1)\n",
                                               board_check.Signed(3.0, 4.0, {}), "nonce", None, self.tree, {"/MAINS_L"})
        self.assertEqual([(v.rule, v.design) for v in found], [("mounting_hole", "hardware/m/board/board.kicad_pro")])
        self.assertIn("H'3", found[0].location)
        self.assertIn("rename the part", found[0].message)


# --- The design's own rules --------------------------------------------------


class TheMainsRuleHasOneForm(Tree):
    """SOL-HW-BOARD-RULE-CHECK-GATE.C3: The separation basis is a written rule the layout check enforces at no less than the signed figure, and a mains-carrying design without it fails."""

    design = board_check.Design("b/b.kicad_pro")

    def rules(self, text):
        if text is not None:
            self.write("b/b.kicad_dru", text)
        rules, hidden = board_check.read_rules(self.root, self.design, self.everything())
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
        self.assertEqual(self.verdict(MAINS_RULE.replace("3mm", "5mm").replace("4mm", "6.35mm")), [])
        self.assertEqual(self.verdict(MAINS_RULE.replace("(constraint clearance", "(severity error)\n\t(constraint clearance")), [])

    def test_a_condition_not_written_exactly_as_required_fails(self):
        for written in ("A.hasNetclass('Mains')&&!B.hasNetclass('Mains')",
                        "A.hasNetclass('Ma ins') && !B.hasNetclass('Mains')",
                        "A.hasNetclass('Mains') && !B.hasNetclass('Mains ')",
                        "A.hasNetclass(\\\"Mains\\\") && !B.hasNetclass('Mains')"):
            with self.subTest(condition=written):
                self.assertOnly(self.verdict(MAINS_RULE.replace(board_check.MAINS_CONDITION, written)),
                                "not in the required form")

    def test_a_second_condition_after_the_required_one_is_not_the_mains_rule(self):
        text = MAINS_RULE.replace("Mains')\")", "Mains')\")\n\t(condition \"A.Type == 'Via'\")")
        self.assertOnly(self.verdict(text), "not in the required form")
        _, hidden = self.rules(text)
        self.assertEqual([(v.rule, v.location) for v in hidden], [("custom_rules", "b/b.kicad_dru rule 'Mains separation'")])
        self.assertIn("holds 2 (condition ...) clauses", hidden[0].message)

    def test_a_constraint_the_check_does_not_read_or_stated_twice_fails(self):
        self.assertOnly(self.verdict(MAINS_RULE.replace("(constraint creepage", "(constraint track_width (min 1mm))\n\t(constraint creepage")),
                        "holds a (constraint track_width ...) constraint, which the check does not read")
        self.assertOnly(self.verdict(MAINS_RULE.replace("(constraint creepage", "(constraint clearance (min 9mm))\n\t(constraint creepage")),
                        "holds 2 clearance constraints")

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
        for written in ("(max 9mm)", "(min 3mm) (opt 4mm)", "(min 118mil)", "(min 0.12in)", "(min 3)", '(min "3mm")',
                        "(min .3mm)", "(min 3e0mm)", "(min 3 mm)"):
            with self.subTest(figure=written):
                self.assertOnly(self.verdict(MAINS_RULE.replace("(min 3mm)", written)),
                                "where the check reads only (constraint clearance (min <number>mm))")
        split = MAINS_RULE.replace("\t(constraint creepage (min 4mm)))", ")") + MAINS_RULE.split("\n", 1)[1].replace(
            "\t(constraint clearance (min 3mm))\n", "")
        self.assertOnly(self.verdict(split), "more than one rule")

    def test_a_declared_figure_below_the_record_fails(self):
        self.assertOnly(self.verdict(MAINS_RULE.replace("3mm", "2.9mm")), "clearance of 2.9 mm, below the signed 3 mm")
        self.assertOnly(self.verdict(MAINS_RULE.replace("4mm", "3.81mm")), "creepage of 3.81 mm, below the signed 4 mm")

    def test_figures_are_not_compared_when_there_is_no_signed_basis(self):
        self.assertEqual(self.verdict(MAINS_RULE.replace("3mm", "0.1mm"), signed=None), [])


class RulesThatHideWhatTheyFind(Tree):
    """SOL-HW-BOARD-RULE-CHECK-GATE.C2: A design passes only if KiCad's own electrical and layout rule checks find no violation, including no layout-schematic disagreement."""

    design = board_check.Design("b/b.kicad_pro")

    def test_a_custom_rule_set_to_ignore_or_exclusion_fails(self):
        for level in ("ignore", "exclusion"):
            with self.subTest(severity=level):
                write(self.root, "b/b.kicad_dru", MAINS_RULE + f'(rule "quiet"\n\t(condition "A.Type == \'Via\'")\n\t(severity {level}))\n')
                _, hidden = board_check.read_rules(self.root, self.design, self.everything())
                self.assertEqual([(v.rule, v.location) for v in hidden], [("ignored_check", "b/b.kicad_dru rule 'quiet'")])

    def test_a_rule_at_error_or_warning_is_not_flagged(self):
        write(self.root, "b/b.kicad_dru", MAINS_RULE + '(rule "w" (condition "A.Type == \'Via\'") (severity warning))\n')
        self.assertEqual(board_check.read_rules(self.root, self.design, self.everything())[1], [])

    def test_a_rules_file_git_does_not_track_fails_and_is_not_read(self):
        write(self.root, "b/b.kicad_dru", MAINS_RULE)
        rules, hidden = board_check.read_rules(self.root, self.design, board_check.Repository(self.root, []))
        self.assertEqual(rules, [])
        self.assertEqual([(v.rule, v.location) for v in hidden], [("custom_rules", "b/b.kicad_dru")])
        self.assertIn("custom rules file is not tracked in the repository", hidden[0].message)
        self.assertEqual(board_check.read_rules(self.root, board_check.Design("c/c.kicad_pro"),
                                                board_check.Repository(self.root, [])), (None, []))

    def test_a_rule_named_with_the_words_reserved_for_the_check_fails(self):
        for name in ("pre-order check: rules loaded", "Pre-Order Check: signed separation basis", "my pre-order check"):
            with self.subTest(name=name):
                write(self.root, "b/b.kicad_dru", MAINS_RULE + f'(rule "{name}" (condition "A.Type == \'Pad\'") (constraint assertion "false"))\n')
                _, hidden = board_check.read_rules(self.root, self.design, self.everything())
                self.assertEqual([(v.rule, v.location) for v in hidden], [("custom_rules", f"b/b.kicad_dru rule '{name}'")])
                self.assertIn("reserved for the rules the check adds", hidden[0].message)

    def test_a_rules_file_that_cannot_be_read_fails(self):
        write(self.root, "b/b.kicad_dru", MAINS_RULE + "(rule \"broken\"")
        rules, hidden = board_check.read_rules(self.root, self.design, self.everything())
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


class TheRulesFileIsReadInOneForm(Tree):
    """SOL-HW-BOARD-RULE-CHECK-GATE.C2: A design passes only if KiCad's own electrical and layout rule checks find no violation, including no layout-schematic disagreement.

    KiCad loads a rule holding a clause twice and keeps only one of them, and
    loads two rules of one name; the check reads neither, so each fails by name
    rather than being read one way by the check and another by KiCad.
    """

    design = board_check.Design("b/b.kicad_pro")

    def hidden(self, text: str):
        self.write("b/b.kicad_dru", "(version 1)\n" + text)
        return board_check.read_rules(self.root, self.design, self.everything())[1]

    def test_a_clause_kicad_takes_once_given_twice_fails(self):
        for clause, body in (("condition", "(condition \"A.Type == 'Pad'\")"), ("severity", "(severity warning)")):
            with self.subTest(clause=clause):
                found = self.hidden(f'(rule "r"\n\t{body}\n\t{body}\n\t(constraint clearance (min 1mm)))\n')
                self.assertEqual([(v.rule, v.location) for v in found], [("custom_rules", "b/b.kicad_dru rule 'r'")])
                self.assertIn(f"holds 2 ({clause} ...) clauses", found[0].message)

    def test_one_of_each_clause_is_read_without_complaint(self):
        self.assertEqual(self.hidden('(rule "r"\n\t(layer outer)\n\t(condition "A.Type == \'Pad\'")\n\t(severity warning)\n'
                                     '\t(constraint clearance (min 1mm))\n\t(constraint track_width (min 1mm)))\n'), [])

    def test_two_rules_of_one_name_fail_once_naming_it(self):
        rule = '(rule "same"\n\t(condition "A.Type == \'Pad\'")\n\t(constraint clearance (min 1mm)))\n'
        found = self.hidden(rule + rule + rule.replace("same", "other"))
        self.assertEqual([(v.rule, v.location) for v in found], [("custom_rules", "b/b.kicad_dru rule 'same'")])
        self.assertIn("2 rules are named 'same'", found[0].message)


class TheChecksOwnRulesCannotBeForged(unittest.TestCase):
    """SOL-HW-BOARD-RULE-CHECK-GATE.C2: A design passes only if KiCad's own electrical and layout rule checks find no violation, including no layout-schematic disagreement.

    The check sets aside only the findings of the rules it adds itself, and it
    knows them by a name drawn for the run, so a design rule written to look
    like one of them has its findings reported like any other.
    """

    def entry(self, rule: str) -> dict:
        return {"type": "assertion_failure", "description": f"Assertion failure (rule '{rule}')", "items": []}

    def test_the_added_rules_are_named_for_the_run_and_carry_the_reserved_words(self):
        text = board_check.appended_rules((3.0, 4.0), "0123abcd")
        names = [form[1] for form in sexpr.parse(text) if sexpr.head(form) == "rule"]
        self.assertEqual(names, ["pre-order check 0123abcd: rules loaded", board_check.SIGNED_RULE])
        self.assertTrue(all(board_check.RESERVED in name for name in names))
        self.assertEqual(len([f for f in sexpr.parse(board_check.appended_rules(None, "n")) if sexpr.head(f) == "rule"]), 1)

    def test_only_this_runs_rules_are_recognised(self):
        report = {"violations": [self.entry("pre-order check: rules loaded"), self.entry("pre-order check other: rules loaded"),
                                 self.entry(board_check.marker_rule("run")), {"type": "clearance", "description":
                                 f"(rule '{board_check.marker_rule('run')}')"}]}
        self.assertEqual(board_check.fired(report, board_check.marker_rule("run")), [report["violations"][2]])

    def test_each_design_check_draws_its_own_name_and_reports_a_lookalike(self):
        # A stand-in for kicad-cli that keeps every rules file it is given and
        # reports a finding of the fixed name a design might copy, plus the
        # marker of whichever run it is serving.
        with tempfile.TemporaryDirectory() as root:
            kept = os.path.join(root, "kept")
            fake = os.path.join(root, "kicad-cli")
            with open(fake, "w", encoding="utf-8") as handle:
                handle.write(f"""#!{sys.executable}
import glob, json, re, sys
args = sys.argv[1:]
out = args[args.index("-o") + 1]
if args[:2] == ["sch", "erc"]:
    report = {{"sheets": []}}
elif args[:3] == ["sch", "export", "netlist"]:
    open(out, "w").write("(export (nets))"); sys.exit(0)
else:
    rules = open(glob.glob("*.kicad_dru")[0]).read()
    open({kept!r}, "a").write(rules + "\\n=====\\n")
    marker = re.findall(r'rule "(pre-order check [0-9a-f]+: rules loaded)"', rules)[-1]
    report = {{"violations": [
        {{"type": "assertion_failure", "description": "Assertion failure (rule 'pre-order check: rules loaded')", "items": []}},
        {{"type": "assertion_failure", "description": "Assertion failure (rule '" + marker + "')", "items": []}}]}}
json.dump(report, open(out, "w"))
""")
            os.chmod(fake, 0o755)
            for path, text in (("a/a.kicad_pro", none_project()), ("a/a.kicad_sch", schematic()),
                               ("a/a.kicad_pcb", "(kicad_pcb)"), ("a/a.kicad_dru", "(version 1)\n" + WORKMANSHIP)):
                write(root, path, text)
            repository = board_check.Repository(root, ["a/a.kicad_pro", "a/a.kicad_sch", "a/a.kicad_pcb", "a/a.kicad_dru"])
            design = board_check.Design("a/a.kicad_pro")
            runs = [board_check.check_design(design, repository, fake, board_check.require_yaml(), TODAY, [])
                    for _ in range(2)]
            with open(kept, encoding="utf-8") as handle:
                names = re.findall(r'rule "(pre-order check ([0-9a-f]+): rules loaded)"', handle.read())
        # Each design check runs KiCad's layout check on the design under a name
        # of its own; a design with no nets has no class membership to ask about.
        nonces = [nonce for _, nonce in names]
        self.assertEqual(len(nonces), 2)
        self.assertNotEqual(nonces[0], nonces[1], "two runs used the same name for the marker")
        self.assertTrue(all(len(nonce) >= 16 for nonce in nonces))
        for found in runs:
            # This design holds no pin allocation, parts specification or catalogue extract record; their own rules are tested apart.
            self.assertEqual([(v.rule, v.message) for v in found if v.rule != "pin_allocation" and not v.rule.startswith("parts_")],
                             [("assertion_failure", "Assertion failure (rule 'pre-order check: rules loaded')")])


class MainsMembershipIsReadWhereverItIsDeclared(unittest.TestCase):
    """SOL-HW-BOARD-RULE-CHECK-GATE.C3: The separation basis is a written rule the layout check enforces at no less than the signed figure, and a mains-carrying design without it fails.

    A net sits in the Mains class whether the layout's copper, the schematic or
    the project file's net settings put it there, and each of the three is read
    as KiCad resolves it.
    """

    def test_the_schematic_netlist_gives_every_net_kicad_puts_in_mains(self):
        netlist = sexpr.parse_one('(export (nets (net (code "1") (name "/A") (class "Mains"))'
                                  ' (net (code "2") (name "/B") (class "Default"))'
                                  ' (net (code "3") (name "/C") (class "Fast,Mains"))'
                                  ' (net (code "4") (name "/D") (class "Mainsish"))'
                                  ' (net (code "5") (name "/E"))))')
        self.assertEqual(board_check.schematic_mains(board_check.schematic_nets(netlist)), {"/A", "/C"})

    def test_the_schematic_netlist_says_which_pins_each_net_joins(self):
        netlist = sexpr.parse_one('(export (nets (net (code "1") (name "/A") (class "Mains")'
                                  ' (node (ref "R1") (pin "2")) (node (ref "J1") (pin "1"))) (net (name "/B"))))')
        self.assertEqual(board_check.schematic_nets(netlist),
                         {"/A": (["Mains"], ["R1 pin 2", "J1 pin 1"]), "/B": ([], [])})

    def test_the_layouts_mains_items_are_matched_to_its_own_net_names_brackets_and_all(self):
        layout = sexpr.parse_one('(kicad_pcb (footprint "x" (pad "1" smd rect (net "/AC] of R9 [x")))'
                                 ' (segment (net "/AC")) (zone (net "/LV")))')
        names = board_check.layout_nets(layout)
        self.assertEqual(names, {"/AC] of R9 [x", "/AC", "/LV"})
        probe = [{"items": [{"description": "SMD pad 1 [/AC] of R9 [x] of X1"}]},
                 {"items": [{"description": "Track [/AC] on F.Cu, length 2 mm"}]}]
        self.assertEqual(board_check.probed_nets(probe, names), {"/AC] of R9 [x", "/AC"})
        self.assertEqual(board_check.probed_nets(probe[1:], set()), {"/AC"})



class TheThreeStatementsOfMainsMustAgree(unittest.TestCase):
    """SOL-HW-BOARD-RULE-CHECK-GATE.C3: The separation basis is a written rule the layout check enforces at no less than the signed figure, and a mains-carrying design without it fails.

    The layout's Mains nets are the ones the separation rule is enforced
    against, so a net the schematic or the project file puts in Mains while the
    layout does not would carry mains with nothing holding low-voltage copper
    away from it. Taking the union of the three would read such a design as
    carrying mains and pass it; every net must be in all three or in none.
    """

    design = board_check.Design("b/b.kicad_pro")
    L, S, P = board_check.ON_LAYOUT, board_check.IN_SCHEMATIC, board_check.IN_PROJECT

    def disagreements(self, layout, schematic, project, mains="present"):
        locate = {self.L: {net: f"pad of {net}" for net in layout}, self.S: {}, self.P: {}}
        found = board_check.mains_agreement(self.design, mains, {self.L: set(layout), self.S: set(schematic),
                                                                 self.P: set(project)}, locate)
        self.assertTrue(all(v.rule == "mains_class" and v.design == "b/b.kicad_pro" for v in found), found)
        return found

    def test_three_sources_naming_the_same_nets_agree(self):
        self.assertEqual(self.disagreements({"/L", "/N"}, {"/L", "/N"}, {"/L", "/N"}), [])
        self.assertEqual(self.disagreements(set(), set(), set(), "none"), [])

    def test_a_net_only_the_schematic_puts_in_mains_fails_naming_where_it_is_missing(self):
        found = self.disagreements(set(), {"/L"}, set())
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].location, "net /L")
        self.assertIn("net /L is in the Mains net class in the schematic but not on the layout or in the project "
                      "file's net settings", found[0].message)

    def test_a_net_only_the_project_file_puts_in_mains_fails(self):
        found = self.disagreements(set(), set(), {"/GHOST"})
        self.assertIn("in the project file's net settings but not on the layout or in the schematic", found[0].message)

    def test_a_net_only_the_layout_puts_in_mains_fails_pointing_at_the_layouts_own_class(self):
        found = self.disagreements({"/L", "/LV"}, {"/L"}, {"/L"})
        self.assertEqual([v.location for v in found], ["net /LV: pad of /LV"])
        self.assertIn("on the layout but not in the schematic or in the project file's net settings", found[0].message)
        self.assertIn("(net_class ...) block in the layout file", found[0].message)

    def test_one_net_differing_fails_for_that_net_alone_whatever_the_others_agree_on(self):
        found = self.disagreements({"/L", "/N"}, {"/L", "/N", "/LV_B"}, {"/L", "/N"})
        self.assertEqual([v.location for v in found], ["net /LV_B"])
        found = self.disagreements({"/L", "/N", "/LV_A"}, {"/L", "/N"}, {"/L", "/N", "/LV_A"})
        self.assertIn("on the layout and in the project file's net settings but not in the schematic", found[0].message)

    def test_a_design_declaring_no_mains_is_told_to_take_the_net_out_or_declare_mains(self):
        found = self.disagreements(set(), {"/L"}, set(), mains="none")
        self.assertIn("take it out of Mains wherever it is, or set MAINS to present", found[0].message)


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


NET_TIE = """(kicad_pcb
	(footprint "x" (at 5 6) (property "Reference" "NT1") {groups}
		(pad "1" smd rect (net "/MAINS_L")) (pad "2" smd rect (net "{net2}")) (pad "3" smd rect (net "/LV_A"))))"""


class NothingExemptsMainsCopperFromSeparation(unittest.TestCase):
    """SOL-HW-BOARD-RULE-CHECK-GATE.C3: The separation basis is a written rule the layout check enforces at no less than the signed figure, and a mains-carrying design without it fails.

    A net tie joins its nets in copper and KiCad checks no clearance between
    the pads it ties, so one joining a Mains-class net to any other joins
    low-voltage copper to mains unchecked; one joining Mains-class nets only is
    harmless.
    """

    design = board_check.Design("b/b.kicad_pro")

    def found(self, groups: str, net2: str = "/MAINS_N"):
        tree = sexpr.parse_one(NET_TIE.format(groups=groups, net2=net2))
        return board_check.net_ties(self.design, tree, {"/MAINS_L", "/MAINS_N"})

    def test_a_footprint_that_is_no_net_tie_or_ties_only_mains_nets_passes(self):
        self.assertEqual(self.found(""), [])
        self.assertEqual(self.found('(net_tie_pad_groups "1, 2")'), [])

    def test_a_net_tie_joining_mains_to_any_other_net_fails_naming_both(self):
        for groups, net2, words in (('(net_tie_pad_groups "1, 3")', "/MAINS_N", "joins Mains-class /MAINS_L to /LV_A"),
                                    ('(net_tie_pad_groups "1,2")', "", "joins Mains-class /MAINS_L to (no net)"),
                                    ('(net_tie_pad_groups "1, 2" "2, 3")', "/MAINS_N", "joins Mains-class /MAINS_N to /LV_A")):
            with self.subTest(groups=groups, net2=net2):
                found = self.found(groups, net2)
                self.assertEqual([(v.rule, v.location) for v in found], [("mains_net_tie", "footprint NT1 at (5, 6) mm")])
                self.assertIn(words, found[0].message)

    def test_a_group_naming_a_pad_the_footprint_lacks_fails(self):
        found = self.found('(net_tie_pad_groups "1, 7")')
        self.assertEqual([v.rule for v in found], ["mains_net_tie"])
        self.assertIn("names pad 7, which the footprint does not have", found[0].message)


class TheProjectFileIsReadInOneForm(Tree):
    """SOL-HW-BOARD-RULE-CHECK-GATE.C2: A design passes only if KiCad's own electrical and layout rule checks find no violation, including no layout-schematic disagreement.

    The settings the check reads from the project file -- its text variables,
    exclusion lists and net class assignments -- are read only in the form KiCad
    writes them, each key once; any other form fails the design by name before
    anything is read from it.
    """

    design = board_check.Design("p/p.kicad_pro")

    def check(self, text: str):
        self.write("p/p.kicad_pro", text)
        return board_check.check_design(self.design, self.everything(), "kicad-cli-never-run", board_check.require_yaml(), TODAY, [])

    def test_a_key_given_twice_fails_and_nothing_else_is_read(self):
        found = self.check('{"text_variables": {"MAINS": "none", "MAINS": "present"}}')
        self.assertEqual([(v.rule, v.location) for v in found], [("project_file", "p/p.kicad_pro")])
        self.assertIn("gives the key 'MAINS' more than once", found[0].message)
        found = self.check('{"board": {"x": 1}, "board": {"design_settings": {}}}')
        self.assertEqual([v.rule for v in found], ["project_file"])

    def test_a_setting_not_of_the_type_kicad_writes_fails_naming_it(self):
        cases = {
            '{"text_variables": ["MAINS", "none"]}': "text_variables",
            '{"text_variables": {"MAINS": "none"}, "board": {"design_settings": {"drc_exclusions": {"a": 1}}}}': "board.design_settings.drc_exclusions",
            '{"text_variables": {"MAINS": "none"}, "erc": {"erc_exclusions": "clearance"}}': "erc.erc_exclusions",
            '{"text_variables": {"MAINS": "none"}, "net_settings": {"netclass_assignments": ["/A"]}}': "net_settings.netclass_assignments",
            '{"text_variables": {"MAINS": true}}': "text_variables.MAINS",
            '{"text_variables": {"MAINS": "none", "NOT_FOR_MANUFACTURE": "yes"}}': "text_variables.NOT_FOR_MANUFACTURE",
            '{"text_variables": {"MAINS": "none", "NOT_FOR_MANUFACTURE": "True"}}': "text_variables.NOT_FOR_MANUFACTURE",
        }
        for text, setting in cases.items():
            with self.subTest(project=text):
                found = self.check(text)
                self.assertEqual([(v.rule, v.location) for v in found], [("project_file", f"p/p.kicad_pro {setting}")])

    def test_the_forms_kicad_writes_are_read_without_complaint(self):
        project = {"text_variables": {"MAINS": "none", "NOT_FOR_MANUFACTURE": "false"},
                   "board": {"design_settings": {"drc_exclusions": []}}, "erc": {"erc_exclusions": None},
                   "net_settings": {"netclass_assignments": None}}
        self.assertEqual(board_check.project_form(self.design, project), [])
        self.assertEqual(board_check.project_form(self.design, {}), [])


class KiCadRunsWithAConfigurationOfTheChecksOwn(Tree):
    """SOL-HW-BOARD-RULE-CHECK-GATE.C4: One task-runner command runs the whole check with tools any reader can obtain.

    KiCad is run with a configuration the check makes, holding only the
    libraries KiCad installs with itself, and with no KICAD variable from the
    caller's environment, so nothing set up on the author's machine reaches the
    result; a library only that machine supplies is reported by KiCad as one its
    configuration does not include, and the check names it as the design's.
    """

    def fake(self, makes: str) -> str:
        return fake_tool(os.path.join(self.root, "kicad-cli"), f"""
import os, sys
home = os.environ["KICAD_CONFIG_HOME"]
for name in {makes!r}:
    os.makedirs(os.path.join(home, name), exist_ok=True)
with open(os.path.join(home, "seen-environment"), "w") as handle:
    handle.write("\\n".join(sorted(os.environ)))
print("10.0.7")
""", sys.executable)

    def test_the_configuration_names_only_kicads_own_libraries_and_no_caller_variable_reaches_kicad(self):
        home = os.path.join(self.root, "home")
        os.makedirs(home)
        with mock.patch.dict(os.environ, {"KICAD10_FOOTPRINT_DIR": "/mine", "KICAD_CONFIG_HOME": "/my-config",
                                          "KIPRJMOD": "/x", "KiCad_User_Libs": "/y", "HOME_STAYS": "1"}):
            environment = board_check.isolate_kicad(self.fake(["10.0"]), "10.0.7", home)
        self.assertEqual(environment["KICAD_CONFIG_HOME"], home)
        self.assertEqual([name for name in environment if name.upper().startswith("KICAD") or name == "KIPRJMOD"],
                         ["KICAD_CONFIG_HOME"])
        self.assertIn("HOME_STAYS", environment)
        with open(os.path.join(home, "seen-environment"), encoding="utf-8") as handle:
            seen = handle.read().split()
        self.assertIn("HOME_STAYS", seen)
        self.assertEqual([name for name in seen if name.upper().startswith("KICAD") or name == "KIPRJMOD"], ["KICAD_CONFIG_HOME"])
        for kind in ("sym", "fp"):
            with open(os.path.join(home, "10.0", f"{kind}-lib-table"), encoding="utf-8") as handle:
                entries = sexpr.children(sexpr.parse_one(handle.read()), "lib")
            self.assertEqual(len(entries), 1)
            self.assertEqual(sexpr.child(entries[0], "type")[1], "Table")
            self.assertEqual(sexpr.child(entries[0], "uri")[1], f"${{KICAD10_TEMPLATE_DIR}}/{kind}-lib-table")

    def test_a_kicad_that_makes_no_single_configuration_folder_stops_the_check(self):
        for makes in ([], ["10.0", "9.0"]):
            with self.subTest(makes=makes):
                home = tempfile.mkdtemp(dir=self.root)
                with self.assertRaises(board_check.CannotRun) as raised:
                    board_check.isolate_kicad(self.fake(makes), "10.0.7", home)
                self.assertIn("configuration of its own", str(raised.exception))

    def test_every_kicad_run_is_given_the_configuration(self):
        board_check.KICAD_ENVIRONMENT = {"KICAD_CONFIG_HOME": "/isolated", "PATH": os.environ.get("PATH", "")}
        self.addCleanup(setattr, board_check, "KICAD_ENVIRONMENT", None)
        tool = fake_tool(os.path.join(self.root, "kicad-cli"), """
import os, sys
open(sys.argv[sys.argv.index("-o") + 1], "w").write(os.environ.get("KICAD_CONFIG_HOME", "unset"))
""", sys.executable)
        self.assertEqual(board_check.run_kicad([tool, "pcb", "drc"], self.root, "out.txt"), ("/isolated", ""))

    def test_a_library_kicads_configuration_does_not_include_is_named_as_the_designs(self):
        design = board_check.Design("d/d.kicad_pro")
        missing = board_check.kicad_violation(design, {"type": "lib_footprint_issues", "description":
                                              "The current configuration does not include the footprint library 'mine'",
                                              "items": [{"description": "Footprint R1", "pos": {"x": 1, "y": 2}}]}, "d/d.kicad_pcb")
        self.assertEqual((missing.rule, missing.location), ("design_library", "Footprint R1 @ (1, 2) mm"))
        self.assertIn("name it in the design's own table through ${KIPRJMOD}", missing.message)
        other = board_check.kicad_violation(design, {"type": "lib_symbol_issues", "description":
                                            "Symbol 'R' doesn't match copy in library 'proof'", "items": []}, "d/d.kicad_sch")
        self.assertEqual(other.rule, "lib_symbol_issues")


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

    def test_a_git_older_than_the_minimum_stops_naming_it(self):
        def git_reporting(version: str) -> str:
            return fake_tool(os.path.join(self.root, f"git-{version}"),
                             f'if [ "$1" = "--version" ]; then echo "git version {version}"; else exec git "$@"; fi')
        for version in ("2.10.5", "1.9.0"):
            with self.subTest(version=version), self.assertRaises(board_check.CannotRun) as stop:
                board_check.require_git(git_reporting(version), REPO)
            self.assertIn("git 2.11 or newer", str(stop.exception))
            self.assertIn(f"git version {version}", str(stop.exception))
        with self.assertRaises(board_check.CannotRun) as stop:
            board_check.require_git(fake_tool(os.path.join(self.root, "not-git"), "echo hello"), REPO)
        self.assertIn("git 2.11 or newer", str(stop.exception))
        self.assertEqual(board_check.require_git(git_reporting("2.11.0"), REPO), REPO)

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
            for words in ("KiCad 10.0", "Python 3.9", "PyYAML 5.1", "git 2.11", "KICAD_CLI"):
                self.assertIn(words, text)
        for location in ("/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli",
                         r"C:\Program Files\KiCad\10.0\bin\kicad-cli.exe", "/usr/bin/kicad-cli"):
            self.assertIn(location, readme)


# --- The report ------------------------------------------------------------------


class WhyNoRejectedRuleCanBeNamedIsSaid(unittest.TestCase):
    """SOL-HW-BOARD-RULE-CHECK-GATE.C6: The check's report names each design, its verdict and every violation in terms a builder can act on.

    When KiCad drops a rules file and no single rule in it can be named, the
    report says why, by cause, rather than claiming every form loads.
    """

    def rejected(self, text: str):
        # A stand-in for kicad-cli whose layout check loads a rules file only
        # when it holds no '#' comment.
        with tempfile.TemporaryDirectory() as root:
            fake = os.path.join(root, "kicad-cli")
            with open(fake, "w", encoding="utf-8") as handle:
                handle.write(f"""#!{sys.executable}
import glob, json, re, sys
args = sys.argv[1:]
rules = open(glob.glob("*.kicad_dru")[0]).read()
names = [] if "#" in rules else re.findall(r'rule "([^"]*)"', rules)
json.dump({{"violations": [{{"type": "assertion_failure", "description": "(rule '" + n + "')"}} for n in names]}},
          open(args[args.index("-o") + 1], "w"))
""")
            os.chmod(fake, 0o755)
            return board_check.rejected_form(fake, root, "b.kicad_pcb", os.path.join(root, "b.kicad_dru"), text, "n")

    def test_a_file_that_is_not_well_formed_is_said_to_be_so_at_its_line(self):
        where, what = self.rejected("(version 1)\n(rule \"a\"\n\t(condition \"A.Type == 'Pad'\")\n")
        self.assertEqual(where, "at its end")
        self.assertIn("not well-formed (1 unclosed '(' at end of text)", what)
        self.assertNotIn("each loads", what)
        where, what = self.rejected("(version 1)\n(rule \"a\"))\n")
        self.assertEqual(where, "at line 2")
        self.assertIn("unbalanced ')' at line 2", what)

    def test_a_file_whose_every_form_loads_alone_is_said_to_fail_between_them(self):
        where, what = self.rejected("(version 1)\n# a comment KiCad will not take\n(rule \"a\" (condition \"A.Type == 'Pad'\"))\n")
        self.assertEqual(where, "between its rules")
        self.assertIn("comments", what)


#: A stand-in for kicad-cli's layout check on the class read's boards of one
#: track per net. It answers as KiCad does: the marker for each track on the back
#: copper, each class's probe for each track whose net is in the class, and,
#: past KiCad's report limit, that many of the failures chosen at random. Which
#: nets are in which class comes from FAKE_MEMBERS (a class -> nets mapping,
#: "*" for every net); FAKE_FLOOD adds that many failures of a further rule, and
#: FAKE_LOG records each board's tracks.
FAKE_CLASS_READ = r"""
import json, os, random, re, sys
args = sys.argv[1:]
out = args[args.index("-o") + 1]
board = open(args[args.index("-o") - 1]).read()
rules = open(args[args.index("-o") - 1].replace(".kicad_pcb", ".kicad_dru")).read()
tracks = re.findall(r'\(layer "([^"]+)"\) \(net "([^"]*)"\)', board)
members = json.loads(os.environ["FAKE_MEMBERS"])
marker = re.findall(r'rule "(pre-order check [0-9a-f]+: rules loaded)"', rules)
probes = re.findall(r'rule "(pre-order check [0-9a-f]+: (.+?) item)"', rules)
entries = []
for layer, net in tracks:
    item = {"description": "Track [" + net + "] on " + layer + ", length 1.0000 mm"}
    if layer == "B.Cu" and marker:
        entries.append({"type": "assertion_failure", "description": "Assertion failure (rule '" + marker[0] + "')", "items": [item]})
    for rule, netclass in probes:
        if members.get(netclass) == "*" or net in members.get(netclass, []):
            entries.append({"type": "assertion_failure", "description": "Assertion failure (rule '" + rule + "')", "items": [item]})
entries += [{"type": "assertion_failure", "description": "Assertion failure (rule 'flood')", "items": []}] * int(os.environ.get("FAKE_FLOOD", "0"))
if len(entries) > 199:
    entries = random.sample(entries, 199)
with open(os.environ["FAKE_LOG"], "a") as log:
    log.write(json.dumps({"tracks": len(tracks), "back": sum(layer == "B.Cu" for layer, _ in tracks)}) + "\n")
json.dump({"violations": entries}, open(out, "w"))
"""


class AClassIsReadWholeOnABoardOfAnySize(unittest.TestCase):
    """Which nets are in a class is read in batches small enough that no run reaches KiCad's report limit.

    KiCad reports at most REPORT_LIMIT failures of one kind and drops the rest
    at random, so a class read in one run on a large board comes back short or
    empty from run to run. These drive the class read against a stand-in that
    drops failures past the limit exactly as KiCad does.
    """

    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.root = scratch.name
        self.fake = fake_tool(os.path.join(self.root, "kicad-cli"), FAKE_CLASS_READ, sys.executable)
        self.project = write(self.root, "p.kicad_pro", "{}")
        self.log = os.path.join(self.root, "runs.log")

    def read(self, names, classes, members, flood=0):
        open(self.log, "w").close()
        with mock.patch.dict(os.environ, {"FAKE_MEMBERS": json.dumps(members), "FAKE_FLOOD": str(flood),
                                          "FAKE_LOG": self.log}):
            found, why = board_check.class_members(self.fake, self.root, os.path.join(self.root, self.project),
                                                   classes, set(names), "0123abcd", "20260206")
        with open(self.log, encoding="utf-8") as handle:
            runs = [json.loads(line) for line in handle]
        return found, why, runs

    def test_every_net_in_every_class_is_read_whole_on_every_run(self):
        # SOL-HW-BOARD-CLASS-READ-ANY-SIZE.C1: A net class's membership is read completely and identically on every run, on a board of any size
        names = [f"/N{index}" for index in range(500)]
        for classes in (["Mains"], ["Mains", "Default", "Power"]):
            for _ in range(3):
                with self.subTest(classes=classes):
                    found, why, runs = self.read(names, classes, {name: "*" for name in classes})
                    self.assertEqual(why, "")
                    self.assertEqual(found, {name: set(names) for name in classes})
                    self.assertEqual(sum(run["tracks"] for run in runs), len(names), "a net was read twice or not at all")
                    for run in runs:
                        self.assertEqual(run["back"], 1, "the marker is to fire on one track of each board")
                        self.assertLess(1 + run["tracks"] * len(classes), board_check.REPORT_LIMIT)

    def test_each_class_holds_only_its_own_nets_merged_across_batches(self):
        # SOL-HW-BOARD-CLASS-READ-ANY-SIZE.C1: A net class's membership is read completely and identically on every run, on a board of any size
        names = [f"/N{index:03d}" for index in range(450)]
        mains = {names[0], names[196], names[197], names[449]}
        found, why, runs = self.read(names, ["Mains", "Power"], {"Mains": sorted(mains), "Power": []})
        self.assertEqual(why, "")
        self.assertGreater(len(runs), 2)
        self.assertEqual(found, {"Mains": mains, "Power": set()})

    def test_no_nets_need_no_run_and_hold_no_class(self):
        # SOL-HW-BOARD-CLASS-READ-ANY-SIZE.C1: A net class's membership is read completely and identically on every run, on a board of any size
        found, why, runs = self.read([], ["Mains"], {"Mains": "*"})
        self.assertEqual((found, why, runs), ({"Mains": set()}, "", []))

    def test_a_run_whose_reports_reach_the_limit_is_refused_naming_the_class_and_the_limit(self):
        # SOL-HW-BOARD-CLASS-READ-ANY-SIZE.C1: A net class's membership is read completely and identically on every run, on a board of any size
        found, why, _ = self.read([f"/N{index}" for index in range(40)], ["Mains"], {"Mains": "*"},
                                  flood=board_check.REPORT_LIMIT)
        self.assertIsNone(found)
        self.assertIn("which nets are in Mains reached its limit of 199 failures of one kind", why)
        self.assertIn("is not read as complete", why)

    def test_batches_cover_every_name_once_and_stay_below_the_limit(self):
        # SOL-HW-BOARD-CLASS-READ-ANY-SIZE.C1: A net class's membership is read completely and identically on every run, on a board of any size
        names = {f"/N{index}" for index in range(1000)}
        for count in (1, 2, 5, 40):
            classes = [f"C{index}" for index in range(count)]
            batches = board_check.class_batches(names, classes)
            self.assertEqual(sorted(name for batch in batches for name in batch), sorted(names))
            self.assertTrue(all(1 + len(batch) * count < board_check.REPORT_LIMIT for batch in batches), count)
            self.assertEqual(len(batches[0]), (board_check.REPORT_LIMIT - 2) // count, "the batches are smaller than they need be")
        self.assertEqual(board_check.class_batches(set(), ["Mains"]), [])

    def test_a_report_at_the_limit_is_refused_and_one_below_it_is_read(self):
        # SOL-HW-BOARD-CLASS-READ-ANY-SIZE.C1: A net class's membership is read completely and identically on every run, on a board of any size
        def report(count):
            entries = [{"type": "assertion_failure", "description": f"(rule '{board_check.marker_rule('n')}')", "items": []}]
            entries += [{"type": "assertion_failure", "description": f"(rule '{board_check.probe_rule('n', 'Mains')}')",
                         "items": [{"description": f"Track [/N{index}] on F.Cu"}]} for index in range(count - 1)]
            entries.append({"type": "track_dangling", "description": "not an assertion", "items": []})
            return {"violations": entries}
        names = {f"/N{index}" for index in range(board_check.REPORT_LIMIT)}
        found, why = board_check.batch_members(report(board_check.REPORT_LIMIT - 1), ["Mains"], names, "n")
        self.assertEqual(found, {"Mains": {f"/N{index}" for index in range(board_check.REPORT_LIMIT - 2)}}, why)
        found, why = board_check.batch_members(report(board_check.REPORT_LIMIT), ["Mains"], names, "n")
        self.assertIsNone(found)
        self.assertIn("Mains", why)
        self.assertIn(str(board_check.REPORT_LIMIT), why)
        found, why = board_check.batch_members({"violations": []}, ["Mains"], names, "n")
        self.assertEqual((found, why), (None, board_check.PROBES_NOT_LOADED))

    def test_merging_unites_each_classs_nets_across_batches(self):
        # SOL-HW-BOARD-CLASS-READ-ANY-SIZE.C1: A net class's membership is read completely and identically on every run, on a board of any size
        self.assertEqual(board_check.merged([{"Mains": {"/A"}, "Power": set()}, {"Mains": {"/B"}, "Power": {"/P"}},
                                             {"Mains": set(), "Power": set()}], ["Mains", "Power"]),
                         {"Mains": {"/A", "/B"}, "Power": {"/P"}})
        self.assertEqual(board_check.merged([], ["Mains"]), {"Mains": set()})


class TheChecksMarkerFiresOnOneNet(unittest.TestCase):
    """The marker showing KiCad loaded the rules fires on the layout's net with the fewest items, not on every item.

    A marker on every item of a large board would itself fill KiCad's report
    and crowd the design's own assertion failures out of it.
    """

    LAYOUT = ('(kicad_pcb (footprint "x" (at 10 20) (property "Reference" "R1")'
              ' (pad "1" smd rect (at 0 0) (net "/BUSY")) (pad "2" smd rect (at 1 0) (net "/QUIET")) (pad "3" smd rect (at 2 0)))'
              ' (segment (start 0 0) (end 1 0) (net "/BUSY")) (arc (start 0 1) (mid 1 2) (end 2 1) (net "/BUSY"))'
              ' (via (at 5 5) (net "/QUIET")) (segment (start 3 3) (end 4 3) (net "it\'s"))'
              ' (zone (net "/BUSY") (polygon (pts (xy 1 1) (xy 2 1) (arc (start 2 1) (mid 3 2) (end 2 3))))))')

    def test_the_net_with_fewest_items_whose_name_a_condition_can_hold_is_chosen(self):
        # SOL-HW-BOARD-CLASS-READ-ANY-SIZE.C1: A net class's membership is read completely and identically on every run, on a board of any size
        items = board_check.net_items(sexpr.parse_one(self.LAYOUT))
        self.assertEqual({net: len(found) for net, found in items.items()}, {"/BUSY": 4, "/QUIET": 2, "it's": 1})
        self.assertEqual(items["/QUIET"], ["pad 2 [/QUIET] of R1 (footprint at (10, 20) mm)", "via [/QUIET] at (5, 5) mm"])
        self.assertEqual(board_check.marker_net(items), "/QUIET")
        self.assertIsNone(board_check.marker_net(board_check.net_items(sexpr.parse_one('(kicad_pcb (segment (net "")))'))))
        self.assertIsNone(board_check.marker_net({"it's": ["track"]}))

    def test_the_marker_is_written_for_that_net_or_every_item_when_there_is_none(self):
        # SOL-HW-BOARD-CLASS-READ-ANY-SIZE.C1: A net class's membership is read completely and identically on every run, on a board of any size
        def condition(text):
            return [str(sexpr.child(form, "condition")[1]) for form in sexpr.parse(text) if sexpr.head(form) == "rule"][0]
        self.assertEqual(condition(board_check.appended_rules(None, "n", "/QUIET")), "A.NetName == '/QUIET'")
        self.assertEqual(condition(board_check.appended_rules(None, "n")), "A.Type != ''")


class AReportCutShortFailsTheDesign(unittest.TestCase):
    """A design whose assertion failures reach KiCad's report limit fails, since the report may be missing more."""

    def check(self, design_failures: int, marker: bool = True):
        with tempfile.TemporaryDirectory() as root:
            fake = os.path.join(root, "kicad-cli")
            with open(fake, "w", encoding="utf-8") as handle:
                handle.write(f"""#!{sys.executable}
import glob, json, re, sys
args = sys.argv[1:]
out = args[args.index("-o") + 1]
if args[:2] == ["sch", "erc"]:
    report = {{"sheets": []}}
elif args[:3] == ["sch", "export", "netlist"]:
    open(out, "w").write("(export (nets))"); sys.exit(0)
else:
    rules = open(glob.glob("*.kicad_dru")[0]).read()
    found = re.findall(r'rule "(pre-order check [0-9a-f]+: rules loaded)"', rules)
    entries = [{{"type": "assertion_failure", "description": "Assertion failure (rule 'every track')", "items": []}}] * {design_failures}
    if {marker} and found:
        entries.append({{"type": "assertion_failure", "description": "Assertion failure (rule '" + found[-1] + "')", "items": []}})
    report = {{"violations": entries}}
json.dump(report, open(out, "w"))
""")
            os.chmod(fake, 0o755)
            for path, text in (("a/a.kicad_pro", none_project()), ("a/a.kicad_sch", schematic()),
                               ("a/a.kicad_pcb", "(kicad_pcb)"),
                               ("a/a.kicad_dru", '(version 1)\n(rule "every track"\n\t(condition "A.Type == \'Track\'")\n'
                                                 '\t(constraint assertion "false"))\n' + WORKMANSHIP)):
                write(root, path, text)
            repository = board_check.Repository(root, ["a/a.kicad_pro", "a/a.kicad_sch", "a/a.kicad_pcb", "a/a.kicad_dru"])
            found = board_check.check_design(board_check.Design("a/a.kicad_pro"), repository, fake,
                                             board_check.require_yaml(), TODAY, [])
            # This design holds no pin allocation record; the record's own rules are tested apart.
            return [v for v in found if v.rule != "pin_allocation"]

    def cut(self, found):
        return [v for v in found if v.rule == "custom_rules" and "KiCad's report was cut short" in v.message]

    def test_a_report_reaching_the_limit_fails_saying_it_was_cut_short(self):
        # SOL-HW-BOARD-CLASS-READ-ANY-SIZE.C1: A net class's membership is read completely and identically on every run, on a board of any size
        found = self.check(board_check.REPORT_LIMIT - 1)
        self.assertEqual(len(self.cut(found)), 1, found)
        self.assertEqual(self.cut(found)[0].location, "a/a.kicad_dru")
        self.assertIn(f"at most {board_check.REPORT_LIMIT} assertion failures", self.cut(found)[0].message)

    def test_a_report_below_the_limit_is_not_said_to_be_cut_short(self):
        # SOL-HW-BOARD-CLASS-READ-ANY-SIZE.C1: A net class's membership is read completely and identically on every run, on a board of any size
        found = self.check(board_check.REPORT_LIMIT - 2)
        self.assertEqual(self.cut(found), [])
        self.assertEqual({v.rule for v in found if not v.rule.startswith("parts_")}, {"assertion_failure"})

    def test_a_marker_crowded_out_of_a_full_report_is_not_taken_for_unloaded_rules(self):
        # SOL-HW-BOARD-CLASS-READ-ANY-SIZE.C1: A net class's membership is read completely and identically on every run, on a board of any size
        found = self.check(board_check.REPORT_LIMIT, marker=False)
        self.assertEqual(len(self.cut(found)), 1, found)
        self.assertFalse([v for v in found if "did not load" in v.message], found)
        found = self.check(3, marker=False)
        self.assertTrue([v for v in found if v.rule == "custom_rules" and "did not load" in v.message], found)


# --- Workmanship ---------------------------------------------------------------------


def seg(net: str, a, b, width: float = 0.25, layer: str = "F.Cu") -> str:
    return (f'(segment (start {a[0]} {a[1]}) (end {b[0]} {b[1]}) (width {width}) (layer "{layer}") (net "{net}") '
            '(uuid "00000000-0000-4000-8000-000000000000"))')


def arc(net: str, a, mid, b, width: float = 0.25, layer: str = "F.Cu") -> str:
    return (f'(arc (start {a[0]} {a[1]}) (mid {mid[0]} {mid[1]}) (end {b[0]} {b[1]}) (width {width}) (layer "{layer}") '
            f'(net "{net}") (uuid "00000000-0000-4000-8000-000000000000"))')


def via(net: str, at, size: float = 0.8) -> str:
    return f'(via (at {at[0]} {at[1]}) (size {size}) (drill 0.4) (layers "F.Cu" "B.Cu") (net "{net}"))'


def zone(net: str, corners, layer: str = "F.Cu") -> str:
    points = " ".join(f"(xy {x} {y})" for x, y in corners)
    return f'(zone (net "{net}") (layer "{layer}") (polygon (pts {points})))'


def part(reference: str, at: str, *pads) -> str:
    """A footprint at `at` holding pads given as (number, net, x, y, shape, width, height[, angle])."""
    body = ""
    for number, net, x, y, shape, width, height, *angle in pads:
        body += (f'(pad "{number}" smd {shape} (at {x} {y} {angle[0] if angle else ""}) (size {width} {height}) '
                 f'(layers "F.Cu" "F.Mask") (net "{net}"))')
    return f'(footprint "lib:part" (layer "F.Cu") (at {at}) (property "Reference" "{reference}" (at 0 0 0)) {body})'


def board(*items: str, outline: str = '(gr_rect (start 0 0) (end 100 60) (layer "Edge.Cuts"))') -> board_check.Layout:
    return board_check.Layout(sexpr.parse_one("(kicad_pcb (version 20260206) " + outline + " " + " ".join(items) + ")"))


#: Two round pads 10 mm apart on /A, R1's at (10, 10) and R2's at (20, 10).
TWO_PADS = (part("R1", "10 10", ("1", "/A", 0, 0, "circle", 1, 1)), part("R2", "20 10", ("1", "/A", 0, 0, "circle", 1, 1)))
DESIGN = board_check.Design("a/a.kicad_pro")


class TheWorkmanshipFiguresAreTheDesignsOwn(unittest.TestCase):
    # SOL-BOARD-LAYOUT-WORKMANSHIP-ITEMS.C2: The pre-order check measures every rule-kind workmanship item and fails a board that breaks one
    """Each measured rule's figure is a project text variable, and one missing or
    malformed fails the design, naming it, rather than being read as some
    figure of the check's own.
    """

    def test_every_figure_given_is_read(self):
        figures, found = board_check.workmanship_figures(DESIGN, FIGURES)
        self.assertEqual(found, [])
        self.assertEqual(figures, {"WORK_DETOUR_RATIO": 1.5, "WORK_NECK_MM": 1.0,
                                   "WORK_ANGLE_TOLERANCE_DEG": 0.1, "WORK_PAD_ENTRY_RATIO": 2.0, "WORK_PAD_ANGLE_DEG": 90.0,
                                   "BARRIER_COPPER_MM2": 0.0, "PASTE_OVER_VIA_MM2": 0.0})

    def test_each_missing_figure_fails_naming_its_item_and_variable(self):
        figures, found = board_check.workmanship_figures(DESIGN, {})
        self.assertEqual(figures, {})
        self.assertEqual([(v.rule, v.location) for v in found],
                         [("workmanship_figure", f"a/a.kicad_pro text_variables.{name}") for _, _, name, _, _, _ in board_check.MEASURED])
        self.assertIn("WORK-2 (route length) has no figure", found[0].message)

    def test_a_figure_written_any_way_but_a_plain_number_within_its_range_fails(self):
        for name, value in (("WORK_NECK_MM", "1mm"), ("WORK_NECK_MM", "-1"), ("WORK_NECK_MM", ""), ("WORK_DETOUR_RATIO", "0.9"),
                            ("WORK_DETOUR_RATIO", "1e1"), ("WORK_ANGLE_TOLERANCE_DEG", "22.5"), ("WORK_PAD_ENTRY_RATIO", "two"),
                            ("BARRIER_COPPER_MM2", "0.5mm2"), ("BARRIER_COPPER_MM2", "-0.1"), ("BARRIER_COPPER_MM2", ""),
                            ("PASTE_OVER_VIA_MM2", "none"), ("PASTE_OVER_VIA_MM2", "-1"), ("PASTE_OVER_VIA_MM2", "1e-3")):
            with self.subTest(name=name, value=value):
                figures, found = board_check.workmanship_figures(DESIGN, {**FIGURES, name: value})
                self.assertNotIn(name, figures)
                self.assertEqual(len(found), 1, found)
                self.assertEqual(found[0].rule, "workmanship_figure")
                self.assertIn(f"{name} is '{value}'", found[0].message)

    def test_the_figures_at_the_ends_of_their_ranges_are_read(self):
        figures, found = board_check.workmanship_figures(DESIGN, {**FIGURES, "WORK_DETOUR_RATIO": "1", "WORK_ANGLE_TOLERANCE_DEG": "22.4"})
        self.assertEqual(found, [])
        self.assertEqual((figures["WORK_DETOUR_RATIO"], figures["WORK_ANGLE_TOLERANCE_DEG"]), (1.0, 22.4))


class TheRulesFileHoldsTheWorkmanshipRules(unittest.TestCase):
    # SOL-BOARD-LAYOUT-WORKMANSHIP-ITEMS.C2: The pre-order check measures every rule-kind workmanship item and fails a board that breaks one
    """The corner and jog items are KiCad's to measure, so the check requires
    only that the rules file holds each, on every track; the stub and
    unconnected-via items need no rule, KiCad reporting each unaided.
    """

    def rules(self, text: str):
        return board_check.rule_forms(text)

    def found(self, text: str):
        return [(v.rule, v.message.split(":")[0]) for v in board_check.workmanship_rules(DESIGN, self.rules(text))]

    def test_both_rules_with_no_condition_or_the_every_track_condition_pass(self):
        self.assertEqual(self.found(WORKMANSHIP), [])
        every = WORKMANSHIP.replace('(rule "Jogs"', '(rule "Jogs"\n\t(condition "A.Type == \'Track\'")')
        self.assertEqual(self.found(every), [])

    def test_a_rules_file_or_a_design_without_them_fails_for_each(self):
        expected = [("workmanship_rule", "WORK-4 (corner) has no rule"), ("workmanship_rule", "WORK-5 (jog) has no rule")]
        self.assertEqual(self.found("(version 1)"), expected)
        self.assertEqual([(v.rule, v.message.split(":")[0]) for v in board_check.workmanship_rules(DESIGN, None)], expected)

    def test_a_rule_narrowed_to_some_tracks_or_a_layer_is_not_in_force(self):
        for narrowed in (WORKMANSHIP.replace('(rule "Corners"', '(rule "Corners"\n\t(condition "A.hasNetclass(\'Power\')")'),
                         WORKMANSHIP.replace('(rule "Corners"', '(rule "Corners"\n\t(layer "F.Cu")')):
            with self.subTest(rules=narrowed):
                found = board_check.workmanship_rules(DESIGN, self.rules(narrowed))
                self.assertEqual([v.rule for v in found], ["workmanship_rule"])
                self.assertIn("WORK-4 (corner) is not in force on every track", found[0].message)
                self.assertEqual(found[0].location, "a/a.kicad_dru rule 'Corners'")

    def test_a_minimum_written_in_another_form_is_not_taken_as_the_rule(self):
        for rule in (WORKMANSHIP.replace("(min 135)", "(min 135deg)"), WORKMANSHIP.replace("(min 0.5mm)", "(min 20mil)"),
                     WORKMANSHIP.replace("(min 135)", "(max 135)"), WORKMANSHIP.replace("(min 135)", "(min 135) (opt 150)")):
            with self.subTest(rules=rule):
                self.assertEqual([v.rule for v in board_check.workmanship_rules(DESIGN, self.rules(rule))], ["workmanship_rule"])

    def test_a_good_rule_beside_a_narrowed_one_is_enough(self):
        both = WORKMANSHIP + '(rule "Power corners"\n\t(condition "A.hasNetclass(\'Power\')")\n\t(constraint track_angle (min 150)))\n'
        self.assertEqual(self.found(both), [])

    def test_a_narrowed_rule_at_the_boards_own_figure_passes(self):
        same = WORKMANSHIP + '(rule "Power jogs"\n\t(condition "A.hasNetclass(\'Power\')")\n\t(constraint track_segment_length (min 0.5mm)))\n'
        self.assertEqual(self.found(same), [])

    def test_a_later_narrowed_rule_looser_than_the_boards_figure_fails_naming_it_its_line_and_both_figures(self):
        # A later rule wins wherever it matches, so square corners or short jogs on Power tracks would pass KiCad's check.
        for loose, item, location, figures in (
                ('(rule "Power corners"\n\t(condition "A.hasNetclass(\'Power\')")\n\t(constraint track_angle (min 90)))\n',
                 "WORK-4 (corner) is loosened", "a/a.kicad_dru rule 'Power corners' at line 5",
                 ("track_angle (min 90), looser than the board's figure of 135 degrees in rule 'Corners' at line 1",)),
                ('(rule "Power jogs"\n\t(condition "A.hasNetclass(\'Power\')")\n\t(constraint track_segment_length (min 0.1mm)))\n',
                 "WORK-5 (jog) is loosened", "a/a.kicad_dru rule 'Power jogs' at line 5",
                 ("track_segment_length (min 0.1mm), looser than the board's figure of 0.5mm in rule 'Jogs' at line 3",))):
            with self.subTest(rule=loose):
                found = board_check.workmanship_rules(DESIGN, self.rules(WORKMANSHIP + loose))
                self.assertEqual([(v.rule, v.message.split(":")[0], v.location) for v in found],
                                 [("workmanship_rule", item, location)])
                for words in figures:
                    self.assertIn(words, found[0].message)

    def test_a_looser_rule_before_the_one_in_force_fails(self):
        for before in ('(rule "Old corners"\n\t(constraint track_angle (min 90)))\n',
                       '(rule "Power corners"\n\t(condition "A.hasNetclass(\'Power\')")\n\t(constraint track_angle (min 120)))\n'):
            with self.subTest(rule=before):
                found = board_check.workmanship_rules(DESIGN, self.rules(before + WORKMANSHIP))
                self.assertEqual([(v.rule, v.message.split(":")[0]) for v in found],
                                 [("workmanship_rule", "WORK-4 (corner) is loosened")])
                self.assertTrue(found[0].location.endswith("at line 1"), found[0].location)
                self.assertIn("the board's figure of 135 degrees in rule 'Corners' at line", found[0].message)

    def test_a_later_wider_rule_makes_the_earlier_one_looser_than_the_boards_figure(self):
        later = WORKMANSHIP + '(rule "Wider corners"\n\t(constraint track_angle (min 150)))\n'
        found = board_check.workmanship_rules(DESIGN, self.rules(later))
        self.assertEqual([(v.message.split(":")[0], v.location) for v in found],
                         [("WORK-4 (corner) is loosened", "a/a.kicad_dru rule 'Corners' at line 1")])
        self.assertIn("figure of 150 degrees in rule 'Wider corners' at line 5", found[0].message)

    def test_a_narrowed_rule_whose_minimum_cannot_be_read_fails_beside_one_in_force(self):
        for odd in ("(min 20mil)", "(max 2mm)", "(min 0.1mm) (opt 2mm)"):
            loose = f'(rule "Power jogs"\n\t(condition "A.hasNetclass(\'Power\')")\n\t(constraint track_segment_length {odd}))\n'
            with self.subTest(rule=loose):
                found = board_check.workmanship_rules(DESIGN, self.rules(WORKMANSHIP + loose))
                self.assertEqual([(v.message.split(":")[0], v.location) for v in found],
                                 [("WORK-5 (jog) is loosened", "a/a.kicad_dru rule 'Power jogs' at line 5")])
                self.assertIn("cannot be shown to be no looser than the board's figure of 0.5mm", found[0].message)

    def test_the_corner_minimum_is_read_from_the_last_corner_rule_in_force(self):
        self.assertEqual(board_check.corner_minimum(self.rules(WORKMANSHIP)), 135.0)
        later = WORKMANSHIP + '(rule "Wider corners"\n\t(constraint track_angle (min 150)))\n'
        self.assertEqual(board_check.corner_minimum(self.rules(later)), 150.0, "KiCad applies the last rule that matches")
        narrowed = WORKMANSHIP + '(rule "Power corners"\n\t(condition "A.hasNetclass(\'Power\')")\n\t(constraint track_angle (min 90)))\n'
        self.assertEqual(board_check.corner_minimum(self.rules(narrowed)), 135.0, "a rule narrowed to some tracks is not the board's figure")
        for none in ("(version 1)", WORKMANSHIP.replace("(min 135)", "(min 135deg)")):
            with self.subTest(rules=none):
                self.assertIsNone(board_check.corner_minimum(self.rules(none)))
        self.assertIsNone(board_check.corner_minimum(None))


class ALoosenedRuleIsNamedAtItsLineInTheRulesFile(Tree):
    # SOL-BOARD-LAYOUT-WORKMANSHIP-ITEMS.C2: The pre-order check measures every rule-kind workmanship item and fails a board that breaks one
    """The rules the check reads from a design's file carry the line each
    starts on, comments and blank lines counted, so a loosened rule is named
    where a builder will find it.
    """

    def test_the_loosened_rule_read_from_the_file_is_named_at_its_line(self):
        self.write("a/a.kicad_dru", "(version 1)\n# Corners and jogs.\n\n" + WORKMANSHIP
                   + "# Power is held looser.\n(rule \"Power corners\"\n\t(condition \"A.hasNetclass('Power')\")\n"
                   "\t(constraint track_angle (min 90)))\n")
        rules, hidden = board_check.read_rules(self.root, DESIGN, self.everything())
        self.assertEqual(hidden, [])
        found = board_check.workmanship_rules(DESIGN, rules)
        self.assertEqual([(v.rule, v.location) for v in found],
                         [("workmanship_rule", "a/a.kicad_dru rule 'Power corners' at line 9")])
        self.assertIn("in rule 'Corners' at line 4", found[0].message)


class TracksMeetingAtAPadAreMeasured(unittest.TestCase):
    # SOL-BOARD-LAYOUT-WORKMANSHIP-ITEMS.C2: The pre-order check measures every rule-kind workmanship item and fails a board that breaks one
    """KiCad's corner rule does not compare tracks that meet at a pad, so the
    check measures them: two tracks meeting at a pad are one route turning
    there, held to the corner rule's own minimum, and only where three or more
    leave a pad on one layer is the route branching, held to the design's
    branch figure.
    """

    PAD = part("R1", "10 10", ("1", "/A", 0, 0, "circle", 1, 1))

    def corners(self, *tracks, corner=135, branch=90):
        return board_check.pad_corners(DESIGN, board(self.PAD, *tracks), corner, branch)

    def test_a_route_running_straight_or_at_45_degrees_through_a_pad_passes(self):
        self.assertEqual(self.corners(seg("/A", (5, 10), (10, 10)), seg("/A", (10, 10), (15, 10))), [])
        self.assertEqual(self.corners(seg("/A", (5, 10), (10, 10)), seg("/A", (10, 10), (13, 13))), [])

    def test_a_route_turning_square_through_a_pad_fails_against_the_corner_rule(self):
        found = self.corners(seg("/A", (5, 10), (10, 10)), seg("/A", (10, 10), (10, 15)))
        self.assertEqual([v.rule for v in found], ["workmanship_pad_corner"])
        self.assertIn("/A turns through pad 1 of R1 on F.Cu, and two tracks leave it 90.00 degrees apart, where the corner "
                      "rule's track_angle allows no less than 135 degrees", found[0].message)
        self.assertIn("pad 1 of R1 at (10, 10) mm on F.Cu", found[0].location)
        self.assertEqual(self.corners(seg("/A", (5, 10), (10, 10)), seg("/A", (10, 10), (10, 15)), corner=90), [],
                         "the figure is the corner rule's, whatever it is")

    def test_with_no_corner_rule_in_force_two_tracks_at_a_pad_are_left_to_the_failing_rule(self):
        self.assertEqual(self.corners(seg("/A", (5, 10), (10, 10)), seg("/A", (10, 10), (10, 15)), corner=None), [])

    def test_a_branch_leaving_a_pad_square_passes_and_one_at_45_degrees_fails_against_its_figure(self):
        tee = (seg("/A", (5, 10), (10, 10)), seg("/A", (10, 10), (15, 10)), seg("/A", (10, 10), (10, 15)))
        self.assertEqual(self.corners(*tee), [])
        wedge = (seg("/A", (5, 10), (10, 10)), seg("/A", (10, 10), (15, 10)), seg("/A", (10, 10), (13, 13)))
        found = self.corners(*wedge)
        self.assertEqual([v.rule for v in found], ["workmanship_pad_corner"])
        self.assertIn("/A branches at pad 1 of R1 on F.Cu, 3 of its tracks leaving it, and two tracks leave it 45.00 "
                      "degrees apart, where WORK_PAD_ANGLE_DEG allows no less than 90 degrees", found[0].message)
        self.assertEqual(self.corners(*wedge, branch=45), [])

    def test_tracks_on_other_layers_or_nets_or_lying_wholly_on_the_pad_are_not_compared(self):
        for other in (seg("/A", (10, 10), (13, 13), layer="B.Cu"), seg("/B", (10, 10), (13, 13)), seg("/A", (10, 10), (10.2, 10.2))):
            with self.subTest(other=other):
                self.assertEqual(self.corners(seg("/A", (10, 10), (15, 10)), seg("/A", (5, 10), (10, 10)), other), [])

    def test_an_arc_is_compared_by_the_way_it_leaves_the_pad(self):
        # A quarter circle leaving the pad's centre heading along +x, beside a track along +x: 0 degrees apart.
        leaving = arc("/A", (10, 10), (10 + math.sqrt(0.5) * 3, 13 - math.sqrt(0.5) * 3), (13, 13))
        found = self.corners(seg("/A", (10, 10), (15, 10)), leaving)
        self.assertEqual(len(found), 1)
        self.assertIn("0.00 degrees apart", found[0].message)

    def test_tracks_ending_short_of_the_pad_meet_it_by_their_end_caps(self):
        # Neither end lies on the 1 mm round pad: each stops 0.1 mm short of its edge, inside a 0.25 mm track's cap.
        found = self.corners(seg("/A", (5, 10), (9.4, 10)), seg("/A", (10, 10.6), (10, 15)))
        self.assertEqual([v.rule for v in found], ["workmanship_pad_corner"])
        self.assertIn("90.00 degrees apart", found[0].message)
        self.assertEqual(self.corners(seg("/A", (5, 10), (9.3, 10), 0.15), seg("/A", (10, 10.7), (10, 15), 0.15)), [],
                         "tracks whose caps fall short of the pad do not meet it")


class RouteLengthIsMeasuredAgainstThePadTree(unittest.TestCase):
    # SOL-BOARD-LAYOUT-WORKMANSHIP-ITEMS.C2: The pre-order check measures every rule-kind workmanship item and fails a board that breaks one
    """A net's track length, on every layer, against its figure times the
    shortest straight-line tree joining the centres of all its pads, which no
    zone enters.
    """

    def test_a_direct_route_passes(self):
        self.assertEqual(board_check.detours(DESIGN, board(*TWO_PADS, seg("/A", (10, 10), (20, 10))), 1.3), [])

    def test_a_route_looping_round_fails_with_its_length_against_the_tree(self):
        loop = [seg("/A", (10, 10), (10, 4)), seg("/A", (10, 4), (20, 4)), seg("/A", (20, 4), (20, 10))]
        found = board_check.detours(DESIGN, board(*TWO_PADS, *loop), 1.3)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].rule, "workmanship_detour")
        self.assertEqual(found[0].location, "net /A: 2 pads, from pad 1 of R1 at (10, 10) mm")
        self.assertIn("/A's tracks are 22.00 mm long, 2.20 times the 10.00 mm of the shortest straight-line tree", found[0].message)
        self.assertIn("where WORK_DETOUR_RATIO allows 1.3 times", found[0].message)
        self.assertEqual(board_check.detours(DESIGN, board(*TWO_PADS, *loop), 2.2), [])

    def test_every_layer_and_every_arc_counts(self):
        bottom = board(*TWO_PADS, seg("/A", (10, 10), (15, 10)), via("/A", (15, 10)), seg("/A", (15, 10), (20, 10), layer="B.Cu"),
                       arc("/A", (20, 10), (21, 11), (20, 12)), seg("/A", (20, 12), (20, 10.5)))
        found = board_check.detours(DESIGN, bottom, 1.3)
        self.assertEqual(len(found), 1, "half a circle of 1 mm radius and its return take the net past 1.3 times its tree")
        self.assertIn(f"{10 + math.pi + 1.5:.2f} mm long", found[0].message)

    def test_a_zone_never_exempts_a_nets_tracks(self):
        # A token zone of the net sat over R2's pad leaves the looping route measured as before.
        loop = [seg("/A", (10, 10), (10, 4)), seg("/A", (10, 4), (20, 4)), seg("/A", (20, 4), (20, 10))]
        token = zone("/A", [(19.8, 9.8), (20.2, 9.8), (20.2, 10.2), (19.8, 10.2)])
        found = board_check.detours(DESIGN, board(*TWO_PADS, *loop, token), 1.3)
        self.assertEqual([v.rule for v in found], ["workmanship_detour"])
        self.assertIn("2.20 times the 10.00 mm", found[0].message)

    def test_a_route_ending_in_a_zone_short_of_its_pad_is_measured_against_every_pad(self):
        # The loop stops 2.5 mm short of R2's pad, inside a pour of its net over the pad: the pour joins them, and the
        # route is still measured against the 10 mm joining both pads.
        loop = [seg("/A", (10, 10), (10, 4)), seg("/A", (10, 4), (20, 4)), seg("/A", (20, 4), (20, 7))]
        pour = zone("/A", [(19, 6), (21, 6), (21, 11), (19, 11)])
        found = board_check.detours(DESIGN, board(*TWO_PADS, *loop, pour), 1.3)
        self.assertEqual([(v.rule, v.location) for v in found], [("workmanship_detour", "net /A: 2 pads, from pad 1 of R1 at (10, 10) mm")])
        self.assertIn("/A's tracks are 19.00 mm long, 1.90 times the 10.00 mm", found[0].message)

    def test_a_pad_only_a_zone_joins_stays_in_the_tree_so_the_zone_only_gains_the_net_room(self):
        # R3, 20.6 mm from the nearer of the others, is joined only by the net's pour: it stays in the tree, which grows
        # to 30.62 mm, and the 22 mm loop passes against it.
        far = part("R3", "15 30", ("1", "/A", 0, 0, "circle", 1, 1))
        loop = [seg("/A", (10, 10), (10, 4)), seg("/A", (10, 4), (20, 4)), seg("/A", (20, 4), (20, 10))]
        self.assertEqual(board_check.detours(DESIGN, board(*TWO_PADS, far, *loop, zone("/A", [(0, 25), (30, 25), (30, 35)])), 1.3), [])
        found = board_check.detours(DESIGN, board(*TWO_PADS, far, *loop), 0.7)
        self.assertIn("22.00 mm long, 0.72 times the 30.62 mm", found[0].message)
        self.assertEqual(found[0].location, "net /A: 3 pads, from pad 1 of R1 at (10, 10) mm")

    def test_a_net_whose_pad_copper_cannot_be_sized_is_still_measured_from_its_pad_centres(self):
        loop = [seg("/A", (10, 10), (10, 4)), seg("/A", (10, 4), (20, 4)), seg("/A", (20, 4), (20, 10))]
        found = board_check.detours(DESIGN, board(TWO_PADS[0], APadTheCheckCannotSizeFailsByName.CUSTOM, *loop), 1.3)
        self.assertEqual([v.rule for v in found], ["workmanship_detour"])
        self.assertIn("2.20 times the 10.00 mm", found[0].message)

    def test_a_net_of_one_pad_is_not_measured(self):
        loop = [seg("/A", (10, 10), (10, 4)), seg("/A", (10, 4), (20, 4)), seg("/A", (20, 4), (20, 10))]
        self.assertEqual(board_check.detours(DESIGN, board(TWO_PADS[0], *loop), 1.3), [])

    def test_a_net_of_many_pads_is_measured_against_its_tree_not_a_chain(self):
        three = TWO_PADS + (part("R3", "15 20", ("1", "/A", 0, 0, "circle", 1, 1)),)
        # The tree joins R1 and R2 to R3, about 22.4 mm; a route through R1, R2 and back to R3 is 10 + 11.2 mm.
        through = [seg("/A", (10, 10), (20, 10)), seg("/A", (20, 10), (15, 20))]
        self.assertEqual(board_check.detours(DESIGN, board(*three, *through), 1.0), [])


class DirectionIsMeasuredAgainstTheBoardsEdges(unittest.TestCase):
    # SOL-BOARD-LAYOUT-WORKMANSHIP-ITEMS.C2: The pre-order check measures every rule-kind workmanship item and fails a board that breaks one

    def test_tracks_along_the_edges_and_at_45_degrees_pass(self):
        tracks = [seg("/A", (0, 0), (10, 0)), seg("/A", (10, 0), (10, 5)), seg("/A", (10, 5), (13, 8)), seg("/A", (13, 8), (10, 11))]
        self.assertEqual(board_check.directions(DESIGN, board(*tracks), 0.1), [])

    def test_a_track_a_few_degrees_off_fails_with_how_far_off_it_runs(self):
        found = board_check.directions(DESIGN, board(seg("/A", (0, 0), (10, 0.5))), 0.1)
        self.assertEqual([v.rule for v in found], ["workmanship_direction"])
        self.assertIn(f"{math.degrees(math.atan2(0.5, 10)):.2f} degrees off", found[0].message)
        self.assertEqual(board_check.directions(DESIGN, board(seg("/A", (0, 0), (10, 0.5))), 3), [])

    def test_a_track_midway_between_two_directions_is_22_5_degrees_off(self):
        angle = math.radians(22.5)
        found = board_check.directions(DESIGN, board(seg("/A", (0, 0), (10 * math.cos(angle), 10 * math.sin(angle)))), 0.1)
        self.assertIn("22.50 degrees off", found[0].message)

    @staticmethod
    def bowed(start, heading: float, length: float, half_sweep: float) -> str:
        """An arc from `start` along a chord `length` long at `heading` degrees, turning `half_sweep` degrees each side of it."""
        chord, turn = math.radians(heading), math.radians(half_sweep)
        end = (start[0] + length * math.cos(chord), start[1] + length * math.sin(chord))
        rise = length / 2 * math.tan(turn / 2)
        mid = ((start[0] + end[0]) / 2 - rise * math.sin(chord), (start[1] + end[1]) / 2 + rise * math.cos(chord))
        return arc("/A", start, mid, end)

    def test_a_fillet_between_tracks_along_the_edges_and_at_45_degrees_passes(self):
        # A 2 mm fillet centred at (10, 12) leaves the track along x and meets the one at 45 degrees along it.
        fillet = arc("/A", (10, 10), (10 + 2 * math.cos(math.radians(-67.5)), 12 + 2 * math.sin(math.radians(-67.5))),
                     (10 + math.sqrt(2), 12 - math.sqrt(2)))
        tracks = [seg("/A", (0, 10), (10, 10)), fillet, seg("/A", (10 + math.sqrt(2), 12 - math.sqrt(2)), (15, 12 - math.sqrt(2) + 5 - math.sqrt(2)))]
        self.assertEqual(board_check.directions(DESIGN, board(*tracks), 0.1), [])
        quarter = arc("/A", (0, 0), (math.sqrt(0.5) * 2, 2 - math.sqrt(0.5) * 2), (2, 2))
        self.assertEqual(board_check.directions(DESIGN, board(quarter), 0.1), [], "a quarter circle turning square")

    def test_flat_arcs_drawn_at_an_odd_angle_fail_by_the_way_they_run_at_their_ends(self):
        # Two flat arcs meeting at 160 degrees, each bowed 2 degrees either side of a chord 10 degrees off the edges:
        # each runs 12 degrees off at one end and 8 at the other.
        first = self.bowed((0, 0), 10, 2.5, 2)
        second = self.bowed((2.5 * math.cos(math.radians(10)), 2.5 * math.sin(math.radians(10))), -10, 2.5, 2)
        found = board_check.directions(DESIGN, board(first, second), 0.1)
        self.assertEqual([v.rule for v in found], ["workmanship_direction"] * 2)
        for violation in found:
            self.assertIn("the arc runs 12.00 degrees off the nearest of those directions at its end at", violation.message)
            self.assertIn("arc [/A] on F.Cu from", violation.location)
        self.assertEqual(board_check.directions(DESIGN, board(first, second), 12.1), [])
        self.assertEqual(len(board_check.directions(DESIGN, board(first, second), 11.9)), 2, "the worse end decides")

    def test_the_directions_follow_a_board_whose_outline_is_turned(self):
        turned = '(gr_poly (pts (xy 0 0) (xy 86.6 50) (xy 56.6 101.96) (xy -30 51.96)) (layer "Edge.Cuts"))'
        along = seg("/A", (10, 10), (10 + 8.66, 10 + 5))
        self.assertEqual(board_check.directions(DESIGN, board(along, outline=turned), 0.1), [])
        self.assertEqual(len(board_check.directions(DESIGN, board(seg("/A", (0, 0), (10, 0)), outline=turned), 0.1)), 1)

    def test_a_board_whose_longest_edge_is_a_line_takes_its_direction(self):
        lines = ('(gr_line (start 0 0) (end 80 80) (layer "Edge.Cuts")) (gr_line (start 0 0) (end 1 -1) (layer "Edge.Cuts"))')
        self.assertAlmostEqual(board(outline=lines).edges, 45.0)


class TheEdgesAreReadAtTheirTrueShape(unittest.TestCase):
    # SOL-BOARD-LAYOUT-WORKMANSHIP-ITEMS.C2: The pre-order check measures every rule-kind workmanship item and fails a board that breaks one
    """The board's edge direction is that of the longest straight side of its
    outline as drawn: a rectangle's four real sides, a polygon's straight
    runs, its footprints' outline shapes where they are placed, and nothing
    from a shape that turns all along it.
    """

    #: A 20 mm square cut out of the board, turned 30 degrees.
    CUTOUT = ('(gr_poly (pts (xy 40 20) (xy 57.32 30) (xy 47.32 47.32) (xy 30 37.32)) (layer "Edge.Cuts"))')
    RECT = '(gr_rect (start 0 0) (end 100 60) (layer "Edge.Cuts"))'

    def test_a_rectangle_outline_holds_its_own_sides_against_a_turned_cutout(self):
        outline = self.RECT + " " + self.CUTOUT
        self.assertAlmostEqual(board(outline=outline).edges, 0.0)
        self.assertEqual(board_check.directions(DESIGN, board(seg("/A", (5, 5), (25, 5)), outline=outline), 0.1), [])
        found = board_check.directions(DESIGN, board(seg("/A", (5, 5), (5 + 17.32, 15)), outline=outline), 0.1)
        self.assertEqual([v.rule for v in found], ["workmanship_direction"])
        self.assertIn("15.00 degrees off", found[0].message)

    def test_a_rounded_rectangle_counts_only_its_straight_sides(self):
        line = '(gr_line (start 0 0) (end 6.06 3.5) (layer "Edge.Cuts"))'
        self.assertAlmostEqual(board(outline='(gr_rect (start 0 0) (end 10 10) (layer "Edge.Cuts")) ' + line).edges, 0.0)
        rounded = '(gr_rect (start 0 0) (end 10 10) (radius 2) (layer "Edge.Cuts")) '
        self.assertAlmostEqual(board(outline=rounded + line).edges, 30.0, places=1,
                               msg="6 mm of each side is straight, shorter than the 7 mm line")
        self.assertAlmostEqual(board(outline='(gr_rect (start 0 0) (end 10 10) (radius 5) (layer "Edge.Cuts")) ' + line).edges,
                               30.0, places=1, msg="a rectangle rounded into a circle has no straight side")

    def test_a_polygons_arc_pieces_are_not_sides_and_its_straight_runs_are(self):
        # Read as corners alone, the arc's ends would make a 41 mm diagonal from (10, 0) to (0, 40).
        outline = '(gr_poly (pts (xy 0 0) (xy 10 0) (arc (start 10 0) (mid 40 20) (end 10 40)) (xy 0 40)) (layer "Edge.Cuts"))'
        self.assertAlmostEqual(board(outline=outline).edges, 0.0)

    def test_an_arc_or_a_circle_on_the_edge_gives_no_direction(self):
        for curved in ('(gr_circle (center 50 50) (end 100 50) (layer "Edge.Cuts"))',
                       '(gr_arc (start 0 50) (mid 50 0) (end 100 50) (layer "Edge.Cuts"))'):
            with self.subTest(shape=curved):
                self.assertAlmostEqual(board(outline=curved + ' (gr_line (start 0 0) (end 3 3) (layer "Edge.Cuts"))').edges, 45.0)
        self.assertEqual(board(outline='(gr_circle (center 50 50) (end 100 50) (layer "Edge.Cuts"))').edges, 0.0,
                         "an outline with no straight side is held to the board's own axes")

    def test_a_footprints_outline_shapes_count_where_the_footprint_places_them(self):
        slot = ('(footprint "lib:slot" (layer "F.Cu") (at 50 30 30) (property "Reference" "H1" (at 0 0 0)) '
                '(fp_line (start -40 0) (end 40 0) (layer "Edge.Cuts")))')
        self.assertAlmostEqual(board(slot, outline='(gr_rect (start 0 0) (end 10 10) (layer "Edge.Cuts"))').edges, 60.0)
        silk = slot.replace("Edge.Cuts", "F.SilkS")
        self.assertAlmostEqual(board(silk, outline='(gr_rect (start 0 0) (end 10 10) (layer "Edge.Cuts"))').edges, 0.0)


class AnArcIsReadAtItsTrueShape(unittest.TestCase):
    # SOL-BOARD-LAYOUT-WORKMANSHIP-ITEMS.C2: The pre-order check measures every rule-kind workmanship item and fails a board that breaks one
    """The straight pieces an arc is measured along stand no further off it
    than ARC_SAG, whatever its radius, so a wide arc's copper is found where it
    is.
    """

    def test_no_piece_of_a_wide_arc_stands_further_off_it_than_the_sag(self):
        wide = board(arc("/A", (-50, 0), (0, -50), (50, 0))).copper[0]
        line = wide.points()
        for a, b in zip(line, line[1:]):
            middle = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
            self.assertLessEqual(50 - math.hypot(*middle), board_check.ARC_SAG + 1e-9)

    def test_a_pad_the_arcs_copper_reaches_beyond_its_chords_is_joined(self):
        # A round 1 mm pad 50.6 mm out from the arc's centre, midway between two of the 32 pieces a half circle was once
        # read as: the 0.25 mm track's copper reaches it by 0.025 mm, where those pieces stood 0.06 mm inside the arc.
        wide = board(arc("/A", (-50, 0), (0, -50), (50, 0))).copper[0]
        angle = math.radians(-90 + 180 / 64)
        at = f"{50.6 * math.cos(angle)} {50.6 * math.sin(angle)}"
        pad = board_check.Layout(sexpr.parse_one("(kicad_pcb " + part("R1", at, ("1", "/A", 0, 0, "circle", 1, 1)) + ")")).pads[0]
        self.assertTrue(board_geometry.joins(pad, wide.points(), wide.width))
        far = board_check.Layout(sexpr.parse_one("(kicad_pcb " + part("R1", f"{50.65 * math.cos(angle)} {50.65 * math.sin(angle)}",
                                                                        ("1", "/A", 0, 0, "circle", 1, 1)) + ")")).pads[0]
        self.assertFalse(board_geometry.joins(far, wide.points(), wide.width), "0.025 mm further out it is not reached")


class LongPadsAreEnteredAlongTheirAxis(unittest.TestCase):
    # SOL-BOARD-LAYOUT-WORKMANSHIP-ITEMS.C2: The pre-order check measures every rule-kind workmanship item and fails a board that breaks one

    LEAD = part("U1", "10 10", ("1", "/A", 0, 0, "roundrect", 1, 0.3))

    def test_a_track_running_in_along_the_long_axis_passes(self):
        self.assertEqual(board_check.pad_entries(DESIGN, board(self.LEAD, seg("/A", (10, 10), (15, 10))), 2, 0.1), [])

    def test_a_track_entering_from_the_side_or_at_a_slant_fails(self):
        for track, off in ((seg("/A", (10, 10), (10, 15)), 90.0), (seg("/A", (10, 10), (13, 13)), 45.0)):
            with self.subTest(track=track):
                found = board_check.pad_entries(DESIGN, board(self.LEAD, track), 2, 0.1)
                self.assertEqual([v.rule for v in found], ["workmanship_pad_entry"])
                self.assertIn(f"enters it {off:.2f} degrees off its long axis", found[0].message)
                self.assertIn("entering pad 1 of U1 at (10, 10) mm", found[0].location)

    def test_a_turned_pad_is_entered_along_its_turned_axis(self):
        turned = part("U1", "10 10 90", ("1", "/A", 0, 0, "roundrect", 1, 0.3, 90))
        self.assertEqual(board_check.pad_entries(DESIGN, board(turned, seg("/A", (10, 10), (10, 15))), 2, 0.1), [])
        self.assertEqual(len(board_check.pad_entries(DESIGN, board(turned, seg("/A", (10, 10), (15, 10))), 2, 0.1)), 1)

    def test_a_pad_exactly_the_ratio_long_may_be_entered_from_its_side_and_one_longer_may_not(self):
        exact = part("R1", "10 10", ("1", "/A", 0, 0, "roundrect", 1.0, 0.5))
        self.assertEqual(board_check.pad_entries(DESIGN, board(exact, seg("/A", (10, 10), (10, 15))), 2, 0.1), [])
        longer = part("R1", "10 10", ("1", "/A", 0, 0, "roundrect", 1.02, 0.5))
        found = board_check.pad_entries(DESIGN, board(longer, seg("/A", (10, 10), (10, 15))), 2, 0.1)
        self.assertEqual([v.rule for v in found], ["workmanship_pad_entry"])
        self.assertIn("more than the 2 times as long as wide", found[0].message)

    def test_a_pad_short_of_the_ratio_may_be_entered_from_any_side(self):
        chip = part("R1", "10 10", ("1", "/A", 0, 0, "roundrect", 0.8, 1.45))
        self.assertEqual(board_check.pad_entries(DESIGN, board(chip, seg("/A", (10, 10), (15, 10))), 2, 0.1), [])
        self.assertEqual(len(board_check.pad_entries(DESIGN, board(chip, seg("/A", (10, 10), (15, 10))), 1.5, 0.1)), 1)

    def test_a_track_running_across_a_long_pad_from_side_to_side_fails_and_one_along_it_passes(self):
        found = board_check.pad_entries(DESIGN, board(self.LEAD, seg("/A", (10, 8), (10, 12))), 2, 0.1)
        self.assertEqual([v.rule for v in found], ["workmanship_pad_entry"])
        self.assertIn("runs across it 90.00 degrees off its long axis", found[0].message)
        self.assertIn("running across pad 1 of U1 at (10, 10) mm", found[0].location)
        self.assertEqual(board_check.pad_entries(DESIGN, board(self.LEAD, seg("/A", (8, 10), (12, 10))), 2, 0.1), [])
        self.assertEqual(board_check.pad_entries(DESIGN, board(self.LEAD, seg("/A", (8, 12), (12, 12))), 2, 0.1), [],
                         "a track passing beside the pad does not cross it")

    def test_a_track_wholly_on_the_pad_or_of_another_net_is_not_judged(self):
        self.assertEqual(board_check.pad_entries(DESIGN, board(self.LEAD, seg("/A", (10, 10), (10, 10.1))), 2, 0.1), [])
        self.assertEqual(board_check.pad_entries(DESIGN, board(self.LEAD, seg("/B", (10, 10), (10, 15))), 2, 0.1), [])

    def test_a_track_ending_short_of_a_long_pads_side_enters_it_by_its_end_cap(self):
        # The pad's long side is at y = 10.15; the track stops 0.1 mm short of it, inside its 0.125 mm cap.
        found = board_check.pad_entries(DESIGN, board(self.LEAD, seg("/A", (10, 15), (10, 10.25))), 2, 0.1)
        self.assertEqual([v.rule for v in found], ["workmanship_pad_entry"])
        self.assertIn("enters it 90.00 degrees off its long axis", found[0].message)
        self.assertEqual(board_check.pad_entries(DESIGN, board(self.LEAD, seg("/A", (10, 15), (10, 10.25), 0.15)), 2, 0.1), [],
                         "a narrower track's cap falls short of the pad")

    def test_a_track_whose_copper_runs_over_a_long_pads_end_off_its_centre_line_runs_across_it(self):
        # The centre line at x = 10.55 passes 0.05 mm beyond the pad's rounded end; the 0.25 mm track's copper runs over it.
        found = board_check.pad_entries(DESIGN, board(self.LEAD, seg("/A", (10.55, 8), (10.55, 12))), 2, 0.1)
        self.assertEqual([v.rule for v in found], ["workmanship_pad_entry"])
        self.assertIn("runs across it 90.00 degrees off its long axis", found[0].message)

    def test_an_arc_is_judged_by_the_way_it_runs_where_it_enters(self):
        # A quarter circle centred at (10, 11) leaves the pad's centre running along x, along the long axis.
        along = arc("/A", (10, 10), (10 + math.sqrt(0.5), 11 - math.sqrt(0.5)), (11, 11))
        self.assertEqual(board_check.pad_entries(DESIGN, board(self.LEAD, along), 2, 0.1), [])
        across = arc("/A", (10, 10), (11 - math.sqrt(0.5), 10 + math.sqrt(0.5)), (11, 11))
        self.assertEqual(len(board_check.pad_entries(DESIGN, board(self.LEAD, across), 2, 0.1)), 1)


class NarrowingIsMeasuredAgainstTheClassWidth(unittest.TestCase):
    # SOL-BOARD-LAYOUT-WORKMANSHIP-ITEMS.C2: The pre-order check measures every rule-kind workmanship item and fails a board that breaks one
    """A track narrower than its net class's width passes only as a neck within
    the figure of a pad; a track widened past it never fails.
    """

    def found(self, *tracks, neck: float = 1.0):
        return board_check.narrowings(DESIGN, board(*TWO_PADS, *tracks), neck, {"/A": 0.4})

    def test_a_route_at_its_class_width_or_widened_passes(self):
        self.assertEqual(self.found(seg("/A", (10, 10), (20, 10), 0.4)), [])
        self.assertEqual(self.found(seg("/A", (10, 10), (11, 10), 0.4), seg("/A", (11, 10), (19, 10), 1.2),
                                    seg("/A", (19, 10), (20, 10), 0.4)), [])

    def test_a_neck_into_a_pad_within_the_figure_passes(self):
        self.assertEqual(self.found(seg("/A", (10, 10), (10.6, 10), 0.2), seg("/A", (10.6, 10), (11, 10), 0.3),
                                    seg("/A", (11, 10), (20, 10), 0.4)), [])

    def test_a_neck_longer_than_the_figure_fails(self):
        found = self.found(seg("/A", (10, 10), (12, 10), 0.2), seg("/A", (12, 10), (20, 10), 0.4))
        self.assertEqual([v.rule for v in found], ["workmanship_width"])
        # The run is 2 mm long, 0.5 mm of it on R1's pad: 1.5 mm runs off the pad.
        self.assertIn("0.2 mm wide, narrower than its net class's 0.4 mm, along 1.50 mm of route off its pads from the pad it enters",
                      found[0].message)
        self.assertEqual(self.found(seg("/A", (10, 10), (12, 10), 0.2), seg("/A", (12, 10), (20, 10), 0.4), neck=1.5), [])

    def test_a_narrow_track_between_two_pads_close_together_passes_counting_only_what_lies_off_them(self):
        close = (part("U1", "10 10", ("1", "/A", 0, 0, "roundrect", 0.3, 1.2)), part("U2", "10 11.8", ("1", "/A", 0, 0, "rect", 2, 2)))
        layout = board(*close, seg("/A", (10, 10), (10, 11.8), 0.25))
        self.assertEqual(board_check.narrowings(DESIGN, layout, 1, {"/A": 0.5}), [], "0.2 mm of the 1.8 mm track lies off the pads")
        self.assertEqual(len(board_check.narrowings(DESIGN, layout, 0.1, {"/A": 0.5})), 1)

    def test_a_route_narrowed_partway_along_fails_however_short_the_narrowing(self):
        found = self.found(seg("/A", (10, 10), (14, 10), 0.4), seg("/A", (14, 10), (14.5, 10), 0.2), seg("/A", (14.5, 10), (20, 10), 0.4))
        self.assertEqual([v.rule for v in found], ["workmanship_width"])
        self.assertIn("that reaches no pad", found[0].message)

    def test_a_net_with_no_class_width_is_not_judged(self):
        self.assertEqual(board_check.narrowings(DESIGN, board(*TWO_PADS, seg("/A", (10, 10), (20, 10), 0.1)), 1, {}), [])

    def test_each_class_width_is_read_and_a_class_with_none_takes_the_defaults(self):
        project = {"net_settings": {"classes": [{"name": "Default", "track_width": 0.25, "priority": 2147483647},
                                                {"name": "Power", "track_width": 0.8, "priority": 1},
                                                {"name": "Sense", "track_width": None, "priority": 2},
                                                {"name": "Odd", "track_width": "wide"}]}}
        widths, unreadable = board_check.class_widths(project)
        self.assertEqual(widths, {"Default": (2147483647.0, 0.25), "Power": (1.0, 0.8), "Sense": (2.0, 0.25)})
        self.assertEqual(unreadable, ["Odd"])
        self.assertEqual(board_check.class_widths({"net_settings": {"classes": [{"name": "Power", "track_width": 0.8}]}})[1],
                         ["Default"])

    def test_a_net_in_several_classes_takes_the_width_of_the_class_ranked_first(self):
        widths = {"Default": (math.inf, 0.25), "Power": (1.0, 0.8), "Sense": (2.0, 0.3)}
        members = {"Power": {"/BOTH"}, "Sense": {"/BOTH", "/S"}}
        self.assertEqual(board_check.net_widths({"/BOTH", "/S", "/OTHER"}, members, widths),
                         {"/BOTH": 0.8, "/S": 0.3, "/OTHER": 0.25})


class APadTheCheckCannotSizeFailsByName(unittest.TestCase):
    # SOL-BOARD-LAYOUT-WORKMANSHIP-ITEMS.C2: The pre-order check measures every rule-kind workmanship item and fails a board that breaks one
    """Whether a track meets a pad is judged from the pad's copper, so a pad
    whose copper the check cannot size fails the measures that need it,
    naming the pad, rather than being guessed.
    """

    CUSTOM = ('(footprint "lib:part" (layer "F.Cu") (at 20 10) (property "Reference" "U9" (at 0 0 0)) '
              '(pad "1" smd custom (at 0 0) (size 0.5 0.5) (layers "F.Cu") (net "/A") (options (clearance outline) (anchor rect)) '
              '(primitives (gr_poly (pts (xy 0 0) (xy 3 0) (xy 0 3)) (width 0) (fill yes)))))')

    def test_a_custom_pad_a_track_of_its_net_reaches_fails_naming_it(self):
        layout = board(TWO_PADS[0], self.CUSTOM, seg("/A", (10, 10), (20, 10)))
        found = board_check.measured(DESIGN, layout, FIGURES_READ, 135)
        self.assertEqual([(v.rule, v.location) for v in found],
                         [("workmanship_pad_copper", "net /A: pad 1 of U9 at (20, 10) mm")])
        self.assertIn("cannot be measured at pad 1 of U9: its shape is custom", found[0].message)

    def test_a_custom_pad_no_track_of_its_net_reaches_is_not_needed(self):
        self.assertEqual(board_check.measured(DESIGN, board(self.CUSTOM), FIGURES_READ, 135), [])
        self.assertEqual(board_check.measured(DESIGN, board(self.CUSTOM, seg("/A", (10, 10), (10, 4), layer="B.Cu")),
                                              FIGURES_READ, 135), [], "a track of its net on a layer the pad is not on")


# --- Barrier, paste and pour ---------------------------------------------------------

def tree_of(*items: str, layers: str = "", setup: str = "") -> list:
    """A layout holding `items`, with the copper layer table and `setup` where given."""
    return sexpr.parse_one(f"(kicad_pcb (version 20260206) {layers} {setup} " + " ".join(items) + ")")


def hole(net: str, at, drill: float = 0.3, size: float = 0.6, layers: str = '"F.Cu" "B.Cu"') -> str:
    return f'(via (at {at[0]} {at[1]}) (size {size}) (drill {drill}) (layers {layers}) (net "{net}"))'


def fill(net: str, layer: str, corners) -> tuple:
    return net, layer, [(float(x), float(y)) for x, y in corners]


def pasted(reference: str, at: str, layers: str = '"F.Cu" "F.Paste" "F.Mask"', shape: str = "rect", size: str = "1 1",
           angle: str = "", number: str = "1", net: str = "", pad_extra: str = "", part_extra: str = "") -> str:
    """A footprint `reference` at `at` holding one surface-mount pad at its origin."""
    return (f'(footprint "lib:p" (layer "F.Cu") (at {at}) (property "Reference" "{reference}" (at 0 0 0)) {part_extra} '
            f'(pad "{number}" smd {shape} (at 0 0 {angle}) (size {size}) (layers {layers}) (net "{net}") {pad_extra}))')


#: U1 at (10, 10) with a pad on Mains-class /MAINS and one on /LV, 6 mm apart: the strip between them runs from
#: (10.5, 9.5) to (15.5, 10.5) mm.
BRIDGE = part("U1", "10 10", ("1", "/MAINS", 0, 0, "rect", 1, 1), ("2", "/LV", 6, 0, "rect", 1, 1))


class TheFillsAreReadFromTheBoardKiCadRefilled(unittest.TestCase):
    # SOL-BOARD-REVIEW-PROOF-BASELINE-CLEAN.C3: Each rule the proof design's review adds fails on a fault seeded for it and passes the clean design
    """Every fill is read as KiCad writes it: a net, a layer and the corners of
    one outline, and a form it does not write fails by name.
    """

    ZONE = ('(zone (net "/G") (layer "F.Cu") (polygon (pts (xy 0 0) (xy 9 0) (xy 9 9))) '
            '(filled_polygon (layer "F.Cu") (pts (xy 0 0) (xy 5 0) (xy 5 5))) '
            '(filled_polygon (layer "B.Cu") (pts (xy 1 1) (xy 4 1) (xy 4 4) (xy 1 4))))')

    def test_each_fill_is_read_with_its_zones_net_and_its_own_layer(self):
        # SOL-BOARD-REVIEW-PROOF-BASELINE-CLEAN.C3: Each rule the proof design's review adds fails on a fault seeded for it and passes the clean design
        self.assertEqual(board_check.zone_fills(tree_of(self.ZONE)),
                         [("/G", "F.Cu", [(0.0, 0.0), (5.0, 0.0), (5.0, 5.0)]),
                          ("/G", "B.Cu", [(1.0, 1.0), (4.0, 1.0), (4.0, 4.0), (1.0, 4.0)])])

    def test_a_zone_with_no_net_carries_no_fill_and_a_zone_not_filled_has_none(self):
        # SOL-BOARD-REVIEW-PROOF-BASELINE-CLEAN.C3: Each rule the proof design's review adds fails on a fault seeded for it and passes the clean design
        self.assertEqual(board_check.zone_fills(tree_of('(zone (layer "F.Cu") (filled_polygon (layer "F.Cu") (pts (xy 0 0) (xy 5 0) (xy 5 5))))',
                                                        '(zone (net "/G") (layer "F.Cu") (polygon (pts (xy 0 0) (xy 9 0) (xy 9 9))))')), [])

    def test_a_net_numbered_in_the_older_form_is_read_by_name(self):
        # SOL-BOARD-REVIEW-PROOF-BASELINE-CLEAN.C3: Each rule the proof design's review adds fails on a fault seeded for it and passes the clean design
        text = '(net 2 "/G") (zone (net 2) (net_name "/G") (layer "F.Cu") (filled_polygon (layer "F.Cu") (pts (xy 0 0) (xy 5 0) (xy 5 5))))'
        self.assertEqual(board_check.zone_fills(tree_of(text))[0][:2], ("/G", "F.Cu"))

    def test_a_fill_in_a_form_kicad_does_not_write_fails_by_name(self):
        # SOL-BOARD-REVIEW-PROOF-BASELINE-CLEAN.C3: Each rule the proof design's review adds fails on a fault seeded for it and passes the clean design
        for what, text in (("no layer", '(zone (net "/G") (filled_polygon (pts (xy 0 0) (xy 5 0) (xy 5 5))))'),
                           ("no corners", '(zone (net "/G") (filled_polygon (layer "F.Cu")))'),
                           ("an arc", '(zone (net "/G") (filled_polygon (layer "F.Cu") (pts (xy 0 0) (arc (start 1 0) (mid 2 1) (end 3 0)) (xy 5 5))))'),
                           ("two corners", '(zone (net "/G") (filled_polygon (layer "F.Cu") (pts (xy 0 0) (xy 5 0))))'),
                           ("a corner without a position", '(zone (net "/G") (filled_polygon (layer "F.Cu") (pts (xy 0 0) (xy 5 0) (xy 5))))')):
            with self.subTest(fill=what):
                with self.assertRaises(board_geometry.Unreadable) as raised:
                    board_check.zone_fills(tree_of(text))
                self.assertIn("/G", str(raised.exception))

    def test_the_copper_layers_are_stacked_front_to_back_with_the_two_outer_ones_where_none_are_named(self):
        # SOL-BOARD-REVIEW-PROOF-BASELINE-CLEAN.C3: Each rule the proof design's review adds fails on a fault seeded for it and passes the clean design
        layers = '(layers (0 "F.Cu" signal) (4 "In1.Cu" signal) (6 "In10.Cu" signal) (8 "In2.Cu" signal) (2 "B.Cu" signal) (25 "Edge.Cuts" user))'
        self.assertEqual(board_check.copper_layers(tree_of(layers=layers)), ["F.Cu", "In1.Cu", "In2.Cu", "In10.Cu", "B.Cu"])
        self.assertEqual(board_check.copper_layers(tree_of()), ["F.Cu", "B.Cu"])


class NoCopperLiesUnderAPartThatBridgesTheBarrier(unittest.TestCase):
    # SOL-BOARD-REVIEW-PROOF-BASELINE-CLEAN.C3: Each rule the proof design's review adds fails on a fault seeded for it and passes the clean design
    """A part with a pad in the Mains net class and a pad on another net has no
    copper of any net, on any layer, in the strip between the two groups of
    pads: not a track, an arc, a via, another pad, nor a pour's fill.
    """

    MAINS = {"/MAINS"}

    def found(self, *items, fills=(), mains=None, layers="", allowed=0.0):
        return board_check.mains_barrier(DESIGN, tree_of(BRIDGE, *items, layers=layers), list(fills),
                                         self.MAINS if mains is None else mains, allowed)

    def test_a_part_with_nothing_between_its_pads_passes_wherever_the_rest_of_the_board_runs(self):
        # SOL-BOARD-REVIEW-PROOF-BASELINE-CLEAN.C3: Each rule the proof design's review adds fails on a fault seeded for it and passes the clean design
        self.assertEqual(self.found(seg("/X", (11, 12), (15, 12)), seg("/X", (11, 8), (15, 8), layer="B.Cu"), hole("/X", (13, 12))), [])
        self.assertEqual(self.found(), [])

    def test_a_track_between_the_pads_fails_naming_the_part_the_layer_the_net_the_strip_and_the_area(self):
        # SOL-BOARD-REVIEW-PROOF-BASELINE-CLEAN.C3: Each rule the proof design's review adds fails on a fault seeded for it and passes the clean design
        found = self.found(seg("/X", (11, 10), (15, 10)))
        self.assertEqual([v.rule for v in found], ["mains_barrier"])
        self.assertEqual(found[0].location, "U1 at (10, 10) mm: track of /X on F.Cu")
        for text in ("U1 joins Mains-class /MAINS (pad 1) to /LV (pad 2)", "a track of net /X on F.Cu lies under it",
                     "1.049 square mm inside the strip from (10.5, 9.5) to (15.5, 10.5) mm", "near (13, 10) mm",
                     "the part has 1.049 square mm of copper between its Mains-class pads and its other pads, over all layers, "
                     "where BARRIER_COPPER_MM2 allows 0"):
            self.assertIn(text, found[0].message)

    def test_copper_touching_the_strip_without_entering_it_passes(self):
        # SOL-BOARD-REVIEW-PROOF-BASELINE-CLEAN.C3: Each rule the proof design's review adds fails on a fault seeded for it and passes the clean design
        self.assertEqual(self.found(seg("/X", (11, 10.75), (15, 10.75), width=0.5)), [], "a track whose edge lies on the strip's")
        self.assertEqual(self.found(seg("/X", (10.25, 8), (10.25, 12), width=0.5)), [], "a track whose edge lies on its end")
        self.assertEqual(self.found(hole("/X", (10.1, 10), size=0.8)), [])
        self.assertEqual(self.found(fills=[fill("/X", "F.Cu", [(15.5, 5), (20, 5), (20, 15), (15.5, 15)])]), [])
        self.assertEqual(len(self.found(seg("/X", (11, 10.74), (15, 10.74), width=0.5))), 1, "0.01 mm further in, it is inside")

    def test_a_via_is_copper_on_every_layer_it_joins(self):
        # SOL-BOARD-REVIEW-PROOF-BASELINE-CLEAN.C3: Each rule the proof design's review adds fails on a fault seeded for it and passes the clean design
        found = self.found(hole("/X", (13, 10)))
        self.assertEqual([(v.rule, v.location) for v in found],
                         [("mains_barrier", "U1 at (10, 10) mm: via of /X on F.Cu"), ("mains_barrier", "U1 at (10, 10) mm: via of /X on B.Cu")])
        layers = '(layers (0 "F.Cu" signal) (4 "In1.Cu" signal) (6 "In2.Cu" signal) (2 "B.Cu" signal))'
        for joins, layer_names in (('"F.Cu" "In1.Cu"', ["F.Cu", "In1.Cu"]), ('"In1.Cu" "B.Cu"', ["In1.Cu", "In2.Cu", "B.Cu"]),
                                   ('"F.Cu" "B.Cu"', ["F.Cu", "In1.Cu", "In2.Cu", "B.Cu"])):
            with self.subTest(joins=joins):
                found = self.found(hole("/X", (13, 10), layers=joins), layers=layers)
                self.assertEqual([v.location.rsplit(" on ", 1)[1] for v in found], layer_names)

    def test_an_arc_is_copper_the_way_a_track_is(self):
        # SOL-BOARD-REVIEW-PROOF-BASELINE-CLEAN.C3: Each rule the proof design's review adds fails on a fault seeded for it and passes the clean design
        found = self.found(arc("/X", (11, 9.8), (13, 10.2), (15, 9.8)))
        self.assertEqual([(v.rule, v.location) for v in found], [("mains_barrier", "U1 at (10, 10) mm: arc of /X on F.Cu")])

    def test_copper_of_one_net_and_layer_and_kind_is_reported_once_with_its_area_summed(self):
        # SOL-BOARD-REVIEW-PROOF-BASELINE-CLEAN.C3: Each rule the proof design's review adds fails on a fault seeded for it and passes the clean design
        found = self.found(seg("/X", (11, 10.2), (15, 10.2), width=0.2), seg("/X", (11, 9.8), (15, 9.8), width=0.2),
                           seg("/Y", (11, 10), (15, 10), width=0.2), seg("/X", (11, 10), (15, 10), width=0.2, layer="B.Cu"))
        self.assertEqual([v.location.split(": ")[1] for v in found],
                         ["track of /X on F.Cu", "track of /Y on F.Cu", "track of /X on B.Cu"])
        self.assertIn("2 tracks of net /X on F.Cu lie under it between them: 1.663 square mm", found[0].message)

    def test_a_pad_of_another_part_or_the_same_part_in_the_strip_fails_on_the_layers_its_copper_is_on(self):
        # SOL-BOARD-REVIEW-PROOF-BASELINE-CLEAN.C3: Each rule the proof design's review adds fails on a fault seeded for it and passes the clean design
        through = ('(footprint "lib:t" (layer "F.Cu") (at 13 10) (property "Reference" "J1" (at 0 0 0)) '
                   '(pad "1" thru_hole circle (at 0 0) (size 1.6 1.6) (drill 0.8) (layers "*.Cu" "*.Mask") (net "/X")))')
        found = self.found(through)
        self.assertEqual([v.location.split(": ")[1] for v in found], ["pad of /X on F.Cu", "pad of /X on B.Cu"])
        found = self.found(part("R1", "13 10", ("1", "/Y", 0, 0, "rect", 1, 1)))
        self.assertEqual([v.location.split(": ")[1] for v in found], ["pad of /Y on F.Cu"])
        # A pad of the part's own with no net, between its groups, is in the way too; one with paste and no copper is not.
        middle = part("U1", "10 10", ("1", "/MAINS", 0, 0, "rect", 1, 1), ("2", "/LV", 6, 0, "rect", 1, 1), ("3", "", 3, 0, "rect", 1, 1))
        found = board_check.mains_barrier(DESIGN, tree_of(middle), [], self.MAINS, 0.0)
        self.assertEqual([v.location.split(": ")[1] for v in found], ["pad of (no net) on F.Cu"])
        self.assertIn("a pad of no net on F.Cu lies under it", found[0].message)
        self.assertEqual(self.found(pasted("U2", "13 10", layers='"F.Paste"')), [])

    def test_a_pour_filling_the_strip_fails_and_one_with_the_strip_cut_out_of_it_passes(self):
        # SOL-BOARD-REVIEW-PROOF-BASELINE-CLEAN.C3: Each rule the proof design's review adds fails on a fault seeded for it and passes the clean design
        found = self.found(fills=[fill("/G", "F.Cu", [(5, 5), (20, 5), (20, 15), (5, 15)])])
        self.assertEqual([v.location.split(": ")[1] for v in found], ["zone fill of /G on F.Cu"])
        self.assertIn("5.000 square mm inside the strip", found[0].message)
        found = self.found(fills=[fill("/G", "B.Cu", [(5, 5), (13, 5), (13, 15), (5, 15)]), fill("/G", "B.Cu", [(14, 5), (20, 5), (20, 15), (14, 15)])])
        self.assertIn("2 zone fills of net /G on B.Cu", found[0].message)
        self.assertIn("4.000 square mm", found[0].message)
        # The outline of a pour with a hole joins the hole to it by a bridge of no width; the hole is not copper.
        holed = [(5, 5), (20, 5), (20, 15), (5, 15), (5, 10), (10, 10), (10, 11), (16, 11), (16, 9), (10, 9), (10, 10), (5, 10)]
        self.assertEqual(self.found(fills=[fill("/G", "F.Cu", holed)]), [], "a hole 5 mm by 2 mm across the strip leaves nothing in it")
        self.assertEqual(len(self.found(fills=[fill("/G", "F.Cu", [(5, 5), (20, 5), (20, 15), (5, 15), (5, 10), (10, 10), (10, 10.1), (16, 10.1),
                                                                  (16, 9.9), (10, 9.9), (10, 10), (5, 10)])])), 1,
                         "a hole narrower than the strip leaves the rest of it covered")

    def test_a_figure_above_nothing_admits_that_much_copper_in_the_strip_and_no_more(self):
        # SOL-BOARD-REVIEW-PROOF-BASELINE-CLEAN.C3: Each rule the proof design's review adds fails on a fault seeded for it and passes the clean design
        track = seg("/X", (11, 10), (15, 10))
        self.assertEqual(self.found(track, allowed=1.05), [], "the track has 1.049 square mm in the strip")
        found = self.found(track, allowed=1.0)
        self.assertEqual(len(found), 1)
        self.assertIn("1.049 square mm of copper between its Mains-class pads and its other pads, over all layers, "
                      "where BARRIER_COPPER_MM2 allows 1,", found[0].message)

    def test_the_figure_is_held_to_the_parts_copper_over_all_its_nets_and_layers(self):
        # SOL-BOARD-REVIEW-PROOF-BASELINE-CLEAN.C3: Each rule the proof design's review adds fails on a fault seeded for it and passes the clean design
        both = [seg("/X", (11, 10.2), (15, 10.2), width=0.2), seg("/Y", (11, 9.8), (15, 9.8), width=0.2, layer="B.Cu")]
        self.assertEqual(self.found(*both, allowed=1.7), [], "1.663 square mm in all")
        found = self.found(*both, allowed=1.6)
        self.assertEqual([v.location.split(": ")[1] for v in found], ["track of /X on F.Cu", "track of /Y on B.Cu"])
        self.assertIn("the part has 1.663 square mm", found[1].message)

    def test_a_part_that_does_not_cross_the_barrier_is_not_measured(self):
        # SOL-BOARD-REVIEW-PROOF-BASELINE-CLEAN.C3: Each rule the proof design's review adds fails on a fault seeded for it and passes the clean design
        track = seg("/X", (11, 10), (15, 10))
        for what, pads in (("only Mains-class pads", (("1", "/MAINS", 0, 0), ("2", "/MAINS", 6, 0))),
                           ("only other pads", (("1", "/LV", 0, 0), ("2", "/LV", 6, 0))),
                           ("only pads with no net", (("1", "", 0, 0), ("2", "", 6, 0)))):
            with self.subTest(part=what):
                layout = tree_of(part("U1", "10 10", *[(n, net, x, y, "rect", 1, 1) for n, net, x, y in pads]), track)
                self.assertEqual(board_check.mains_barrier(DESIGN, layout, [], self.MAINS, 0.0), [])
        self.assertEqual(self.found(track, mains=set()), [], "a board with no Mains-class net")

    def test_pads_whose_boxes_overlap_on_both_axes_have_no_strip_and_the_part_fails_as_not_measurable(self):
        # SOL-BOARD-REVIEW-PROOF-BASELINE-CLEAN.C3: Each rule the proof design's review adds fails on a fault seeded for it and passes the clean design
        crossed = part("U1", "10 10", ("1", "/MAINS", 0, 0, "rect", 1, 1), ("2", "/LV", 0.5, 0.5, "rect", 1, 1))
        found = board_check.mains_barrier(DESIGN, tree_of(crossed, seg("/X", (8, 10), (14, 10))), [], self.MAINS, 0.0)
        self.assertEqual([(v.rule, v.location) for v in found], [("mains_barrier", "U1 at (10, 10) mm: barrier not measurable")])
        for text in ("U1 has Mains-class /MAINS (pad 1) and other pads (pad 2)", "cannot be measured",
                     "overlap along both axes, so no strip lies between them", "does not support such a part"):
            self.assertIn(text, found[0].message)
        self.assertEqual(len(board_check.mains_barrier(DESIGN, tree_of(crossed), [], self.MAINS, 0.0)), 1,
                         "it fails whether or not copper lies near it, and whatever figure is allowed")
        self.assertEqual(len(board_check.mains_barrier(DESIGN, tree_of(crossed), [], self.MAINS, 5.0)), 1)
        first = [board_geometry.Pad("U", "1", "/M", (0, 0), (2, 2), 0, "rect", ["F.Cu"])]
        for centre, strip in (((2, 0), (1.0, -1.0, 1.0, 1.0)), ((0, 2), (-1.0, 1.0, 1.0, 1.0)), ((1.5, 1.5), None), ((-3, 0), (-2.0, -1.0, -1.0, 1.0))):
            second = [board_geometry.Pad("U", "2", "/L", centre, (2, 2), 0, "rect", ["F.Cu"])]
            self.assertEqual(board_check.barrier_strip(first, second), strip)

    def test_a_part_whose_only_pads_off_the_class_have_no_net_fails_as_not_measurable(self):
        # SOL-BOARD-REVIEW-PROOF-BASELINE-CLEAN.C3: Each rule the proof design's review adds fails on a fault seeded for it and passes the clean design
        unnetted = part("U1", "10 10", ("1", "/MAINS", 0, 0, "rect", 1, 1), ("2", "", 6, 0, "rect", 1, 1), ("3", "", 6, 2, "rect", 1, 1))
        found = board_check.mains_barrier(DESIGN, tree_of(unnetted), [], self.MAINS, 0.0)
        self.assertEqual([(v.rule, v.location) for v in found], [("mains_barrier", "U1 at (10, 10) mm: barrier not measurable")])
        self.assertIn("its only pads off the Mains class, pads 2, 3, have no net, so whether it bridges the barrier is not known",
                      found[0].message)
        netted = part("U1", "10 10", ("1", "/MAINS", 0, 0, "rect", 1, 1), ("2", "", 6, 0, "rect", 1, 1), ("3", "/LV", 6, 2, "rect", 1, 1))
        self.assertEqual(board_check.mains_barrier(DESIGN, tree_of(netted), [], self.MAINS, 0.0), [],
                         "with one pad on another net the part is measured as before, and an unnetted pad is not its edge")

    def test_pads_apart_along_y_leave_a_strip_between_them_along_y(self):
        # SOL-BOARD-REVIEW-PROOF-BASELINE-CLEAN.C3: Each rule the proof design's review adds fails on a fault seeded for it and passes the clean design
        upright = part("U1", "10 10", ("1", "/MAINS", 0, 0, "rect", 1, 1), ("2", "/LV", 0, 6, "rect", 1, 1))
        found = board_check.mains_barrier(DESIGN, tree_of(upright, seg("/X", (10, 11), (10, 15))), [], self.MAINS, 0.0)
        self.assertIn("inside the strip from (9.5, 10.5) to (10.5, 15.5) mm", found[0].message)
        self.assertEqual(board_check.mains_barrier(DESIGN, tree_of(upright, seg("/X", (11, 11), (11, 15))), [], self.MAINS, 0.0), [])

    def test_a_pad_turned_on_the_board_is_boxed_as_it_lies(self):
        # SOL-BOARD-REVIEW-PROOF-BASELINE-CLEAN.C3: Each rule the proof design's review adds fails on a fault seeded for it and passes the clean design
        # Turned a quarter, a 4 mm by 1 mm pad reaches 4 mm along y and 1 mm along x, so the strip is taller than the pads' extent along y.
        turned = part("U1", "10 10", ("1", "/MAINS", 0, 0, "rect", 4, 1, 90), ("2", "/LV", 6, 0, "rect", 1, 1))
        flat = part("U1", "10 10", ("1", "/MAINS", 0, 0, "rect", 4, 1, 0), ("2", "/LV", 6, 0, "rect", 1, 1))
        track = seg("/X", (11, 8.5), (15, 8.5))
        self.assertEqual(len(board_check.mains_barrier(DESIGN, tree_of(turned, track), [], self.MAINS, 0.0)), 1)
        self.assertEqual(board_check.mains_barrier(DESIGN, tree_of(flat, track), [], self.MAINS, 0.0), [])
        for found, wanted in zip(board_geometry.Pad("U", "1", "", (0, 0), (4, 1), 90, "rect", []).box(), (-0.5, -2.0, 0.5, 2.0)):
            self.assertAlmostEqual(found, wanted)
        slanted = board_geometry.Pad("U", "1", "", (0, 0), (4, 2), 45, "rect", []).box()
        self.assertAlmostEqual(slanted[2], 3 / 2 * math.sqrt(2))

    def test_the_copper_of_a_pad_turned_on_the_board_lies_as_it_is_turned(self):
        # SOL-BOARD-REVIEW-PROOF-BASELINE-CLEAN.C3: Each rule the proof design's review adds fails on a fault seeded for it and passes the clean design
        # A 4 mm by 1 mm pad of R1 centred at y 12 lies clear of the strip, which ends at y 10.5, unless it is turned a quarter.
        flat = part("R1", "13 12", ("1", "/Y", 0, 0, "rect", 4, 1))
        turned = part("R1", "13 12", ("1", "/Y", 0, 0, "rect", 4, 1, 90))
        self.assertEqual(self.found(flat), [])
        found = self.found(turned)
        self.assertEqual([v.location.split(": ")[1] for v in found], ["pad of /Y on F.Cu"])
        self.assertIn("0.500 square mm inside the strip", found[0].message)

    def test_a_pad_whose_copper_is_not_sized_is_boxed_at_its_full_size(self):
        # SOL-BOARD-REVIEW-PROOF-BASELINE-CLEAN.C3: Each rule the proof design's review adds fails on a fault seeded for it and passes the clean design
        custom = ('(footprint "lib:c" (layer "F.Cu") (at 10 10) (property "Reference" "U1" (at 0 0 0)) '
                  '(pad "1" smd custom (at 0 0) (size 1 1) (layers "F.Cu") (net "/MAINS") (options (clearance outline) (anchor rect)) '
                  '(primitives (gr_poly (pts (xy 0 0) (xy 3 0) (xy 0 3)) (width 0) (fill yes)))) '
                  '(pad "2" smd rect (at 6 0) (size 1 1) (layers "F.Cu") (net "/LV")))')
        found = board_check.mains_barrier(DESIGN, tree_of(custom, seg("/X", (11, 10), (15, 10))), [], self.MAINS, 0.0)
        self.assertEqual([v.rule for v in found], ["mains_barrier"])
        self.assertIn("from (10.5, 9.5) to (15.5, 10.5) mm", found[0].message)


class SolderPasteIsNotPrintedOverAViasHole(unittest.TestCase):
    # SOL-BOARD-REVIEW-PROOF-BASELINE-CLEAN.C3: Each rule the proof design's review adds fails on a fault seeded for it and passes the clean design
    """A via whose hole a pad's paste opening reaches into fails, whichever side
    the paste is on, the opening being the pad's shape grown by its paste
    margin and ratio as the layout writes them.
    """

    def found(self, pad: str, *vias: str, setup: str = "", allowed: float = 0.0):
        return board_check.paste_over_vias(DESIGN, tree_of(pad, *vias, setup=setup), allowed)

    def test_a_via_clear_of_the_opening_or_a_pad_with_no_paste_passes(self):
        # SOL-BOARD-REVIEW-PROOF-BASELINE-CLEAN.C3: Each rule the proof design's review adds fails on a fault seeded for it and passes the clean design
        self.assertEqual(self.found(pasted("U4", "10 10"), hole("/G", (12, 10)), hole("/G", (10, 11))), [])
        self.assertEqual(self.found(pasted("U4", "10 10", layers='"F.Cu" "F.Mask"'), hole("/G", (10, 10))), [])
        self.assertEqual(self.found(pasted("U4", "10 10", layers='"*.Cu" "*.Mask"'), hole("/G", (10, 10))), [])
        self.assertEqual(self.found(pasted("U4", "10 10")), [], "a board with no via")

    def test_a_via_drilled_through_the_opening_fails_naming_the_via_the_pad_and_how_far_in_the_opening_reaches(self):
        # SOL-BOARD-REVIEW-PROOF-BASELINE-CLEAN.C3: Each rule the proof design's review adds fails on a fault seeded for it and passes the clean design
        found = self.found(pasted("U4", "10 10", net="/G"), hole("/G", (10, 10)))
        self.assertEqual([(v.rule, v.location) for v in found],
                         [("paste_via", "net /G: via at (10, 10) mm, under the paste of pad 1 of U4 at (10, 10) mm")])
        for text in ("solder paste is printed over the hole of the 0.3 mm via at (10, 10) mm of net /G",
                     "the F.Paste opening of pad 1 of U4 at (10, 10) mm, the pad's shape with no paste margin, covers 0.0707 square mm "
                     "of the hole of 0.0707, where PASTE_OVER_VIA_MM2 allows 0",
                     "paste in a via's hole runs through it and starves the joint"):
            self.assertIn(text, found[0].message)

    def test_a_figure_above_nothing_admits_that_much_of_the_hole_under_the_opening_and_no_more(self):
        # SOL-BOARD-REVIEW-PROOF-BASELINE-CLEAN.C3: Each rule the proof design's review adds fails on a fault seeded for it and passes the clean design
        pad, via = pasted("U4", "10 10"), hole("/G", (10.64, 10))
        self.assertEqual(self.found(pad, via, allowed=0.001), [], "0.0007 square mm of the hole is under the opening")
        self.assertEqual(len(self.found(pad, via, allowed=0.0005)), 1)
        centred = hole("/G", (10, 10))
        self.assertEqual(self.found(pad, centred, allowed=0.0707), [], "the whole 0.0707 square mm of the hole")
        found = self.found(pad, centred, allowed=0.07)
        self.assertEqual(len(found), 1)
        self.assertIn("where PASTE_OVER_VIA_MM2 allows 0.07;", found[0].message)

    def test_one_violation_for_each_via_and_opening_and_a_pad_with_no_number_or_net_is_named_so(self):
        # SOL-BOARD-REVIEW-PROOF-BASELINE-CLEAN.C3: Each rule the proof design's review adds fails on a fault seeded for it and passes the clean design
        found = self.found(pasted("U4", "10 10", number=""), hole("/G", (10.2, 10)), hole("", (9.8, 10)))
        self.assertEqual(len(found), 2)
        self.assertIn("pad (unnumbered) of U4", found[0].message)
        self.assertTrue(any("of no net" in v.message and v.location.startswith("net (no net): ") for v in found), found)

    def test_a_via_whose_hole_only_touches_the_opening_passes_and_one_a_little_further_in_fails(self):
        # SOL-BOARD-REVIEW-PROOF-BASELINE-CLEAN.C3: Each rule the proof design's review adds fails on a fault seeded for it and passes the clean design
        self.assertEqual(self.found(pasted("U4", "10 10"), hole("/G", (10.65, 10))), [])
        found = self.found(pasted("U4", "10 10"), hole("/G", (10.64, 10)))
        self.assertEqual(len(found), 1)
        self.assertIn("covers 0.0007 square mm of the hole", found[0].message)

    def test_the_opening_is_the_pad_grown_or_shrunk_by_its_paste_margin(self):
        # SOL-BOARD-REVIEW-PROOF-BASELINE-CLEAN.C3: Each rule the proof design's review adds fails on a fault seeded for it and passes the clean design
        via = hole("/G", (10.7, 10))
        self.assertEqual(self.found(pasted("U4", "10 10"), via), [])
        grown = self.found(pasted("U4", "10 10", pad_extra="(solder_paste_margin 0.1)"), via)
        self.assertEqual(len(grown), 1)
        self.assertIn("the pad's shape grown by 0.1 mm on every side, covers 0.0077 square mm", grown[0].message)
        shrunk = self.found(pasted("U4", "10 10", pad_extra="(solder_paste_margin -0.1)"), hole("/G", (10.6, 10)))
        self.assertEqual(shrunk, [])
        self.assertEqual(len(self.found(pasted("U4", "10 10"), hole("/G", (10.6, 10)))), 1)

    def test_the_opening_is_also_grown_by_the_margin_ratio_times_the_pads_shorter_side(self):
        # SOL-BOARD-REVIEW-PROOF-BASELINE-CLEAN.C3: Each rule the proof design's review adds fails on a fault seeded for it and passes the clean design
        # 0.1 of a 1 mm by 3 mm pad's shorter side, 1 mm, is 0.1 mm.
        pad = "(solder_paste_margin_ratio {})"
        long_pad = dict(size="1 3")
        self.assertEqual(len(self.found(pasted("U4", "10 10", pad_extra=pad.format(0.1), **long_pad), hole("/G", (10.7, 10)))), 1)
        self.assertEqual(self.found(pasted("U4", "10 10", pad_extra=pad.format(0.05), **long_pad), hole("/G", (10.7, 10))), [])
        self.assertEqual(self.found(pasted("U4", "10 10", pad_extra=pad.format(-0.1), **long_pad), hole("/G", (10.6, 10))), [])
        both = self.found(pasted("U4", "10 10", pad_extra="(solder_paste_margin 0.05) (solder_paste_margin_ratio 0.05)", **long_pad),
                          hole("/G", (10.7, 10)))
        self.assertEqual(len(both), 1, "0.05 mm and 0.05 of 1 mm make 0.1 mm")

    def test_a_margin_the_pad_does_not_write_is_its_footprints_and_then_the_boards(self):
        # SOL-BOARD-REVIEW-PROOF-BASELINE-CLEAN.C3: Each rule the proof design's review adds fails on a fault seeded for it and passes the clean design
        via = hole("/G", (10.7, 10))
        board_wide = "(setup (pad_to_paste_clearance 0.1))"
        self.assertEqual(len(self.found(pasted("U4", "10 10"), via, setup=board_wide)), 1)
        self.assertEqual(self.found(pasted("U4", "10 10", part_extra="(solder_paste_margin 0)"), via, setup=board_wide), [],
                         "the footprint's own margin outranks the board's")
        self.assertEqual(len(self.found(pasted("U4", "10 10", part_extra="(solder_paste_margin -0.2)", pad_extra="(solder_paste_margin 0.1)"),
                                        via, setup=board_wide)), 1, "the pad's own margin outranks the footprint's")
        ratio = "(setup (pad_to_paste_clearance_ratio 0.1))"
        self.assertEqual(len(self.found(pasted("U4", "10 10"), via, setup=ratio)), 1)
        self.assertEqual(self.found(pasted("U4", "10 10", part_extra="(solder_paste_margin_ratio 0)"), via, setup=ratio), [])
        self.assertEqual(len(self.found(pasted("U4", "10 10", part_extra="(solder_paste_margin_ratio -0.1)", pad_extra="(solder_paste_margin_ratio 0.1)"),
                                        via, setup=ratio)), 1)

    def test_an_opening_shrunk_to_nothing_covers_nothing(self):
        # SOL-BOARD-REVIEW-PROOF-BASELINE-CLEAN.C3: Each rule the proof design's review adds fails on a fault seeded for it and passes the clean design
        for extra in ("(solder_paste_margin -0.5)", "(solder_paste_margin -0.9)", "(solder_paste_margin_ratio -0.5)"):
            with self.subTest(extra=extra):
                self.assertEqual(self.found(pasted("U4", "10 10", pad_extra=extra), hole("/G", (10, 10))), [])

    def test_paste_on_either_side_counts_and_a_pad_with_paste_and_no_copper_is_measured(self):
        # SOL-BOARD-REVIEW-PROOF-BASELINE-CLEAN.C3: Each rule the proof design's review adds fails on a fault seeded for it and passes the clean design
        found = self.found(pasted("U4", "10 10", layers='"B.Cu" "B.Paste" "B.Mask"'), hole("/G", (10, 10)))
        self.assertIn("the B.Paste opening of pad 1 of U4", found[0].message)
        found = self.found(pasted("U4", "10 10", layers='"F.Paste"'), hole("/G", (10, 10), layers='"B.Cu" "B.Cu"'))
        self.assertEqual(len(found), 1, "paste-only exposed-pad opening over a via on the other side")
        found = self.found(pasted("U4", "10 10", layers='"F.Paste" "B.Paste"'), hole("/G", (10, 10)))
        self.assertIn("the F.Paste and B.Paste opening", found[0].message)

    def test_a_pad_turned_on_the_board_is_opened_as_it_lies(self):
        # SOL-BOARD-REVIEW-PROOF-BASELINE-CLEAN.C3: Each rule the proof design's review adds fails on a fault seeded for it and passes the clean design
        via = hole("/G", (10, 10.9))
        self.assertEqual(self.found(pasted("U4", "10 10", shape="oval", size="2 0.5"), via), [])
        self.assertEqual(len(self.found(pasted("U4", "10 10", shape="oval", size="2 0.5", angle="90"), via)), 1)

    def test_each_shape_is_opened_as_it_is_sized(self):
        # SOL-BOARD-REVIEW-PROOF-BASELINE-CLEAN.C3: Each rule the proof design's review adds fails on a fault seeded for it and passes the clean design
        corner = hole("/G", (10.55, 10.55))
        self.assertEqual(len(self.found(pasted("U4", "10 10"), corner)), 1, "a rectangle covers its corner")
        self.assertEqual(self.found(pasted("U4", "10 10", shape="roundrect", pad_extra="(roundrect_rratio 0.25)"), corner), [],
                         "a rounded corner leaves it")
        self.assertEqual(self.found(pasted("U4", "10 10", shape="circle"), corner), [])
        self.assertEqual(len(self.found(pasted("U4", "10 10", shape="circle"), hole("/G", (10.4, 10)))), 1)
        self.assertEqual(self.found(pasted("U4", "10 10", shape="oval", size="2 1"), hole("/G", (11.3, 10.4))), [])

    def test_a_pad_with_paste_whose_copper_is_not_sized_fails_by_name_wherever_the_board_has_a_via(self):
        # SOL-BOARD-REVIEW-PROOF-BASELINE-CLEAN.C3: Each rule the proof design's review adds fails on a fault seeded for it and passes the clean design
        custom = pasted("U4", "10 10", shape="custom", pad_extra="(options (clearance outline) (anchor rect)) "
                                                                 "(primitives (gr_poly (pts (xy 0 0) (xy 3 0) (xy 0 3)) (width 0) (fill yes)))")
        found = self.found(custom, hole("/G", (30, 30)))
        self.assertEqual([(v.rule, v.location) for v in found], [("paste_via", "net (no net): pad 1 of U4 at (10, 10) mm")])
        self.assertIn("whether the F.Paste opening of pad 1 of U4 reaches a via's hole cannot be measured: its shape is custom", found[0].message)
        self.assertEqual(self.found(custom), [], "nothing to reach")
        chamfered = pasted("U4", "10 10", pad_extra="(chamfer_ratio 0.2) (chamfer top_left)")
        self.assertIn("its corners are chamfered", self.found(chamfered, hole("/G", (30, 30)))[0].message)

    def test_a_via_with_no_drill_has_no_hole(self):
        # SOL-BOARD-REVIEW-PROOF-BASELINE-CLEAN.C3: Each rule the proof design's review adds fails on a fault seeded for it and passes the clean design
        self.assertEqual(self.found(pasted("U4", "10 10"), '(via (at 10 10) (size 0.6) (layers "F.Cu" "B.Cu") (net "/G"))'), [])


class APourStopsNoNarrowerThanTheMinimumClearanceShortOfItsOwnNet(unittest.TestCase):
    # SOL-BOARD-REVIEW-PROOF-BASELINE-CLEAN.C3: Each rule the proof design's review adds fails on a fault seeded for it and passes the clean design
    """KiCad compares no copper of one net, so a gap between a pour's fill and a
    track, via or pad of its own net that the fill stops short of is measured
    here against the board's minimum clearance.
    """

    SQUARE = fill("/A", "F.Cu", [(0, 0), (10, 0), (10, 10), (0, 10)])

    def found(self, *items, fills=None, minimum=0.15, layers=""):
        return board_check.pour_gaps(DESIGN, tree_of(*items, layers=layers), [self.SQUARE] if fills is None else fills, minimum)

    def test_copper_inside_the_fill_or_crossing_its_edge_or_far_from_it_passes(self):
        # SOL-BOARD-REVIEW-PROOF-BASELINE-CLEAN.C3: Each rule the proof design's review adds fails on a fault seeded for it and passes the clean design
        self.assertEqual(self.found(seg("/A", (2, 5), (8, 5))), [])
        self.assertEqual(self.found(seg("/A", (12, 5), (8, 5))), [], "a track running into the fill from outside")
        self.assertEqual(self.found(seg("/A", (8, 5), (12, 5))), [])
        self.assertEqual(self.found(seg("/A", (2, 12), (8, 12))), [], "well clear of it")
        self.assertEqual(self.found(), [])

    def test_a_track_stopping_short_of_the_fill_by_less_than_the_minimum_fails_naming_the_gap(self):
        # SOL-BOARD-REVIEW-PROOF-BASELINE-CLEAN.C3: Each rule the proof design's review adds fails on a fault seeded for it and passes the clean design
        found = self.found(seg("/A", (2, 10.13), (8, 10.13), width=0.1))
        self.assertEqual([(v.rule, v.location) for v in found], [("pour_gap", "net /A: track from (2, 10.13) to (8, 10.13) mm on F.Cu")])
        for text in ("the pour of /A on F.Cu (a fill spanning (0, 0) to (10, 10) mm) stops 0.080 mm short of track from (2, 10.13) to (8, 10.13) mm",
                     "narrower than the board's 0.15 mm minimum clearance", "KiCad's clearance check compares no copper of one net"):
            self.assertIn(text, found[0].message)

    def test_a_gap_exactly_the_minimum_passes_and_a_hair_under_it_fails(self):
        # SOL-BOARD-REVIEW-PROOF-BASELINE-CLEAN.C3: Each rule the proof design's review adds fails on a fault seeded for it and passes the clean design
        self.assertEqual(self.found(seg("/A", (2, 10.2), (8, 10.2), width=0.1)), [])
        self.assertEqual(len(self.found(seg("/A", (2, 10.1999), (8, 10.1999), width=0.1))), 1)
        self.assertEqual(self.found(seg("/A", (2, 10.2), (8, 10.2), width=0.1), minimum=0.1), [])

    def test_the_gap_is_to_the_copper_of_a_tracks_end_cap_as_much_as_its_side(self):
        # SOL-BOARD-REVIEW-PROOF-BASELINE-CLEAN.C3: Each rule the proof design's review adds fails on a fault seeded for it and passes the clean design
        self.assertEqual(self.found(seg("/A", (10.2, 5), (14, 5), width=0.1)), [])
        found = self.found(seg("/A", (10.18, 5), (14, 5), width=0.1))
        self.assertIn("stops 0.130 mm short", found[0].message)

    def test_copper_within_the_touch_distance_of_the_fill_is_touched_and_beyond_it_is_not(self):
        # SOL-BOARD-REVIEW-PROOF-BASELINE-CLEAN.C3: Each rule the proof design's review adds fails on a fault seeded for it and passes the clean design
        self.assertEqual(self.found(seg("/A", (2, 10.05005), (8, 10.05005), width=0.1)), [])
        self.assertEqual(len(self.found(seg("/A", (2, 10.0502), (8, 10.0502), width=0.1))), 1)

    def test_copper_wholly_inside_the_fill_is_touched_however_near_the_edge_it_runs(self):
        # SOL-BOARD-REVIEW-PROOF-BASELINE-CLEAN.C3: Each rule the proof design's review adds fails on a fault seeded for it and passes the clean design
        self.assertEqual(self.found(seg("/A", (2, 9.92), (8, 9.92), width=0.1)), [], "0.03 mm from the edge, inside it")
        self.assertEqual(self.found(hole("/A", (5, 9.9), size=0.1)), [])
        self.assertEqual(self.found(part("R1", "9.5 5", ("1", "/A", 0, 0, "rect", 1, 1))), [], "a pad with its edge on the fill's")

    def test_copper_of_another_net_or_on_another_layer_is_not_judged(self):
        # SOL-BOARD-REVIEW-PROOF-BASELINE-CLEAN.C3: Each rule the proof design's review adds fails on a fault seeded for it and passes the clean design
        self.assertEqual(self.found(seg("/B", (2, 10.13), (8, 10.13), width=0.1)), [])
        self.assertEqual(self.found(seg("/A", (2, 10.13), (8, 10.13), width=0.1, layer="B.Cu")), [])

    def test_an_arc_is_judged_by_its_copper_along_its_length(self):
        # SOL-BOARD-REVIEW-PROOF-BASELINE-CLEAN.C3: Each rule the proof design's review adds fails on a fault seeded for it and passes the clean design
        found = self.found(arc("/A", (2, 10.2), (5, 10.13), (8, 10.2), width=0.1))
        self.assertEqual([v.location.split(": ")[1].split(" from")[0] for v in found], ["arc"])
        self.assertIn("stops 0.080", found[0].message)

    def test_a_via_is_copper_on_every_layer_it_joins(self):
        # SOL-BOARD-REVIEW-PROOF-BASELINE-CLEAN.C3: Each rule the proof design's review adds fails on a fault seeded for it and passes the clean design
        under = fill("/A", "B.Cu", [(0, 0), (10, 0), (10, 10), (0, 10)])
        found = self.found(hole("/A", (5, 10.35), size=0.5), fills=[self.SQUARE, under])
        self.assertEqual([v.location for v in found], ["net /A: via at (5, 10.35) mm on F.Cu", "net /A: via at (5, 10.35) mm on B.Cu"])
        self.assertIn("stops 0.100 mm short of via at (5, 10.35) mm", found[0].message)
        self.assertEqual(self.found(hole("/A", (5, 10.45), size=0.5)), [], "0.2 mm clear")
        self.assertEqual(self.found(hole("/A", (5, 5))), [], "a via inside the fill")

    def test_a_hole_in_the_fill_is_outside_it(self):
        # SOL-BOARD-REVIEW-PROOF-BASELINE-CLEAN.C3: Each rule the proof design's review adds fails on a fault seeded for it and passes the clean design
        ring = [(0, 0), (10, 0), (10, 10), (0, 10), (0, 5), (4.8, 5), (4.8, 5.2), (5.2, 5.2), (5.2, 4.8), (4.8, 4.8), (4.8, 5), (0, 5)]
        punched = fill("/A", "F.Cu", ring)
        found = self.found(hole("/A", (5, 5), size=0.2), fills=[punched])
        self.assertEqual([v.rule for v in found], ["pour_gap"])
        self.assertIn("stops 0.100 mm short of via", found[0].message)
        self.assertEqual(self.found(hole("/A", (5, 5), size=0.1), fills=[punched]), [], "0.15 mm clear of the hole's edge")

    def test_a_pad_is_judged_on_the_layers_it_is_on_as_it_is_turned(self):
        # SOL-BOARD-REVIEW-PROOF-BASELINE-CLEAN.C3: Each rule the proof design's review adds fails on a fault seeded for it and passes the clean design
        self.assertEqual(self.found(part("R1", "10.65 5", ("1", "/A", 0, 0, "rect", 1, 1))), [])
        found = self.found(part("R1", "10.6 5", ("1", "/A", 0, 0, "rect", 1, 1)))
        self.assertEqual([v.location for v in found], ["net /A: pad 1 of R1 at (10.6, 5) mm on F.Cu"])
        self.assertIn("stops 0.100 mm short of pad 1 of R1 at (10.6, 5) mm", found[0].message)
        self.assertEqual(len(self.found(part("R1", "11.1 5", ("1", "/A", 0, 0, "rect", 2, 1)))), 1, "2 mm wide, its edge is 0.1 mm off")
        self.assertEqual(self.found(part("R1", "11.1 5", ("1", "/A", 0, 0, "rect", 2, 1, 90))), [], "turned, it is 1 mm wide along x")
        under = fill("/A", "B.Cu", [(0, 0), (10, 0), (10, 10), (0, 10)])
        self.assertEqual(self.found(part("R1", "10.6 5", ("1", "/A", 0, 0, "rect", 1, 1)), fills=[under]), [], "a surface pad on the other layer")

    def test_a_pad_whose_copper_is_not_sized_is_judged_as_the_box_of_its_full_size(self):
        # SOL-BOARD-REVIEW-PROOF-BASELINE-CLEAN.C3: Each rule the proof design's review adds fails on a fault seeded for it and passes the clean design
        custom = ('(footprint "lib:c" (layer "F.Cu") (at 10.6 5) (property "Reference" "U9" (at 0 0 0)) '
                  '(pad "1" smd custom (at 0 0) (size 1 1) (layers "F.Cu") (net "/A") (options (clearance outline) (anchor rect)) '
                  '(primitives (gr_poly (pts (xy 0 0) (xy 3 0) (xy 0 3)) (width 0) (fill yes)))))')
        found = self.found(custom)
        self.assertIn("stops 0.100 mm short of pad 1 of U9", found[0].message)

    def test_each_fill_is_judged_alone_and_a_copper_item_reported_once_for_each_it_falls_short_of(self):
        # SOL-BOARD-REVIEW-PROOF-BASELINE-CLEAN.C3: Each rule the proof design's review adds fails on a fault seeded for it and passes the clean design
        second = fill("/A", "F.Cu", [(20, 0), (30, 0), (30, 10), (20, 10)])
        found = self.found(seg("/A", (2, 10.13), (8, 10.13), width=0.1), seg("/A", (22, 10.13), (28, 10.13), width=0.1), fills=[self.SQUARE, second])
        self.assertEqual(len(found), 2)
        self.assertIn("(a fill spanning (0, 0) to (10, 10) mm)", found[0].message)
        self.assertIn("(a fill spanning (20, 0) to (30, 10) mm)", found[1].message)

    def test_a_fill_of_thousands_of_corners_is_judged_in_one_pass_over_its_edges(self):
        # SOL-BOARD-REVIEW-PROOF-BASELINE-CLEAN.C3: Each rule the proof design's review adds fails on a fault seeded for it and passes the clean design
        ring = [(100 + 90 * math.cos(2 * math.pi * i / 4000), 100 + 90 * math.sin(2 * math.pi * i / 4000)) for i in range(4000)]
        inside = [seg("/A", (100 + index, 100), (100 + index, 120), width=0.1) for index in range(-60, 60)]
        found = self.found(*inside, hole("/A", (190.2, 100), size=0.2, layers='"F.Cu" "F.Cu"'), fills=[fill("/A", "F.Cu", ring)])
        self.assertEqual([v.location for v in found], ["net /A: via at (190.2, 100) mm on F.Cu"])
        self.assertIn("stops 0.100 mm short", found[0].message)

    def test_the_figure_is_the_boards_minimum_clearance_and_a_board_that_states_none_fails(self):
        # SOL-BOARD-REVIEW-PROOF-BASELINE-CLEAN.C3: Each rule the proof design's review adds fails on a fault seeded for it and passes the clean design
        project = {"board": {"design_settings": {"rules": {"min_clearance": 0.15}}}}
        self.assertEqual(board_check.pour_gap_figure(DESIGN, project), (0.15, []))
        self.assertEqual(board_check.pour_gap_figure(DESIGN, {"board": {"design_settings": {"rules": {"min_clearance": 1}}}})[0], 1.0)
        for what, project in (("none", {}), ("no rules", {"board": {"design_settings": {}}}), ("null", {"board": {"design_settings": {"rules": {"min_clearance": None}}}}),
                              ("zero", {"board": {"design_settings": {"rules": {"min_clearance": 0}}}}),
                              ("negative", {"board": {"design_settings": {"rules": {"min_clearance": -0.1}}}}),
                              ("text", {"board": {"design_settings": {"rules": {"min_clearance": "0.15mm"}}}}),
                              ("true", {"board": {"design_settings": {"rules": {"min_clearance": True}}}}),
                              ("rules not an object", {"board": {"design_settings": {"rules": []}}})):
            with self.subTest(figure=what):
                figure, found = board_check.pour_gap_figure(DESIGN, project)
                self.assertIsNone(figure)
                self.assertEqual([(v.rule, v.location) for v in found], [("pour_gap", "a/a.kicad_pro board.design_settings.rules.min_clearance")])
                self.assertIn("MFG-6 pour gap has no figure", found[0].message)
                self.assertIn("set the minimum clearance in Board Setup", found[0].message)
        self.assertIn("states \"0.15mm\"", board_check.pour_gap_figure(DESIGN, {"board": {"design_settings": {"rules": {"min_clearance": "0.15mm"}}}})[1][0].message)


class ThePourRulesAreMeasuredOnTheBoardKiCadRefilled(Tree):
    # SOL-BOARD-REVIEW-PROOF-BASELINE-CLEAN.C3: Each rule the proof design's review adds fails on a fault seeded for it and passes the clean design
    """The layout check refills the copy it runs on and saves it over the copy,
    and the pour rules measure that board, never the fills as committed.
    """

    ZONE = '(zone (net "/A") (layer "F.Cu") (polygon (pts (xy 0 0) (xy 10 0) (xy 10 10) (xy 0 10)))'
    TRACK = seg("/A", (2, 10.13), (8, 10.13), width=0.1)
    #: The fill KiCad is made to write: stopping 0.08 mm short of the track, or running to cover it.
    SHORT = '(filled_polygon (layer "F.Cu") (pts (xy 0 0) (xy 10 0) (xy 10 10) (xy 0 10))))'
    COVERING = '(filled_polygon (layer "F.Cu") (pts (xy 0 0) (xy 10 0) (xy 10 10.5) (xy 0 10.5))))'

    def check(self, committed: str, refilled: str, minimum=0.15):
        project = json.dumps({"text_variables": {"MAINS": "none", **FIGURES},
                              "board": {"design_settings": {"rules": {} if minimum is None else {"min_clearance": minimum}}}})
        for path, text in (("a/a.kicad_pro", project), ("a/a.kicad_sch", schematic()), ("a/a.kicad_pcb", committed),
                           ("a/a.kicad_dru", '(version 1)\n' + WORKMANSHIP)):
            self.write(path, text)
        record = os.path.join(self.root, "arguments")
        fake = fake_tool(os.path.join(self.root, "kicad-cli"), f"""
import glob, json, re, sys
args = sys.argv[1:]
out = args[args.index("-o") + 1]
if args[:2] == ["sch", "erc"]:
    report = {{"sheets": []}}
elif args[:3] == ["sch", "export", "netlist"]:
    open(out, "w").write("(export (nets))"); sys.exit(0)
else:
    if "--save-board" in args:
        open(args[-3], "w").write({refilled!r})
        open({record!r}, "a").write(" ".join(args) + "\\n")
    rules = open(glob.glob("*.kicad_dru")[0]).read()
    found = re.findall(r'rule "(pre-order check [0-9a-f]+: rules loaded)"', rules)
    entries = [{{"type": "assertion_failure", "description": "Assertion failure (rule '" + found[-1] + "')", "items": []}}] if found else []
    report = {{"violations": entries}}
json.dump(report, open(out, "w"))
""", sys.executable)
        repository = board_check.Repository(self.root, ["a/a.kicad_pro", "a/a.kicad_sch", "a/a.kicad_pcb", "a/a.kicad_dru"])
        read = []
        found = board_check.check_design(board_check.Design("a/a.kicad_pro"), repository, fake, board_check.require_yaml(), TODAY, [], read)
        return [v for v in found if v.rule != "pin_allocation"], read, record

    def layout(self, *items: str) -> str:
        return "(kicad_pcb (version 20260206) " + " ".join(items) + ")"

    def test_the_layout_check_is_told_to_save_the_board_it_refilled(self):
        # SOL-BOARD-REVIEW-PROOF-BASELINE-CLEAN.C3: Each rule the proof design's review adds fails on a fault seeded for it and passes the clean design
        _, _, record = self.check(self.layout(), self.layout())
        with open(record, encoding="utf-8") as handle:
            arguments = handle.read().split()
        self.assertEqual(arguments[:2], ["pcb", "drc"])
        self.assertLess(arguments.index("--refill-zones"), arguments.index("--save-board"))

    def test_a_fill_that_stops_short_in_the_refilled_board_fails_whatever_the_committed_one_covered(self):
        # SOL-BOARD-REVIEW-PROOF-BASELINE-CLEAN.C3: Each rule the proof design's review adds fails on a fault seeded for it and passes the clean design
        found, _, _ = self.check(self.layout(self.ZONE + self.COVERING, self.TRACK), self.layout(self.ZONE + self.SHORT, self.TRACK))
        self.assertEqual([v.rule for v in found if v.rule.startswith("pour")], ["pour_gap"])
        self.assertIn("stops 0.080 mm short of track", [v for v in found if v.rule == "pour_gap"][0].message)

    def test_a_fill_that_covers_the_copper_in_the_refilled_board_passes_whatever_the_committed_one_left_short(self):
        # SOL-BOARD-REVIEW-PROOF-BASELINE-CLEAN.C3: Each rule the proof design's review adds fails on a fault seeded for it and passes the clean design
        found, _, _ = self.check(self.layout(self.ZONE + self.SHORT, self.TRACK), self.layout(self.ZONE + self.COVERING, self.TRACK))
        self.assertEqual([v for v in found if v.rule == "pour_gap"], [])

    def test_a_refilled_board_that_cannot_be_read_fails_the_design_by_name(self):
        # SOL-BOARD-REVIEW-PROOF-BASELINE-CLEAN.C3: Each rule the proof design's review adds fails on a fault seeded for it and passes the clean design
        found, _, _ = self.check(self.layout(self.ZONE + self.SHORT, self.TRACK), "(kicad_pcb (zone")
        unreadable = [v for v in found if v.rule == "design_unreadable"]
        self.assertEqual(len(unreadable), 1, found)
        self.assertEqual(unreadable[0].location, "a/a.kicad_pcb")
        self.assertIn("the layout KiCad refilled cannot be read for its pours", unreadable[0].message)
        found, _, _ = self.check(self.layout(self.ZONE + self.SHORT, self.TRACK),
                                 self.layout('(zone (net "/A") (filled_polygon (pts (xy 0 0) (xy 1 0) (xy 1 1))))'))
        self.assertIn("has no layer or no corners", [v for v in found if v.rule == "design_unreadable"][0].message)

    def test_a_board_with_fills_and_no_minimum_clearance_fails_naming_it_and_one_without_fills_does_not(self):
        # SOL-BOARD-REVIEW-PROOF-BASELINE-CLEAN.C3: Each rule the proof design's review adds fails on a fault seeded for it and passes the clean design
        found, read, _ = self.check(self.layout(), self.layout(self.ZONE + self.SHORT, self.TRACK), minimum=None)
        self.assertEqual([(v.rule, v.location) for v in found if v.rule == "pour_gap"],
                         [("pour_gap", "a/a.kicad_pro board.design_settings.rules.min_clearance")])
        self.assertFalse([item for item in read if item[0] == "MFG-6 pour gap"])
        found, _, _ = self.check(self.layout(), self.layout(self.TRACK), minimum=None)
        self.assertEqual([v for v in found if v.rule == "pour_gap"], [])

    def test_the_minimum_clearance_is_stated_among_the_figures_read(self):
        # SOL-BOARD-REVIEW-PROOF-BASELINE-CLEAN.C3: Each rule the proof design's review adds fails on a fault seeded for it and passes the clean design
        _, read, _ = self.check(self.layout(), self.layout())
        self.assertIn(("MFG-6 pour gap", "Board Setup min_clearance", "0.15 mm, the narrowest gap a pour may leave between its "
                       "fill and copper of its own net that it stops short of"), read)


def reference_part(reference: str, layer: str = "F.SilkS", side: str = "F.Cu", extra: str = "", attributes: str = "") -> str:
    return (f'(footprint "lib:part" (layer "{side}") (at 5 5) (property "Reference" "{reference}" (at 0 0 0) (layer "{layer}") {extra}) '
            f'{attributes})')


class EveryReferenceIsOnTheSilkscreenOfItsSide(unittest.TestCase):
    # SOL-BOARD-METHOD-FOLLOWABLE-AND-MACHINE-FREE.C3: Each rule the method proof design's review adds fails on a fault seeded for it and passes the clean design
    """MFG-7: a footprint's Reference text is shown, on F.SilkS for a part on the
    front and B.SilkS for one on the back; the figure is an inherent zero."""

    def found(self, *items):
        return board_check.references_off_silkscreen(DESIGN, tree_of(*items))

    def test_a_reference_on_the_silkscreen_of_its_side_passes(self):
        # SOL-BOARD-METHOD-FOLLOWABLE-AND-MACHINE-FREE.C3: Each rule the method proof design's review adds fails on a fault seeded for it and passes the clean design
        self.assertEqual(self.found(reference_part("R1"), reference_part("R2", "B.SilkS", "B.Cu"), reference_part("R3", extra="(hide no)")), [])

    def test_a_reference_on_another_layer_or_the_other_side_fails_naming_the_part_and_the_layer(self):
        # SOL-BOARD-METHOD-FOLLOWABLE-AND-MACHINE-FREE.C3: Each rule the method proof design's review adds fails on a fault seeded for it and passes the clean design
        for layer, side, text in (("F.Fab", "F.Cu", "on F.Fab, not F.SilkS"), ("B.Fab", "B.Cu", "on B.Fab, not B.SilkS"),
                                  ("F.SilkS", "B.Cu", "on F.SilkS, not B.SilkS"), ("B.SilkS", "F.Cu", "on B.SilkS, not F.SilkS")):
            with self.subTest(layer=layer, side=side):
                found = self.found(reference_part("U1", layer, side))
                self.assertEqual([(v.rule, v.location) for v in found], [("reference_off_silkscreen", "U1 at (5, 5) mm")])
                self.assertIn(f"MFG-7 every part's reference designator is on a silkscreen layer: the reference of U1 is {text}", found[0].message)

    def test_a_hidden_reference_fails_except_on_a_footprint_left_out_of_the_bill_of_materials(self):
        # SOL-BOARD-METHOD-FOLLOWABLE-AND-MACHINE-FREE.C3: Each rule the method proof design's review adds fails on a fault seeded for it and passes the clean design
        found = self.found(reference_part("U1", extra="(hide yes)"))
        self.assertIn("the reference of U1 is on F.SilkS, but hidden", found[0].message)
        self.assertEqual(len(self.found(reference_part("U1", extra="(effects (hide yes))"))), 1)
        self.assertIn("on F.Fab, not F.SilkS, and hidden", self.found(reference_part("U1", "F.Fab", extra="(hide yes)"))[0].message)
        mounting = "(attr exclude_from_pos_files exclude_from_bom)"
        self.assertEqual(self.found(reference_part("H1", extra="(hide yes)", attributes=mounting)), [])
        self.assertEqual(len(self.found(reference_part("H1", "F.Fab", extra="(hide yes)", attributes=mounting))), 1)

    def test_a_hidden_reference_written_inside_effects_as_a_bare_atom_is_hidden(self):
        # SOL-BOARD-METHOD-FOLLOWABLE-AND-MACHINE-FREE.C3: Each rule the method proof design's review adds fails on a fault seeded for it and passes the clean design
        found = self.found(reference_part("U1", extra="(effects (font (size 1 1)) hide)"))
        self.assertIn("on F.SilkS, but hidden", found[0].message)
        self.assertEqual(self.found(reference_part("U1", extra="(effects (font (size 1 1)))")), [])

    def test_a_footprint_with_no_reference_text_fails_naming_it_even_when_left_out_of_the_bill_of_materials(self):
        # SOL-BOARD-METHOD-FOLLOWABLE-AND-MACHINE-FREE.C3: Each rule the method proof design's review adds fails on a fault seeded for it and passes the clean design
        bare = '(footprint "lib:hole" (layer "F.Cu") (at 3 4) {})'
        for attributes in ("", "(attr exclude_from_bom)"):
            with self.subTest(attributes=attributes):
                found = self.found(bare.format(attributes))
                self.assertEqual([(v.rule, v.location) for v in found], [("reference_off_silkscreen", "lib:hole at (3, 4) mm")])
                self.assertIn("the footprint lib:hole has no reference text; give it one on F.SilkS", found[0].message)
        self.assertIn("give it one on B.SilkS", self.found('(footprint "lib:p" (layer "B.Cu") (at 1 1))')[0].message)
        self.assertEqual(len(self.found(bare.format(""), reference_part("R1"))), 1)

    def test_an_older_footprints_reference_text_is_read_too(self):
        # SOL-BOARD-METHOD-FOLLOWABLE-AND-MACHINE-FREE.C3: Each rule the method proof design's review adds fails on a fault seeded for it and passes the clean design
        old = '(footprint "lib:p" (layer "F.Cu") (at 1 2) (fp_text reference "R9" (at 0 0) (layer "F.Fab")))'
        self.assertEqual([v.location for v in self.found(old)], ["R9 at (1, 2) mm"])


def lettered(reference: str, at, yard, text_at=(0, 0), layer: str = "F.SilkS", side: str = "F.Cu", extra: str = "") -> str:
    """A part at `at` with a courtyard box (left, top, right, bottom) of its own axes on the courtyard of its side, and its reference at `text_at`."""
    left, top, right, bottom = yard
    crt = "B.CrtYd" if side == "B.Cu" else "F.CrtYd"
    return (f'(footprint "lib:part" (layer "{side}") (at {at[0]} {at[1]}) '
            f'(property "Reference" "{reference}" (at {text_at[0]} {text_at[1]} 0) (layer "{layer}") (effects (font (size 1 1) (thickness 0.15)) {extra})) '
            f'(fp_rect (start {left} {top}) (end {right} {bottom}) (layer "{crt}")))')


class EveryDesignatorStandsOutsideEveryCourtyardBesideItsOwnPart(unittest.TestCase):
    # SOL-BOARD-REVIEW-LOOP-PROPORTIONATE.C5: A recurring cosmetic nit that a measurement can state is a measured rule the pre-order check enforces
    """MFG-9: a designator's estimated text box is outside every courtyard and no
    nearer another part's courtyard than its own; the figure is an inherent zero."""

    def found(self, *items):
        return board_check.designators_astray(DESIGN, tree_of(*items))

    def test_designators_beside_their_own_parts_pass(self):
        # SOL-BOARD-REVIEW-LOOP-PROPORTIONATE.C5: The pre-order check enforces that rule, converting the catalogue's judgement-kind designator item MFG-9 in place so one statement of it stands: it fails a designator inside a part's courtyard or nearer another part than its own.
        self.assertEqual(self.found(lettered("R1", (10, 10), (-2, -1, 2, 1), (0, -2.2)), lettered("R2", (30, 10), (-2, -1, 2, 1), (0, 2.2))), [])

    def test_a_designator_inside_a_courtyard_fails_naming_the_part_whose_courtyard_it_is_in_and_where(self):
        # SOL-BOARD-REVIEW-LOOP-PROPORTIONATE.C5: The pre-order check enforces that rule, converting the catalogue's judgement-kind designator item MFG-9 in place so one statement of it stands: it fails a designator inside a part's courtyard or nearer another part than its own.
        found = self.found(lettered("R1", (10, 10), (-2, -1, 2, 1)), lettered("R2", (30, 10), (-2, -1, 2, 1), (0, -2.2)))
        self.assertEqual([(v.rule, v.location) for v in found], [("designator_astray", "R1 at (10, 10) mm")])
        self.assertIn("MFG-9 each designator stands outside every part's courtyard, beside its own part: the text of R1 stands inside the courtyard of R1", found[0].message)

    def test_a_designator_inside_another_parts_courtyard_names_that_part(self):
        # SOL-BOARD-REVIEW-LOOP-PROPORTIONATE.C5: The pre-order check enforces that rule, converting the catalogue's judgement-kind designator item MFG-9 in place so one statement of it stands: it fails a designator inside a part's courtyard or nearer another part than its own.
        found = self.found(lettered("R1", (10, 10), (-2, -1, 2, 1), (8, 0)), lettered("R2", (20, 10), (-2, -1, 2, 1), (0, -2.2)))
        self.assertEqual([v.location for v in found], ["R1 at (18, 10) mm"])
        self.assertIn("stands inside the courtyard of R2", found[0].message)

    def test_a_designator_nearer_another_part_than_its_own_fails(self):
        # SOL-BOARD-REVIEW-LOOP-PROPORTIONATE.C5: The pre-order check enforces that rule, converting the catalogue's judgement-kind designator item MFG-9 in place so one statement of it stands: it fails a designator inside a part's courtyard or nearer another part than its own.
        found = self.found(lettered("R1", (10, 10), (-2, -1, 2, 1), (3.5, 0)), lettered("R2", (16.5, 10), (-2, -1, 2, 1), (0, -2.2)))
        self.assertEqual([(v.rule, v.location) for v in found], [("designator_astray", "R1 at (13.5, 10) mm")])
        self.assertIn("is 0.325 mm from the courtyard of R2, nearer than the 0.825 mm from its own; move it beside R1", found[0].message)

    def test_a_designator_clear_of_every_part_with_no_nearer_neighbour_passes(self):
        # SOL-BOARD-REVIEW-LOOP-PROPORTIONATE.C5: The pre-order check enforces that rule, converting the catalogue's judgement-kind designator item MFG-9 in place so one statement of it stands: it fails a designator inside a part's courtyard or nearer another part than its own.
        self.assertEqual(self.found(lettered("R1", (10, 10), (-2, -1, 2, 1), (0, -5)), lettered("R2", (60, 10), (-2, -1, 2, 1), (0, -2.2))), [])

    def test_a_stroke_touching_the_courtyard_line_is_not_inside(self):
        # SOL-BOARD-REVIEW-LOOP-PROPORTIONATE.C5: The pre-order check enforces that rule, converting the catalogue's judgement-kind designator item MFG-9 in place so one statement of it stands: it fails a designator inside a part's courtyard or nearer another part than its own.
        edge = board_check.TEXT_ADVANCE * 2 + 0.15
        self.assertEqual(self.found(lettered("R1", (10, 10), (-2, -1, 2, 1), (2 + edge / 2 - 0.02, 0))), [])
        self.assertEqual(len(self.found(lettered("R1", (10, 10), (-2, -1, 2, 1), (2 + edge / 2 - 0.2, 0)))), 1)

    def test_a_longer_name_reaches_further_into_a_courtyard(self):
        # SOL-BOARD-REVIEW-LOOP-PROPORTIONATE.C5: The pre-order check enforces that rule, converting the catalogue's judgement-kind designator item MFG-9 in place so one statement of it stands: it fails a designator inside a part's courtyard or nearer another part than its own.
        place = (2 + 1.0, 0)
        self.assertEqual(self.found(lettered("R1", (10, 10), (-2, -1, 2, 1), place)), [])
        self.assertEqual(len(self.found(lettered("RV1234", (10, 10), (-2, -1, 2, 1), place))), 1)

    def test_a_text_turned_a_quarter_stands_on_its_end(self):
        # SOL-BOARD-REVIEW-LOOP-PROPORTIONATE.C5: The pre-order check enforces that rule, converting the catalogue's judgement-kind designator item MFG-9 in place so one statement of it stands: it fails a designator inside a part's courtyard or nearer another part than its own.
        part = lettered("R1", (10, 10), (-2, -1, 2, 1), (0, -1.6))
        self.assertEqual(self.found(part), [])
        turned = part.replace("(at 0 -1.6 0)", "(at 0 -1.6 90)")
        self.assertEqual(len(self.found(turned)), 1)

    def test_a_footprint_turned_on_the_board_carries_its_text_with_it(self):
        # SOL-BOARD-REVIEW-LOOP-PROPORTIONATE.C5: The pre-order check enforces that rule, converting the catalogue's judgement-kind designator item MFG-9 in place so one statement of it stands: it fails a designator inside a part's courtyard or nearer another part than its own.
        part = lettered("R1", (10, 10), (-2, -1, 2, 1), (0, -2.2)).replace("(at 10 10)", "(at 10 10 90)")
        self.assertEqual(self.found(part), [])
        inside = lettered("R1", (10, 10), (-2, -1, 2, 1), (0, 0.5)).replace("(at 10 10)", "(at 10 10 90)")
        self.assertEqual([v.location for v in self.found(inside)], ["R1 at (10.5, 10) mm"])

    def test_a_back_side_part_is_held_to_back_courtyards_only(self):
        # SOL-BOARD-REVIEW-LOOP-PROPORTIONATE.C5: The pre-order check enforces that rule, converting the catalogue's judgement-kind designator item MFG-9 in place so one statement of it stands: it fails a designator inside a part's courtyard or nearer another part than its own.
        front = lettered("R1", (10, 10), (-2, -1, 2, 1), (0, -2.2))
        under = lettered("R2", (10, 10), (-2, -1, 2, 1), (0, 4), "B.SilkS", "B.Cu")
        self.assertEqual(self.found(front, under), [])
        self.assertEqual([v.location for v in self.found(front, lettered("R2", (10, 10), (-2, -1, 2, 1), (0, 0), "B.SilkS", "B.Cu"))], ["R2 at (10, 10) mm"])

    def test_a_hidden_designator_or_one_off_the_silkscreen_is_left_to_the_silkscreen_rule(self):
        # SOL-BOARD-REVIEW-LOOP-PROPORTIONATE.C5: The pre-order check enforces that rule, converting the catalogue's judgement-kind designator item MFG-9 in place so one statement of it stands: it fails a designator inside a part's courtyard or nearer another part than its own.
        self.assertEqual(self.found(lettered("R1", (10, 10), (-2, -1, 2, 1), extra="(hide yes)")), [])
        self.assertEqual(self.found(lettered("R1", (10, 10), (-2, -1, 2, 1), layer="F.Fab")), [])

    def test_a_part_with_no_courtyard_is_held_to_the_inside_test_only_and_a_board_with_none_passes(self):
        # SOL-BOARD-REVIEW-LOOP-PROPORTIONATE.C5: The pre-order check enforces that rule, converting the catalogue's judgement-kind designator item MFG-9 in place so one statement of it stands: it fails a designator inside a part's courtyard or nearer another part than its own.
        bare = '(footprint "lib:p" (layer "F.Cu") (at 10 10) (property "Reference" "H1" (at {} 0 0) (layer "F.SilkS")))'
        far = lettered("R2", (57, 10), (-2, -1, 2, 1), (0, -2.2))
        self.assertEqual(self.found(bare.format(0)), [])
        self.assertEqual(self.found(bare.format(0), far), [])
        self.assertEqual(self.found(), [])
        inside = self.found(bare.format(47), far)
        self.assertEqual([v.location for v in inside], ["H1 at (57, 10) mm"])
        self.assertIn("the text of H1 stands inside the courtyard of R2", inside[0].message)

    def test_justified_text_is_placed_along_its_own_direction_at_every_quarter_turn(self):
        # SOL-BOARD-REVIEW-LOOP-PROPORTIONATE.C5: The pre-order check enforces that rule, converting the catalogue's judgement-kind designator item MFG-9 in place so one statement of it stands: it fails a designator inside a part's courtyard or nearer another part than its own.
        yard = (-2, -1, 2, 1)
        # (angle, anchor, justification, whether the text stands in the courtyard)
        cases = [(0, (2.3, 0), "left", False), (0, (2.3, 0), "right", True), (180, (2.3, 0), "left", True), (180, (2.3, 0), "right", False),
                 (90, (0, -1.3), "left", False), (90, (0, -1.3), "right", True), (270, (0, -1.3), "left", True), (270, (0, -1.3), "right", False),
                 (0, (3.2, 0), "", False), (0, (2.5, 0), "", True), (90, (0, -2.0), "", False), (90, (0, -1.5), "", True),
                 (0, (2.3, 0), "left mirror", True), (0, (2.3, 0), "right mirror", False), (180, (2.3, 0), "left mirror", False)]
        for angle, anchor, justify, inside in cases:
            with self.subTest(angle=angle, anchor=anchor, justify=justify):
                part = lettered("R1", (10, 10), yard, anchor, extra=f"(justify {justify})" if justify else "").replace(
                    f"(at {anchor[0]} {anchor[1]} 0)", f"(at {anchor[0]} {anchor[1]} {angle})")
                self.assertEqual(len(self.found(part)), 1 if inside else 0)

    def test_a_vertical_or_top_justified_text_hangs_from_its_anchor_on_the_right_side(self):
        # SOL-BOARD-REVIEW-LOOP-PROPORTIONATE.C5: The pre-order check enforces that rule, converting the catalogue's judgement-kind designator item MFG-9 in place so one statement of it stands: it fails a designator inside a part's courtyard or nearer another part than its own.
        for angle, anchor, justify, inside in ((0, (0, -1.3), "top", True), (0, (0, -1.3), "bottom", False), (180, (0, -1.3), "top", False),
                                               (180, (0, -1.3), "bottom", True), (90, (2.3, 0), "top", False), (90, (2.3, 0), "bottom", True)):
            with self.subTest(angle=angle, justify=justify):
                part = lettered("R1", (10, 10), (-2, -1, 2, 1), anchor, extra=f"(justify {justify})").replace(
                    f"(at {anchor[0]} {anchor[1]} 0)", f"(at {anchor[0]} {anchor[1]} {angle})")
                self.assertEqual(len(self.found(part)), 1 if inside else 0)

    def test_a_text_at_an_angle_that_is_not_a_quarter_turn_is_boxed_turned(self):
        # SOL-BOARD-REVIEW-LOOP-PROPORTIONATE.C5: The pre-order check enforces that rule, converting the catalogue's judgement-kind designator item MFG-9 in place so one statement of it stands: it fails a designator inside a part's courtyard or nearer another part than its own.
        for angle, inside in ((0, False), (45, True)):
            with self.subTest(angle=angle):
                part = lettered("R1", (10, 10), (-2, -1, 2, 1), (2.8, 0)).replace("(at 2.8 0 0)", f"(at 2.8 0 {angle})")
                part = part.replace("(at 2.8 0 0)", "(at 2.8 0 0)")
                self.assertEqual(len(self.found(part)), 1 if inside else 0)

    def test_an_arc_courtyard_reaches_as_far_as_the_arc_does(self):
        # SOL-BOARD-REVIEW-LOOP-PROPORTIONATE.C5: The pre-order check enforces that rule, converting the catalogue's judgement-kind designator item MFG-9 in place so one statement of it stands: it fails a designator inside a part's courtyard or nearer another part than its own.
        arc = ('(footprint "lib:a" (layer "F.Cu") (at 10 10) (property "Reference" "A1" (at 4.4 0 0) (layer "F.SilkS")) '
               '(fp_arc (start 2 -3.464) (mid 3.759 1.368) (end 2 3.464) (layer "F.CrtYd")))')
        self.assertEqual([v.location for v in self.found(arc)], ["A1 at (14.4, 10) mm"])
        self.assertEqual(self.found(arc.replace("(at 4.4 0 0)", "(at 5.2 0 0)")), [])

    def test_a_circular_courtyard_is_its_full_circle(self):
        # SOL-BOARD-REVIEW-LOOP-PROPORTIONATE.C5: The pre-order check enforces that rule, converting the catalogue's judgement-kind designator item MFG-9 in place so one statement of it stands: it fails a designator inside a part's courtyard or nearer another part than its own.
        round_part = ('(footprint "lib:h" (layer "F.Cu") (at 10 10) (property "Reference" "H1" (at 0 -3 0) (layer "F.SilkS")) '
                      '(fp_circle (center 0 0) (end 2 0) (layer "F.CrtYd")))')
        self.assertEqual(self.found(round_part), [])
        self.assertEqual(len(self.found(round_part.replace("(at 0 -3 0)", "(at 0 -1 0)"))), 1)

    def test_a_reference_with_a_position_unreadable_is_reported_unreadable(self):
        # SOL-BOARD-REVIEW-LOOP-PROPORTIONATE.C5: The pre-order check enforces that rule, converting the catalogue's judgement-kind designator item MFG-9 in place so one statement of it stands: it fails a designator inside a part's courtyard or nearer another part than its own.
        with self.assertRaises(board_geometry.Unreadable):
            self.found('(footprint "lib:p" (layer "F.Cu") (at 10 x) (property "Reference" "R1" (at 0 0 0) (layer "F.SilkS")))')


def circuit(*extra: str) -> list:
    """U1 with its +5V pin at (10, 10) and ground pin at (10, 12), typed as power inputs, and C1 across them 4 mm east."""
    def pad(number, net, x, y, kind="power_in"):
        return f'(pad "{number}" smd rect (at {x} {y}) (size 1 1) (layers "F.Cu" "F.Mask") (net "{net}") (pintype "{kind}"))'

    def footprint(reference, at, *pads):
        return f'(footprint "lib:p" (layer "F.Cu") (at {at}) (property "Reference" "{reference}" (at 0 0 0)) {" ".join(pads)})'

    return tree_of(footprint("U1", "0 0", pad(1, "+5V", 10, 10), pad(2, "GND", 10, 12)),
                   footprint("C1", "0 0", pad(1, "+5V", 14, 10, "passive"), pad(2, "GND", 14, 12, "passive")), *extra)


class NoViaSitsBetweenADecouplingCapacitorAndThePinItDecouples(unittest.TestCase):
    # SOL-BOARD-METHOD-FOLLOWABLE-AND-MACHINE-FREE.C3: Each rule the method proof design's review adds fails on a fault seeded for it and passes the clean design
    """DECOUPLE-6: circuits and decoupling parts are the review views' own; the
    box about a capacitor's supply pad and the circuit pin on its net holds no
    via of that net."""

    def found(self, *vias, ground=frozenset({"GND"})):
        return board_check.decoupling_vias(DESIGN, circuit(*vias), set(ground))

    def test_a_via_of_the_supply_net_in_the_box_between_the_pad_and_the_pin_fails_naming_both(self):
        # SOL-BOARD-METHOD-FOLLOWABLE-AND-MACHINE-FREE.C3: Each rule the method proof design's review adds fails on a fault seeded for it and passes the clean design
        found = self.found(hole("+5V", (12, 10)))
        self.assertEqual([(v.rule, v.location) for v in found],
                         [("decoupling_via", "net +5V: via at (12, 10) mm, between pad 1 of C1 and pad 1 of U1")])
        self.assertIn("lies in the box from (9.5, 9.5) to (14.5, 10.5) mm about pad 1 of C1 of +5V and pad 1 of U1, the pin of U1 that C1 decouples",
                      found[0].message)

    def test_a_via_whose_copper_reaches_into_the_box_fails_and_one_clear_of_it_does_not(self):
        # SOL-BOARD-METHOD-FOLLOWABLE-AND-MACHINE-FREE.C3: Each rule the method proof design's review adds fails on a fault seeded for it and passes the clean design
        self.assertEqual(len(self.found(hole("+5V", (12, 10.8), size=0.8))), 1)
        self.assertIn("0.30 mm off, its copper reaching into,", self.found(hole("+5V", (12, 10.8), size=0.8))[0].message)
        self.assertEqual(self.found(hole("+5V", (12, 11.0), size=0.8)), [])
        self.assertEqual(self.found(hole("+5V", (16, 10))), [], "beyond the capacitor's pad")

    def test_a_via_of_another_net_is_not_in_the_capacitors_path(self):
        # SOL-BOARD-METHOD-FOLLOWABLE-AND-MACHINE-FREE.C3: Each rule the method proof design's review adds fails on a fault seeded for it and passes the clean design
        self.assertEqual(self.found(hole("/OTHER", (12, 10))), [])
        self.assertEqual(self.found(hole("GND", (12, 10))), [], "the ground pad is not the supply pad")

    def test_the_ground_pad_is_checked_too_when_the_ground_class_does_not_tell_it_apart(self):
        # SOL-BOARD-METHOD-FOLLOWABLE-AND-MACHINE-FREE.C3: Each rule the method proof design's review adds fails on a fault seeded for it and passes the clean design
        self.assertEqual(len(self.found(hole("GND", (12, 12)), ground=frozenset())), 1)
        self.assertEqual(self.found(hole("GND", (12, 12))), [])
        self.assertEqual(len(self.found(hole("GND", (12, 12)), ground=frozenset({"GND", "+5V"}))), 1)

    def test_a_board_whose_pads_carry_no_pin_types_has_no_decoupling_parts(self):
        # SOL-BOARD-METHOD-FOLLOWABLE-AND-MACHINE-FREE.C3: Each rule the method proof design's review adds fails on a fault seeded for it and passes the clean design
        tree = sexpr.parse_one(sexpr.dump(circuit(hole("+5V", (12, 10)))).replace("(pintype", "(pinfunction"))
        self.assertEqual(board_check.decoupling_vias(DESIGN, tree, {"GND"}), [])
        self.assertEqual(self.found(), [])


class AnOrderableBoardsIntegratedCircuitHasItsSupplyPadsTyped(unittest.TestCase):
    # SOL-BOARD-METHOD-FOLLOWABLE-AND-MACHINE-FREE.C3: Each rule the method proof design's review adds fails on a fault seeded for it and passes the clean design
    """DECOUPLE-6: a board not marked not for manufacture whose integrated circuit
    has netted pads and none typed as a power pin measures nothing, so it fails."""

    def found(self, tree: list, marked: bool = False):
        return board_check.untyped_circuits(DESIGN, tree, marked)

    def untyped(self, *extra: str) -> list:
        return tree_of(*[sexpr.dump(node).replace("(pintype", "(pinfunction") for node in sexpr.children(circuit(*extra), "footprint")])

    def test_an_orderable_board_whose_circuit_has_netted_pads_and_none_typed_fails_naming_the_part(self):
        # SOL-BOARD-METHOD-FOLLOWABLE-AND-MACHINE-FREE.C3: Each rule the method proof design's review adds fails on a fault seeded for it and passes the clean design
        found = self.found(self.untyped())
        self.assertEqual([(v.rule, v.location) for v in found], [("decoupling_pintype", "U1 at (0, 0) mm")])
        self.assertIn("U1 has netted pads and none typed power input or power output", found[0].message)

    def test_an_orderable_board_whose_circuit_is_typed_passes(self):
        # SOL-BOARD-METHOD-FOLLOWABLE-AND-MACHINE-FREE.C3: Each rule the method proof design's review adds fails on a fault seeded for it and passes the clean design
        self.assertEqual(self.found(circuit()), [])
        passive = tree_of(*[sexpr.dump(node).replace('(pintype "power_in")', '(pintype "passive")')
                            for node in sexpr.children(circuit(), "footprint")])
        self.assertEqual([v.rule for v in self.found(passive)], ["decoupling_pintype"], "typed, but none as a power pin")
        one = sexpr.dump(circuit()).replace('(pintype "power_in")', '(pintype "passive")', 1)
        self.assertEqual(self.found(sexpr.parse_one(one)), [], "one power pin is enough")

    def test_a_design_marked_not_for_manufacture_is_not_refused(self):
        # SOL-BOARD-METHOD-FOLLOWABLE-AND-MACHINE-FREE.C3: Each rule the method proof design's review adds fails on a fault seeded for it and passes the clean design
        self.assertEqual(self.found(self.untyped(), marked=True), [])

    def test_a_circuit_with_no_netted_pads_and_a_part_not_beginning_with_u_are_not_refused(self):
        # SOL-BOARD-METHOD-FOLLOWABLE-AND-MACHINE-FREE.C3: Each rule the method proof design's review adds fails on a fault seeded for it and passes the clean design
        bare = tree_of('(footprint "lib:p" (layer "F.Cu") (at 0 0) (property "Reference" "U1" (at 0 0 0)) '
                       '(pad "1" smd rect (at 1 1) (size 1 1) (layers "F.Cu" "F.Mask")))')
        self.assertEqual(self.found(bare), [])
        other = tree_of(*[sexpr.dump(node).replace("(pintype", "(pinfunction").replace('"U1"', '"Q1"')
                          for node in sexpr.children(circuit(), "footprint")])
        self.assertEqual(self.found(other), [])

    def test_each_untyped_circuit_is_named(self):
        # SOL-BOARD-METHOD-FOLLOWABLE-AND-MACHINE-FREE.C3: Each rule the method proof design's review adds fails on a fault seeded for it and passes the clean design
        two = tree_of(*[sexpr.dump(node).replace("(pintype", "(pinfunction") for node in sexpr.children(circuit(), "footprint")],
                      sexpr.dump(sexpr.children(circuit(), "footprint")[0]).replace('"U1"', '"U2"').replace("(pintype", "(pinfunction"))
        self.assertEqual([v.location.split(" ")[0] for v in self.found(two)], ["U1", "U2"])


def placed_circuit(*extra: str, chip_side: str = "F.Cu", cap_side: str = "F.Cu", cap_at: str = "0 0",
                   cap_pads: tuple = ("(at 14 10) (size 1 1)", "(at 14 12) (size 1 1)")) -> list:
    """U1 and C1 as `circuit` lays them out, each on the side given, C1 turned and its pads placed as given."""
    def pad(number, net, where, side, kind):
        mask = side.replace("Cu", "Mask")
        return f'(pad "{number}" smd rect {where} (layers "{side}" "{mask}") (net "{net}") (pintype "{kind}"))'

    return tree_of(
        f'(footprint "lib:p" (layer "{chip_side}") (at 0 0) (property "Reference" "U1" (at 0 0 0)) '
        f'{pad(1, "+5V", "(at 10 10) (size 1 1)", chip_side, "power_in")} {pad(2, "GND", "(at 10 12) (size 1 1)", chip_side, "power_in")})',
        f'(footprint "lib:p" (layer "{cap_side}") (at {cap_at}) (property "Reference" "C1" (at 0 0 0)) '
        f'{pad(1, "+5V", cap_pads[0], cap_side, "passive")} {pad(2, "GND", cap_pads[1], cap_side, "passive")})', *extra)


class DecouplingRuleOnTurnedAndBackSideParts(unittest.TestCase):
    # SOL-BOARD-METHOD-FOLLOWABLE-AND-MACHINE-FREE.C3: Each rule the method proof design's review adds fails on a fault seeded for it and passes the clean design
    """DECOUPLE-6 reads a pad turned on its own, a footprint turned on the board, and parts on the back."""

    def found(self, tree: list):
        return board_check.decoupling_vias(DESIGN, tree, {"GND"})

    def test_a_capacitor_pad_turned_a_quarter_turn_has_its_turned_box(self):
        # SOL-BOARD-METHOD-FOLLOWABLE-AND-MACHINE-FREE.C3: Each rule the method proof design's review adds fails on a fault seeded for it and passes the clean design
        beyond = hole("+5V", (15, 10))
        ground = "(at 14 12) (size 1 1)"
        self.assertEqual(self.found(placed_circuit(beyond, cap_pads=("(at 14 10) (size 1 3)", ground))), [], "a 1 mm wide pad ends at 14.5")
        self.assertEqual(len(self.found(placed_circuit(beyond, cap_pads=("(at 14 10 90) (size 1 3)", ground)))), 1,
                         "the same pad turned lies 3 mm across the board and ends at 15.5")

    def test_a_capacitor_footprint_turned_on_the_board_puts_its_pads_where_the_turn_puts_them(self):
        # SOL-BOARD-METHOD-FOLLOWABLE-AND-MACHINE-FREE.C3: Each rule the method proof design's review adds fails on a fault seeded for it and passes the clean design
        turned = dict(cap_at="14 11 90", cap_pads=("(at 1 0 90) (size 1 1)", "(at -1 0 90) (size 1 1)"))
        self.assertEqual(len(self.found(placed_circuit(hole("+5V", (12, 10)), **turned))), 1)
        self.assertEqual(self.found(placed_circuit(hole("+5V", (12, 13)), **turned)), [])
        unturned = dict(turned, cap_at="14 11 0")
        self.assertEqual(self.found(placed_circuit(hole("+5V", (12, 11.2)), **turned)), [], "the turned pads lie along y 10 to 12 at x 14")
        self.assertEqual(len(self.found(placed_circuit(hole("+5V", (12, 11.2)), **unturned))), 1, "with no turn pad 1 lies at (15, 11)")

    def test_a_capacitor_and_a_circuit_on_the_back_are_measured_as_on_the_front(self):
        # SOL-BOARD-METHOD-FOLLOWABLE-AND-MACHINE-FREE.C3: Each rule the method proof design's review adds fails on a fault seeded for it and passes the clean design
        for chip, cap in (("B.Cu", "B.Cu"), ("F.Cu", "B.Cu"), ("B.Cu", "F.Cu")):
            with self.subTest(chip=chip, cap=cap):
                self.assertEqual([v.rule for v in self.found(placed_circuit(hole("+5V", (12, 10)), chip_side=chip, cap_side=cap))],
                                 ["decoupling_via"])
                self.assertEqual(self.found(placed_circuit(hole("+5V", (12, 13)), chip_side=chip, cap_side=cap)), [])

    def test_the_coverage_counts_circuits_with_a_supply_pin_and_the_paths_between_their_decoupling_pads_and_pins(self):
        # SOL-BOARD-METHOD-FOLLOWABLE-AND-MACHINE-FREE.C3: Each rule the method proof design's review adds fails on a fault seeded for it and passes the clean design
        count, paths = board_check.decoupling_paths(circuit(), {"GND"})
        self.assertEqual((count, [(c, n, p.name(), q.name()) for c, n, p, q in paths]), (1, [("U1", "C1", "pad 1 of C1", "pad 1 of U1")]))
        count, paths = board_check.decoupling_paths(circuit(), set())
        self.assertEqual((count, len(paths)), (1, 2), "both pads when the ground class does not tell them apart")
        untyped = tree_of(*[sexpr.dump(node).replace("(pintype", "(pinfunction") for node in sexpr.children(circuit(), "footprint")])
        self.assertEqual(board_check.decoupling_paths(untyped, {"GND"}), (0, []))


def named_part(library_name: str, reference: str, *pads) -> str:
    """A footprint of the library name `library_name` and reference `reference`, holding pads given as (number, net, width, height)."""
    body = "".join(f'(pad "{n}" smd rect (at {2 * index} 0) (size {w} {h}) (layers "F.Cu" "F.Mask") (net "{net}"))'
                   for index, (n, net, w, h) in enumerate(pads))
    return (f'(footprint "lib:{library_name}" (layer "F.Cu") (at {10 * len(reference)} 10) '
            f'(property "Reference" "{reference}" (at 0 0 0)) {body})')


def rules_of(*texts: str) -> list:
    return board_check.rule_forms("(version 1)\n" + "\n".join(texts))


KEEP_CLEAR = ('(rule "Crystal keep-clear"\n\t(condition "A.Reference == \'Y1\' && B.Reference != \'C1\'")\n'
              '\t(constraint courtyard_clearance (min 25mm)))')


class TheCrystalKeepClearIsInTheRulesFileOfABoardWithACrystal(unittest.TestCase):
    # SOL-BOARD-REVIEW-PROOF-BASELINE-CLEAN.C3: Each rule the proof design's review adds fails on a fault seeded for it and passes the clean design
    """A board with a crystal or a resonator needs the rule keeping unrelated
    parts 25 mm from its courtyard, in the one form, exempting some parts and
    not all of them; a board with none needs no rule.
    """

    BOARD = tree_of(named_part("Crystal_SMD_5032", "Y1", ("1", "/X", 1, 1)), named_part("C_0603", "C1", ("1", "/X", 1, 1)),
                    named_part("R_0603", "R1", ("1", "/Y", 1, 1)))

    def found(self, *rules, tree=None):
        return board_check.crystal_keep_clear(DESIGN, rules_of(*rules) if rules else None, tree or self.BOARD)

    def test_the_rule_in_its_form_passes(self):
        # SOL-BOARD-REVIEW-PROOF-BASELINE-CLEAN.C3: Each rule the proof design's review adds fails on a fault seeded for it and passes the clean design
        self.assertEqual(self.found(KEEP_CLEAR), [])
        self.assertEqual(self.found(KEEP_CLEAR.replace("25mm", "30.5mm")), [])

    def test_a_board_with_no_crystal_needs_no_rule(self):
        # SOL-BOARD-REVIEW-PROOF-BASELINE-CLEAN.C3: Each rule the proof design's review adds fails on a fault seeded for it and passes the clean design
        plain = tree_of(named_part("C_0603", "C1", ("1", "/X", 1, 1)), named_part("Crystalline_Cap", "C2", ("1", "/X", 1, 1)))
        self.assertEqual(self.found(tree=plain), [])
        self.assertEqual([v.rule for v in self.found(tree=tree_of(named_part("Resonator_SMD", "X1", ("1", "/X", 1, 1))))], ["crystal_keepclear"])

    def test_a_board_whose_rules_file_lacks_the_rule_fails_naming_the_crystal(self):
        # SOL-BOARD-REVIEW-PROOF-BASELINE-CLEAN.C3: Each rule the proof design's review adds fails on a fault seeded for it and passes the clean design
        for what, rules in (("no rules file", ()), ("an unrelated rule", ('(rule "Other"\n\t(constraint clearance (min 1mm)))',))):
            with self.subTest(what=what):
                found = self.found(*rules)
                self.assertEqual([(v.rule, v.location) for v in found], [("crystal_keepclear", f"{DESIGN.rules} crystal Y1")])
                self.assertIn("Y1 is a crystal, and the rules file holds no rule keeping the parts unrelated", found[0].message)

    def test_a_rule_exempting_every_other_part_holds_nothing_and_fails(self):
        # SOL-BOARD-REVIEW-PROOF-BASELINE-CLEAN.C3: Each rule the proof design's review adds fails on a fault seeded for it and passes the clean design
        blanket = KEEP_CLEAR.replace("&& B.Reference != 'C1'", "&& B.Reference != 'C1' && B.Reference != 'R1'")
        found = self.found(blanket)
        self.assertEqual([v.rule for v in found], ["crystal_keepclear"])
        self.assertIn("exempts every other part of the layout from the keep-clear of Y1", found[0].message)
        self.assertEqual(self.found(blanket.replace("&& B.Reference != 'R1'", "&& B.Reference != 'Z9'")), [],
                         "an exemption for a part not on the board leaves R1 under the rule")

    def test_a_figure_below_the_keep_clear_fails(self):
        # SOL-BOARD-REVIEW-PROOF-BASELINE-CLEAN.C3: Each rule the proof design's review adds fails on a fault seeded for it and passes the clean design
        found = self.found(KEEP_CLEAR.replace("25mm", "24.9mm"))
        self.assertEqual([v.rule for v in found], ["crystal_keepclear"])
        self.assertIn("keeps parts 24.9 mm from the courtyard of Y1, under the 25 mm", found[0].message)

    def test_a_rule_in_any_other_form_does_not_hold_the_keep_clear(self):
        # SOL-BOARD-REVIEW-PROOF-BASELINE-CLEAN.C3: Each rule the proof design's review adds fails on a fault seeded for it and passes the clean design
        for what, rule in (("a layer", KEEP_CLEAR[:-1] + '\n\t(layer "F.Cu"))'),
                           ("a severity", KEEP_CLEAR[:-1] + '\n\t(severity ignore))'),
                           ("a looser condition", KEEP_CLEAR.replace("A.Reference == 'Y1' && ", "")),
                           ("another crystal", KEEP_CLEAR.replace("'Y1'", "'Y2'")),
                           ("a different constraint", KEEP_CLEAR.replace("courtyard_clearance", "clearance")),
                           ("no unit", KEEP_CLEAR.replace("25mm", "25"))):
            with self.subTest(what=what):
                self.assertEqual([v.rule for v in self.found(rule)], ["crystal_keepclear"])

    def test_a_later_courtyard_rule_naming_the_crystal_that_loosens_it_fails(self):
        # SOL-BOARD-REVIEW-PROOF-BASELINE-CLEAN.C3: Each rule the proof design's review adds fails on a fault seeded for it and passes the clean design
        loosening = '(rule "Loose"\n\t(condition "A.Reference == \'Y1\'")\n\t(constraint courtyard_clearance (min 1mm)))'
        found = self.found(KEEP_CLEAR, loosening)
        self.assertEqual([v.rule for v in found], ["crystal_keepclear"])
        self.assertIn("rule 'Loose'", found[0].location)
        self.assertEqual(self.found(KEEP_CLEAR, '(rule "Else"\n\t(condition "A.Reference == \'J9\'")\n\t(constraint courtyard_clearance (min 1mm)))'), [])

    def test_each_crystal_of_the_board_needs_its_own_rule(self):
        # SOL-BOARD-REVIEW-PROOF-BASELINE-CLEAN.C3: Each rule the proof design's review adds fails on a fault seeded for it and passes the clean design
        two = tree_of(named_part("Crystal_A", "Y1", ("1", "/X", 1, 1)), named_part("Crystal_B", "Y2", ("1", "/X", 1, 1)),
                      named_part("R_0603", "R1", ("1", "/Y", 1, 1)))
        found = self.found(KEEP_CLEAR, tree=two)
        self.assertEqual([v.location for v in found], [f"{DESIGN.rules} crystal Y2"])
        self.assertEqual(self.found(KEEP_CLEAR, KEEP_CLEAR.replace("'Y1'", "'Y2'"), tree=two), [])


class TheGroundPadReliefsAreInTheRulesFileOfABoardWithGroundPads(unittest.TestCase):
    # SOL-BOARD-REVIEW-PROOF-BASELINE-CLEAN.C3: Each rule the proof design's review adds fails on a fault seeded for it and passes the clean design
    """A board with a pad on a ground net class needs the rule giving ground
    pads thermal reliefs, exempting only an exposed pad; a board with no such
    pad needs no rule.
    """

    BOARD = tree_of(named_part("QFN", "U4", ("1", "/G", 0.5, 0.5), ("2", "/S", 0.5, 0.5), ("21", "/G", 2.6, 2.6)),
                    named_part("R_0603", "R1", ("1", "/G", 1, 1), ("2", "/S", 1, 1)))
    CLASSES = {"Ground": {"/G"}, "Supply": {"/S"}, "Mains": set()}
    RELIEF = ('(rule "Ground pad reliefs"\n\t(condition "A.Type == \'Pad\' && A.hasNetclass(\'Ground\') && '
              '!(A.Reference == \'U4\' && A.Pad_Number == \'21\')")\n\t(constraint zone_connection thermal_reliefs))')

    def found(self, *rules, tree=None, classes=None):
        return board_check.ground_reliefs(DESIGN, rules_of(*rules) if rules else None, tree or self.BOARD, classes or self.CLASSES)

    def test_the_rule_in_its_form_passes_with_or_without_an_exposed_pad_exemption(self):
        # SOL-BOARD-REVIEW-PROOF-BASELINE-CLEAN.C3: Each rule the proof design's review adds fails on a fault seeded for it and passes the clean design
        self.assertEqual(self.found(self.RELIEF), [])
        plain = self.RELIEF.replace(" && !(A.Reference == 'U4' && A.Pad_Number == '21')", "")
        self.assertEqual(self.found(plain), [])

    def test_a_board_with_no_ground_pad_needs_no_rule(self):
        # SOL-BOARD-REVIEW-PROOF-BASELINE-CLEAN.C3: Each rule the proof design's review adds fails on a fault seeded for it and passes the clean design
        self.assertEqual(self.found(classes={"Supply": {"/S"}, "Ground": set()}), [])
        only_exposed = tree_of(named_part("QFN", "U4", ("1", "/S", 0.5, 0.5), ("2", "/S", 0.5, 0.5), ("21", "/G", 2.6, 2.6)))
        self.assertEqual(self.found(tree=only_exposed), [], "the exposed pad is exempt by its nature, so nothing is left to relieve")

    def test_a_board_whose_rules_file_lacks_the_rule_fails_naming_the_class(self):
        # SOL-BOARD-REVIEW-PROOF-BASELINE-CLEAN.C3: Each rule the proof design's review adds fails on a fault seeded for it and passes the clean design
        for what, rules in (("no rules file", ()), ("an unrelated rule", ('(rule "Other"\n\t(constraint clearance (min 1mm)))',))):
            with self.subTest(what=what):
                found = self.found(*rules)
                self.assertEqual([(v.rule, v.location) for v in found], [("ground_relief", f"{DESIGN.rules} ground class Ground")])
                self.assertIn("the rules file holds no rule giving them thermal reliefs", found[0].message)

    def test_a_rule_exempting_a_pad_that_is_not_an_exposed_pad_fails(self):
        # SOL-BOARD-REVIEW-PROOF-BASELINE-CLEAN.C3: Each rule the proof design's review adds fails on a fault seeded for it and passes the clean design
        for what, exempt in (("an ordinary pad", "R1' && A.Pad_Number == '1"), ("a pad the part lacks", "U4' && A.Pad_Number == '7"),
                             ("a pad of another class", "R1' && A.Pad_Number == '2")):
            with self.subTest(what=what):
                found = self.found(self.RELIEF.replace("U4' && A.Pad_Number == '21", exempt))
                self.assertEqual([v.rule for v in found], ["ground_relief"])
                self.assertIn("is not an exposed pad on a net of the class", found[0].message)

    def test_a_rule_in_any_other_form_does_not_hold_the_reliefs(self):
        # SOL-BOARD-REVIEW-PROOF-BASELINE-CLEAN.C3: Each rule the proof design's review adds fails on a fault seeded for it and passes the clean design
        for what, rule in (("a layer", self.RELIEF[:-1] + '\n\t(layer "F.Cu"))'),
                           ("a severity", self.RELIEF[:-1] + '\n\t(severity ignore))'),
                           ("a narrower condition", self.RELIEF.replace("A.Type == 'Pad' && ", "A.Type == 'Pad' && A.Reference == 'R1' && ")),
                           ("another class", self.RELIEF.replace("hasNetclass('Ground')", "hasNetclass('Supply')")),
                           ("full connection", self.RELIEF.replace("thermal_reliefs", "solid")),
                           ("a condition on footprints", self.RELIEF.replace("A.Type == 'Pad'", "A.Type == 'Footprint'"))):
            with self.subTest(what=what):
                self.assertEqual([v.rule for v in self.found(rule)], ["ground_relief"])

    def test_each_ground_class_with_pads_needs_its_own_rule(self):
        # SOL-BOARD-REVIEW-PROOF-BASELINE-CLEAN.C3: Each rule the proof design's review adds fails on a fault seeded for it and passes the clean design
        two = tree_of(named_part("R_0603", "R1", ("1", "/G", 1, 1), ("2", "/AG", 1, 1)))
        classes = {"Ground": {"/G"}, "Analog ground": {"/AG"}}
        plain = self.RELIEF.replace(" && !(A.Reference == 'U4' && A.Pad_Number == '21')", "")
        found = self.found(plain, tree=two, classes=classes)
        self.assertEqual([v.location for v in found], [f"{DESIGN.rules} ground class Analog ground"])


class KiCadsWorkmanshipFindingsNameTheirItem(unittest.TestCase):
    # SOL-BOARD-LAYOUT-WORKMANSHIP-ITEMS.C2: The pre-order check measures every rule-kind workmanship item and fails a board that breaks one

    def test_each_of_kicads_workmanship_findings_names_the_item_it_is(self):
        for kind, item in (("track_angle", "WORK-4"), ("track_segment_length", "WORK-5"), ("track_dangling", "WORK-6"),
                           ("via_dangling", "WORK-7")):
            with self.subTest(kind=kind):
                found = board_check.kicad_violation(DESIGN, {"type": kind, "description": "found", "items": []}, "a/a.kicad_pcb")
                self.assertEqual(found.rule, kind)
                self.assertIn(f"(workmanship item {item} ", found.message)
        other = board_check.kicad_violation(DESIGN, {"type": "clearance", "description": "found", "items": []}, "a/a.kicad_pcb")
        self.assertNotIn("workmanship", other.message)


class TheReportStatesEachFigureRead(Tree):
    # SOL-BOARD-LAYOUT-WORKMANSHIP-ITEMS.C2: The pre-order check measures every rule-kind workmanship item and fails a board that breaks one
    """Under each design's verdict line, one FIGURE line for every measured rule
    whose figure the design sets, before its violations.
    """

    def test_each_figure_read_has_its_line_under_its_designs_verdict(self):
        for path in ("a/a.kicad_pro", "a/a.kicad_sch", "a/a.kicad_pcb"):
            self.write(path, schematic() if path.endswith("sch") else "")

        def check(design, repository, kicad_cli, yaml, today, already, read=None):
            read.append(("WORK-8 narrowing", "WORK_NECK_MM", "1 mm off its net's pads"))
            return [board_check.Violation(design.project, "workmanship_width", "here", "a neck")]

        out = io.StringIO()
        with mock.patch.object(board_check, "tracked_files", return_value=["a/a.kicad_pro", "a/a.kicad_sch", "a/a.kicad_pcb"]), \
                mock.patch.object(board_check, "check_design", side_effect=check):
            status = board_check.report(self.root, "kicad-cli", "git", "10.0.7", TODAY, None, out)
        self.assertEqual(status, 1)
        self.assertEqual(out.getvalue().splitlines()[1:], [
            "DESIGN | a/a.kicad_pro | FAIL | 1 violation",
            "FIGURE | a/a.kicad_pro | WORK-8 narrowing | WORK_NECK_MM | 1 mm off its net's pads",
            "VIOLATION | a/a.kicad_pro | workmanship_width | here | a neck",
            "RESULT | FAIL | 1 of 1 designs failed"])


class EachViolationIsOneLine(unittest.TestCase):
    """SOL-HW-BOARD-RULE-CHECK-GATE.C6: The check's report names each design, its verdict and every violation in terms a builder can act on."""

    def test_a_violation_is_one_line_of_five_fields_whatever_its_text(self):
        line = board_check.Violation("a/a.kicad_pro", "clearance", "pad 1 | of R1\n@ (1, 2)",
                                     "Clearance violation\n(rule 'x|y')").line()
        self.assertNotIn("\n", line)
        self.assertEqual(line.split(" | "),
                         ["VIOLATION", "a/a.kicad_pro", "clearance", "pad 1 / of R1 @ (1, 2)", "Clearance violation (rule 'x/y')"])


# --- What the build round and the nightly run of the board tooling ----------------------


class TheDesignsReadingsAreListedWithoutKiCad(Tree):
    """A build round asks which files the designs read to tell whether a changed path reaches one, on a host that may lack KiCad."""

    def setUp(self):
        super().setUp()
        self.git("init", "-q")

    def commit(self):
        self.git("add", "-A")

    def listing(self, *arguments):
        out, error = io.StringIO(), io.StringIO()
        with mock.patch.object(board_check, "require_kicad", side_effect=AssertionError("KiCad is not needed to list")), \
                mock.patch.object(board_check, "require_yaml", side_effect=AssertionError("PyYAML is not needed to list")), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(error):
            status = board_check.main(["--root", self.root, "--list-reads", *arguments])
        return status, out.getvalue().splitlines(), error.getvalue()

    def design(self, folder: str, *sheets: str):
        self.write(f"{folder}/board.kicad_pro")
        self.write(f"{folder}/board.kicad_pcb")
        self.write(f"{folder}/board.kicad_sch", schematic(*sheets))

    def test_a_designs_folder_sheets_libraries_and_record_are_listed_and_nothing_else(self):
        # SOL-HW-GATE-IN-ROUND-AND-NIGHTLY.C1: The build round runs the board check when the branch changes a board design, anything it reads, or the check
        self.design("hw/m/board", "../power.kicad_sch")
        self.write("hw/m/board/notes.txt")
        self.write("hw/m/power.kicad_sch", schematic())
        self.write("hw/m/shared.pretty/R.kicad_mod")
        self.write("hw/m/shared.kicad_sym")
        self.write("hw/m/board/fp-lib-table", library_table("fp_lib_table", ("shared", "${KIPRJMOD}/../shared.pretty")))
        self.write("hw/m/board/sym-lib-table", library_table("sym_lib_table", ("syms", "${KIPRJMOD}/../shared.kicad_sym")))
        self.write("hw/m/separation-basis.yaml", SIGNED_RECORD)
        self.write("hw/m/other.txt")
        self.write("docs/unrelated.md")
        self.commit()
        status, lines, error = self.listing()
        self.assertEqual((status, error), (0, ""))
        self.assertEqual(lines, [
            "hw/m/board/", "hw/m/board/board.kicad_pcb", "hw/m/board/board.kicad_pro", "hw/m/board/board.kicad_sch",
            "hw/m/board/fp-lib-table", "hw/m/board/notes.txt", "hw/m/board/sym-lib-table", "hw/m/power.kicad_sch",
            "hw/m/separation-basis.yaml", "hw/m/shared.kicad_sym", "hw/m/shared.pretty/R.kicad_mod"])

    def test_a_record_not_yet_committed_that_is_nearer_than_a_committed_one_is_listed(self):
        # SOL-HW-GATE-IN-ROUND-AND-NIGHTLY.C1: The build round runs the board check when the branch changes a board design, anything it reads, or the check
        self.design("hw/m/board")
        self.write("hw/separation-basis.yaml", SIGNED_RECORD)
        self.commit()
        self.write("hw/m/separation-basis.yaml", SIGNED_RECORD)
        _, lines, _ = self.listing()
        self.assertIn("hw/m/separation-basis.yaml", lines)
        self.assertNotIn("hw/separation-basis.yaml", lines)

    def test_a_design_in_the_top_folder_reads_the_whole_repository(self):
        # SOL-HW-GATE-IN-ROUND-AND-NIGHTLY.C1: The build round runs the board check when the branch changes a board design, anything it reads, or the check
        self.design(".")
        self.write("docs/unrelated.md")
        self.commit()
        _, lines, _ = self.listing()
        self.assertIn(board_check.WHOLE_REPOSITORY, lines)
        self.assertIn("docs/unrelated.md", lines)

    def test_a_repository_with_no_design_lists_nothing_and_succeeds(self):
        # SOL-HW-GATE-IN-ROUND-AND-NIGHTLY.C1: The build round runs the board check when the branch changes a board design, anything it reads, or the check
        self.write("docs/unrelated.md")
        self.commit()
        self.assertEqual(self.listing(), (0, [], ""))

    def test_a_design_git_does_not_track_is_not_listed(self):
        # SOL-HW-GATE-IN-ROUND-AND-NIGHTLY.C1: The build round runs the board check when the branch changes a board design, anything it reads, or the check
        self.design("hw/tracked")
        self.commit()
        self.design("hw/loose")
        _, lines, _ = self.listing()
        self.assertIn("hw/tracked/", lines)
        self.assertFalse([line for line in lines if line.startswith("hw/loose")], lines)

    def test_a_folder_that_is_not_a_git_work_tree_cannot_be_listed(self):
        # SOL-HW-GATE-IN-ROUND-AND-NIGHTLY.C1: The build round runs the board check when the branch changes a board design, anything it reads, or the check
        with tempfile.TemporaryDirectory() as outside:
            out, error = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(error):
                status = board_check.main(["--root", outside, "--list-reads"])
        self.assertEqual(status, 2)
        self.assertEqual(out.getvalue(), "")
        self.assertTrue(error.getvalue().startswith("CANNOT RUN | "), error.getvalue())
        self.assertIn("not inside a git work tree", error.getvalue())

    def test_every_file_the_check_reads_of_the_designs_in_this_repository_is_listed(self):
        # SOL-HW-GATE-IN-ROUND-AND-NIGHTLY.C1: The build round runs the board check when the branch changes a board design, anything it reads, or the check
        files = board_check.tracked_files("git", REPO)
        reads = set(board_check.design_reads(REPO, files))
        designs, _, _ = board_check.discover(REPO, files)
        self.assertTrue(designs)
        repository = board_check.Repository(REPO, files)
        for design in designs:
            with self.subTest(design=design.project):
                self.assertIn(design.directory + "/", reads)
                read, _ = board_check.design_files(design, repository)
                self.assertEqual(set(read) - reads, set())
                record = board_check.find_record(REPO, design.directory, repository.tracked)
                self.assertIn(record, reads)
                pin_record = board_check.find_record(REPO, design.directory, repository.tracked, board_check.PIN_RECORD_NAME)
                self.assertIsNotNone(pin_record, "every tracked design is held to a pin allocation record")
                self.assertIn(pin_record, reads)


# --- The pin allocation record and the connectivity it holds a design to ---------


PIN_RECORD = """\
channels:
  - channel: heater_drive
    net: HEATER
    controller_pin: PA0
    connector: J2
    connector_pin: 1
    firmware_channel: kHeater
  - channel: pump_drive
    net: PUMP
    controller_pin: PA1
    connector: J2
    connector_pin: 2
  - channel: status_led
    net: LED
    controller_pin: PB3
"""


class PinRecordTree(Tree):
    """A pin allocation record beside a design two folders down, read as the check reads it."""

    design = board_check.Design("hardware/m/board/board.kicad_pro")

    def record(self, text: str, not_for_manufacture: bool = False):
        self.write("hardware/m/pin-allocation.yaml", text)
        found = board_check.find_record(self.root, self.design.directory, name=board_check.PIN_RECORD_NAME)
        return board_check.read_pin_record(board_check.require_yaml(), self.root, self.design, found, not_for_manufacture)

    def assertFails(self, text: str, location_end: str, words: str, not_for_manufacture: bool = False):
        channels, problems = self.record(text, not_for_manufacture)
        self.assertIsNone(channels)
        self.assertTrue(any(v.rule == "pin_allocation" and v.location.endswith(location_end) and words in v.message
                            for v in problems), [(v.location, v.message) for v in problems])


class ThePinAllocationRecordMustBeUsable(PinRecordTree):
    def test_a_complete_record_gives_each_channel_and_ignores_the_firmware_keys(self):
        # SOL-HW-CONNECTIVITY-CHECK.C3: A design with no usable pin allocation record fails, and a synthetic record passes only a design not for manufacture
        channels, problems = self.record(PIN_RECORD)
        self.assertEqual(problems, [])
        self.assertEqual([(c.channel, c.net, c.controller_pin, c.connector, c.connector_pin) for c in channels],
                         [("heater_drive", "HEATER", "PA0", "J2", "1"), ("pump_drive", "PUMP", "PA1", "J2", "2"),
                          ("status_led", "LED", "PB3", None, None)])

    def test_a_connector_pin_written_as_a_number_is_read_as_the_pin_number(self):
        # SOL-HW-CONNECTIVITY-CHECK.C3: A design with no usable pin allocation record fails, and a synthetic record passes only a design not for manufacture
        channels, _ = self.record(PIN_RECORD.replace("connector_pin: 1", "connector_pin: 1\n    firmware_sensor: kX"))
        self.assertEqual(channels[0].connector_pin, "1")

    def test_a_record_is_found_by_its_own_name_and_the_nearest_wins(self):
        # SOL-HW-CONNECTIVITY-CHECK.C3: A design with no usable pin allocation record fails, and a synthetic record passes only a design not for manufacture
        self.write("pin-allocation.yaml", PIN_RECORD)
        self.write("hardware/m/separation-basis.yaml", SIGNED_RECORD)
        self.write("hardware/m/board/pin-allocation.yaml", PIN_RECORD)
        self.assertEqual(board_check.find_record(self.root, self.design.directory, name=board_check.PIN_RECORD_NAME),
                         "hardware/m/board/pin-allocation.yaml")
        self.assertEqual(board_check.find_record(self.root, "hardware/m", name=board_check.PIN_RECORD_NAME),
                         "pin-allocation.yaml", "the separation basis record beside it is not the record asked for")
        self.assertEqual(board_check.find_record(self.root, "hardware/m"), "hardware/m/separation-basis.yaml")

    def test_a_design_with_no_record_at_or_above_it_fails(self):
        # SOL-HW-CONNECTIVITY-CHECK.C3: A design with no usable pin allocation record fails, and a synthetic record passes only a design not for manufacture
        channels, problems = board_check.read_pin_record(board_check.require_yaml(), self.root, self.design, None, True)
        self.assertIsNone(channels)
        self.assertEqual([v.rule for v in problems], ["pin_allocation"])
        self.assertIn("no pin-allocation.yaml", problems[0].message)

    def test_a_record_that_cannot_be_parsed_fails(self):
        # SOL-HW-CONNECTIVITY-CHECK.C3: A design with no usable pin allocation record fails, and a synthetic record passes only a design not for manufacture
        self.assertFails("channels: [unclosed\n", "pin-allocation.yaml", "cannot be parsed")

    def test_a_record_that_is_not_a_mapping_fails(self):
        # SOL-HW-CONNECTIVITY-CHECK.C3: A design with no usable pin allocation record fails, and a synthetic record passes only a design not for manufacture
        self.assertFails("- just\n- a list\n", "pin-allocation.yaml", "not a mapping")
        self.assertFails("", "pin-allocation.yaml", "not a mapping")

    def test_a_record_giving_a_key_twice_or_using_a_merge_key_fails(self):
        # SOL-HW-CONNECTIVITY-CHECK.C3: A design with no usable pin allocation record fails, and a synthetic record passes only a design not for manufacture
        self.assertFails(PIN_RECORD.replace("    net: PUMP\n", "    net: PUMP\n    net: LED\n"), "pin-allocation.yaml", "more than once")
        self.assertFails("base: &b {channel: x}\nchannels:\n  - <<: *b\n    net: N\n    controller_pin: PA0\n",
                         "pin-allocation.yaml", "merge key")

    def test_a_record_with_no_channels_key_fails(self):
        # SOL-HW-CONNECTIVITY-CHECK.C3: A design with no usable pin allocation record fails, and a synthetic record passes only a design not for manufacture
        self.assertFails("chanels: []\n", "channels", "lacks channels")
        self.assertFails("channels: not-a-list\n", "channels", "lacks channels")

    def test_a_record_listing_no_channel_fails_since_it_would_hold_a_design_to_nothing(self):
        # SOL-HW-CONNECTIVITY-CHECK.C3: A design with no usable pin allocation record fails, and a synthetic record passes only a design not for manufacture
        self.assertFails("channels: []\n", "channels", "lists no channel")
        self.assertFails("synthetic: true\nchannels:\n", "channels", "lacks channels", not_for_manufacture=True)

    def test_an_entry_missing_a_required_key_fails_naming_the_key_and_the_channel(self):
        # SOL-HW-CONNECTIVITY-CHECK.C3: A design with no usable pin allocation record fails, and a synthetic record passes only a design not for manufacture
        for key in ("net", "controller_pin"):
            with self.subTest(key=key):
                text = PIN_RECORD.replace(f"    {key}: {'HEATER' if key == 'net' else 'PA0'}\n", "", 1)
                self.assertFails(text, "channel heater_drive", f"lacks {key}")
        self.assertFails(PIN_RECORD.replace("  - channel: heater_drive\n", "  - net: X\n", 1).replace("    net: HEATER\n", ""), "channels[0]", "lacks channel")

    def test_an_entry_that_is_not_a_mapping_or_holds_a_blank_value_fails(self):
        # SOL-HW-CONNECTIVITY-CHECK.C3: A design with no usable pin allocation record fails, and a synthetic record passes only a design not for manufacture
        self.assertFails("channels:\n  - just-text\n", "channels[0]", "not a mapping")
        self.assertFails(PIN_RECORD.replace("net: HEATER", "net: ''"), "channel heater_drive", "net is ''")
        self.assertFails(PIN_RECORD.replace("controller_pin: PA0", "controller_pin: [PA0]"), "channel heater_drive", "controller_pin is")

    def test_a_connector_without_its_pin_or_a_pin_without_its_connector_fails(self):
        # SOL-HW-CONNECTIVITY-CHECK.C3: A design with no usable pin allocation record fails, and a synthetic record passes only a design not for manufacture
        self.assertFails(PIN_RECORD.replace("    connector_pin: 1\n", "", 1), "channel heater_drive", "only one of connector and connector_pin")
        self.assertFails(PIN_RECORD.replace("    connector: J2\n    connector_pin: 1\n", "    connector_pin: 1\n", 1),
                         "channel heater_drive", "only one of connector and connector_pin")

    def test_a_channel_net_or_pin_listed_twice_fails(self):
        # SOL-HW-CONNECTIVITY-CHECK.C3: A design with no usable pin allocation record fails, and a synthetic record passes only a design not for manufacture
        self.assertFails(PIN_RECORD.replace("channel: pump_drive", "channel: heater_drive"), "channel heater_drive", "channel heater_drive is listed")
        self.assertFails(PIN_RECORD.replace("net: PUMP", "net: HEATER"), "channel pump_drive", "net HEATER is listed")
        self.assertFails(PIN_RECORD.replace("controller_pin: PA1", "controller_pin: PA0"), "channel pump_drive", "controller pin PA0 is listed")
        self.assertFails(PIN_RECORD.replace("connector_pin: 2", "connector_pin: 1"), "channel pump_drive", "connector pin J2 pin 1 is listed")

    def test_a_synthetic_record_passes_only_a_design_marked_not_for_manufacture(self):
        # SOL-HW-CONNECTIVITY-CHECK.C3: A design with no usable pin allocation record fails, and a synthetic record passes only a design not for manufacture
        synthetic = "synthetic: true\n" + PIN_RECORD
        self.assertFails(synthetic, "synthetic", "marked synthetic", not_for_manufacture=False)
        channels, problems = self.record(synthetic, not_for_manufacture=True)
        self.assertEqual((len(channels), problems), (3, []))

    def test_a_record_not_marked_synthetic_passes_either_kind_of_design(self):
        # SOL-HW-CONNECTIVITY-CHECK.C3: A design with no usable pin allocation record fails, and a synthetic record passes only a design not for manufacture
        for flag in (True, False):
            for text in (PIN_RECORD, "synthetic: false\n" + PIN_RECORD):
                channels, problems = self.record(text, flag)
                self.assertEqual((len(channels), problems), (3, []), (flag, text[:20]))

    def test_a_synthetic_mark_that_is_not_true_or_false_fails(self):
        # SOL-HW-CONNECTIVITY-CHECK.C3: A design with no usable pin allocation record fails, and a synthetic record passes only a design not for manufacture
        self.assertFails("synthetic: 'yes'\n" + PIN_RECORD, "synthetic", "synthetic is 'yes'", not_for_manufacture=True)


def netlist_text(nets: dict) -> str:
    """KiCad's netlist of the given nets, each name -> its (reference, pin number, pin name or None) nodes."""
    parts = []
    for code, (name, nodes) in enumerate(nets.items(), 1):
        body = "".join(f'(node (ref "{ref}") (pin "{pin}")' + (f' (pinfunction "{function}")' if function else "") + ' (pintype "passive"))'
                       for ref, pin, function in nodes)
        parts.append(f'(net (code "{code}") (name "{name}") (class "Default") {body})')
    return "(export (version \"E\") (nets " + " ".join(parts) + "))"


#: A design that satisfies PIN_RECORD: the controller U1 names its pins as KiCad's netlist writes them, with the pin number appended.
GOOD_NETS = {
    "/HEATER": [("J2", "1", "Pin_1_1"), ("U1", "7", "PA0_7"), ("R1", "1", None)],
    "/PUMP": [("J2", "2", "Pin_2_2"), ("U1", "8", "PA1_8")],
    "LED": [("U1", "9", "AREF/PB3_9"), ("R2", "1", None)],
    "/GND": [("U1", "1", "VSS_1"), ("R2", "2", None), ("J3", "1", "Pin_1_1")],
    "unconnected-(U1-PA5-Pad10)": [("U1", "10", "PA5_10")],
}


class TheDesignIsHeldToTheRecordsChannels(PinRecordTree):
    def channels(self, text: str = PIN_RECORD):
        channels, problems = self.record(text)
        self.assertEqual(problems, [])
        return channels

    def violations(self, nets: dict, text: str = PIN_RECORD):
        nodes = board_check.schematic_pin_nodes(sexpr.parse_one(netlist_text(nets)))
        found = board_check.connectivity(self.design_under_check(), "hardware/m/pin-allocation.yaml", self.channels(text), nodes)
        self.assertEqual({v.rule for v in found} - {"connectivity"}, set())
        return [(v.location, v.message) for v in found]

    def design_under_check(self):
        return board_check.Design("hardware/m/board/board.kicad_pro")

    def test_a_design_whose_channels_all_land_where_the_record_says_and_connects_nothing_else_passes(self):
        # SOL-HW-CONNECTIVITY-CHECK.C2: A channel the record lists and the design lacks, and a net on a pin the record omits, each fail the check
        self.assertEqual(self.violations(GOOD_NETS), [])

    def test_the_pin_function_keeps_its_name_without_the_number_kicad_appends(self):
        # SOL-HW-CONNECTIVITY-CHECK.C1: A channel whose net does not reach the pin and connector its record entry names fails the check
        nodes = board_check.schematic_pin_nodes(sexpr.parse_one(netlist_text(GOOD_NETS)))
        self.assertEqual([pin.names() for pin in nodes["LED"]], [["AREF", "PB3"], []])
        self.assertEqual([pin.ports() for pin in nodes["LED"]], [["PB3"], []])
        self.assertEqual(nodes["/HEATER"][1].describe(), "U1 pin 7")

    def test_a_net_on_the_wrong_controller_pin_fails_naming_the_channel_net_and_both_pins(self):
        # SOL-HW-CONNECTIVITY-CHECK.C1: A channel whose net does not reach the pin and connector its record entry names fails the check
        nets = dict(GOOD_NETS)
        nets["/HEATER"] = [("J2", "1", "Pin_1_1"), ("U1", "8", "PA1_8")]
        nets["/PUMP"] = [("J2", "2", "Pin_2_2"), ("U1", "7", "PA0_7")]
        found = self.violations(nets)
        self.assertEqual(len(found), 2, found)
        location, message = found[0]
        self.assertEqual(location, "hardware/m/pin-allocation.yaml channel heater_drive")
        for words in ("heater_drive", "/HEATER", "controller pin PA1", "controller pin PA0"):
            self.assertIn(words, message)

    def test_a_net_that_reaches_no_controller_pin_fails_saying_so(self):
        # SOL-HW-CONNECTIVITY-CHECK.C1: A channel whose net does not reach the pin and connector its record entry names fails the check
        nets = dict(GOOD_NETS)
        nets["/PUMP"] = [("J2", "2", "Pin_2_2")]
        found = self.violations(nets)
        self.assertEqual(len(found), 1, found)
        self.assertIn("reaches no controller pin, where the record names controller pin PA1", found[0][1])

    def test_a_net_on_the_wrong_pin_of_its_connector_fails_naming_both_pins(self):
        # SOL-HW-CONNECTIVITY-CHECK.C1: A channel whose net does not reach the pin and connector its record entry names fails the check
        nets = dict(GOOD_NETS)
        nets["/HEATER"] = [("J2", "2", "Pin_2_2"), ("U1", "7", "PA0_7")]
        nets["/PUMP"] = [("J2", "1", "Pin_1_1"), ("U1", "8", "PA1_8")]
        found = self.violations(nets)
        self.assertEqual(len(found), 2, found)
        self.assertIn("channel heater_drive: net /HEATER reaches connector pin J2 pin 2, where the record names connector pin J2 pin 1", found[0][1])

    def test_a_net_on_the_wrong_connector_fails_naming_the_connector_it_reached(self):
        # SOL-HW-CONNECTIVITY-CHECK.C1: A channel whose net does not reach the pin and connector its record entry names fails the check
        nets = dict(GOOD_NETS)
        nets["/HEATER"] = [("J3", "1", "Pin_1_1"), ("U1", "7", "PA0_7")]
        nets["/GND"] = [("U1", "1", "VSS_1")]
        found = self.violations(nets)
        self.assertEqual(len(found), 1, found)
        self.assertIn("reaches connector pin J3 pin 1, where the record names connector pin J2 pin 1", found[0][1])

    def test_a_channel_with_no_connector_is_held_to_its_controller_pin_only(self):
        # SOL-HW-CONNECTIVITY-CHECK.C1: A channel whose net does not reach the pin and connector its record entry names fails the check
        nets = dict(GOOD_NETS)
        nets["LED"] = [("U1", "9", "AREF/PB3_9"), ("J2", "1", "Pin_1_1")]
        nets["/HEATER"] = [("U1", "7", "PA0_7")]
        found = self.violations(nets)
        self.assertEqual([location for location, _ in found], ["hardware/m/pin-allocation.yaml channel heater_drive"], found)
        self.assertIn("channel heater_drive", found[0][1])
        nets["LED"] = [("U1", "4", "PB4_4")]
        found = self.violations(nets)
        self.assertTrue(any("channel status_led: net LED reaches controller pin PB4, where the record names controller pin PB3" in m
                            for _, m in found), found)

    def test_a_net_is_matched_with_or_without_the_slash_of_the_top_sheet(self):
        # SOL-HW-CONNECTIVITY-CHECK.C1: A channel whose net does not reach the pin and connector its record entry names fails the check
        self.assertEqual(self.violations(GOOD_NETS, PIN_RECORD.replace("net: HEATER", "net: /HEATER")), [])
        self.assertEqual(self.violations(GOOD_NETS, PIN_RECORD.replace("net: LED", "net: /LED")), [])

    def test_a_listed_channel_the_design_lacks_fails_naming_the_channel_net_and_pins(self):
        # SOL-HW-CONNECTIVITY-CHECK.C2: A channel the record lists and the design lacks, and a net on a pin the record omits, each fail the check
        nets = {name: pins for name, pins in GOOD_NETS.items() if name != "/PUMP"}
        found = self.violations(nets)
        pump = [(location, message) for location, message in found if "channel pump_drive" in location]
        self.assertEqual(len(pump), 1, found)
        for words in ("channel pump_drive", "net PUMP", "controller pin PA1", "connector pin J2 pin 2"):
            self.assertIn(words, pump[0][1])
        self.assertIn("which the design does not have", pump[0][1])

    def test_a_net_on_a_controller_pin_the_record_omits_fails_naming_the_net_and_pin(self):
        # SOL-HW-CONNECTIVITY-CHECK.C2: A channel the record lists and the design lacks, and a net on a pin the record omits, each fail the check
        nets = dict(GOOD_NETS)
        nets["/EXTRA"] = [("U1", "5", "PA4_5"), ("R3", "1", None)]
        found = self.violations(nets)
        self.assertEqual(len(found), 1, found)
        self.assertEqual(found[0][0], "hardware/m/board/board.kicad_sch U1 pin 5")
        self.assertIn("net /EXTRA is on controller pin PA4 (U1 pin 5), which the record does not list", found[0][1])

    def test_a_net_on_a_connector_pin_the_record_omits_fails_naming_the_net_and_pin(self):
        # SOL-HW-CONNECTIVITY-CHECK.C2: A channel the record lists and the design lacks, and a net on a pin the record omits, each fail the check
        nets = dict(GOOD_NETS)
        nets["/SPARE"] = [("J2", "3", "Pin_3_3"), ("R3", "1", None)]
        found = self.violations(nets)
        self.assertEqual(len(found), 1, found)
        self.assertEqual(found[0][0], "hardware/m/board/board.kicad_sch J2 pin 3")
        self.assertIn("net /SPARE is on connector pin J2 pin 3, which the record does not list", found[0][1])

    def test_a_pin_nothing_is_connected_to_is_not_a_net_on_an_omitted_pin(self):
        # SOL-HW-CONNECTIVITY-CHECK.C2: A channel the record lists and the design lacks, and a net on a pin the record omits, each fail the check
        self.assertEqual(self.violations(GOOD_NETS), [])
        nets = dict(GOOD_NETS)
        nets["unconnected-(J2-Pad3)"] = [("J2", "3", "Pin_3_3")]
        self.assertEqual(self.violations(nets), [])

    def test_pins_that_are_not_port_pins_or_not_on_a_connector_the_record_names_are_not_judged(self):
        # SOL-HW-CONNECTIVITY-CHECK.C2: A channel the record lists and the design lacks, and a net on a pin the record omits, each fail the check
        nets = dict(GOOD_NETS)
        nets["/RAIL"] = [("U1", "2", "VDD_2"), ("U1", "3", "BOOT0_3"), ("C1", "1", None), ("J3", "2", "Pin_2_2")]
        self.assertEqual(self.violations(nets), [])

    def test_a_pin_that_answers_to_an_alternate_function_name_is_its_port_pin(self):
        # SOL-HW-CONNECTIVITY-CHECK.C1: A channel whose net does not reach the pin and connector its record entry names fails the check
        nets = dict(GOOD_NETS)
        nets["LED"] = [("U1", "9", "TIM2_CH1/PB3_9")]
        self.assertEqual(self.violations(nets), [])

    def test_a_netlist_node_with_no_pin_name_is_read_as_a_pin_with_none(self):
        # SOL-HW-CONNECTIVITY-CHECK.C1: A channel whose net does not reach the pin and connector its record entry names fails the check
        nodes = board_check.schematic_pin_nodes(sexpr.parse_one(netlist_text({"/N": [("R1", "1", None)], "/M": []})))
        self.assertEqual([(pin.ref, pin.pin, pin.function) for pin in nodes["/N"]], [("R1", "1", "")])
        self.assertEqual(nodes["/M"], [])
        self.assertEqual(board_check.schematic_pin_nodes(sexpr.parse_one("(export)")), {})


class ThePinAllocationRecordIsAmongWhatADesignReads(Tree):
    def test_the_record_a_design_is_held_to_is_listed_with_the_separation_basis_record(self):
        # SOL-HW-CONNECTIVITY-CHECK.C5: Every tracked design passes the connectivity check, and a change to a pin allocation record re-runs the board tier in the build round
        self.write("hardware/m/board/board.kicad_pro", "{}")
        self.write("hardware/m/board/board.kicad_sch", "(kicad_sch)")
        self.write("hardware/m/board/board.kicad_pcb", "(kicad_pcb)")
        self.write("hardware/m/pin-allocation.yaml", PIN_RECORD)
        self.write("hardware/m/separation-basis.yaml", SIGNED_RECORD)
        self.git("init", "-q")
        self.git("add", "-A")
        reads = board_check.design_reads(self.root, board_check.tracked_files("git", self.root))
        self.assertIn("hardware/m/pin-allocation.yaml", reads)
        self.assertIn("hardware/m/separation-basis.yaml", reads)

    def test_an_uncommitted_record_beside_the_design_is_listed_too(self):
        # SOL-HW-CONNECTIVITY-CHECK.C5: Every tracked design passes the connectivity check, and a change to a pin allocation record re-runs the board tier in the build round
        self.write("hardware/m/board/board.kicad_pro", "{}")
        self.write("hardware/m/board/board.kicad_sch", "(kicad_sch)")
        self.write("hardware/m/board/board.kicad_pcb", "(kicad_pcb)")
        self.git("init", "-q")
        self.git("add", "-A")
        self.write("hardware/m/board/pin-allocation.yaml", PIN_RECORD)
        reads = board_check.design_reads(self.root, board_check.tracked_files("git", self.root))
        self.assertIn("hardware/m/board/pin-allocation.yaml", reads)


DERATING_RECORD = """\
source: a synthetic policy
classes:
  - class: resistor
    voltage:
      share: 0.8
      source: synthetic
    power:
      share: 0.5
      source: synthetic
    temperature:
      share: 1
      source: synthetic
  - class: connector
    voltage:
      share: 0.7
      source: synthetic
    power:
      share: 0.6
      source: synthetic
    temperature:
      share: 0.9
      source: synthetic
"""

PIN_LIMITS_RECORD = """\
domains:
  - name: logic
    rail: V_LOGIC
    highest_voltage_v: 3.3
  - name: sense
    rail: V_SENSE
    highest_voltage_v: 5
parts:
  - lcsc: C100
    source:
      document: synthetic datasheet
      revision: A
      section: absolute maximum ratings
      read_on: 2026-10-01
    pins:
      - pin: PA0
        domain: logic
        absolute_max_v: 3.6
        absolute_min_v: -0.3
        tolerates_driven_unpowered: false
      - pin: 7
        domain: sense
        absolute_max_v: 5.5
        absolute_min_v: 0
        tolerates_driven_unpowered: true
"""


class PolicyRecordTree(Tree):
    """The derating policy and pin-limit records beside a design two folders down, read as the check reads them."""

    design = board_check.Design("hardware/m/board/board.kicad_pro")
    name = ""
    reader = None

    def read(self, text: str, not_for_manufacture: bool = False):
        self.write(f"hardware/m/{self.name}", text)
        return type(self).reader(board_check.require_yaml(), self.root, self.everything(), self.design, not_for_manufacture)

    def assertFails(self, text: str, location_end: str, words: str, not_for_manufacture: bool = False):
        problems = self.read(text, not_for_manufacture)
        self.assertTrue(any(v.rule == self.rule and v.location.endswith(location_end) and words in v.message
                            for v in problems), [(v.location, v.message) for v in problems])


class TheDeratingPolicyRecordIsRead(PolicyRecordTree):
    name = "derating-policy.yaml"
    rule = "derating_record"
    reader = staticmethod(board_check.read_derating)

    def changed(self, old: str, new: str) -> str:
        self.assertIn(old, DERATING_RECORD)
        return DERATING_RECORD.replace(old, new, 1)

    def test_a_complete_synthetic_record_is_accepted_for_a_design_not_for_manufacture(self):
        # SOL-PRE-ORDER-CHECK-READS-RECORD-KEYS.C1: The check accepts and reads every key the record decisions define, fails one they do not, and is shown to on a seeded copy
        self.assertEqual(self.read(DERATING_RECORD + "synthetic: true\n", not_for_manufacture=True), [])

    def test_a_design_whose_folders_hold_no_derating_record_is_not_failed(self):
        # SOL-PRE-ORDER-CHECK-READS-RECORD-KEYS.C1: The check accepts and reads every key the record decisions define, fails one they do not, and is shown to on a seeded copy
        self.write("hardware/m/board/board.kicad_pro", "{}")
        self.assertEqual(board_check.read_derating(board_check.require_yaml(), self.root, self.everything(), self.design, False), [])

    def test_a_synthetic_record_passes_only_a_design_not_for_manufacture(self):
        # SOL-PRE-ORDER-CHECK-READS-RECORD-KEYS.C1: The check accepts and reads every key the record decisions define, fails one they do not, and is shown to on a seeded copy
        self.assertFails(DERATING_RECORD + "synthetic: true\n", "derating-policy.yaml synthetic", "marked synthetic")
        self.assertEqual(self.read(DERATING_RECORD), [])
        self.assertFails(DERATING_RECORD + "synthetic: 'true'\n", "derating-policy.yaml synthetic", "write true or false", True)

    def test_a_share_must_be_above_zero_and_at_most_one(self):
        # SOL-PRE-ORDER-CHECK-READS-RECORD-KEYS.C1: The check accepts and reads every key the record decisions define, fails one they do not, and is shown to on a seeded copy
        for bad in ("0", "-0.5", "1.01", "2", "'0.8'", "true", "null"):
            with self.subTest(share=bad):
                self.assertFails(self.changed("share: 0.8", f"share: {bad}"), "classes[0].voltage.share", "above zero and at most one")
        for good in ("1", "0.01", "1.0"):
            self.assertEqual(self.read(self.changed("share: 0.8", f"share: {good}")), [])

    def test_a_missing_or_unusable_part_of_the_record_fails_by_name(self):
        # SOL-PRE-ORDER-CHECK-READS-RECORD-KEYS.C1: The check accepts and reads every key the record decisions define, fails one they do not, and is shown to on a seeded copy
        self.assertFails(DERATING_RECORD.replace("source: a synthetic policy\n", ""), "derating-policy.yaml source", "lacks source")
        self.assertFails(self.changed("source: a synthetic policy", "source: ''"), "derating-policy.yaml source", "non-empty string")
        self.assertFails("source: x\n", "derating-policy.yaml classes", "lacks classes")
        self.assertFails("source: x\nclasses: []\n", "classes", "lists no part classes")
        self.assertFails("source: x\nclasses: resistor\n", "classes", "not a list")
        self.assertFails(self.changed("  - class: resistor\n", "  - class: ''\n"), "classes[0].class", "non-empty string")
        self.assertFails(self.changed("    power:\n      share: 0.5\n      source: synthetic\n", ""), "classes[0].power", "lacks power")
        self.assertFails(self.changed("      share: 0.8\n      source: synthetic", "      source: synthetic"), "classes[0].voltage.share", "lacks share")
        self.assertFails(self.changed("      share: 0.8\n      source: synthetic", "      share: 0.8"), "classes[0].voltage.source", "lacks source")
        self.assertFails(self.changed("share: 0.8\n      source: synthetic", "share: 0.8\n      source: ''"), "classes[0].voltage.source", "non-empty string")
        self.assertFails(self.changed("    voltage:\n      share: 0.8\n      source: synthetic\n", "    voltage: 0.8\n"),
                         "classes[0].voltage", "not a mapping")
        self.assertFails("- not a mapping\n", "derating-policy.yaml", "not a mapping")
        self.assertFails("classes: [unclosed\n", "derating-policy.yaml", "cannot be parsed")

    def test_a_key_the_decision_does_not_name_is_refused_by_name_at_every_depth(self):
        # SOL-PRE-ORDER-CHECK-READS-RECORD-KEYS.C1: The check accepts and reads every key the record decisions define, fails one they do not, and is shown to on a seeded copy
        for old, new, where, key in (
                ("source: a synthetic policy", "sources: a synthetic policy", "derating-policy.yaml sources", "sources"),
                ("classes:", "classess:", "derating-policy.yaml classess", "classess"),
                ("  - class: resistor", "  - klass: resistor", "classes[0].klass", "klass"),
                ("    power:\n      share", "    powers:\n      share", "classes[0].powers", "powers"),
                ("      share: 0.8", "      shre: 0.8", "classes[0].voltage.shre", "shre"),
                ("      share: 0.5\n      source: synthetic", "      share: 0.5\n      source: synthetic\n      note: x",
                 "classes[0].power.note", "note")):
            with self.subTest(where=where):
                problems = self.read(self.changed(old, new))
                self.assertTrue([v for v in problems if v.location.endswith(where) and f"holds the key '{key}'" in v.message],
                                [(v.location, v.message) for v in problems])
                self.assertEqual({v.rule for v in problems}, {"derating_record"})

    def test_a_key_given_twice_or_a_record_the_repository_does_not_track_fails(self):
        # SOL-PRE-ORDER-CHECK-READS-RECORD-KEYS.C1: The check accepts and reads every key the record decisions define, fails one they do not, and is shown to on a seeded copy
        self.assertFails(DERATING_RECORD + "source: again\n", "derating-policy.yaml", "more than once")
        self.write("hardware/m/derating-policy.yaml", DERATING_RECORD)
        problems = board_check.read_derating(board_check.require_yaml(), self.root, board_check.Repository(self.root, []), self.design, False)
        self.assertEqual([v.rule for v in problems], ["derating_record"])
        self.assertIn("not tracked", problems[0].message)


class ThePinLimitRecordIsRead(PolicyRecordTree):
    name = "pin-limits.yaml"
    rule = "pin_limits_record"
    reader = staticmethod(board_check.read_pin_limits)

    def changed(self, old: str, new: str) -> str:
        self.assertIn(old, PIN_LIMITS_RECORD)
        return PIN_LIMITS_RECORD.replace(old, new, 1)

    def test_a_complete_synthetic_record_is_accepted_for_a_design_not_for_manufacture(self):
        # SOL-PRE-ORDER-CHECK-READS-RECORD-KEYS.C1: The check accepts and reads every key the record decisions define, fails one they do not, and is shown to on a seeded copy
        self.assertEqual(self.read(PIN_LIMITS_RECORD + "synthetic: true\n", not_for_manufacture=True), [])

    def test_a_design_whose_folders_hold_no_pin_limit_record_is_not_failed(self):
        # SOL-PRE-ORDER-CHECK-READS-RECORD-KEYS.C1: The check accepts and reads every key the record decisions define, fails one they do not, and is shown to on a seeded copy
        self.assertEqual(board_check.read_pin_limits(board_check.require_yaml(), self.root, self.everything(), self.design, False), [])

    def test_a_synthetic_record_passes_only_a_design_not_for_manufacture(self):
        # SOL-PRE-ORDER-CHECK-READS-RECORD-KEYS.C1: The check accepts and reads every key the record decisions define, fails one they do not, and is shown to on a seeded copy
        self.assertFails(PIN_LIMITS_RECORD + "synthetic: true\n", "pin-limits.yaml synthetic", "marked synthetic")
        self.assertEqual(self.read(PIN_LIMITS_RECORD), [])

    def test_a_lowest_voltage_above_the_highest_fails(self):
        # SOL-PRE-ORDER-CHECK-READS-RECORD-KEYS.C1: The check accepts and reads every key the record decisions define, fails one they do not, and is shown to on a seeded copy
        self.assertFails(self.changed("absolute_min_v: -0.3", "absolute_min_v: 4"), "parts[0].pins[0].absolute_min_v", "above absolute_max_v")
        self.assertEqual(self.read(self.changed("absolute_min_v: -0.3", "absolute_min_v: 3.6")), [])
        for bad in ("'3'", "true", ".nan", "null"):
            with self.subTest(absolute_max_v=bad):
                self.assertFails(self.changed("absolute_max_v: 3.6", f"absolute_max_v: {bad}"), "parts[0].pins[0].absolute_max_v", "not a number")

    def test_a_pin_must_name_a_domain_the_record_lists(self):
        # SOL-PRE-ORDER-CHECK-READS-RECORD-KEYS.C1: The check accepts and reads every key the record decisions define, fails one they do not, and is shown to on a seeded copy
        self.assertFails(self.changed("domain: logic", "domain: analogue"), "parts[0].pins[0].domain", "which domains does not list")
        self.assertFails(self.changed("domain: logic", "domain: ''"), "parts[0].pins[0].domain", "non-empty string")

    def test_a_pin_is_a_name_or_a_number_and_the_tolerance_is_true_or_false(self):
        # SOL-PRE-ORDER-CHECK-READS-RECORD-KEYS.C1: The check accepts and reads every key the record decisions define, fails one they do not, and is shown to on a seeded copy
        for bad in ("true", "''", "[1]", "1.5", "null"):
            with self.subTest(pin=bad):
                self.assertFails(self.changed("pin: PA0", f"pin: {bad}"), "parts[0].pins[0].pin", "name or number")
        for bad in ("'false'", "1", "null"):
            with self.subTest(tolerates=bad):
                self.assertFails(self.changed("tolerates_driven_unpowered: false", f"tolerates_driven_unpowered: {bad}"),
                                 "parts[0].pins[0].tolerates_driven_unpowered", "true or false")

    def test_a_date_that_is_not_an_iso_date_fails(self):
        # SOL-PRE-ORDER-CHECK-READS-RECORD-KEYS.C1: The check accepts and reads every key the record decisions define, fails one they do not, and is shown to on a seeded copy
        for bad in ("'12/10/2026'", "'2026-02-30'", "2026-10-01T09:00:00", "yesterday", "null"):
            with self.subTest(read_on=bad):
                self.assertFails(self.changed("read_on: 2026-10-01", f"read_on: {bad}"), "parts[0].source.read_on", "not a valid calendar date")

    def test_a_missing_or_unusable_part_of_the_record_fails_by_name(self):
        # SOL-PRE-ORDER-CHECK-READS-RECORD-KEYS.C1: The check accepts and reads every key the record decisions define, fails one they do not, and is shown to on a seeded copy
        self.assertFails("parts: []\n", "pin-limits.yaml domains", "lacks domains")
        self.assertFails("domains: []\nparts: []\n", "domains", "lists no power domains")
        self.assertFails(PIN_LIMITS_RECORD.split("parts:")[0], "pin-limits.yaml parts", "lacks parts")
        self.assertFails(self.changed("    rail: V_LOGIC\n", ""), "domains[0].rail", "lacks rail")
        self.assertFails(self.changed("highest_voltage_v: 3.3", "highest_voltage_v: high"), "domains[0].highest_voltage_v", "not a number")
        self.assertFails(self.changed("      section: absolute maximum ratings\n", ""), "parts[0].source.section", "lacks section")
        self.assertFails(self.changed("  - lcsc: C100", "  - lcsc: ''"), "parts[0].lcsc", "non-empty string")
        self.assertFails(self.changed("        absolute_min_v: -0.3\n", ""), "parts[0].pins[0].absolute_min_v", "lacks absolute_min_v")
        self.assertFails(self.changed("    pins:", "    pins: []\n    unused:"), "parts[0].pins", "lists no pins")
        self.assertFails(self.changed("    source:\n      document: synthetic datasheet\n      revision: A\n      section: absolute maximum ratings\n      read_on: 2026-10-01\n", "    source: datasheet\n"),
                         "parts[0].source", "not a mapping")
        self.assertFails("- not a mapping\n", "pin-limits.yaml", "not a mapping")

    def test_a_key_the_decision_does_not_name_is_refused_by_name_at_every_depth(self):
        # SOL-PRE-ORDER-CHECK-READS-RECORD-KEYS.C1: The check accepts and reads every key the record decisions define, fails one they do not, and is shown to on a seeded copy
        for old, new, where, key in (
                ("domains:", "domain:", "pin-limits.yaml domain", "domain"),
                ("parts:", "part:", "pin-limits.yaml part", "part"),
                ("    rail: V_LOGIC", "    rails: V_LOGIC", "domains[0].rails", "rails"),
                ("  - lcsc: C100", "  - lcsc: C100\n    note: x", "parts[0].note", "note"),
                ("      revision: A", "      revison: A", "parts[0].source.revison", "revison"),
                ("        absolute_max_v: 3.6", "        absolute_mx_v: 3.6", "parts[0].pins[0].absolute_mx_v", "absolute_mx_v"),
                ("        tolerates_driven_unpowered: true", "        tolerates_driven_unpowered: true\n        extra: 1",
                 "parts[0].pins[1].extra", "extra")):
            with self.subTest(where=where):
                problems = self.read(self.changed(old, new))
                self.assertTrue([v for v in problems if v.location.endswith(where) and f"holds the key '{key}'" in v.message],
                                [(v.location, v.message) for v in problems])
                self.assertEqual({v.rule for v in problems}, {"pin_limits_record"})


class TheDeratingAndPinLimitRecordsAreAmongWhatADesignReads(Tree):
    def test_both_records_a_design_is_held_to_are_listed_wherever_they_sit(self):
        # SOL-PRE-ORDER-CHECK-READS-RECORD-KEYS.C1: The check accepts and reads every key the record decisions define, fails one they do not, and is shown to on a seeded copy
        self.write("hardware/m/board/board.kicad_pro", "{}")
        self.write("hardware/m/board/board.kicad_sch", "(kicad_sch)")
        self.write("hardware/m/board/board.kicad_pcb", "(kicad_pcb)")
        self.write("hardware/m/derating-policy.yaml", DERATING_RECORD)
        self.git("init", "-q")
        self.git("add", "-A")
        self.write("hardware/m/board/pin-limits.yaml", PIN_LIMITS_RECORD)
        reads = board_check.design_reads(self.root, board_check.tracked_files("git", self.root))
        self.assertIn("hardware/m/derating-policy.yaml", reads)
        self.assertIn("hardware/m/board/pin-limits.yaml", reads)

    def test_a_design_holding_neither_record_lists_neither(self):
        # SOL-PRE-ORDER-CHECK-READS-RECORD-KEYS.C1: The check accepts and reads every key the record decisions define, fails one they do not, and is shown to on a seeded copy
        self.write("hardware/m/board/board.kicad_pro", "{}")
        self.write("hardware/m/board/board.kicad_sch", "(kicad_sch)")
        self.write("hardware/m/board/board.kicad_pcb", "(kicad_pcb)")
        self.git("init", "-q")
        self.git("add", "-A")
        reads = board_check.design_reads(self.root, board_check.tracked_files("git", self.root))
        self.assertEqual([entry for entry in reads if entry.endswith((".yaml"))], [])


class NamedSchematic(Tree):
    """Designs drawn on synthetic sheets, each sheet given the name a test wants, or none."""

    design = board_check.Design("hw/n/n.kicad_pro")

    def sheet(self, name, path: str = "sub.kicad_sch") -> str:
        property_ = "" if name is None else f'\t\t(property "Sheetname" "{name}")\n'
        return f'\t(sheet\n\t\t(at 0 0)\n{property_}\t\t(property "Sheetfile" "{path}")\n\t)\n'

    def found(self, root_sheets: str, below: str = ""):
        self.write("hw/n/n.kicad_pro")
        self.write("hw/n/n.kicad_pcb")
        self.write("hw/n/n.kicad_sch", f"(kicad_sch\n\t(version 20250114)\n{root_sheets})\n")
        self.write("hw/n/sub.kicad_sch", f"(kicad_sch\n\t(version 20250114)\n{below})\n")
        self.write("hw/n/deep.kicad_sch", "(kicad_sch (version 20250114))")
        return board_check.unnamed_sheets(self.design, self.everything())


class ASheetWithNoNameOfItsOwnFailsByName(NamedSchematic):
    """SOL-PRE-ORDER-CHECK-REFUSES-TOOL-NAMED-NETS-AND-UNNAMED-SHEETS.C1: A net named by the tool and a sheet with no name of its own fail the check by name."""

    def test_a_blank_missing_or_whitespace_name_fails_naming_the_schematic_drawing_it(self):
        # SOL-PRE-ORDER-CHECK-REFUSES-TOOL-NAMED-NETS-AND-UNNAMED-SHEETS.C1: A net named by the tool and a sheet with no name of its own fail the check by name
        for name in ("", "   ", None):
            with self.subTest(name=name):
                found = self.found(self.sheet(name))
                self.assertEqual([(v.rule, v.location) for v in found], [("unnamed_sheet", "hw/n/n.kicad_sch")])
                self.assertIn("its name is blank", found[0].message)
                self.assertIn("Sheetname", found[0].message)

    def test_the_tools_default_name_fails_with_or_without_a_number_and_a_name_that_only_starts_like_it_does_not(self):
        # SOL-PRE-ORDER-CHECK-REFUSES-TOOL-NAMED-NETS-AND-UNNAMED-SHEETS.C1: A net named by the tool and a sheet with no name of its own fail the check by name
        for name in ("Untitled Sheet", "Untitled Sheet 2", "Untitled Sheet 17"):
            with self.subTest(name=name):
                found = self.found(self.sheet(name))
                self.assertEqual([v.rule for v in found], ["unnamed_sheet"])
                self.assertIn(f"'{name}'", found[0].message)
        for name in ("Untitled Sheets", "Untitled Sheet A", "My Untitled Sheet", "untitled sheet", "Power"):
            with self.subTest(name=name):
                self.assertEqual(self.found(self.sheet(name)), [])

    def test_a_sheet_below_another_is_found_and_the_schematic_drawing_it_is_named(self):
        # SOL-PRE-ORDER-CHECK-REFUSES-TOOL-NAMED-NETS-AND-UNNAMED-SHEETS.C1: A net named by the tool and a sheet with no name of its own fail the check by name
        found = self.found(self.sheet("power"), self.sheet("Untitled Sheet", "deep.kicad_sch"))
        self.assertEqual([(v.rule, v.location) for v in found], [("unnamed_sheet", "hw/n/sub.kicad_sch")])

    def test_each_unnamed_sheet_is_reported_and_a_named_one_beside_it_is_not(self):
        # SOL-PRE-ORDER-CHECK-REFUSES-TOOL-NAMED-NETS-AND-UNNAMED-SHEETS.C1: A net named by the tool and a sheet with no name of its own fail the check by name
        found = self.found(self.sheet("") + self.sheet("power") + self.sheet("Untitled Sheet"))
        self.assertEqual(len(found), 2)

    def test_a_design_with_only_a_root_sheet_or_only_named_sheets_passes(self):
        # SOL-PRE-ORDER-CHECK-REFUSES-TOOL-NAMED-NETS-AND-UNNAMED-SHEETS.C1: A net named by the tool and a sheet with no name of its own fail the check by name
        self.assertEqual(self.found(""), [])
        self.assertEqual(self.found(self.sheet("power")), [])

    def test_a_sheet_that_cannot_be_read_is_discoverys_to_report_and_not_this_rules(self):
        # SOL-PRE-ORDER-CHECK-REFUSES-TOOL-NAMED-NETS-AND-UNNAMED-SHEETS.C1: A net named by the tool and a sheet with no name of its own fail the check by name
        self.found(self.sheet("power"))
        self.write("hw/n/n.kicad_sch", "(kicad_sch (sheet")
        self.assertEqual(board_check.unnamed_sheets(self.design, self.everything()), [])

    def test_a_sheet_placing_itself_below_itself_is_followed_once(self):
        # SOL-PRE-ORDER-CHECK-REFUSES-TOOL-NAMED-NETS-AND-UNNAMED-SHEETS.C1: A net named by the tool and a sheet with no name of its own fail the check by name
        found = self.found(self.sheet("power"), self.sheet("", "n.kicad_sch"))
        self.assertEqual([v.location for v in found], ["hw/n/sub.kicad_sch"])


class ANetTheToolNamedFailsByName(unittest.TestCase):
    """SOL-PRE-ORDER-CHECK-REFUSES-TOOL-NAMED-NETS-AND-UNNAMED-SHEETS.C1: A net named by the tool and a sheet with no name of its own fail the check by name."""

    design = board_check.Design("hw/n/n.kicad_pro")

    def found(self, *names: str):
        return board_check.tool_named_nets(self.design, {name: ([], ["R1 pin 1", "R2 pin 1"]) for name in names})

    def test_a_generated_net_fails_naming_the_net_and_the_pins_it_joins(self):
        # SOL-PRE-ORDER-CHECK-REFUSES-TOOL-NAMED-NETS-AND-UNNAMED-SHEETS.C1: A net named by the tool and a sheet with no name of its own fail the check by name
        found = self.found("/HEATER", "Net-(R3-Pad1)")
        self.assertEqual([(v.rule, v.location) for v in found], [("tool_named_net", "hw/n/n.kicad_sch")])
        self.assertIn("the net Net-(R3-Pad1) ", found[0].message)
        self.assertIn("R1 pin 1", found[0].message)

    def test_a_generated_net_fails_wherever_it_sits_in_a_sheet_path(self):
        # SOL-PRE-ORDER-CHECK-REFUSES-TOOL-NAMED-NETS-AND-UNNAMED-SHEETS.C1: A net named by the tool and a sheet with no name of its own fail the check by name
        found = self.found("/power/Net-(C1-Pad2)", "/a/b/Net-(U1-PA0)")
        self.assertEqual(len(found), 2)

    def test_a_pin_nothing_joins_is_exempt_at_the_top_and_in_a_sheet(self):
        # SOL-PRE-ORDER-CHECK-REFUSES-TOOL-NAMED-NETS-AND-UNNAMED-SHEETS.C1: A net named by the tool and a sheet with no name of its own fail the check by name
        self.assertEqual(self.found("unconnected-(R1-Pad1)", "/power/unconnected-(U1-PA5-Pad10)"), [])

    def test_a_name_a_designer_chose_passes_even_when_it_resembles_the_generated_form(self):
        # SOL-PRE-ORDER-CHECK-REFUSES-TOOL-NAMED-NETS-AND-UNNAMED-SHEETS.C1: A net named by the tool and a sheet with no name of its own fail the check by name
        self.assertEqual(self.found("/NET_A", "/Net", "/Net-1", "/Netting-(x)", "/LV_Net-(a", "/power/HEATER"), [])
        self.assertEqual(self.found(), [])

    def test_the_failure_prints_as_one_report_line_under_its_rule(self):
        # SOL-PRE-ORDER-CHECK-REFUSES-TOOL-NAMED-NETS-AND-UNNAMED-SHEETS.C1: A net named by the tool and a sheet with no name of its own fail the check by name
        line = self.found("Net-(R3-Pad1)")[0].line()
        self.assertTrue(line.startswith("VIOLATION | hw/n/n.kicad_pro | tool_named_net | hw/n/n.kicad_sch | "), line)


class AMissingToolIsNamedByEveryModuleOfBoardTests(Tree):
    """A module of board tests that cannot find KiCad or the rasteriser stops with a line naming it, as every board command does."""

    TESTS = os.path.dirname(os.path.abspath(__file__))
    KICAD_ONLY = ("test_board_check_kicad", "test_locked_copper", "test_review_seed")
    WITH_RASTERISER = ("test_board_views", "test_board_placement")

    def run_module(self, module: str, **environment):
        return subprocess.run([sys.executable, "-m", "unittest", module], cwd=self.TESTS, capture_output=True, text=True,
                              env={**os.environ, **environment}, timeout=300)

    def test_a_missing_kicad_stops_every_module_naming_it(self):
        # SOL-HW-GATE-IN-ROUND-AND-NIGHTLY.C1: The build round runs the board check when the branch changes a board design, anything it reads, or the check
        for module in self.KICAD_ONLY + self.WITH_RASTERISER:
            with self.subTest(module=module):
                result = self.run_module(module, KICAD_CLI=os.path.join(self.root, "no-such-kicad-cli"))
                self.assertNotEqual(result.returncode, 0)
                self.assertRegex(result.stderr, r"(?m)^CANNOT RUN \| kicad-cli was not found")
                self.assertIn("KICAD_CLI=/path/to/kicad-cli", result.stderr)

    def test_a_missing_rasteriser_stops_the_modules_that_draw_naming_it(self):
        # SOL-HW-GATE-IN-ROUND-AND-NIGHTLY.C1: The build round runs the board check when the branch changes a board design, anything it reads, or the check
        kicad = fake_tool(os.path.join(self.root, "kicad-cli"), 'echo "10.0.7"')
        for module in self.WITH_RASTERISER:
            with self.subTest(module=module):
                result = self.run_module(module, KICAD_CLI=kicad, RESVG=os.path.join(self.root, "no-such-resvg"))
                self.assertNotEqual(result.returncode, 0)
                self.assertRegex(result.stderr, r"(?m)^CANNOT RUN \| resvg was not found")
                self.assertIn("RESVG=/path/to/resvg", result.stderr)

    def test_a_rasteriser_that_finds_no_font_stops_the_modules_that_draw_naming_the_font(self):
        # SOL-HW-GATE-IN-ROUND-AND-NIGHTLY.C1: The build round runs the board check when the branch changes a board design, anything it reads, or the check
        kicad = fake_tool(os.path.join(self.root, "kicad-cli"), 'echo "10.0.7"')
        # A rasteriser that reports its version and draws a blank image, as one finding no font does.
        resvg = fake_tool(os.path.join(self.root, "resvg"), f"""
if [ "$1" = "--version" ]; then echo "resvg 0.47.0"; exit 0; fi
exec "{sys.executable}" -c '
import struct, sys, zlib
w, h = 120, 30
raw = b"".join(b"\\x00" + bytes([16, 16, 16]) * w for _ in range(h))
def chunk(kind, data):
    body = kind + data
    return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))
png = b"\\x89PNG\\r\\n\\x1a\\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")
open(sys.argv[-1], "wb").write(png)
' "$@"
""")
        for module in self.WITH_RASTERISER:
            with self.subTest(module=module):
                result = self.run_module(module, KICAD_CLI=kicad, RESVG=resvg)
                self.assertNotEqual(result.returncode, 0)
                self.assertRegex(result.stderr, r"(?m)^CANNOT RUN \| resvg at .* found no font")
                self.assertIn("monospaced font", result.stderr)


class TheRoundRunsTheToolingTestsWithoutTheSeededFaultProof(unittest.TestCase):
    """The proof stays on demand, so what the round and the nightly run of the tooling tests leaves out is exactly
    what needs it: every check-behaviour test that can run without the pooled proof stays in."""

    def setUp(self):
        import test_board_check_kicad as module
        self.module = module

    def loaded(self, without_proof: bool):
        environment = {self.module.WITHOUT_PROOF: "1"} if without_proof else {}
        with mock.patch.dict(os.environ, environment):
            if not without_proof:
                os.environ.pop(self.module.WITHOUT_PROOF, None)
            suite = unittest.TestLoader().loadTestsFromModule(self.module)
        return list(self.module.tests_of(suite))

    @staticmethod
    def needs_the_proof(test) -> bool:
        """Whether a test's own source asks the pooled proof's outcomes or runs the proof."""
        source = inspect.getsource(getattr(type(test), test._testMethodName))
        return any(call in source for call in ("assertCaught(", "outcomes(", "board_prove.main("))

    def test_the_subset_leaves_out_exactly_the_tests_that_need_the_proof(self):
        # SOL-HW-GATE-IN-ROUND-AND-NIGHTLY.C1: The build round runs the board check when the branch changes a board design, anything it reads, or the check
        everything, subset = self.loaded(False), self.loaded(True)
        left_out = {test.id() for test in everything} - {test.id() for test in subset}
        needing = {test.id() for test in everything if self.needs_the_proof(test)}
        self.assertTrue(needing)
        # None that needs the proof is in the subset, and none is left out that does not need it.
        self.assertEqual(left_out, needing)
        self.assertEqual({test.id() for test in subset} & needing, set())
        self.assertTrue(all(isinstance(test, self.module.Proved) for test in everything if test.id() in left_out))

    def test_the_subset_keeps_every_check_behaviour_test_that_runs_without_the_pooled_proof(self):
        # SOL-HW-GATE-IN-ROUND-AND-NIGHTLY.C1: The build round runs the board check when the branch changes a board design, anything it reads, or the check
        kept = {type(test).__name__ for test in self.loaded(True)}
        for name in ("AForgedRuleIsReported", "TheProofDesignAndItsFaults", "OnlyWhatTheRepositoryHoldsIsChecked",
                     "TheRejectedRuleIsNamed", "ZonesAreRefilled", "TheSignedFigurePrevails", "OneCommand",
                     "NothingFromTheMachineRunningTheCheck", "TheReport", "AClassIsReadWholeOnABoardOfAnySize"):
            self.assertIn(name, kept)
        for name in ("Discovery", "RuleChecks", "Separation", "TheWorkmanshipRules", "TheSeededFaultProof"):
            self.assertNotIn(name, kept)

    def test_the_full_suite_stays_runnable_with_the_proof_in_it(self):
        # SOL-HW-GATE-IN-ROUND-AND-NIGHTLY.C1: The build round runs the board check when the branch changes a board design, anything it reads, or the check
        everything = {test.id() for test in self.loaded(False)}
        subset = {test.id() for test in self.loaded(True)}
        self.assertLess(subset, everything)
        self.assertIn(f"{self.module.__name__}.TheSeededFaultProof.test_the_clean_design_passes_and_every_fault_is_caught_without_touching_the_tree", everything)

    def test_a_test_pulling_the_pooled_proof_in_is_seen_whatever_it_derives_from(self):
        # SOL-HW-GATE-IN-ROUND-AND-NIGHTLY.C1: The build round runs the board check when the branch changes a board design, anything it reads, or the check
        class Pulls(unittest.TestCase):
            def test_asks(self):
                self.assertCaught("a fault")

            def test_runs(self):
                outcomes()

            def test_proves(self):
                board_prove.main([])

            def test_does_not(self):
                self.assertTrue(True)

        outcomes = board_prove = None
        found = {name: self.needs_the_proof(Pulls(name)) for name in ("test_asks", "test_runs", "test_proves", "test_does_not")}
        self.assertEqual(found, {"test_asks": True, "test_runs": True, "test_proves": True, "test_does_not": False})

    def task_block(self, name: str) -> str:
        with open(os.path.join(REPO, "Taskfile.yml"), encoding="utf-8") as handle:
            lines = handle.read().splitlines()
        start = lines.index(f"  {name}:")
        block = []
        for line in lines[start + 1:]:
            if line.strip() and len(line) - len(line.lstrip(" ")) <= 2:
                break
            block.append(line)
        return "\n".join(block)

    def test_the_round_task_sets_the_variable_and_the_on_demand_task_does_not(self):
        # SOL-HW-GATE-IN-ROUND-AND-NIGHTLY.C1: The build round runs the board check when the branch changes a board design, anything it reads, or the check
        round_task, full_task = self.task_block("hw:test:round"), self.task_block("hw:test")
        self.assertIn(f'      {self.module.WITHOUT_PROOF}: "1"', round_task)
        self.assertNotIn(self.module.WITHOUT_PROOF, full_task)
        discovery = "python3 -m unittest discover -s {{.HW_DIR}}/tools/tests {{.CLI_ARGS}}"
        self.assertIn(discovery, round_task)
        self.assertIn(discovery, full_task)
        for text in (round_task, full_task):
            self.assertIn('KICAD_CLI: "{{.KICAD_CLI}}"', text)
            self.assertIn('RESVG: "{{.RESVG}}"', text)


if __name__ == "__main__":
    unittest.main()
