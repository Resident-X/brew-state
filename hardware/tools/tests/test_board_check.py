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
           "WORK_PAD_ENTRY_RATIO": "2", "WORK_PAD_ANGLE_DEG": "90"}

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
                                   "WORK_ANGLE_TOLERANCE_DEG": 0.1, "WORK_PAD_ENTRY_RATIO": 2.0, "WORK_PAD_ANGLE_DEG": 90.0})

    def test_each_missing_figure_fails_naming_its_item_and_variable(self):
        figures, found = board_check.workmanship_figures(DESIGN, {})
        self.assertEqual(figures, {})
        self.assertEqual([(v.rule, v.location) for v in found],
                         [("workmanship_figure", f"a/a.kicad_pro text_variables.{name}") for _, _, name, _, _, _ in board_check.MEASURED])
        self.assertIn("WORK-2 (route length) has no figure", found[0].message)

    def test_a_figure_written_any_way_but_a_plain_number_within_its_range_fails(self):
        for name, value in (("WORK_NECK_MM", "1mm"), ("WORK_NECK_MM", "-1"), ("WORK_NECK_MM", ""), ("WORK_DETOUR_RATIO", "0.9"),
                            ("WORK_DETOUR_RATIO", "1e1"), ("WORK_ANGLE_TOLERANCE_DEG", "22.5"), ("WORK_PAD_ENTRY_RATIO", "two")):
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
