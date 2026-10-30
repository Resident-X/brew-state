#!/usr/bin/env python3
"""The pre-order check against KiCad itself, on the throwaway proof design, here the pours measured on the filled board and the report's shape and limit.

This is one of the files the check's KiCad tests are divided into by topic; the
shared setup, the seeded-fault proof's pooled outcomes and the exclusion of what
needs that proof are in board_kicad_fixtures.py.
"""

from __future__ import annotations

import datetime
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
from board_kicad_fixtures import load_tests, setUpModule  # noqa: E402,F401
from board_kicad_fixtures import Copy, KICAD_CLI  # noqa: E402



class ThePoursAreMeasuredOnTheBoardKiCadFilled(Copy):
    # SOL-BOARD-REVIEW-PROOF-BASELINE-CLEAN.C3: Each rule the proof design's review adds fails on a fault seeded for it and passes the clean design
    """The pour rules measure the fills the layout check has just refilled and
    saved over its copy, never the fills as committed, and saving the board
    changes nothing KiCad reports.
    """

    def rules(self, lines):
        return [v for v in self.violations(lines) if v[2] in ("mains_barrier", "paste_via", "pour_gap")]

    def stale(self, outline_top: float, fill_top: float) -> None:
        """The seeded pour over a track of its own net, its saved fill reaching up to `fill_top` and its outline to `outline_top`."""
        board_prove.track_beside_pour(self.seed)
        Q = board_prove.sexpr.Quoted

        def edit(tree: list) -> None:
            zone = board_prove.sexpr.child(tree, "zone")
            zone[zone.index(board_prove.sexpr.child(zone, "polygon"))] = [
                "polygon", ["pts", ["xy", "30", "2"], ["xy", "38", "2"], ["xy", "38", f"{outline_top:g}"], ["xy", "30", f"{outline_top:g}"]]]
            zone.append(["filled_polygon", ["layer", Q("F.Cu")], ["pts", ["xy", "30", "2"], ["xy", "38", "2"], ["xy", "38", f"{fill_top:g}"],
                                                                   ["xy", "30", f"{fill_top:g}"]]])
        self.seed.layout(edit)

    def test_the_clean_design_passes_both_rules(self):
        # SOL-BOARD-REVIEW-PROOF-BASELINE-CLEAN.C3: Each rule the proof design's review adds fails on a fault seeded for it and passes the clean design
        status, lines = self.check()
        self.assertEqual(status, 0, lines)
        self.assertEqual(self.rules(lines), [])

    def test_a_saved_fill_covering_the_track_does_not_hide_the_gap_the_refill_leaves(self):
        # SOL-BOARD-REVIEW-PROOF-BASELINE-CLEAN.C3: Each rule the proof design's review adds fails on a fault seeded for it and passes the clean design
        self.stale(outline_top=7, fill_top=7.5)
        status, lines = self.check()
        self.assertEqual(status, 1, lines)
        self.assertEqual([v[2] for v in self.rules(lines)], ["pour_gap"], lines)
        self.assertIn("stops 0.080 mm short of track", self.rules(lines)[0][4])

    def test_a_saved_fill_stopping_short_does_not_fail_a_pour_whose_refill_covers_the_track(self):
        # SOL-BOARD-REVIEW-PROOF-BASELINE-CLEAN.C3: Each rule the proof design's review adds fails on a fault seeded for it and passes the clean design
        self.stale(outline_top=8, fill_top=7)
        status, lines = self.check()
        self.assertEqual(self.rules(lines), [], lines)

    def test_saving_the_refilled_board_changes_nothing_in_kicads_report(self):
        # SOL-BOARD-REVIEW-PROOF-BASELINE-CLEAN.C3: Each rule the proof design's review adds fails on a fault seeded for it and passes the clean design
        board_prove.track_beside_pour(self.seed)
        without = self.drc("--schematic-parity", "--refill-zones", "--all-track-errors")
        saved = self.drc("--schematic-parity", "--refill-zones", "--save-board", "--all-track-errors")
        for report in (without, saved):
            report.pop("date", None)
            report.pop("source", None)
            # KiCad lists a violation's items in no fixed order, and for a missing connection it names either the pad
            # or the track ending on the same point from run to run, so a missing connection is compared by where its
            # items lie and every other violation by its items in full
            for key, entries in report.items():
                if isinstance(entries, list):
                    for entry in entries:
                        if isinstance(entry, dict) and isinstance(entry.get("items"), list):
                            if key == "unconnected_items":
                                entry["items"] = [item["pos"] for item in entry["items"]]
                            entry["items"].sort(key=lambda item: json.dumps(item, sort_keys=True))
                    entries.sort(key=lambda entry: json.dumps(entry, sort_keys=True))
        self.assertEqual(without, saved)

    def test_a_pour_round_a_pad_of_another_net_is_read_with_the_pads_hole_and_its_bridge(self):
        # SOL-BOARD-REVIEW-PROOF-BASELINE-CLEAN.C3: Each rule the proof design's review adds fails on a fault seeded for it and passes the clean design
        # R2's pad 2 on /LV_B, 1.6 mm round at (55.16, 10), sits inside a /LV_A pour: the fill is cut away round it.
        Q = board_prove.sexpr.Quoted
        zone = ["zone", ["net", Q("/LV_A")], ["layer", Q("F.Cu")], ["uuid", Q("0b0e5c1a-0000-4000-8000-000000000b00")],
                ["hatch", "edge", "0.5"], ["connect_pads", ["clearance", "0.2"]], ["min_thickness", "0.25"],
                ["fill", ["thermal_gap", "0.5"], ["thermal_bridge_width", "0.5"], ["island_removal_mode", "1"]],
                ["polygon", ["pts", ["xy", "50", "5"], ["xy", "59", "5"], ["xy", "59", "15"], ["xy", "50", "15"]]]]
        self.seed.layout(lambda tree: tree.insert(len(tree) - 1, zone))
        subprocess.run([KICAD_CLI, "pcb", "drc", "--refill-zones", "--save-board", "-o", os.path.join(self.scratch.name, "drc.rpt"),
                        board_prove.NAME + ".kicad_pcb"], cwd=self.seed.design, check=True, capture_output=True)
        fills = board_check.zone_fills(sexpr.parse_one(self.seed.read(".kicad_pcb")))
        self.assertTrue(fills)
        net, layer, ring = fills[0]
        self.assertEqual((net, layer), ("/LV_A", "F.Cu"))
        self.assertTrue(board_geometry.within((58, 14), ring))
        self.assertFalse(board_geometry.within((55.16, 10), ring), "inside the hole cut round the pad")
        self.assertGreater(len(ring), 8)
        edges = list(zip(ring, ring[1:] + ring[:1]))
        self.assertAlmostEqual(min(board_geometry.distance_to_segment((55.16, 10), a, b) for a, b in edges), 0.8 + 0.2, places=2)



class TheReport(Copy):
    """SOL-HW-BOARD-RULE-CHECK-GATE.C6: The check's report names each design, its verdict and every violation in terms a builder can act on."""

    def test_each_design_gets_a_verdict_each_violation_one_line_and_the_exit_status_matches(self):
        second = os.path.join(self.seed.root, "hardware", "other", "board")
        shutil.copytree(self.seed.design, second)
        for name in os.listdir(second):
            if name.startswith(board_prove.NAME):
                os.rename(os.path.join(second, name), os.path.join(second, name.replace(board_prove.NAME, "board")))
        shutil.copy(os.path.join(self.seed.root, board_prove.SHARED_RECORDS[0]), os.path.join(second, "manufacturer-limits.yaml"))
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



#: Ten Mains nets, nine in the class by the project file's pattern and one by
#: its name, each carrying 22 tracks: 220 items between them, more than KiCad
#: reports failures of one kind. Thirty low-voltage nets of three tracks each
#: bring the board to 310 items.
MAINS_NETS = {f"/MAINS_{index}" for index in range(9)} | {"/LIVE_FEED"}


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
    # this board carries no net ahead of an entry fuse
    data["text_variables"]["MAINS_ENTRY"] = "none"
    data["net_settings"]["netclass_patterns"] = [entry for entry in data["net_settings"]["netclass_patterns"]
                                                 if entry["netclass"] != "Mains_Entry"]
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
