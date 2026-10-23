#!/usr/bin/env python3
"""The locked-copper check, driven on synthetic boards against the real kicad-cli: the commands part.

One of the files the original test file is divided into by topic; the tests are unchanged and only live elsewhere.
"""

from __future__ import annotations

import io
import os
import subprocess
import sys
from unittest import mock

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import board_check  # noqa: E402
import locked_copper  # noqa: E402
from locked_copper_fixtures import AC_TRACK, BASE_PROJECT, Board, ITEMS, KICAD_CLI, REPO, RULES, UNLOCKED_ITEMS, layout, project, setUpModule  # noqa: E402,F401


class WhatTheCommandsRefuse(Board):
    """SOL-BOARD-RULES-AND-LOCKED-CRITICAL-ROUTING.C3: A tested check records critical-class copper before the routing round trip and fails the board after it on any missing, unlocked, changed or added item.

    Locking and recording refuse a board with no valid mains declaration, a set
    of classes that leaves out Mains on a board declaring mains, and a named
    class that is undefined or holds no net; the rules confirmation refuses the
    declaration and the classes the same way, and comparing fails a record whose
    classes leave out Mains on a board declaring mains. A refusal changes nothing.
    """

    def setUp(self):
        super().setUp()
        self.write(layout(UNLOCKED_ITEMS.values()))
        with open(os.path.join(self.folder, "b.kicad_dru"), "w", encoding="utf-8") as handle:
            handle.write(RULES)

    def assertRefusedByAll(self, classes, refused, mentioning):
        before = self.board_text()
        for command in ("lock", "confirm"):
            with self.subTest(command=command):
                status, lines = self.on_classes(command, *classes)
                self.assertEqual(status, 1, lines)
                self.assertTrue(any(line.split(" | ")[1:2] == [refused] and mentioning in line for line in lines), lines)
                self.assertNotIn("CONFIRMED", lines[-1])
                self.assertEqual(self.board_text(), before)
        self.write(layout(ITEMS.values()))
        status, lines = self.record(*classes)
        self.assertEqual(status, 1, lines)
        self.assertTrue(any(line.split(" | ")[1:2] == [refused] and mentioning in line for line in lines), lines)
        self.assertFalse(os.path.exists(self.record_path))
        self.write(before)

    def test_a_board_with_no_valid_mains_declaration(self):
        for mains in (None, "yes", "Present", ""):
            with self.subTest(mains=mains):
                with open(self.project, "w", encoding="utf-8") as handle:
                    handle.write(project({"/PWR": "Power"}, [{"netclass": "Ground", "pattern": "/GND_*"}], mains=mains))
                self.assertRefusedByAll((), f"{self.project} text_variables.MAINS", "MAINS")

    def test_mains_left_out_on_a_board_declaring_mains(self):
        mains_project = project({"/PWR": "Power", "/AC": "Mains"}, [{"netclass": "Ground", "pattern": "/GND_*"}],
                                classes=("Power", "Ground", "Mains"), mains="present")
        self.write(layout(list(UNLOCKED_ITEMS.values()) + [AC_TRACK]), mains_project)
        before = self.board_text()
        for command in ("lock", "confirm", "record"):
            with self.subTest(command=command):
                status, lines = self.record() if command == "record" else self.on_classes(command, "Power", "Ground")
                self.assertEqual(status, 1, lines)
                self.assertTrue(any(line.startswith("REFUSED | Mains | MAINS is present") for line in lines), lines)
                self.assertEqual(self.findings(lines, "CLASS"), [], lines)
                self.assertNotIn("CONFIRMED", lines[-1])
                self.assertEqual(self.board_text(), before)
                self.assertFalse(os.path.exists(self.record_path))
        status, lines = self.on_classes("confirm", "Power", "Ground", "Mains")
        self.assertEqual(status, 0, lines)
        self.assertIn("CLASS | Mains | 1 net | /AC", lines)
        status, lines = self.on_classes("lock", "Power", "Ground", "Mains")
        self.assertEqual(status, 0, lines)
        self.assertIn("LOCKED | track [/AC]", "\n".join(lines))
        status, lines = self.record("Power", "Ground", "Mains")
        self.assertEqual(status, 0, lines)

    def test_a_record_leaving_out_mains_on_a_board_declaring_mains_fails(self):
        self.write(layout(ITEMS.values()))
        self.recorded()
        mains_project = project({"/PWR": "Power", "/AC": "Mains"}, [{"netclass": "Ground", "pattern": "/GND_*"}],
                                classes=("Power", "Ground", "Mains"), mains="present")
        self.write(layout(list(ITEMS.values()) + [AC_TRACK]), mains_project)
        status, lines = self.compare()
        self.assertEqual(status, 1, lines)
        self.assertTrue(any(line.startswith("MAINS | Mains | MAINS is present") for line in lines), lines)
        self.assertNotIn("PASS", lines[-1])

    def test_a_named_class_holding_no_net(self):
        with open(self.project, "w", encoding="utf-8") as handle:
            handle.write(project({"/PWR": "Power"}, [{"netclass": "Ground", "pattern": "/GND_*"}],
                                 classes=("Power", "Ground", "Sensing")))
        self.assertRefusedByAll(("Power", "Ground", "Sensing"), "Sensing", "places no net")

    def test_a_named_class_the_design_does_not_define(self):
        self.assertRefusedByAll(("Power", "Sensing"), "Sensing", "defines no net class")

    def test_a_project_file_not_the_boards_own(self):
        elsewhere = os.path.join(self.work, "b.kicad_pro")
        with open(elsewhere, "w", encoding="utf-8") as handle:
            handle.write(BASE_PROJECT)
        before = self.board_text()
        for command in ("lock", "confirm"):
            with self.subTest(command=command):
                status, lines = self.run_check(command, "--board", self.board, "--project", elsewhere, "--class", "Power")
                self.assertEqual(status, 1, lines)
                self.assertTrue(any(line.startswith(f"REFUSED | {elsewhere} | KiCad opens") for line in lines), lines)
                self.assertEqual(self.board_text(), before)


class OpenInAnEditor(Board):
    """SOL-BOARD-RULES-AND-LOCKED-CRITICAL-ROUTING.C3: A tested check records critical-class copper before the routing round trip and fails the board after it on any missing, unlocked, changed or added item.

    Locking, recording and comparing each refuse to run while KiCad's lock file
    beside the board shows it open in an editor.
    """

    def test_lock_record_and_compare_refuse_while_the_board_is_open(self):
        self.recorded()
        lock_file = os.path.join(self.folder, "~b.kicad_pcb.lck")
        with open(lock_file, "w", encoding="utf-8") as handle:
            handle.write('{"hostname":"bench","username":"designer"}')
        status, lines = self.compare()
        self.assertEqual(status, 1, lines)
        self.assertTrue(lines[0].startswith(f"OPEN | {lock_file} | KiCad's lock file shows"), lines)
        self.assertNotIn("PASS", lines[-1])
        other = os.path.join(self.work, "other.json")
        status, lines = self.record(record_path=other)
        self.assertEqual(status, 1, lines)
        self.assertTrue(lines[0].startswith(f"REFUSED | {lock_file} | KiCad's lock file shows"), lines)
        self.assertFalse(os.path.exists(other))
        self.write(layout(UNLOCKED_ITEMS.values()))
        before = self.board_text()
        status, lines = self.on_classes("lock")
        self.assertEqual(status, 1, lines)
        self.assertTrue(lines[0].startswith(f"REFUSED | {lock_file} | KiCad's lock file shows"), lines)
        self.assertEqual(self.board_text(), before)
        os.remove(lock_file)
        with open(os.path.join(self.folder, "~other.kicad_pcb.lck"), "w", encoding="utf-8") as handle:
            handle.write('{"hostname":"bench","username":"designer"}')
        status, lines = self.on_classes("lock")
        self.assertEqual(status, 0, lines)


class ConfirmingTheRules(Board):
    """SOL-BOARD-RULES-AND-LOCKED-CRITICAL-ROUTING.C3: A tested check records critical-class copper before the routing round trip and fails the board after it on any missing, unlocked, changed or added item.

    The rules confirmation passes only when KiCad's rule check shows, through
    the appended marker, that it loaded the board's own custom rules file, and
    lists each named class's nets as KiCad resolves them.
    """

    def write_rules(self, text):
        path = os.path.join(self.folder, "b.kicad_dru")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
        return path

    def test_a_loaded_rules_file_and_each_class_are_confirmed(self):
        path = self.write_rules(RULES)
        before = self.board_text()
        status, lines = self.on_classes("confirm")
        self.assertEqual(status, 0, lines)
        self.assertEqual(lines, ["CLASS | Power | 1 net | /PWR", "CLASS | Ground | 2 nets | /GND_A, /GND_B",
                                 f"RESULT | CONFIRMED | KiCad loads {path} and places nets in each of Power, Ground"])
        with open(path, encoding="utf-8") as handle:
            self.assertEqual(handle.read(), RULES)
        self.assertEqual(self.board_text(), before)

    def test_a_rules_file_kicad_drops_unread_fails(self):
        dropped = {
            "a misspelled constraint": RULES.replace("track_width", "trak_width"),
            "no version header": RULES.replace("(version 1)\n", ""),
            "an unbalanced rule": RULES[:-2] + "\n",
        }
        for what, text in dropped.items():
            with self.subTest(rules=what):
                path = self.write_rules(text)
                status, lines = self.on_classes("confirm")
                self.assertEqual(status, 1, lines)
                self.assertTrue(any(line.startswith(f"RULES | {path}") and "did not load" in line for line in lines), lines)
                self.assertEqual(self.findings(lines, "CLASS"), [], lines)
                self.assertNotIn("CONFIRMED", lines[-1])

    def test_a_marker_crowded_out_of_a_full_report_is_not_taken_for_unloaded_rules(self):
        # SOL-HW-BOARD-CLASS-READ-ANY-SIZE.C1: A net class's membership is read completely and identically on every run, on a board of any size
        # The marker fires on one net's items, so the board's own assertion
        # rules failing on as many items as KiCad reports can crowd it out.
        path = self.write_rules(RULES)
        full = {"violations": [{"type": "assertion_failure", "description": "Assertion failure (rule 'own')", "items": []}]
                * board_check.REPORT_LIMIT}
        with mock.patch.object(board_check, "run_report", return_value=(full, "")), \
                mock.patch.object(board_check, "rejected_form", side_effect=AssertionError("bisected a loaded file")):
            status, lines = self.on_classes("confirm")
        self.assertEqual(status, 1, lines)
        self.assertTrue(lines[0].startswith(f"RULES | {path} | KiCad's report was cut short at its limit of 199"), lines)
        self.assertEqual(lines[-1], "RESULT | FAIL | KiCad's report was cut short")

    def test_a_board_with_no_rules_file_fails(self):
        status, lines = self.on_classes("confirm")
        self.assertEqual(status, 1, lines)
        self.assertTrue(lines[0].startswith("RULES |") and "no custom rules file" in lines[0], lines)

    def test_membership_by_a_class_the_layout_file_carries(self):
        block = '\t(net_class "Sense" "written by an older KiCad" (clearance 0.2) (add_net "/S1"))\n'
        sense = ('(segment (start 50 0) (end 55 0) (width 0.25) (layer "F.Cu") (net "/S1") '
                 '(uuid "00000000-0000-4000-8000-000000000005"))')
        self.write(layout([sense, ITEMS["lv"]], extra=block), project(classes=()))
        self.write_rules(RULES.replace("Power", "Sense"))
        status, lines = self.on_classes("confirm", "Sense")
        self.assertEqual(status, 0, lines)
        self.assertEqual(lines[0], "CLASS | Sense | 1 net | /S1")


class TheTaskRunnerCommands(Board):
    """SOL-BOARD-RULES-AND-LOCKED-CRITICAL-ROUTING.C3: A tested check records critical-class copper before the routing round trip and fails the board after it on any missing, unlocked, changed or added item.

    Confirming the rules, locking, recording and comparing are each run by a
    task-runner command beside the pre-order check's own, with paths read from
    where the command is run.
    """

    def task(self, name, *argv):
        return subprocess.run(["task", "--taskfile", os.path.join(REPO, "Taskfile.yml"), name, f"KICAD_CLI={KICAD_CLI}",
                               "--", *argv], cwd=self.folder, capture_output=True, text=True, timeout=300)

    def test_record_then_compare_through_the_tasks(self):
        made = self.task("hw:copper-record", "--board", "b.kicad_pcb", "--project", "b.kicad_pro",
                         "--class", "Power", "--class", "Ground", "--record", "../work/b.record.json")
        self.assertEqual(made.returncode, 0, made.stdout + made.stderr)
        self.assertIn("RESULT | RECORDED | 4 locked items", made.stdout)
        same = self.task("hw:copper-compare", "--board", "b.kicad_pcb", "--project", "b.kicad_pro",
                         "--record", "../work/b.record.json")
        self.assertEqual(same.returncode, 0, same.stdout + same.stderr)
        self.write(layout(dict(ITEMS, zone=ITEMS["zone"].replace(" (locked yes)", "")).values()))
        moved = self.task("hw:copper-compare", "--board", "b.kicad_pcb", "--project", "b.kicad_pro",
                          "--record", "../work/b.record.json")
        self.assertNotEqual(moved.returncode, 0, moved.stdout)
        self.assertIn("UNLOCKED | zone [/PWR]", moved.stdout)

    def test_confirm_and_lock_through_the_tasks(self):
        classes = ("--board", "b.kicad_pcb", "--project", "b.kicad_pro", "--class", "Power", "--class", "Ground")
        unread = self.task("hw:rules-confirm", *classes)
        self.assertNotEqual(unread.returncode, 0, unread.stdout)
        self.assertIn("no custom rules file", unread.stdout)
        with open(os.path.join(self.folder, "b.kicad_dru"), "w", encoding="utf-8") as handle:
            handle.write(RULES)
        confirmed = self.task("hw:rules-confirm", *classes)
        self.assertEqual(confirmed.returncode, 0, confirmed.stdout + confirmed.stderr)
        self.assertIn("RESULT | CONFIRMED", confirmed.stdout)
        self.write(layout(UNLOCKED_ITEMS.values()))
        locked = self.task("hw:copper-lock", *classes)
        self.assertEqual(locked.returncode, 0, locked.stdout + locked.stderr)
        self.assertIn("RESULT | LOCKED | 4 items locked now", locked.stdout)
        made = self.task("hw:copper-record", *classes, "--record", "../work/b.record.json")
        self.assertEqual(made.returncode, 0, made.stdout + made.stderr)

    def test_a_missing_kicad_cannot_run(self):
        out = io.StringIO()
        with mock.patch.object(sys, "stderr", io.StringIO()):
            status = locked_copper.main(["--kicad-cli", os.path.join(self.work, "no-such-kicad-cli"), "compare",
                                         "--board", self.board, "--project", self.project, "--record", self.record_path], out=out)
        self.assertEqual(status, 2)
        self.assertNotIn("PASS", out.getvalue())
