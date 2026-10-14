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
import json
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
FIGURES = {"WORK_DETOUR_RATIO": "1.5", "WORK_STUB_MM": "0", "WORK_NECK_MM": "1", "WORK_ANGLE_TOLERANCE_DEG": "0.1",
           "WORK_PAD_ENTRY_RATIO": "2"}

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
            self.assertEqual([(v.rule, v.message) for v in found],
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
            return board_check.check_design(board_check.Design("a/a.kicad_pro"), repository, fake,
                                            board_check.require_yaml(), TODAY, [])

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
        self.assertEqual({v.rule for v in found}, {"assertion_failure"})

    def test_a_marker_crowded_out_of_a_full_report_is_not_taken_for_unloaded_rules(self):
        # SOL-HW-BOARD-CLASS-READ-ANY-SIZE.C1: A net class's membership is read completely and identically on every run, on a board of any size
        found = self.check(board_check.REPORT_LIMIT, marker=False)
        self.assertEqual(len(self.cut(found)), 1, found)
        self.assertFalse([v for v in found if "did not load" in v.message], found)
        found = self.check(3, marker=False)
        self.assertTrue([v for v in found if v.rule == "custom_rules" and "did not load" in v.message], found)


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
