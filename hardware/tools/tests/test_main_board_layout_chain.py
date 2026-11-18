#!/usr/bin/env python3
"""The main board's block scripts and tables, and the chain that rebuilds its copper from the placed board.

The first class runs the board's own chain, `layout-chain/chain.json`, over a copy of the committed board with the chain runner and holds
what it writes against the committed board with the repository's own compare tools. The others run the chain's scripts on synthetic
boards the tests write, where real data is not needed. Every script is run by KiCad's own interpreter, named by KICAD_PYTHON, and the
lock step asks kicad-cli, named by KICAD_CLI; a test that needs one fails naming the variable when it is not set.
"""

from __future__ import annotations

import collections
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import board_check  # noqa: E402
import chain_runner  # noqa: E402
import locked_copper  # noqa: E402
import sexpr  # noqa: E402
import zone_fill_diff  # noqa: E402
from layout_tool_fixtures import Work, board_text, require_kicad_python, run_python, square, track, zone  # noqa: E402
from locked_copper_fixtures import project as project_text  # noqa: E402

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.path.dirname(os.path.dirname(TOOLS))
FOLDER = os.path.join(REPO, "hardware", "sunbeam-em7000", "main-board")
CHAIN = os.path.join(FOLDER, "layout-chain")
BOARD = os.path.join(FOLDER, "main-board.kicad_pcb")
CRITICAL = ("Fast", "Ground", "Mains", "MainsBranch", "MainsTrunk", "Mains_Entry", "Sense", "Supply3V3", "Supply5V")
PROPERTIES = tuple((name, "x") for name in ("A", "B", "C", "D", "E", "F", "G", "H", "I", "J"))
FOOTPRINT = ('(footprint "test:Part" (layer "F.Cu") (uuid "00000000-0000-4000-8000-0000000000f0") (at 5 5) '
             '(property "Reference" "R1" (at 0 -2 0) (layer "F.SilkS") (uuid "00000000-0000-4000-8000-0000000000f1") '
             '(effects (font (size 1 1) (thickness 0.15)))))')


def kicad_cli() -> str:
    """The kicad-cli the lock step and the compare tools need, from KICAD_CLI, or stop naming the variable."""
    path = os.environ.get("KICAD_CLI", "")
    if not path or not os.path.isfile(path):
        message = "KICAD_CLI must name kicad-cli; it is " + (repr(path) if path else "not set")
        print(f"CANNOT RUN | {message}", file=sys.stderr, flush=True)
        raise board_check.CannotRun(message)
    return path


def setUpModule():
    require_kicad_python()
    kicad_cli()


def copper(path: str) -> collections.Counter:
    """Every track, via and copper zone of a layout, by what it is and where, never by its identifier."""
    items: collections.Counter = collections.Counter()

    def value(node, key):
        found = sexpr.child(node, key)
        return None if found is None else tuple(str(part) for part in found[1:])

    for node in sexpr.parse_one(open(path, encoding="utf-8").read()):
        if not isinstance(node, list):
            continue
        kind = sexpr.head(node)
        if kind == "segment":
            items[("segment", value(node, "start"), value(node, "end"), value(node, "width"), value(node, "layer"),
                   value(node, "net"), value(node, "locked"))] += 1
        elif kind == "via":
            items[("via", value(node, "at"), value(node, "size"), value(node, "drill"), value(node, "net"),
                   value(node, "locked"))] += 1
        elif kind == "zone":
            items[("zone", value(node, "name"), value(node, "layer") or value(node, "layers"), value(node, "net"),
                   value(node, "locked"), str(sexpr.child(node, "polygon")))] += 1
    return items


def describe(items) -> str:
    return "; ".join(str(item)[:150] for item in sorted(items, key=str)[:4]) + (" ..." if len(items) > 4 else "")


class TheChainRebuildsTheCommittedBoard(unittest.TestCase):
    """One run of the board's chain over a copy of the committed board, held against the committed board in every way below."""

    @classmethod
    def setUpClass(cls):
        cls.scratch = tempfile.TemporaryDirectory(prefix="main-board-chain-")
        cls.addClassCleanup(cls.scratch.cleanup)
        cls.placed_from = os.path.join(cls.scratch.name, "committed")
        os.makedirs(cls.placed_from)
        for suffix in (".kicad_pcb", ".kicad_pro", ".kicad_dru"):
            shutil.copyfile(os.path.join(FOLDER, "main-board" + suffix), os.path.join(cls.placed_from, "main-board" + suffix))
        cls.rebuilt_folder = os.path.join(cls.scratch.name, "rebuilt")
        os.makedirs(cls.rebuilt_folder)
        for suffix in (".kicad_pro", ".kicad_dru"):
            shutil.copyfile(os.path.join(FOLDER, "main-board" + suffix), os.path.join(cls.rebuilt_folder, "main-board" + suffix))
        cls.rebuilt = os.path.join(cls.rebuilt_folder, "main-board.kicad_pcb")
        cls.work = os.path.join(cls.scratch.name, "work")
        started = time.time()
        import io
        out = io.StringIO()
        cls.status = chain_runner.main(["--board", os.path.join(cls.placed_from, "main-board.kicad_pcb"), "--steps",
                                        os.path.join(CHAIN, "chain.json"), "--output", cls.rebuilt, "--work", cls.work], out=out)
        cls.lines = out.getvalue().splitlines()
        cls.seconds = time.time() - started
        cls.committed = copper(BOARD)
        cls.rebuilt_copper = copper(cls.rebuilt) if os.path.isfile(cls.rebuilt) else collections.Counter()

    def test_the_chain_runs_twice_to_the_same_board_at_every_step(self):
        """see C5 above; this test runs the chain on the real committed board"""
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C5: The block scripts and coordinate tables that draw the main board's copper are tracked in the main board's folder with paths relative to the repository, and running the chain runner over them from the placed board writes the same mains and low-voltage copper the committed board holds. This does not cover the wall board's scripts, which its own work delivers.
        self.assertEqual(self.status, 0, self.lines)
        steps = [line.split(" | ") for line in self.lines if line.startswith("STEP | ")]
        self.assertEqual([step[1] for step in steps],
                         ["1 placed board", "2 mains copper", "3 low-voltage reconnect", "4 chamfered mains zones", "5 critical copper locked"])
        self.assertTrue(all(step[3] == "identical on both runs" for step in steps), steps)
        self.assertTrue(self.lines[-1].startswith("RESULT | REPRODUCED | 5 steps run twice"), self.lines[-1])

    def test_the_placed_board_is_the_committed_board_without_the_copper_the_chain_draws(self):
        """the chain's first step takes up the copper the chain draws, so the later steps draw it again and do not merely keep it"""
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C5: The block scripts and coordinate tables that draw the main board's copper are tracked in the main board's folder with paths relative to the repository, and running the chain runner over them from the placed board writes the same mains and low-voltage copper the committed board holds. This does not cover the wall board's scripts, which its own work delivers.
        placed = copper(os.path.join(self.work, "run1", "01-placed board", "out", "main-board.kicad_pcb"))
        self.assertFalse(placed - self.committed, "the placed board holds an item the committed board does not: " + describe(placed - self.committed))
        taken = self.committed - placed
        kinds = collections.Counter(item[0] for item in taken.elements())
        self.assertGreater(kinds["segment"], 100, kinds)
        self.assertGreater(kinds["via"], 50, kinds)
        zones = {item[1][0] for item in taken if item[0] == "zone"}
        self.assertIn("NEUTRAL pour In2 north", zones)
        self.assertTrue({"ENTRY LINE F 9", "north PUMP_S_MT2 B"} <= zones, zones)
        self.assertTrue(all(name.startswith(("ENTRY ", "north ", "NEUTRAL pour")) for name in zones), zones)
        left = {item[1][0] for item in placed if item[0] == "zone"}
        self.assertFalse({name for name in left if name.startswith(("ENTRY ", "north ", "NEUTRAL pour"))}, left)
        # the hand-routed copper the chain does not draw is still there
        self.assertGreater(sum(placed[item] for item in placed if item[0] == "segment"), 1500)

    def test_every_track_via_and_zone_is_the_one_the_committed_board_holds(self):
        """the rebuilt board's mains and low-voltage copper, locks and zone outlines included, is the committed board's"""
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C5: The block scripts and coordinate tables that draw the main board's copper are tracked in the main board's folder with paths relative to the repository, and running the chain runner over them from the placed board writes the same mains and low-voltage copper the committed board holds. This does not cover the wall board's scripts, which its own work delivers.
        self.assertTrue(self.rebuilt_copper, "the chain wrote no board")
        self.assertEqual(sum(self.rebuilt_copper.values()), sum(self.committed.values()))
        self.assertFalse(self.committed - self.rebuilt_copper, "committed copper the chain did not draw: " + describe(self.committed - self.rebuilt_copper))
        self.assertFalse(self.rebuilt_copper - self.committed, "copper the chain drew that is not committed: " + describe(self.rebuilt_copper - self.committed))
        self.assertGreater(sum(1 for item in self.committed if item[0] == "segment" and item[-1] == ("yes",)), 1000)

    def test_the_mains_copper_compare_finds_every_mains_item_identical_and_locked(self):
        """the mains copper compare, run on the committed board and the rebuilt one, finds no mains item added, missing, changed or unlocked"""
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C5: The block scripts and coordinate tables that draw the main board's copper are tracked in the main board's folder with paths relative to the repository, and running the chain runner over them from the placed board writes the same mains and low-voltage copper the committed board holds. This does not cover the wall board's scripts, which its own work delivers.
        import io
        # 3 mm is the separation the board design and the method hold mains copper to; 0.001 mm is a distance nothing can be nearer than
        for form, distance in (("text", "3"), ("json", "3"), ("text", "0.001")):
            out = io.StringIO()
            status = locked_copper.main(["--kicad-cli", kicad_cli(), "mains-compare", "--before-board", BOARD, "--before-project",
                                         os.path.join(FOLDER, "main-board.kicad_pro"), "--board", self.rebuilt, "--project",
                                         os.path.join(self.rebuilt_folder, "main-board.kicad_pro"), "--distance", distance,
                                         "--format", form], out=out)
            if form == "json":
                findings = [row["finding"] for row in json.loads(out.getvalue())["findings"]]
            else:
                findings = [line.split(" | ")[0] for line in out.getvalue().splitlines() if " | " in line]
            for kind in ("ADDED", "MISSING", "CHANGED", "UNLOCKED"):
                self.assertNotIn(kind, findings, (form, status, out.getvalue()[:600]))
            self.assertEqual((status, findings), (0, ["RESULT"] if form == "text" else []), (form, out.getvalue()[:600]))

    def test_every_mains_zone_fills_as_the_committed_board_does_and_the_ground_planes_to_within_a_quarter_square_millimetre(self):
        """the rebuilt board's zone fills are the committed board's, per zone and layer"""
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C5: The block scripts and coordinate tables that draw the main board's copper are tracked in the main board's folder with paths relative to the repository, and running the chain runner over them from the placed board writes the same mains and low-voltage copper the committed board holds. This does not cover the wall board's scripts, which its own work delivers.
        import io
        out = io.StringIO()
        status = zone_fill_diff.main(["--first", BOARD, "--second", self.rebuilt, "--format", "json"], out=out)
        report = json.loads(out.getvalue())
        differing = report["differences"]
        self.assertTrue(all(row["zone"].startswith("GND ") for row in differing), differing)
        self.assertLessEqual(len(differing), 5, differing)
        self.assertEqual(status, 1 if differing else 0)
        out = io.StringIO()
        status = zone_fill_diff.main(["--first", BOARD, "--second", self.rebuilt, "--tolerance", "0.25"], out=out)
        self.assertEqual(status, 0, out.getvalue())
        self.assertIn("RESULT | SAME", out.getvalue())

    def test_the_run_takes_minutes_not_hours(self):
        """the chain over the committed board, both runs of every step, is a run a build round can afford"""
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C5: The block scripts and coordinate tables that draw the main board's copper are tracked in the main board's folder with paths relative to the repository, and running the chain runner over them from the placed board writes the same mains and low-voltage copper the committed board holds. This does not cover the wall board's scripts, which its own work delivers.
        self.assertLess(self.seconds, 600, self.seconds)


class TheChainReportsInJson(Work):
    def test_the_first_three_steps_report_the_same_checksums_in_json_on_every_run(self):
        """the chain's report in JSON names each step and its checksum, as the text report does"""
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C5: The block scripts and coordinate tables that draw the main board's copper are tracked in the main board's folder with paths relative to the repository, and running the chain runner over them from the placed board writes the same mains and low-voltage copper the committed board holds. This does not cover the wall board's scripts, which its own work delivers.
        with open(os.path.join(CHAIN, "chain.json")) as handle:
            steps = json.load(handle)["steps"][:3]
        for step in steps:
            step["command"] = [part.replace("{steps_dir}", CHAIN) for part in step["command"]]
        steps_file = self.write("steps.json", json.dumps({"steps": steps}))
        board = self.path("committed")
        os.makedirs(board)
        for suffix in (".kicad_pcb", ".kicad_pro", ".kicad_dru"):
            shutil.copyfile(os.path.join(FOLDER, "main-board" + suffix), os.path.join(board, "main-board" + suffix))
        status, report = self.run_json(chain_runner.main, "--board", os.path.join(board, "main-board.kicad_pcb"), "--steps", steps_file,
                                       "--output", self.path("out.kicad_pcb"))
        self.assertEqual(status, 0, report)
        self.assertEqual(report["result"], "REPRODUCED")
        self.assertEqual([step["name"] for step in report["steps"]], ["placed board", "mains copper", "low-voltage reconnect"])
        self.assertTrue(all(step["identical"] and step["sha256_first"] == step["sha256_second"] for step in report["steps"]))
        # the committed copper is back after those steps, but for what the chamfer and the lock add
        rebuilt = copper(self.path("out.kicad_pcb"))
        committed = copper(BOARD)
        self.assertEqual(sum(1 for item in rebuilt if item[0] == "via"), sum(1 for item in committed if item[0] == "via"))


class TheScriptsOnSyntheticBoards(Work):
    """The chain's scripts run on boards the tests write: the placed board step, the low-voltage step, the chamfer and the lock."""

    def kicad(self, script, board, output, *extra):
        os.makedirs(os.path.dirname(output), exist_ok=True)
        return run_python(require_kicad_python(), "-I", "-B", os.path.join(CHAIN, script), board, output, *extra)

    def board_in_folder(self, items, mains=False):
        """A synthetic board with the ten property lines and a part, and its project file beside it, in its own folder.

        With `mains`, the project puts /MAINS_T in the Mains class and a track gives the net the copper that makes it a mains net to the
        fill check, as a pad or track does on the real board."""
        items = list(items) + ([track("/MAINS_T", (200, 10), (201, 10), "B.Cu", 0.25, 900)] if mains else [])
        board = self.write("design/b.kicad_pcb", board_text(items + [FOOTPRINT], PROPERTIES))
        self.write("design/b.kicad_pro", project_text({"/MAINS_T": "Mains"} if mains else {}, [], classes=("Mains",), mains="present"))
        return board

    def table_rows(self):
        """The first row of each block's own table, read in KiCad's interpreter: the copper the placed board step must take up."""
        script = ("import json, sys; sys.path.insert(0, sys.argv[1]); import route_entry, route_supply, route_north, route_lv; "
                  "print(json.dumps({'entry': [route_entry.NETS[route_entry.TRACKS[0][0]], route_entry.TRACKS[0][3][:2]], "
                  "'supply': [route_supply.N[route_supply.TRACKS[0][0]], route_supply.TRACKS[0][3][:2], route_supply.TRACKS[0][1]], "
                  "'north_uuid': sorted(route_north.own_uuids())[0], "
                  "'lv': [route_lv.TRACKS[0][0], route_lv.TRACKS[0][1], route_lv.TRACKS[0][2], route_lv.TRACKS[0][3][:2]]}))")
        done = run_python(require_kicad_python(), "-I", "-B", "-c", script, CHAIN)
        self.assertEqual(done.returncode, 0, done.stderr[-400:])
        return json.loads(done.stdout.strip().splitlines()[-1])

    def test_the_placed_board_step_takes_up_exactly_the_copper_the_blocks_draw(self):
        """the placed board is the board without the copper the blocks draw, and nothing else is taken up"""
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C5: The block scripts and coordinate tables that draw the main board's copper are tracked in the main board's folder with paths relative to the repository, and running the chain runner over them from the placed board writes the same mains and low-voltage copper the committed board holds. This does not cover the wall board's scripts, which its own work delivers.
        rows = self.table_rows()
        lv_net, lv_layer, lv_width, lv_points = rows["lv"]
        layer = {"F": "F.Cu", "B": "B.Cu", "In3": "In3.Cu"}[lv_layer]
        (ax, ay), (bx, by) = lv_points
        entry_net, ((ex0, ey0), (ex1, ey1)) = rows["entry"][0], rows["entry"][1]
        supply_net, ((sx0, sy0), (sx1, sy1)), supply_layer = rows["supply"]
        owned_north = ('(segment (start 3 3) (end 4 3) (width 0.2) (layer "F.Cu") (net "/N") (uuid "%s"))' % rows["north_uuid"])
        items = [
            track(lv_net, (ax, ay), (bx, by), layer, lv_width, 1),                      # the low-voltage block's own copper
            track(lv_net, (ax, ay), (bx, by), layer, round(lv_width + 0.05, 2), 2),               # the same line, another width: a hand track
            track(lv_net, (ax, ay), (bx + 0.5, by), layer, lv_width, 3),                # the same net and width, another line
            track(entry_net, (ex0, ey0), (ex1, ey1), "F.Cu", 0.5, 4),                  # the entry block's own copper
            track("/OTHER", (ex0, ey0 + 2), (ex1, ey1 + 2), "F.Cu", 0.5, 5),            # another net on a line 2 mm away
            track(supply_net, (sx0, sy0), (sx1, sy1), {"F": "F.Cu", "B": "B.Cu", "In2": "In2.Cu"}[supply_layer], 0.25, 6),
            owned_north,
            track("/HAND", (30, 30), (31, 30), "F.Cu", 0.25, 7),
            zone("ENTRY LINE F 9", "/Z", "F.Cu", square(40, 40, 3), "(clearance 0.5)"),
            zone("north PUMP_S_MT2 B", "/Z", "B.Cu", square(50, 40, 3), "(clearance 0.5)"),
            zone("NEUTRAL pour In2 north", "/Z", "In2.Cu", square(60, 40, 3), "(clearance 0.5)"),
            zone("hand ground", "/GND", "B.Cu", square(70, 40, 3), "(clearance 0.5)"),
        ]
        board = self.board_in_folder(items)
        done = self.kicad("strip_copper.py", board, self.path("out/b.kicad_pcb"))
        self.assertEqual(done.returncode, 0, done.stderr[-400:])
        left = copper(self.path("out/b.kicad_pcb"))
        segments = sorted((item[5][0], item[3][0]) for item in left if item[0] == "segment")
        self.assertEqual(segments, sorted([(lv_net, str(round(lv_width + 0.05, 2))), (lv_net, str(lv_width)), ("/OTHER", "0.5"), ("/HAND", "0.25")]),
                         segments)
        # the north block owns a zone by the identifier it draws it with, so a zone of its name with another is not its own
        self.assertEqual({item[1][0] for item in left if item[0] == "zone"}, {"north PUMP_S_MT2 B", "hand ground"})
        self.assertEqual(self.property_lines(self.read(self.path("out/b.kicad_pcb"))), self.property_lines(self.read(board)))

    def test_the_placed_board_step_leaves_a_board_with_none_of_the_chains_copper_as_it_was(self):
        """an empty design, and a board with copper none of the blocks draws, come through the placed board step unchanged"""
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C5: The block scripts and coordinate tables that draw the main board's copper are tracked in the main board's folder with paths relative to the repository, and running the chain runner over them from the placed board writes the same mains and low-voltage copper the committed board holds. This does not cover the wall board's scripts, which its own work delivers.
        for items in ([], [track("/HAND", (30, 30), (31, 30), "F.Cu", 0.25, 1), zone("ground", "/GND", "B.Cu", square(70, 40, 3))]):
            board = self.board_in_folder(items)
            before = copper(board)
            done = self.kicad("strip_copper.py", board, self.path("out/b.kicad_pcb"))
            self.assertEqual(done.returncode, 0, done.stderr[-400:])
            self.assertEqual(copper(self.path("out/b.kicad_pcb")), before)

    def test_a_board_that_cannot_be_read_stops_the_step_naming_it(self):
        """a placed board step given no board, an unreadable one or a board without the ten property lines writes nothing and fails"""
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C5: The block scripts and coordinate tables that draw the main board's copper are tracked in the main board's folder with paths relative to the repository, and running the chain runner over them from the placed board writes the same mains and low-voltage copper the committed board holds. This does not cover the wall board's scripts, which its own work delivers.
        for text, needle in (("", "b.kicad_pcb"), ("(kicad_pcb (version 20260206)\n", "b.kicad_pcb"),
                             (board_text([FOOTPRINT], PROPERTIES[:3]), "10")):
            self.write("design/b.kicad_pcb", text)
            self.write("design/b.kicad_pro", project_text({}, [], classes=("Mains",), mains="present"))
            done = self.kicad("strip_copper.py", self.path("design/b.kicad_pcb"), self.path("out/b.kicad_pcb"))
            self.assertNotEqual(done.returncode, 0, text[:30])
            self.assertFalse(os.path.exists(self.path("out/b.kicad_pcb")))
            self.assertIn(needle, done.stderr + done.stdout)

    def lv_board(self, extra=()):
        """A board carrying every net the low-voltage reconnect draws on, and a Mains zone that fills."""
        script = ("import json, sys; sys.path.insert(0, sys.argv[1]); import route_lv, neutral_pour; "
                  "print(json.dumps({'nets': sorted({r[0] for r in route_lv.TRACKS} | {r[0] for r in route_lv.VIAS}), "
                  "'segments': sum(len(r[3]) - 1 for r in route_lv.TRACKS), 'vias': len(route_lv.VIAS), "
                  "'zones': sorted(neutral_pour.UNSET_CLEARANCE_ZONES)}))")
        done = run_python(require_kicad_python(), "-I", "-B", "-c", script, CHAIN)
        self.assertEqual(done.returncode, 0, done.stderr[-400:])
        info = json.loads(done.stdout.strip().splitlines()[-1])
        items = [track(net, (200, 10 + 3 * index), (201, 10 + 3 * index), "B.Cu", 0.25, 100 + index) for index, net in enumerate(info["nets"])]
        # the zones the step unsets the local clearance of must be there, as they are on the board it was written for
        items += [zone(name, "/MAINS_T", "F.Cu", square(10 + 25 * index, 150, 20), "(clearance 3)") for index, name in enumerate(info["zones"])]
        items.append(track("/MAINS_T", (200, 40), (201, 40), "B.Cu", 0.25, 900))
        return info, items

    def test_the_low_voltage_step_draws_its_table_once_whatever_the_board_already_holds(self):
        """the low-voltage reconnect adds its table's tracks and vias to a board and only those, and run again on its own output it draws the same copper"""
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C5: The block scripts and coordinate tables that draw the main board's copper are tracked in the main board's folder with paths relative to the repository, and running the chain runner over them from the placed board writes the same mains and low-voltage copper the committed board holds. This does not cover the wall board's scripts, which its own work delivers.
        info, items = self.lv_board()
        board = self.write("design/b.kicad_pcb", board_text(items + [FOOTPRINT], PROPERTIES))
        self.write("design/b.kicad_pro", project_text({"/MAINS_T": "Mains"}, [], classes=("Mains",), mains="present"))
        before = copper(board)
        first = self.kicad("route_lv.py", board, self.path("one/b.kicad_pcb"))
        self.assertEqual(first.returncode, 0, first.stderr[-400:] + first.stdout[-400:])
        shutil.copyfile(self.path("design/b.kicad_pro"), self.path("one/b.kicad_pro"))
        once = copper(self.path("one/b.kicad_pcb"))
        added = once - before
        self.assertEqual(sum(1 for item in added if item[0] == "segment"), info["segments"])
        self.assertEqual(sum(1 for item in added if item[0] == "via"), info["vias"])
        self.assertFalse(before - once, "an item the board held was lost")
        second = self.kicad("route_lv.py", self.path("one/b.kicad_pcb"), self.path("two/b.kicad_pcb"))
        self.assertEqual(second.returncode, 0, second.stderr[-400:])
        self.assertEqual(copper(self.path("two/b.kicad_pcb")), once)
        self.assertEqual(self.property_lines(self.read(self.path("two/b.kicad_pcb"))), self.property_lines(self.read(board)))

    def test_the_low_voltage_step_stops_naming_a_net_the_board_lacks_and_a_board_without_a_mains_zone(self):
        """the low-voltage reconnect refuses a board that lacks a net it draws on, and one with no Mains zone to hold the fill check to, writing no board"""
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C5: The block scripts and coordinate tables that draw the main board's copper are tracked in the main board's folder with paths relative to the repository, and running the chain runner over them from the placed board writes the same mains and low-voltage copper the committed board holds. This does not cover the wall board's scripts, which its own work delivers.
        info, items = self.lv_board()
        project = project_text({"/MAINS_T": "Mains"}, [], classes=("Mains",), mains="present")
        short = [item for item in items if '(net "%s")' % info["nets"][0] not in item]
        self.write("design/b.kicad_pcb", board_text(short + [FOOTPRINT], PROPERTIES))
        self.write("design/b.kicad_pro", project)
        done = self.kicad("route_lv.py", self.path("design/b.kicad_pcb"), self.path("out/b.kicad_pcb"))
        self.assertNotEqual(done.returncode, 0)
        self.assertFalse(os.path.exists(self.path("out/b.kicad_pcb")))
        self.write("design/b.kicad_pcb", board_text(items + [FOOTPRINT], PROPERTIES))
        self.write("design/b.kicad_pro", project_text({}, [], classes=("Mains",), mains="present"))
        done = self.kicad("route_lv.py", self.path("design/b.kicad_pcb"), self.path("out/b.kicad_pcb"))
        self.assertNotEqual(done.returncode, 0)
        self.assertIn("Mains-class", done.stderr + done.stdout)
        self.assertFalse(os.path.exists(self.path("out/b.kicad_pcb")))

    def chamfer(self, items, table):
        board = self.board_in_folder(items, mains=True)
        table_path = self.write("table.json", json.dumps(table))
        done = self.kicad("chamfer_corners.py", board, self.path("out/b.kicad_pcb"), table_path)
        return done

    def outline(self, path, name, text=False):
        """The points of the named zone's outline, as floats or, with `text`, as the strings the file writes."""
        for node in sexpr.parse_one(self.read(path)):
            if isinstance(node, list) and sexpr.head(node) == "zone" and sexpr.child(node, "name")[1] == name:
                points = [tuple(point[1:]) for point in sexpr.child(sexpr.child(node, "polygon"), "pts") if point[0] == "xy"]
                return points if text else [tuple(float(value) for value in point) for point in points]
        raise AssertionError("no zone " + name)

    def test_the_chamfer_cuts_the_named_corners_at_forty_five_degrees_and_no_others(self):
        """the chamfer step cuts each corner its table names, by the leg the table gives, and leaves every other corner of the zone as it was"""
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C5: The block scripts and coordinate tables that draw the main board's copper are tracked in the main board's folder with paths relative to the repository, and running the chain runner over them from the placed board writes the same mains and low-voltage copper the committed board holds. This does not cover the wall board's scripts, which its own work delivers.
        zone_item = zone("MAINS Z", "/MAINS_T", "F.Cu", [(10, 10), (30, 10), (30, 30), (10, 30)], "(clearance 0.5)")
        done = self.chamfer([zone_item], {"MAINS Z": [[10, 10, 1.0], [30, 30, 2.5]]})
        self.assertEqual(done.returncode, 0, done.stderr[-400:] + done.stdout[-400:])
        self.assertEqual(self.outline(self.path("out/b.kicad_pcb"), "MAINS Z"),
                         [(10.0, 11.0), (11.0, 10.0), (30.0, 10.0), (30.0, 27.5), (27.5, 30.0), (10.0, 30.0)])
        self.assertIn("(filled_polygon", self.read(self.path("out/b.kicad_pcb")))
        self.assertEqual(self.property_lines(self.read(self.path("out/b.kicad_pcb"))), self.property_lines(self.read(self.path("design/b.kicad_pcb"))))

    def test_the_chamfer_cuts_a_corner_of_two_edges_that_meet_at_a_diagonal_without_drifting_off_the_grid(self):
        """a cut on an outline whose edges are not on the axes lands on whole nanometres, so a second run cuts nothing it has not cut"""
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C5: The block scripts and coordinate tables that draw the main board's copper are tracked in the main board's folder with paths relative to the repository, and running the chain runner over them from the placed board writes the same mains and low-voltage copper the committed board holds. This does not cover the wall board's scripts, which its own work delivers.
        zone_item = zone("MAINS Z", "/MAINS_T", "F.Cu", [(10, 10), (30, 10), (30, 30), (10, 30.4)], "(clearance 0.5)")
        done = self.chamfer([zone_item], {"MAINS Z": [[10, 30.4, 0.7]]})
        self.assertEqual(done.returncode, 0, done.stderr[-400:])
        points = self.outline(self.path("out/b.kicad_pcb"), "MAINS Z")
        self.assertEqual(len(points), 5)
        length = math.hypot(20, 0.4)
        self.assertEqual(points[:3], [(10.0, 10.0), (30.0, 10.0), (30.0, 30.0)])
        self.assertAlmostEqual(points[3][0], 10 + 20 * 0.7 / length, delta=1e-6)
        self.assertAlmostEqual(points[3][1], 30.4 - 0.4 * 0.7 / length, delta=1e-6)
        self.assertEqual(points[4], (10.0, 29.7))
        for x, y in self.outline(self.path("out/b.kicad_pcb"), "MAINS Z", text=True):
            for value in (x, y):
                self.assertLessEqual(len(value.partition(".")[2]), 6, value)

    def test_the_chamfer_stops_naming_the_zone_or_corner_it_cannot_cut(self):
        """a chamfer table naming a zone the board lacks, a corner the zone lacks or a leg as long as an edge, or a zone with a hole, writes no board and names it"""
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C5: The block scripts and coordinate tables that draw the main board's copper are tracked in the main board's folder with paths relative to the repository, and running the chain runner over them from the placed board writes the same mains and low-voltage copper the committed board holds. This does not cover the wall board's scripts, which its own work delivers.
        zone_item = zone("MAINS Z", "/MAINS_T", "F.Cu", [(10, 10), (30, 10), (30, 30), (10, 30)], "(clearance 0.5)")
        for table, needle in (({"NO SUCH": [[10, 10, 1]]}, "NO SUCH"), ({"MAINS Z": [[11, 10, 1]]}, "no corner at (11"),
                              ({"MAINS Z": [[10, 10, 20]]}, "no longer than its 20"), ({"MAINS Z": [[10, 10, 25]]}, "no longer than")):
            done = self.chamfer([zone_item], table)
            self.assertNotEqual(done.returncode, 0, table)
            self.assertIn(needle, done.stderr + done.stdout)
            self.assertFalse(os.path.exists(self.path("out/b.kicad_pcb")))
        twice = self.chamfer([zone_item, zone("MAINS Z", "/MAINS_T", "B.Cu", square(50, 50, 5))], {"MAINS Z": [[10, 10, 1]]})
        self.assertNotEqual(twice.returncode, 0)
        self.assertIn("2 zones named 'MAINS Z'", twice.stderr + twice.stdout)

    def test_the_lock_step_locks_the_critical_classes_and_leaves_the_rest(self):
        """the lock step locks every track, via and zone of the critical classes and nothing on the other classes, and passes KiCad's own class read"""
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C5: The block scripts and coordinate tables that draw the main board's copper are tracked in the main board's folder with paths relative to the repository, and running the chain runner over them from the placed board writes the same mains and low-voltage copper the committed board holds. This does not cover the wall board's scripts, which its own work delivers.
        classes = CRITICAL + ("Noisy",)
        assignments = {f"/N_{name}": name for name in classes}
        items = [track(f"/N_{name}", (10 * index, 0), (10 * index + 5, 0), "F.Cu", 0.25, index + 1) for index, name in enumerate(classes)]
        items.append(track("/FREE", (0, 20), (5, 20), "F.Cu", 0.25, 50))
        board = self.write("design/b.kicad_pcb", board_text(items))
        self.write("design/b.kicad_pro", project_text(assignments, [], classes=classes, mains="present"))
        os.makedirs(self.path("out"))
        done = subprocess.run([sys.executable, os.path.join(CHAIN, "lock_critical.py"), board, self.path("out/b.kicad_pcb")],
                              capture_output=True, text=True, timeout=600, env=dict(os.environ, KICAD_CLI=kicad_cli()))
        self.assertEqual(done.returncode, 0, done.stdout[-400:] + done.stderr[-400:])
        locked = {item[5][0]: item[-1] for item in copper(self.path("out/b.kicad_pcb")) if item[0] == "segment"}
        for name in CRITICAL:
            self.assertEqual(locked[f"/N_{name}"], ("yes",), name)
        self.assertIsNone(locked["/N_Noisy"])
        self.assertIsNone(locked["/FREE"])
        self.assertEqual(self.read(board), self.read(self.path("design/b.kicad_pcb")))

    def test_the_lock_step_refuses_a_board_whose_project_lacks_a_critical_class_and_a_missing_kicad_cli(self):
        """the lock step on a board whose project lacks a critical class fails and names the class, and with KICAD_CLI unset it exits 2 naming the variable"""
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C5: The block scripts and coordinate tables that draw the main board's copper are tracked in the main board's folder with paths relative to the repository, and running the chain runner over them from the placed board writes the same mains and low-voltage copper the committed board holds. This does not cover the wall board's scripts, which its own work delivers.
        board = self.write("design/b.kicad_pcb", board_text([track("/N_Fast", (0, 0), (5, 0), "F.Cu", 0.25, 1)]))
        self.write("design/b.kicad_pro", project_text({"/N_Fast": "Fast"}, [], classes=("Fast",), mains="present"))
        os.makedirs(self.path("out"))
        os.makedirs(self.path("out2"))
        done = subprocess.run([sys.executable, os.path.join(CHAIN, "lock_critical.py"), board, self.path("out/b.kicad_pcb")],
                              capture_output=True, text=True, timeout=600, env=dict(os.environ, KICAD_CLI=kicad_cli()))
        self.assertNotEqual(done.returncode, 0)
        self.assertIn("Ground", done.stdout + done.stderr)
        environment = {key: value for key, value in os.environ.items() if key != "KICAD_CLI"}
        done = subprocess.run([sys.executable, os.path.join(CHAIN, "lock_critical.py"), board, self.path("out2/b.kicad_pcb")],
                              capture_output=True, text=True, timeout=600, env=environment)
        self.assertEqual(done.returncode, 2)
        self.assertIn("KICAD_CLI", done.stderr)

    def test_the_stock_footprint_folder_is_asked_for_by_name_when_a_part_must_come_from_it(self):
        """a block that must take a part from KiCad's stock libraries stops naming KICAD_FOOTPRINTS when it is unset or names no folder, and reads it when it names one"""
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C5: The block scripts and coordinate tables that draw the main board's copper are tracked in the main board's folder with paths relative to the repository, and running the chain runner over them from the placed board writes the same mains and low-voltage copper the committed board holds. This does not cover the wall board's scripts, which its own work delivers.
        script = "import sys; sys.path.insert(0, sys.argv[1]); import neutral_pour; print(neutral_pour.stock_footprints())"
        environment = {key: value for key, value in os.environ.items() if key != "KICAD_FOOTPRINTS"}
        done = subprocess.run([require_kicad_python(), "-I", "-B", "-c", script, CHAIN], capture_output=True, text=True, env=environment)
        self.assertNotEqual(done.returncode, 0)
        self.assertIn("KICAD_FOOTPRINTS must name KiCad's stock footprint libraries", done.stderr)
        self.assertIn("not set", done.stderr)
        done = subprocess.run([require_kicad_python(), "-I", "-B", "-c", script, CHAIN], capture_output=True, text=True,
                              env=dict(environment, KICAD_FOOTPRINTS=self.path("missing")))
        self.assertNotEqual(done.returncode, 0)
        self.assertIn("missing", done.stderr)
        os.makedirs(self.path("stock"))
        done = subprocess.run([require_kicad_python(), "-I", "-B", "-c", script, CHAIN], capture_output=True, text=True,
                              env=dict(environment, KICAD_FOOTPRINTS=self.path("stock")))
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(done.stdout.strip(), self.path("stock"))


class TheTrackedFilesAreTheChainsAndHoldNoMachinePath(unittest.TestCase):
    def files(self):
        return sorted(name for name in os.listdir(CHAIN) if os.path.isfile(os.path.join(CHAIN, name)) and not name.endswith(".pyc"))

    def test_every_tracked_file_is_used_by_the_chain_and_every_step_names_a_tracked_script(self):
        """the folder holds the one version of each block script the chain uses, no superseded copy and no script the chain does not reach"""
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C5: The block scripts and coordinate tables that draw the main board's copper are tracked in the main board's folder with paths relative to the repository, and running the chain runner over them from the placed board writes the same mains and low-voltage copper the committed board holds. This does not cover the wall board's scripts, which its own work delivers.
        steps = chain_runner.read_steps(os.path.join(CHAIN, "chain.json"))
        named = set()
        for step in steps:
            for part in step["command"]:
                if "{steps_dir}/" in part:
                    named.add(part.split("{steps_dir}/")[1])
        self.assertTrue(named and all(os.path.isfile(os.path.join(CHAIN, name)) for name in named), named)
        reached = set(named) | {"chain.json"}
        queue = list(named)
        while queue:
            with open(os.path.join(CHAIN, queue.pop()), encoding="utf-8") as handle:
                text = handle.read()
            for name in self.files():
                if name not in reached and (re.search(r"^import %s\b|^from %s import|import %s\b" % ((re.escape(os.path.splitext(name)[0]),) * 3), text, re.M)
                                            or ('"%s"' % name) in text):
                    reached.add(name)
                    queue.append(name)
        self.assertEqual(set(self.files()) - reached, set(), "files the chain does not reach")
        for name in self.files():
            self.assertFalse(re.search(r"before_|\.orig|\.bak|_v\d|2\.py$", name), name)

    def test_no_file_holds_a_path_fixed_to_one_machine_or_a_working_file_outside_the_repository(self):
        """every path in the tracked scripts and tables is relative to the folder or an argument or an environment variable"""
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C5: The block scripts and coordinate tables that draw the main board's copper are tracked in the main board's folder with paths relative to the repository, and running the chain runner over them from the placed board writes the same mains and low-voltage copper the committed board holds. This does not cover the wall board's scripts, which its own work delivers.
        pattern = re.compile(r"/Users/|/home/|/Applications/|/opt/|[A-Za-z]:\\|real5|\bKP\b|/tmp/")
        for name in self.files():
            with open(os.path.join(CHAIN, name), encoding="utf-8") as handle:
                for number, line in enumerate(handle, 1):
                    self.assertIsNone(pattern.search(line), f"{name}:{number}: {line.strip()[:100]}")

    def test_the_tables_are_well_formed_json(self):
        """the coordinate tables the scripts read parse, and each row has the fields the scripts use"""
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C5: The block scripts and coordinate tables that draw the main board's copper are tracked in the main board's folder with paths relative to the repository, and running the chain runner over them from the placed board writes the same mains and low-voltage copper the committed board holds. This does not cover the wall board's scripts, which its own work delivers.
        with open(os.path.join(CHAIN, "moves_north.json")) as handle:
            moves = json.load(handle)
        self.assertTrue(moves)
        for move in moves:
            self.assertEqual(set(move), {"ref", "x", "y", "rot"})
            self.assertTrue(all(isinstance(move[key], (int, float)) for key in ("x", "y", "rot")))
        with open(os.path.join(CHAIN, "chamfer_corners.json")) as handle:
            chamfers = json.load(handle)
        self.assertTrue(chamfers)
        for name, corners in chamfers.items():
            self.assertTrue(corners, name)
            for corner in corners:
                self.assertEqual(len(corner), 3, (name, corner))
                self.assertGreater(corner[2], 0, (name, corner))


class TheNotesDescribeTheChain(unittest.TestCase):
    def section(self):
        with open(os.path.join(REPO, "hardware", "README.md"), encoding="utf-8") as handle:
            text = handle.read()
        start = text.index("## The main board's layout chain")
        return text[start:text.index("\n## ", start + 5)]

    def test_the_hardware_notes_give_the_command_inputs_outputs_tables_and_prerequisites_and_name_every_tracked_file(self):
        """The notes read clause by clause: the command, the inputs, the outputs, the board folder tables read and the prerequisites."""
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C5: The block scripts and coordinate tables that draw the main board's copper are tracked in the main board's folder with paths relative to the repository, and running the chain runner over them from the placed board writes the same mains and low-voltage copper the committed board holds. This does not cover the wall board's scripts, which its own work delivers.
        section = self.section()
        for clause in ("**Command**", "**Inputs**", "**Outputs**", "**The tables it reads", "**Prerequisites**", "hardware/tools/chain_runner.py",
                       "hardware/sunbeam-em7000/main-board/layout-chain/chain.json", "KICAD_PYTHON", "KICAD_CLI", "KICAD_FOOTPRINTS"):
            self.assertIn(clause, section)
        for name in sorted(os.listdir(CHAIN)):
            if os.path.isfile(os.path.join(CHAIN, name)) and not name.endswith(".pyc"):
                self.assertIn(name, section, name)
        self.assertNotRegex(section, r"/Users/|real5")


if __name__ == "__main__":
    unittest.main()
