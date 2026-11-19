#!/usr/bin/env python3
"""The acceptance-entry generator, on synthetic boards and check logs the tests write, and against the real pre-order check."""

from __future__ import annotations

import contextlib
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest

TESTS = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(TESTS)
HARDWARE = os.path.dirname(TOOLS)
sys.path.insert(0, TOOLS)
sys.path.insert(0, TESTS)

import acceptance_entries  # noqa: E402
import board_check  # noqa: E402
import sexpr  # noqa: E402
import board_prove  # noqa: E402
from layout_tool_fixtures import Work, board_text, track, zone  # noqa: E402

KICAD_CLI = os.environ.get("KICAD_CLI") or "kicad-cli"
DESIGN = "hardware/synthetic/low.kicad_pro"
TRACE = ("SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD")

TABLE = """accepted_by: "proof-owner"
synthetic: true
net_kinds:
  - kind: slow signal
    nets: ["/SLOW_*"]
    bounded_by: a synthetic bound
    reasons:
      workmanship_pad_corner: a synthetic reason for a slow signal corner
      workmanship_detour: a synthetic reason for a slow signal detour
  - kind: supply
    nets: ["+5V", "/sheet/GND"]
    bounded_by: a synthetic supply bound
    reasons:
      workmanship_pad_corner: a synthetic reason for a supply corner
"""

REGION = ('(zone (layers "F.Cu" "B.Cu") (uuid "00000000-0000-4000-8000-000000000001") (name "mains") (hatch edge 0.5) '
          '(keepout (tracks allowed) (vias allowed) (pads allowed) (copperpour allowed) (footprints allowed)) '
          '(polygon (pts (xy 50 50) (xy 60 50) (xy 60 60) (xy 50 60))))')


LOW_VOLTAGE_NETS = ("/SLOW_A", "/SLOW_B", "/SLOW_C", "/UNKNOWN_NET", "/LV_A", "/LV_B", "+5V", "/sheet/GND", "/MAINS_L")
#: One track per low-voltage net, wholly outside the mains region.
COPPER = [track(net, (2, 2 + 3 * index), (20, 2 + 3 * index), number=100 + index) for index, net in enumerate(LOW_VOLTAGE_NETS)]


def line(rule: str, net: str, at=(5, 5), kind: str = "VIOLATION", design: str = DESIGN) -> str:
    return (f"{kind} | {design} | {rule} | net {net}: P1 at ({at[0]}, {at[1]}) mm on F.Cu: Track [{net}] on F.Cu | "
            f"{rule} message for {net}")


def log(*lines: str, design: str = DESIGN) -> str:
    return f"Checking board designs\nDESIGN | {design} | FAIL | {len(lines)} violations\n" + "".join(l + "\n" for l in lines) \
        + "RESULT | FAIL | 1 of 1 designs failed\n"


class Generator(Work):
    """A synthetic board folder, its table and a log, written in a scratch folder."""

    def setUp(self):
        super().setUp()
        self.board = self.write("b/low.kicad_pcb", board_text([REGION, *COPPER]))
        self.project = self.write("b/low.kicad_pro", json.dumps({
            "net_settings": {"classes": [{"name": "Default"}, {"name": "Mains"}, {"name": "Mains_Entry"}],
                             "netclass_assignments": {"/LINE_X": "Mains"},
                             "netclass_patterns": [{"netclass": "Mains", "pattern": "/MAINS_*"},
                                                   {"netclass": "Mains_Entry", "pattern": "/ENTRY_*"}]},
            "text_variables": {"MAINS": "present"}}))
        self.table = self.write("b/acceptance-reasons.yaml", TABLE)
        self.record = self.path("b/workmanship-acceptance.yaml")

    def argv(self, log_text: str, *extra: str, table=None):
        return ["--log", self.write("check.log", log_text), "--board", self.board, "--project", self.project,
                "--table", table or self.table, "--accepted-on", "2026-10-01", *extra]

    def generate(self, log_text: str, *extra: str, **kwargs):
        return self.run_tool(acceptance_entries.main, *self.argv(log_text, *extra, **kwargs))

    def generate_json(self, log_text: str, *extra: str, **kwargs):
        return self.run_json(acceptance_entries.main, *self.argv(log_text, *extra, **kwargs))

    def record_text(self) -> str:
        return self.read(self.record) if os.path.exists(self.record) else ""

    def both(self, log_text: str, *extra: str):
        """(exit status, text lines, JSON report) of the same run in each format, the record as the text run left it."""
        status, lines = self.generate(log_text, *extra)
        written = self.record_text()
        if os.path.exists(self.record):
            os.remove(self.record)
        json_status, report = self.generate_json(log_text, *extra)
        self.assertEqual(status, json_status)
        self.assertEqual(written, self.record_text(), "the two formats write the same record")
        self.assertEqual(report["result"], "FAIL" if status else "PASS")
        return status, lines, report


class MainsLinesAreRefused(Generator):
    def test_a_line_on_a_mains_class_net_is_refused_and_never_entered(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C8: Given a check log whose failing neatness lines include one on a Mains-class net, one inside a mains region and one on a low-voltage net whose copper lies in or crosses a mains region, the generator writes no entry for any of them, names each as refused and exits with failure. A line is judged from the copper of the nets it names in the board it is given, not from the positions the log prints. A line that names no resolvable net is refused when the project declares mains present and the board has a mains region. Tests cover a line on a Mains-class net, a line inside a mains region, a low-voltage net whose copper crosses a region while its printed point lies outside, a line with no position, a line on none of these and a log with no failing lines, in text and in JSON. This does not cover entries for any line other than a failing neatness line.
        for net in ("/MAINS_L", "/LINE_X", "/ENTRY_N"):
            with self.subTest(net=net):
                if os.path.exists(self.record):
                    os.remove(self.record)
                status, lines, report = self.both(log(line("workmanship_pad_corner", net)), "--partial")
                self.assertEqual(status, 1)
                self.assertEqual(self.record_text(), "")
                refused = [l for l in lines if l.startswith("REFUSED | ")]
                self.assertEqual(len(refused), 1, lines)
                self.assertIn(f"net {net} is in the net class", refused[0])
                self.assertEqual([r["scope"] for r in report["refused"]], [net])
                self.assertEqual(report["entries"], [])
                self.assertIn("is in the net class", report["refused"][0]["why"])

    def put(self, *items):
        """Rewrite the board with the mains region and the given copper (the low-voltage nets' own copper is left out)."""
        self.write("b/low.kicad_pcb", board_text([REGION, *items]))

    def refused_one(self, text, why, rule="workmanship_detour"):
        """The run of `text` refuses its one line for `why`, writes nothing and fails, in text and in JSON."""
        status, lines, report = self.both(text, "--partial")
        self.assertEqual(status, 1)
        self.assertEqual(self.record_text(), "")
        self.assertEqual((len(report["refused"]), report["entries"]), (1, []))
        self.assertIn(why, report["refused"][0]["why"])
        self.assertTrue(any(l.startswith(f"REFUSED | {rule}") and why in l for l in lines), lines)
        return report

    def test_a_low_voltage_net_whose_copper_lies_in_a_mains_region_is_refused_wherever_the_line_prints_its_position(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C8: Given a check log whose failing neatness lines include one on a Mains-class net, one inside a mains region and one on a low-voltage net whose copper lies in or crosses a mains region, the generator writes no entry for any of them, names each as refused and exits with failure. A line is judged from the copper of the nets it names in the board it is given, not from the positions the log prints. A line that names no resolvable net is refused when the project declares mains present and the board has a mains region. Tests cover a line on a Mains-class net, a line inside a mains region, a low-voltage net whose copper crosses a region while its printed point lies outside, a line with no position, a line on none of these and a log with no failing lines, in text and in JSON. This does not cover entries for any line other than a failing neatness line.
        inside = {"a track": track("/SLOW_A", (55, 52), (55, 58), number=11),
                  "a track ending on the edge": track("/SLOW_A", (5, 55), (50, 55), number=12),
                  "a via": '(via (at 55 55) (size 0.8) (drill 0.4) (layers "F.Cu" "B.Cu") (net "/SLOW_A") (uuid "00000000-0000-4000-8000-000000000013"))',
                  "a zone corner": zone("a", "/SLOW_A", "F.Cu", [(40, 40), (52, 40), (52, 52), (40, 52)], ""),
                  "a plane enclosing the region": zone("a", "/SLOW_A", "F.Cu", [(40, 40), (70, 40), (70, 70), (40, 70)], "")}
        for name, item in inside.items():
            for printed in ((5, 5), None):
                with self.subTest(copper=name, printed=printed):
                    self.put(track("/SLOW_A", (5, 5), (20, 5), number=10), item)
                    where = (f"net /SLOW_A: Track [/SLOW_A] on F.Cu" + ("" if printed is None else f" at ({printed[0]}, {printed[1]}) mm"))
                    self.refused_one(log(f"VIOLATION | {DESIGN} | workmanship_pad_corner | {where} | message"),
                                     "lies in or crosses the mains region mains", "workmanship_pad_corner")

    def test_a_line_with_no_position_on_a_net_outside_every_region_is_entered_and_says_nothing_on_standard_error(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C8: Given a check log whose failing neatness lines include one on a Mains-class net, one inside a mains region and one on a low-voltage net whose copper lies in or crosses a mains region, the generator writes no entry for any of them, names each as refused and exits with failure. A line is judged from the copper of the nets it names in the board it is given, not from the positions the log prints. A line that names no resolvable net is refused when the project declares mains present and the board has a mains region. Tests cover a line on a Mains-class net, a line inside a mains region, a low-voltage net whose copper crosses a region while its printed point lies outside, a line with no position, a line on none of these and a log with no failing lines, in text and in JSON. This does not cover entries for any line other than a failing neatness line.
        unplaced = f"VIOLATION | {DESIGN} | workmanship_detour | net /SLOW_A: Track [/SLOW_A] on F.Cu | message"
        errors = io.StringIO()
        with contextlib.redirect_stderr(errors):
            status, lines, report = self.both(log(unplaced, unplaced))
        self.assertEqual((status, report["refused"], errors.getvalue()), (0, [], ""))
        self.assertEqual([(e["scope"], e["count"]) for e in report["entries"]], [("/SLOW_A", 2)])
        self.assertNotIn("no_position", report)

    def test_a_detour_whose_first_pad_is_outside_but_whose_copper_crosses_a_region_is_refused(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C8: Given a check log whose failing neatness lines include one on a Mains-class net, one inside a mains region and one on a low-voltage net whose copper lies in or crosses a mains region, the generator writes no entry for any of them, names each as refused and exits with failure. A line is judged from the copper of the nets it names in the board it is given, not from the positions the log prints. A line that names no resolvable net is refused when the project declares mains present and the board has a mains region. Tests cover a line on a Mains-class net, a line inside a mains region, a low-voltage net whose copper crosses a region while its printed point lies outside, a line with no position, a line on none of these and a log with no failing lines, in text and in JSON. This does not cover entries for any line other than a failing neatness line.
        detour = (f"VIOLATION | {DESIGN} | workmanship_detour | net /SLOW_A: 3 pads, from R1 pad 1 at (5, 5) mm to U1 pad 2 "
                  "at (5, 10) mm | the net runs 3 times its shortest")
        for start, end in (((0, 55), (70, 55)), ((55, 0), (55, 70)), ((45, 55), (55, 65)), ((40, 40), (70, 70)), ((50, 40), (50, 70))):
            with self.subTest(crossing=(start, end)):
                self.put(track("/SLOW_A", (5, 5), (5, 10), number=10), track("/SLOW_A", start, end, number=11))
                self.refused_one(log(detour), "crosses the mains region mains")
        for start, end in (((0, 5), (70, 5)), ((0, 40), (40, 70)), ((61, 40), (61, 70)), ((49, 40), (49, 70))):
            with self.subTest(clear=(start, end)):
                if os.path.exists(self.record):
                    os.remove(self.record)
                self.put(track("/SLOW_A", (5, 5), (5, 10), number=10), track("/SLOW_A", start, end, number=11))
                status, lines, report = self.both(log(detour))
                self.assertEqual((status, report["refused"]), (0, []))
                self.assertEqual([e["scope"] for e in report["entries"]], ["/SLOW_A"])

    def test_a_bracketed_net_that_differs_from_the_prefix_net_is_judged_too(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C8: Given a check log whose failing neatness lines include one on a Mains-class net, one inside a mains region and one on a low-voltage net whose copper lies in or crosses a mains region, the generator writes no entry for any of them, names each as refused and exits with failure. A line is judged from the copper of the nets it names in the board it is given, not from the positions the log prints. A line that names no resolvable net is refused when the project declares mains present and the board has a mains region. Tests cover a line on a Mains-class net, a line inside a mains region, a low-voltage net whose copper crosses a region while its printed point lies outside, a line with no position, a line on none of these and a log with no failing lines, in text and in JSON. This does not cover entries for any line other than a failing neatness line.
        self.put(track("/SLOW_A", (5, 5), (20, 5), number=10), track("/SLOW_B", (5, 8), (20, 8), number=11),
                 track("/MAINS_L", (5, 11), (20, 11), number=12), track("/SLOW_C", (52, 52), (58, 58), number=13))
        for bracket, why in (("/MAINS_L", "net /MAINS_L is in the net class Mains, a mains class"),
                             ("/SLOW_C", "copper of net /SLOW_C")):
            with self.subTest(bracket=bracket):
                text = f"VIOLATION | {DESIGN} | workmanship_pad_corner | net /SLOW_A: Track [{bracket}] on F.Cu | message"
                self.refused_one(log(text), why, "workmanship_pad_corner")
        both = f"VIOLATION | {DESIGN} | workmanship_pad_corner | net /SLOW_A: Track [/SLOW_B] on F.Cu | message"
        status, lines, report = self.both(log(both), "--partial")
        self.assertEqual((status, report["entries"], len(report["refused"])), (1, [], 1))
        self.assertIn("names 2 nets", report["refused"][0]["why"], "two clear nets are still refused for having no one kind")

    def test_a_line_naming_no_net_with_copper_on_the_board_is_refused_while_mains_is_present_and_a_region_exists(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C8: Given a check log whose failing neatness lines include one on a Mains-class net, one inside a mains region and one on a low-voltage net whose copper lies in or crosses a mains region, the generator writes no entry for any of them, names each as refused and exits with failure. A line is judged from the copper of the nets it names in the board it is given, not from the positions the log prints. A line that names no resolvable net is refused when the project declares mains present and the board has a mains region. Tests cover a line on a Mains-class net, a line inside a mains region, a low-voltage net whose copper crosses a region while its printed point lies outside, a line with no position, a line on none of these and a log with no failing lines, in text and in JSON. This does not cover entries for any line other than a failing neatness line.
        names_none = f"VIOLATION | {DESIGN} | silk_overlap | Footprint R1 @ (5, 5) mm | silkscreen overlaps"
        absent = f"VIOLATION | {DESIGN} | workmanship_pad_corner | net /NOT_ON_BOARD: Track [/NOT_ON_BOARD] on F.Cu | message"
        for text in (names_none, absent):
            with self.subTest(text=text[:60]):
                rule = text.split(" | ")[2]
                self.refused_one(log(text), "so a mains region cannot be ruled out", rule)
        self.declare("none")
        self.write("b/low.kicad_pcb", board_text([]))
        status, lines, report = self.both(log(line("workmanship_pad_corner", "/SLOW_A")))
        self.assertEqual((status, report["refused"]), (0, []), "no mains declared: the net's own kind decides")

    def test_a_low_voltage_zone_clear_of_every_region_is_entered_and_the_other_nets_are_judged_by_their_own_copper(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C8: Given a check log whose failing neatness lines include one on a Mains-class net, one inside a mains region and one on a low-voltage net whose copper lies in or crosses a mains region, the generator writes no entry for any of them, names each as refused and exits with failure. A line is judged from the copper of the nets it names in the board it is given, not from the positions the log prints. A line that names no resolvable net is refused when the project declares mains present and the board has a mains region. Tests cover a line on a Mains-class net, a line inside a mains region, a low-voltage net whose copper crosses a region while its printed point lies outside, a line with no position, a line on none of these and a log with no failing lines, in text and in JSON. This does not cover entries for any line other than a failing neatness line.
        self.put(zone("plane", "/sheet/GND", "F.Cu", [(0, 0), (40, 0), (40, 40), (0, 40)], ""),
                 track("/SLOW_A", (5, 5), (20, 5), number=10))
        status, lines, report = self.both(log(line("workmanship_pad_corner", "/sheet/GND"), line("workmanship_pad_corner", "/SLOW_A")))
        self.assertEqual((status, report["refused"]), (0, []))
        self.assertEqual(sorted(e["scope"] for e in report["entries"]), ["/SLOW_A", "/sheet/GND"])

    def test_mains_and_low_voltage_lines_together_write_nothing_by_default_and_the_low_voltage_ones_with_partial(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C8: Given a check log whose failing neatness lines include one on a Mains-class net, one inside a mains region and one on a low-voltage net whose copper lies in or crosses a mains region, the generator writes no entry for any of them, names each as refused and exits with failure. A line is judged from the copper of the nets it names in the board it is given, not from the positions the log prints. A line that names no resolvable net is refused when the project declares mains present and the board has a mains region. Tests cover a line on a Mains-class net, a line inside a mains region, a low-voltage net whose copper crosses a region while its printed point lies outside, a line with no position, a line on none of these and a log with no failing lines, in text and in JSON. This does not cover entries for any line other than a failing neatness line.
        self.put(track("/SLOW_A", (55, 52), (55, 58), number=10), track("/SLOW_B", (5, 5), (20, 5), number=11))
        mixed = log(line("workmanship_pad_corner", "/MAINS_L"), line("workmanship_pad_corner", "/SLOW_A"),
                    line("workmanship_pad_corner", "/SLOW_B"))
        status, lines, report = self.both(mixed)
        self.assertEqual(status, 1)
        self.assertEqual(self.record_text(), "", "nothing is written while any line is refused")
        self.assertEqual(len(report["refused"]), 2)
        self.assertEqual(report["written"], False)
        status, lines, report = self.both(mixed, "--partial")
        self.assertEqual(status, 1, "a refusal fails even when the rest is written")
        written = self.record_text()
        self.assertIn('scope: "/SLOW_B"', written)
        for held in ("/MAINS_L", "/SLOW_A"):
            self.assertNotIn(held, written)
        self.assertEqual([e["scope"] for e in report["entries"]], ["/SLOW_B"])

    def test_a_log_with_no_failing_lines_writes_nothing_and_passes(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C8: Given a check log whose failing neatness lines include one on a Mains-class net, one inside a mains region and one on a low-voltage net whose copper lies in or crosses a mains region, the generator writes no entry for any of them, names each as refused and exits with failure. A line is judged from the copper of the nets it names in the board it is given, not from the positions the log prints. A line that names no resolvable net is refused when the project declares mains present and the board has a mains region. Tests cover a line on a Mains-class net, a line inside a mains region, a low-voltage net whose copper crosses a region while its printed point lies outside, a line with no position, a line on none of these and a log with no failing lines, in text and in JSON. This does not cover entries for any line other than a failing neatness line.
        for text in (log(), log(line("workmanship_pad_corner", "/SLOW_A", kind="ACCEPTED")),
                     log(line("workmanship_pad_corner", "/SLOW_A", design="hardware/other/o.kicad_pro"), design=DESIGN)):
            with self.subTest(log=text[:60]):
                status, lines, report = self.both(text)
                self.assertEqual((status, report["entries"], report["refused"], report["written"]), (0, [], [], False))
                self.assertFalse(os.path.exists(self.record))
                self.assertTrue(lines[-1].startswith("RESULT | PASS | 0 entries"), lines)

    def test_a_failing_line_of_a_rule_the_record_does_not_accept_is_counted_and_never_refused_or_entered(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C8: Given a check log whose failing neatness lines include one on a Mains-class net, one inside a mains region and one on a low-voltage net whose copper lies in or crosses a mains region, the generator writes no entry for any of them, names each as refused and exits with failure. A line is judged from the copper of the nets it names in the board it is given, not from the positions the log prints. A line that names no resolvable net is refused when the project declares mains present and the board has a mains region. Tests cover a line on a Mains-class net, a line inside a mains region, a low-voltage net whose copper crosses a region while its printed point lies outside, a line with no position, a line on none of these and a log with no failing lines, in text and in JSON. This does not cover entries for any line other than a failing neatness line.
        status, lines, report = self.both(log(line("mains_to_mains", "/MAINS_L"), line("hole_to_hole", "/SLOW_A")))
        self.assertEqual((status, report["entries"], report["refused"], report["not_covered"]), (0, [], [], 2))
        self.assertIn("2 failing lines of other rules not covered", lines[-1])
        self.assertFalse(os.path.exists(self.record))

    def test_the_mains_class_patterns_and_region_names_are_arguments(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C8: Given a check log whose failing neatness lines include one on a Mains-class net, one inside a mains region and one on a low-voltage net whose copper lies in or crosses a mains region, the generator writes no entry for any of them, names each as refused and exits with failure. A line is judged from the copper of the nets it names in the board it is given, not from the positions the log prints. A line that names no resolvable net is refused when the project declares mains present and the board has a mains region. Tests cover a line on a Mains-class net, a line inside a mains region, a low-voltage net whose copper crosses a region while its printed point lies outside, a line with no position, a line on none of these and a log with no failing lines, in text and in JSON. This does not cover entries for any line other than a failing neatness line.
        # /SLOW_A is Default class; naming Default as a mains class refuses it, and /MAINS_L is then no longer refused by class.
        status, lines, report = self.both(log(line("workmanship_pad_corner", "/SLOW_A")), "--mains-class", "Default")
        self.assertEqual((status, len(report["refused"])), (1, 1))
        status, lines, report = self.both(log(line("workmanship_pad_corner", "/MAINS_L")), "--mains-class", "Default")
        self.assertEqual(status, 1, "the net has no table kind, so it is refused for that, not as mains")
        self.assertIn("is in no net kind", report["refused"][0]["why"])
        status, lines, report = self.both(log(line("workmanship_pad_corner", "/SLOW_A", (5, 5))), "--mains-region", "mains")
        self.assertEqual((status, len(report["entries"])), (0, 1))
        status, lines = self.generate(log(line("workmanship_pad_corner", "/SLOW_A", (55, 55))), "--mains-region", "second")
        self.assertEqual(status, 2, "a region named by argument must exist while MAINS is present")

    def declare(self, value, classes=("Default", "Mains", "Mains_Entry")):
        """Rewrite the project file with MAINS declared `value` (None: not declared) and the net classes it defines."""
        data = {"net_settings": {"classes": [{"name": name} for name in classes],
                                 "netclass_assignments": {"/LINE_X": "Mains"},
                                 "netclass_patterns": [{"netclass": "Mains", "pattern": "/MAINS_*"}]},
                "text_variables": {} if value is None else {"MAINS": value}}
        self.write("b/low.kicad_pro", json.dumps(data))

    def refusal(self, text, *extra):
        """(exit status, stderr) of a run in each format; both stop with exit 2 and the same message on stderr."""
        messages = []
        for fmt in ("text", "json"):
            done = subprocess.run([sys.executable, os.path.join(TOOLS, "acceptance_entries.py"), *self.argv(text, *extra),
                                   "--format", fmt], capture_output=True, text=True)
            self.assertEqual(done.returncode, 2, done.stderr)
            self.assertEqual(done.stdout == "", fmt == "text", done.stdout)
            self.assertTrue(done.stderr.startswith("CANNOT RUN | "), done.stderr)
            messages.append(done.stderr)
        self.assertEqual(messages[0], messages[1])
        return messages[0]

    def test_a_board_declaring_mains_present_must_hold_the_mains_region_whatever_it_is_named(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C8: Given a check log whose failing neatness lines include one on a Mains-class net, one inside a mains region and one on a low-voltage net whose copper lies in or crosses a mains region, the generator writes no entry for any of them, names each as refused and exits with failure. A line is judged from the copper of the nets it names in the board it is given, not from the positions the log prints. A line that names no resolvable net is refused when the project declares mains present and the board has a mains region. Tests cover a line on a Mains-class net, a line inside a mains region, a low-voltage net whose copper crosses a region while its printed point lies outside, a line with no position, a line on none of these and a log with no failing lines, in text and in JSON. This does not cover entries for any line other than a failing neatness line.
        text = log(line("workmanship_pad_corner", "/SLOW_A", (55, 55)))
        self.write("b/low.kicad_pcb", board_text([REGION.replace('(name "mains")', '(name "HV_AREA")'),
                                                  track("/SLOW_A", (55, 52), (55, 58))]))
        message = self.refusal(text)
        self.assertIn("no rule area named mains", message)
        self.assertIn("holds the rule areas HV_AREA", message)
        self.assertIn("--mains-region", message)
        self.assertEqual(self.generate(text)[0], 2)
        self.assertEqual(self.record_text(), "", "nothing is entered for a line whose region could not be told")
        status, lines, report = self.both(text, "--mains-region", "HV_AREA")
        self.assertEqual((status, len(report["refused"]), report["entries"]), (1, 1, []))
        self.assertIn("lies in or crosses the mains region HV_AREA", report["refused"][0]["why"])
        self.write("b/low.kicad_pcb", board_text([]))
        self.assertIn("holds no rule area", self.refusal(text))

    def test_every_rule_area_whose_name_holds_the_mains_pattern_is_a_mains_region_and_other_keepouts_are_not(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C8: Given a check log whose failing neatness lines include one on a Mains-class net, one inside a mains region and one on a low-voltage net whose copper lies in or crosses a mains region, the generator writes no entry for any of them, names each as refused and exits with failure. A line is judged from the copper of the nets it names in the board it is given, not from the positions the log prints. A line that names no resolvable net is refused when the project declares mains present and the board has a mains region. Tests cover a line on a Mains-class net, a line inside a mains region, a low-voltage net whose copper crosses a region while its printed point lies outside, a line with no position, a line on none of these and a log with no failing lines, in text and in JSON. This does not cover entries for any line other than a failing neatness line.
        def area(name, uuid, x):
            return REGION.replace('(name "mains")', f'(name "{name}")').replace("00000000-0000-4000-8000-000000000001", uuid) \
                .replace("(xy 50 50) (xy 60 50) (xy 60 60) (xy 50 60)", f"(xy {x} 50) (xy {x + 10} 50) (xy {x + 10} 60) (xy {x} 60)")
        areas = [area("mains", "00000000-0000-4000-8000-000000000001", 50),
                 area("H3 Mains pour pull-back", "00000000-0000-4000-8000-000000000002", 70),
                 area("antenna keepout", "00000000-0000-4000-8000-000000000003", 90)]
        for x, refused in ((55, True), ((75), True), ((95), False)):
            if os.path.exists(self.record):
                os.remove(self.record)
            self.write("b/low.kicad_pcb", board_text([*areas, track("/SLOW_A", (x, 52), (x, 58))]))
            status, lines, report = self.both(log(line("workmanship_pad_corner", "/SLOW_A")))
            self.assertEqual((status, len(report["refused"]), len(report["entries"])), (1, 1, 0) if refused else (0, 0, 1), (x, lines))
            if refused:
                self.assertIn("lies in or crosses the mains region", report["refused"][0]["why"])
                self.assertTrue(any(l.startswith("REFUSED | ") for l in lines), lines)
        os.remove(self.record)
        status, lines, report = self.both(log(line("workmanship_pad_corner", "/SLOW_A")), "--mains-region", "keepout")
        self.assertEqual((status, len(report["refused"])), (1, 1), "the argument overrides the pattern")

    def test_a_board_declaring_no_mains_needs_no_region_and_an_undeclared_one_is_refused(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C8: Given a check log whose failing neatness lines include one on a Mains-class net, one inside a mains region and one on a low-voltage net whose copper lies in or crosses a mains region, the generator writes no entry for any of them, names each as refused and exits with failure. A line is judged from the copper of the nets it names in the board it is given, not from the positions the log prints. A line that names no resolvable net is refused when the project declares mains present and the board has a mains region. Tests cover a line on a Mains-class net, a line inside a mains region, a low-voltage net whose copper crosses a region while its printed point lies outside, a line with no position, a line on none of these and a log with no failing lines, in text and in JSON. This does not cover entries for any line other than a failing neatness line.
        text = log(line("workmanship_pad_corner", "/SLOW_A", (55, 55)))
        self.write("b/low.kicad_pcb", board_text([]))
        self.declare("none")
        status, lines, report = self.both(text)
        self.assertEqual((status, len(report["entries"])), (0, 1), lines)
        os.remove(self.record)
        status, lines, report = self.both(text, "--mains-region", "absent")
        self.assertEqual((status, len(report["entries"])), (0, 1), lines)
        for value in (None, "maybe"):
            self.declare(value)
            self.assertIn("the project variable MAINS", self.refusal(text))

    def test_a_board_declaring_mains_present_must_define_a_class_the_mains_pattern_matches(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C8: Given a check log whose failing neatness lines include one on a Mains-class net, one inside a mains region and one on a low-voltage net whose copper lies in or crosses a mains region, the generator writes no entry for any of them, names each as refused and exits with failure. A line is judged from the copper of the nets it names in the board it is given, not from the positions the log prints. A line that names no resolvable net is refused when the project declares mains present and the board has a mains region. Tests cover a line on a Mains-class net, a line inside a mains region, a low-voltage net whose copper crosses a region while its printed point lies outside, a line with no position, a line on none of these and a log with no failing lines, in text and in JSON. This does not cover entries for any line other than a failing neatness line.
        text = log(line("workmanship_pad_corner", "/SLOW_A"))
        self.declare("present", classes=("Default", "HighVoltage"))
        message = self.refusal(text)
        self.assertIn("defines no net class matching Mains*", message)
        self.assertIn("HighVoltage", message)
        self.assertEqual(self.generate(text, "--mains-class", "HighVoltage")[0], 0)
        os.remove(self.record)
        self.declare("none", classes=("Default", "HighVoltage"))
        self.assertEqual(self.generate(text)[0], 0)

    def test_a_region_named_on_the_command_line_must_exist_when_mains_is_present(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C8: Given a check log whose failing neatness lines include one on a Mains-class net, one inside a mains region and one on a low-voltage net whose copper lies in or crosses a mains region, the generator writes no entry for any of them, names each as refused and exits with failure. A line is judged from the copper of the nets it names in the board it is given, not from the positions the log prints. A line that names no resolvable net is refused when the project declares mains present and the board has a mains region. Tests cover a line on a Mains-class net, a line inside a mains region, a low-voltage net whose copper crosses a region while its printed point lies outside, a line with no position, a line on none of these and a log with no failing lines, in text and in JSON. This does not cover entries for any line other than a failing neatness line.
        text = log(line("workmanship_pad_corner", "/SLOW_A"))
        self.assertIn("no rule area named absent", self.refusal(text, "--mains-region", "absent"))
        self.write("b/low.kicad_pcb", board_text([]))
        self.assertIn("no rule area named mains", self.refusal(text))


class EntriesFollowTheTable(Generator):
    def test_each_net_kind_of_the_table_gives_its_reason_to_the_entry_it_writes(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C9: Over a synthetic board and check log, every entry the generator writes, with its reason taken from the board's table by net kind, is accepted by the pre-order check, which then no longer reports the entry's line as failing. Tests cover each net kind in the table and a net kind missing from the table, which the generator refuses by name. This does not cover the reasons themselves, which each board's table holds.
        status, lines, report = self.both(log(line("workmanship_pad_corner", "/SLOW_A"), line("workmanship_pad_corner", "/SLOW_A"),
                                              line("workmanship_detour", "/SLOW_A"), line("workmanship_pad_corner", "+5V"),
                                              line("workmanship_pad_corner", "/sheet/GND")))
        self.assertEqual(status, 0, lines)
        got = {(e["rule"], e["scope"]): (e["count"], e["kind"], e["reason"]) for e in report["entries"]}
        self.assertEqual(got, {
            ("workmanship_pad_corner", "/SLOW_A"): (2, "slow signal", "a synthetic reason for a slow signal corner"),
            ("workmanship_detour", "/SLOW_A"): (1, "slow signal", "a synthetic reason for a slow signal detour"),
            ("workmanship_pad_corner", "+5V"): (1, "supply", "a synthetic reason for a supply corner"),
            ("workmanship_pad_corner", "/sheet/GND"): (1, "supply", "a synthetic reason for a supply corner")})
        yaml = board_check.require_yaml()
        record = board_check.strict_yaml(yaml, self.record_text())
        self.assertEqual(record["synthetic"], True)
        for entry in record["accepted_workmanship"]:
            self.assertEqual(set(entry), set(board_check.WORKMANSHIP_ENTRY_KEYS))
            self.assertEqual((entry["accepted_by"], str(entry["accepted_on"])), ("proof-owner", "2026-10-01"))
            self.assertIsNone(board_check.entry_unsigned(entry, None, __import__("datetime").date(2026, 10, 2)))
        by = {(e["rule"], e["scope"]): e for e in record["accepted_workmanship"]}
        self.assertEqual(by[("workmanship_pad_corner", "/SLOW_A")]["count"], 2)
        self.assertEqual(by[("workmanship_pad_corner", "+5V")]["bounded_by"], "a synthetic supply bound")

    def test_a_net_in_no_kind_a_kind_without_the_rule_and_a_net_in_two_kinds_are_refused_by_name(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C9: Over a synthetic board and check log, every entry the generator writes, with its reason taken from the board's table by net kind, is accepted by the pre-order check, which then no longer reports the entry's line as failing. Tests cover each net kind in the table and a net kind missing from the table, which the generator refuses by name. This does not cover the reasons themselves, which each board's table holds.
        status, lines, report = self.both(log(line("workmanship_pad_corner", "/UNKNOWN_NET")))
        self.assertEqual(status, 1)
        self.assertEqual(self.record_text(), "")
        self.assertIn("the net /UNKNOWN_NET is in no net kind of the reasons table", report["refused"][0]["why"])
        self.assertTrue(any(l.startswith("REFUSED | workmanship_pad_corner") and "/UNKNOWN_NET" in l for l in lines), lines)
        status, lines, report = self.both(log(line("workmanship_detour", "+5V")))
        self.assertEqual(status, 1)
        self.assertIn("the net kind supply of the reasons table has no reason for the rule workmanship_detour", report["refused"][0]["why"])
        both = TABLE + ('  - kind: also slow\n    nets: ["/SLOW_*"]\n    bounded_by: x\n    reasons:\n      workmanship_pad_corner: y\n')
        table = self.write("b/two.yaml", both)
        status, lines = self.generate(log(line("workmanship_pad_corner", "/SLOW_A")), table=table)
        self.assertEqual(status, 1)
        self.assertTrue(any("more than one net kind" in l and "slow signal, also slow" in l for l in lines), lines)

    def test_a_line_naming_no_net_or_several_is_refused_for_having_no_kind(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C9: Over a synthetic board and check log, every entry the generator writes, with its reason taken from the board's table by net kind, is accepted by the pre-order check, which then no longer reports the entry's line as failing. Tests cover each net kind in the table and a net kind missing from the table, which the generator refuses by name. This does not cover the reasons themselves, which each board's table holds.
        none = f"VIOLATION | {DESIGN} | silk_overlap | Footprint R1 @ (5, 5) mm | silkscreen overlaps"
        two = f"VIOLATION | {DESIGN} | track_angle | Track [/SLOW_A] on F.Cu @ (5, 5) mm; Track [/SLOW_B] on F.Cu @ (6, 6) mm | angle"
        status, lines, report = self.both(log(none, two))
        self.assertEqual(status, 1)
        self.assertEqual([r["rule"] for r in report["refused"]], ["silk_overlap", "track_angle"])
        self.assertIn("a mains region cannot be ruled out", report["refused"][0]["why"])
        self.assertIn("names 2 nets", report["refused"][1]["why"])

    def test_an_entry_the_record_already_holds_is_never_raised_and_a_stale_one_is_removed(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C9: Over a synthetic board and check log, every entry the generator writes, with its reason taken from the board's table by net kind, is accepted by the pre-order check, which then no longer reports the entry's line as failing. Tests cover each net kind in the table and a net kind missing from the table, which the generator refuses by name. This does not cover the reasons themselves, which each board's table holds.
        def entry(rule, scope, count):
            return (f"  - rule: {rule}\n    scope: \"{scope}\"\n    count: {count}\n    reason: r\n    bounded_by: b\n"
                    "    accepted_by: \"proof-owner\"\n    accepted_on: \"2026-09-01\"\n")
        existing = ("# the owner's own header comment\naccepted_workmanship:\n  # a note for the first entry\n"
                    + entry("workmanship_pad_corner", "/SLOW_A", 1) + "\n  # a note for the stale entry\n"
                    + entry("workmanship_detour", "/SLOW_B", 1) + "synthetic: true\n")
        self.write("b/workmanship-acceptance.yaml", existing)
        stale = (f"VIOLATION | {DESIGN} | workmanship_acceptance | {self.record} accepted_workmanship[1] | "
                 "accepted_workmanship[1] (workmanship_detour at /SLOW_B) is used by no line: the entry is stale; remove it")
        status, lines = self.generate(log(line("workmanship_pad_corner", "/SLOW_A"), stale))
        self.assertEqual(status, 1)
        self.assertTrue(any(l.startswith("REFUSED | workmanship_pad_corner") and "already exists and is exhausted" in l for l in lines), lines)
        status, report = self.generate_json(log(line("workmanship_pad_corner", "/SLOW_A"), stale))
        self.assertEqual((status, report["written"]), (1, False))
        self.assertIn("a signed count is never raised", report["refused"][0]["why"])
        self.assertEqual(self.record_text(), existing, "a refused run leaves the record as it was")
        status, lines = self.generate(log(line("workmanship_pad_corner", "/SLOW_C"), stale), "--partial")
        self.assertEqual(status, 0, lines)
        self.assertIn("REMOVED | workmanship_detour | /SLOW_B | stale entry 1", lines)
        text = self.record_text()
        self.assertIn("# the owner's own header comment", text)
        self.assertIn("# a note for the first entry", text)
        self.assertNotIn('"/SLOW_B"', text)
        self.assertNotIn("a note for the stale entry", text)
        record = board_check.strict_yaml(board_check.require_yaml(), text)
        self.assertEqual([(e["rule"], e["scope"]) for e in record["accepted_workmanship"]],
                         [("workmanship_pad_corner", "/SLOW_A"), ("workmanship_pad_corner", "/SLOW_C")])

    def test_removing_the_last_entry_leaves_a_record_the_check_reads_as_empty(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C9: Over a synthetic board and check log, every entry the generator writes, with its reason taken from the board's table by net kind, is accepted by the pre-order check, which then no longer reports the entry's line as failing. Tests cover each net kind in the table and a net kind missing from the table, which the generator refuses by name. This does not cover the reasons themselves, which each board's table holds.
        self.write("b/workmanship-acceptance.yaml", "accepted_workmanship:\n  - rule: workmanship_detour\n    scope: \"/SLOW_B\"\n    count: 1\n"
                   "    reason: r\n    bounded_by: b\n    accepted_by: \"proof-owner\"\n    accepted_on: \"2026-09-01\"\nsynthetic: true\n")
        stale = (f"VIOLATION | {DESIGN} | workmanship_acceptance | {self.record} accepted_workmanship[0] | "
                 "accepted_workmanship[0] (workmanship_detour at /SLOW_B) is used by no line: stale")
        status, lines = self.generate(log(stale))
        self.assertEqual(status, 0, lines)
        record = board_check.strict_yaml(board_check.require_yaml(), self.record_text())
        self.assertEqual(record["accepted_workmanship"], [])

    def test_a_dry_run_reports_and_writes_nothing(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C9: Over a synthetic board and check log, every entry the generator writes, with its reason taken from the board's table by net kind, is accepted by the pre-order check, which then no longer reports the entry's line as failing. Tests cover each net kind in the table and a net kind missing from the table, which the generator refuses by name. This does not cover the reasons themselves, which each board's table holds.
        status, lines, report = self.both(log(line("workmanship_pad_corner", "/SLOW_A")), "--dry-run")
        self.assertEqual((status, report["written"]), (0, False))
        self.assertFalse(os.path.exists(self.record))
        self.assertIn("1 entries would be written", lines[-1])


class TheToolCannotRunOnInputsItCannotTrust(Generator):
    def cannot(self, argv, said):
        before = self.record_text()
        for fmt in ("text", "json"):
            done = subprocess.run([sys.executable, os.path.join(TOOLS, "acceptance_entries.py"), *argv, "--format", fmt],
                                  capture_output=True, text=True, timeout=120)
            self.assertEqual(done.returncode, 2, (fmt, done.stdout, done.stderr))
            self.assertTrue(done.stderr.startswith("CANNOT RUN | "), done.stderr)
            self.assertIn(said, done.stderr)
            self.assertEqual(self.record_text(), before, "a tool that cannot run writes nothing")
            if fmt == "json":
                self.assertEqual(json.loads(done.stdout)["result"], "CANNOT RUN")
            else:
                self.assertEqual(done.stdout, "")

    def test_a_file_that_is_no_check_log_or_is_missing_or_names_several_designs_stops_the_tool(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C8: Given a check log whose failing neatness lines include one on a Mains-class net, one inside a mains region and one on a low-voltage net whose copper lies in or crosses a mains region, the generator writes no entry for any of them, names each as refused and exits with failure. A line is judged from the copper of the nets it names in the board it is given, not from the positions the log prints. A line that names no resolvable net is refused when the project declares mains present and the board has a mains region. Tests cover a line on a Mains-class net, a line inside a mains region, a low-voltage net whose copper crosses a region while its printed point lies outside, a line with no position, a line on none of these and a log with no failing lines, in text and in JSON. This does not cover entries for any line other than a failing neatness line.
        self.cannot(self.argv("not a log\n"), "has no DESIGN line")
        self.cannot(self.argv(""), "has no DESIGN line")
        argv = self.argv(log())
        argv[argv.index("--log") + 1] = self.path("missing.log")
        self.cannot(argv, "cannot be read")
        many = log(line("workmanship_pad_corner", "/SLOW_A")) + f"DESIGN | hardware/other/o.kicad_pro | PASS | 0\n"
        self.cannot(self.argv(many), "names several designs")
        status, lines = self.generate(many, "--design", "hardware/other/o.kicad_pro")
        self.assertEqual(status, 0, "naming the design chooses it")
        self.cannot(self.argv(many, "--design", "hardware/nowhere/x.kicad_pro"), "names no design")

    def test_a_table_that_is_unreadable_malformed_or_cannot_sign_stops_the_tool(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C9: Over a synthetic board and check log, every entry the generator writes, with its reason taken from the board's table by net kind, is accepted by the pre-order check, which then no longer reports the entry's line as failing. Tests cover each net kind in the table and a net kind missing from the table, which the generator refuses by name. This does not cover the reasons themselves, which each board's table holds.
        text = log(line("workmanship_pad_corner", "/SLOW_A"))
        self.cannot(self.argv(text, table=self.path("none.yaml")), "reasons table")
        cases = {
            "placeholder signer": (TABLE.replace('"proof-owner"', '"<owner>"'), "cannot sign an entry"),
            "empty signer": (TABLE.replace('"proof-owner"', '""'), "cannot sign an entry"),
            "not yaml": ("net_kinds: [", "not readable YAML"),
            "not a mapping": ("- a\n", "is a mapping of"),
            "no kinds": ('accepted_by: "x"\n', "is a mapping of"),
            "a rule the record refuses": (TABLE.replace("workmanship_detour", "hole_to_hole"), "does not accept"),
            "an empty reason": (TABLE.replace("a synthetic reason for a slow signal detour", '""'), "is empty or not text"),
            "a kind named twice": (TABLE + TABLE.split("net_kinds:\n")[1], "names the kind slow signal twice"),
            "no patterns": (TABLE.replace('nets: ["/SLOW_*"]', "nets: []"), "not a list of net name patterns"),
            "a key too many": (TABLE.replace("    bounded_by: a synthetic bound\n", "    bounded_by: a\n    extra: 1\n", 1), "exactly kind, nets"),
            "synthetic that is no boolean": (TABLE.replace("synthetic: true", "synthetic: maybe"), "true or false"),
            "a key given twice": (TABLE.replace("synthetic: true\n", "synthetic: true\nsynthetic: false\n"), "more than once"),
        }
        for name, (content, said) in cases.items():
            with self.subTest(case=name):
                self.cannot(self.argv(text, table=self.write("b/bad.yaml", content)), said)
        self.cannot(self.argv(text) + ["--accepted-on", "2999-01-01"], "later than today")
        self.cannot(self.argv(text) + ["--accepted-on", "yesterday"], "not a date")

    def test_a_board_a_project_or_a_record_that_cannot_be_read_stops_the_tool(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C8: Given a check log whose failing neatness lines include one on a Mains-class net, one inside a mains region and one on a low-voltage net whose copper lies in or crosses a mains region, the generator writes no entry for any of them, names each as refused and exits with failure. A line is judged from the copper of the nets it names in the board it is given, not from the positions the log prints. A line that names no resolvable net is refused when the project declares mains present and the board has a mains region. Tests cover a line on a Mains-class net, a line inside a mains region, a low-voltage net whose copper crosses a region while its printed point lies outside, a line with no position, a line on none of these and a log with no failing lines, in text and in JSON. This does not cover entries for any line other than a failing neatness line.
        text = log(line("workmanship_pad_corner", "/SLOW_A"))
        self.write("b/low.kicad_pcb", "not a board")
        self.cannot(self.argv(text), "low.kicad_pcb")
        self.write("b/low.kicad_pcb", board_text([REGION]))
        self.write("b/low.kicad_pro", "{")
        self.cannot(self.argv(text), "project file")
        self.write("b/low.kicad_pro", json.dumps({"text_variables": {"MAINS": "none"}}))
        self.write("b/workmanship-acceptance.yaml", "accepted_workmanship: nothing\n")
        self.cannot(self.argv(text), "holding an accepted_workmanship list")
        self.write("b/workmanship-acceptance.yaml", "accepted_workmanship:\n  - {rule: workmanship_detour, scope: x, count: 1, reason: r, bounded_by: b, accepted_by: a, accepted_on: '2026-01-01'}\n")
        self.cannot(self.argv(text), "block list of entries")


class TheRealCheckAcceptsTheEntries(unittest.TestCase):
    """The generator run on the real pre-order check's own log of a seeded synthetic board."""

    def setUp(self):
        scratch = tempfile.TemporaryDirectory(prefix="acceptance-generator-test-")
        self.addCleanup(scratch.cleanup)
        self.scratch = scratch.name
        self.seed = board_prove.prepare(self.scratch)
        board_prove.right_angle(self.seed)
        self.seed.layout(self.jog)
        self.seed.layout(self.region)

    @staticmethod
    def jog(tree):
        """/LV_A's track replaced by one with a short jog, under uuids of its own so they do not clash with the bend's."""
        tree.remove(board_prove.track_at(tree, *board_prove.LV_A_ENDS))
        points = [(40, 10), (42, 10), (42.3, 10.3), (45, 10.3)]
        for index, (a, b) in enumerate(zip(points, points[1:])):
            tree.insert(len(tree) - 1, board_prove.segment("/LV_A", *a, *b, f"0b0e5c1a-0000-4000-8000-0000000009{index:02d}"))

    @staticmethod
    def region(tree):
        """The mains rule area the board's MAINS declaration requires, off every net's copper."""
        tree.insert(len(tree) - 1, sexpr.parse_one(REGION.replace("(xy 50 50) (xy 60 50) (xy 60 60) (xy 50 60)",
                                                                  "(xy 90 90) (xy 91 90) (xy 91 91) (xy 90 91)")))

    def checked(self):
        status, lines, stderr = board_prove.check(self.seed, KICAD_CLI)
        self.assertNotEqual(status, 2, f"the pre-order check could not run (KICAD_CLI is {KICAD_CLI}): {stderr}")
        return status, lines

    def generate(self, lines, table_text, *extra):
        log_path = os.path.join(self.scratch, "check.log")
        with open(log_path, "w", encoding="utf-8") as handle:
            handle.write("\n".join(lines) + "\n")
        table = os.path.join(self.scratch, "table.yaml")
        with open(table, "w", encoding="utf-8") as handle:
            handle.write(table_text)
        design = self.seed.design
        out = subprocess.run([sys.executable, os.path.join(TOOLS, "acceptance_entries.py"), "--log", log_path,
                              "--board", self.seed.path(".kicad_pcb"), "--project", self.seed.path(".kicad_pro"), "--table", table,
                              "--accepted-on", "2026-10-01", "--format", "json", *extra],
                             capture_output=True, text=True, timeout=300)
        return out.returncode, json.loads(out.stdout), os.path.join(design, board_check.WORKMANSHIP_ACCEPTANCE_NAME)

    def test_every_entry_written_for_each_net_kind_is_accepted_and_its_lines_stop_failing(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C9: Over a synthetic board and check log, every entry the generator writes, with its reason taken from the board's table by net kind, is accepted by the pre-order check, which then no longer reports the entry's line as failing. Tests cover each net kind in the table and a net kind missing from the table, which the generator refuses by name. This does not cover the reasons themselves, which each board's table holds.
        # /LV_B has two track_angle lines and /LV_A one track_segment_length line: two nets, in two kinds of the table.
        table = ('accepted_by: "proof-owner"\nsynthetic: true\nnet_kinds:\n'
                 '  - kind: bend net\n    nets: ["/LV_B"]\n    bounded_by: a synthetic bound for bends\n    reasons:\n'
                 '      track_angle: a synthetic reason for a bend\n'
                 '  - kind: jog net\n    nets: ["/LV_A"]\n    bounded_by: a synthetic bound for jogs\n    reasons:\n'
                 '      track_segment_length: a synthetic reason for a jog\n')
        status, lines = self.checked()
        before = [l.split(" | ") for l in lines if l.startswith("VIOLATION | ")]
        self.assertEqual(sorted(v[2] for v in before), ["track_angle", "track_angle", "track_segment_length"], lines)
        code, report, record = self.generate(lines, table)
        self.assertEqual((code, report["result"]), (0, "PASS"), report)
        self.assertEqual(sorted((e["rule"], e["scope"], e["count"], e["kind"]) for e in report["entries"]),
                         [("track_angle", "/LV_B", 2, "bend net"), ("track_segment_length", "/LV_A", 1, "jog net")])
        self.assertTrue(os.path.isfile(record))
        status, lines = self.checked()
        self.assertEqual([l for l in lines if l.startswith("VIOLATION | ")], [], lines)
        self.assertEqual(status, 0, lines)
        accepted = [l for l in lines if l.startswith("ACCEPTED | ")]
        self.assertEqual(len(accepted), 3, lines)
        for reason in ("a synthetic reason for a bend", "a synthetic reason for a jog"):
            self.assertTrue(any(reason in l for l in accepted), accepted)
        self.assertIn("RESULT | PASS | all 1 designs passed", lines)
        # run again on the passing log: nothing to do, nothing changes
        with open(record, encoding="utf-8") as handle:
            written = handle.read()
        code, report, _ = self.generate(lines, table)
        self.assertEqual((code, report["entries"], report["written"]), (0, [], False))
        with open(record, encoding="utf-8") as handle:
            self.assertEqual(handle.read(), written)

    def test_a_net_kind_missing_from_the_table_is_refused_by_name_and_its_line_still_fails_the_check(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C9: Over a synthetic board and check log, every entry the generator writes, with its reason taken from the board's table by net kind, is accepted by the pre-order check, which then no longer reports the entry's line as failing. Tests cover each net kind in the table and a net kind missing from the table, which the generator refuses by name. This does not cover the reasons themselves, which each board's table holds.
        table = ('accepted_by: "proof-owner"\nsynthetic: true\nnet_kinds:\n'
                 '  - kind: bend net\n    nets: ["/LV_B"]\n    bounded_by: a synthetic bound for bends\n    reasons:\n'
                 '      track_angle: a synthetic reason for a bend\n')
        status, lines = self.checked()
        code, report, record = self.generate(lines, table, "--partial")
        self.assertEqual((code, report["result"]), (1, "FAIL"))
        self.assertEqual([(r["rule"], r["scope"]) for r in report["refused"]], [("track_segment_length", "/LV_A")])
        self.assertIn("the net /LV_A is in no net kind of the reasons table", report["refused"][0]["why"])
        status, lines = self.checked()
        remaining = [l.split(" | ") for l in lines if l.startswith("VIOLATION | ")]
        self.assertEqual([v[2] for v in remaining], ["track_segment_length"], lines)
        self.assertIn("[/LV_A]", remaining[0][3], "only the line of the net the table lacks fails")
        self.assertEqual(status, 1)
        self.assertEqual(len([l for l in lines if l.startswith("ACCEPTED | ")]), 2)

    def test_a_stale_entry_the_check_reports_is_cut_out_and_the_record_then_passes_the_check(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C9: Over a synthetic board and check log, every entry the generator writes, with its reason taken from the board's table by net kind, is accepted by the pre-order check, which then no longer reports the entry's line as failing. Tests cover each net kind in the table and a net kind missing from the table, which the generator refuses by name. This does not cover the reasons themselves, which each board's table holds.
        table = ('accepted_by: "proof-owner"\nsynthetic: true\nnet_kinds:\n'
                 '  - kind: bend net\n    nets: ["/LV_B"]\n    bounded_by: b\n    reasons:\n      track_angle: a synthetic reason for a bend\n'
                 '  - kind: jog net\n    nets: ["/LV_A"]\n    bounded_by: j\n    reasons:\n      track_segment_length: a synthetic reason for a jog\n')
        # An entry for a place with no such line is stale, and fails the check by itself.
        board_prove.accepting(board_prove.acceptance_entry("track_angle", "/LV_A", 1))(self.seed)
        status, lines = self.checked()
        self.assertTrue(any("is used by no line" in l for l in lines if l.startswith("VIOLATION | ")), lines)
        code, report, record = self.generate(lines, table)
        self.assertEqual((code, [(r["rule"], r["scope"]) for r in report["removed"]]), (0, [("track_angle", "/LV_A")]))
        status, lines = self.checked()
        self.assertEqual([l for l in lines if l.startswith("VIOLATION | ")], [], lines)
        self.assertEqual((status, len([l for l in lines if l.startswith("ACCEPTED | ")])), (0, 3))


class TheNotesAndThePaths(unittest.TestCase):
    def notes(self) -> str:
        with open(os.path.join(HARDWARE, "README.md"), encoding="utf-8") as handle:
            text = handle.read()
        start = text.index("## The acceptance-entry generator")
        return text[start:text.index("\n## ", start + 1)]

    def test_the_notes_describe_the_command_its_inputs_outputs_table_and_every_option(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C11: Each tool in this set has a test that runs it on a synthetic design built by the test, and the hardware notes describe each tool's command, its inputs, the board folder table it reads and the manual step of fetching an assembler's library footprints. Checked by reading the hardware notes against the list of tools clause by clause. This does not apply to the fetch of an assembler's library footprints, which stays a documented manual step.
        notes = self.notes()
        self.assertIn("python3 hardware/tools/acceptance_entries.py", notes)
        for needed in ("Inputs", "Output", "acceptance-reasons.yaml", "workmanship-acceptance.yaml", "refuses", "PyYAML"):
            self.assertIn(needed, notes)
        done = subprocess.run([sys.executable, os.path.join(TOOLS, "acceptance_entries.py"), "--help"], capture_output=True, text=True, timeout=120)
        self.assertEqual(done.returncode, 0, done.stderr)
        options = set(re.findall(r"--[a-z][a-z-]+", done.stdout)) - {"--help"}
        self.assertTrue(options)
        self.assertEqual(sorted(option for option in options if option not in notes), [], "an option the notes do not name")
        self.assertTrue(os.path.isfile(os.path.join(HARDWARE, "sunbeam-em7000", "main-board", "acceptance-reasons.yaml")))

    def test_the_main_boards_table_is_read_by_the_generator_and_every_kind_has_its_reasons(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C9: Over a synthetic board and check log, every entry the generator writes, with its reason taken from the board's table by net kind, is accepted by the pre-order check, which then no longer reports the entry's line as failing. Tests cover each net kind in the table and a net kind missing from the table, which the generator refuses by name. This does not cover the reasons themselves, which each board's table holds.
        # Only the table's form is read here, since a test names no real board's nets; the table is held to what the tool reads.
        import datetime
        table = acceptance_entries.Table(os.path.join(HARDWARE, "sunbeam-em7000", "main-board", "acceptance-reasons.yaml"),
                                         datetime.date.today())
        self.assertGreaterEqual(len(table.kinds), 1)
        for kind in table.kinds:
            self.assertTrue({"workmanship_pad_corner", "workmanship_pad_entry", "workmanship_detour"} <= set(kind["reasons"]), kind["kind"])

    def test_the_tool_holds_no_path_fixed_to_one_machine(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C12: Each tracked layout tool that needs KiCad's scripting interface runs it in the interpreter named by a documented environment variable, and the tool and its tests fail naming that variable when it is unset or names nothing runnable. The silkscreen command names the missing package when numpy, shapely or Pillow is not installed. No tool holds a path fixed to one machine: every tool, interpreter and board path is an argument or an environment variable. Tests cover the variable unset, the variable naming a missing file, a missing package and a path given as an argument, in text and in JSON.
        fixed = re.compile(r"(/Users/|/home/[a-z]|/Applications/|/opt/homebrew|/usr/local/|/Library/|[A-Za-z]:\\|\bProgram Files\b)")
        for path in (os.path.join(TOOLS, "acceptance_entries.py"),
                     os.path.join(HARDWARE, "sunbeam-em7000", "main-board", "acceptance-reasons.yaml")):
            with self.subTest(file=os.path.basename(path)):
                with open(path, encoding="utf-8") as handle:
                    self.assertEqual([l.strip() for l in handle if fixed.search(l)], [])

    def test_the_tool_needs_no_kicad_scripting_interpreter_and_runs_without_the_variable(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C12: Each tracked layout tool that needs KiCad's scripting interface runs it in the interpreter named by a documented environment variable, and the tool and its tests fail naming that variable when it is unset or names nothing runnable. The silkscreen command names the missing package when numpy, shapely or Pillow is not installed. No tool holds a path fixed to one machine: every tool, interpreter and board path is an argument or an environment variable. Tests cover the variable unset, the variable naming a missing file, a missing package and a path given as an argument, in text and in JSON.
        env = {k: v for k, v in os.environ.items() if k not in ("KICAD_PYTHON", "KICAD_CLI")}
        done = subprocess.run([sys.executable, os.path.join(TOOLS, "acceptance_entries.py"), "--help"], capture_output=True, text=True, env=env, timeout=120)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertNotIn("kicad-python", done.stdout)


if __name__ == "__main__":
    unittest.main()
