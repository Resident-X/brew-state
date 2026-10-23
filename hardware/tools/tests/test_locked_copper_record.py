#!/usr/bin/env python3
"""The locked-copper check, driven on synthetic boards against the real kicad-cli: the record part.

One of the files the original test file is divided into by topic; the tests are unchanged and only live elsewhere.
"""

from __future__ import annotations

import copy
import difflib
import json
import os
import subprocess
import sys

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import locked_copper  # noqa: E402
import sexpr  # noqa: E402
from locked_copper_fixtures import BASE_PROJECT, Board, ITEMS, KICAD_CLI, PROOF_PROJECT, UNLOCKED_ITEMS, layout, setUpModule, without_locks  # noqa: E402,F401


class TheRecordStep(Board):
    """SOL-BOARD-RULES-AND-LOCKED-CRITICAL-ROUTING.C3: A tested check records critical-class copper before the routing round trip and fails the board after it on any missing, unlocked, changed or added item.

    The record is a working file outside any design's folder, and is taken only
    of critical copper that is locked.
    """

    def test_a_record_inside_the_design_folder_is_refused(self):
        for inside in (os.path.join(self.folder, "b.record.json"), os.path.join(self.folder, "sub", "r.json")):
            with self.subTest(path=inside):
                status, lines = self.record(record_path=inside)
                self.assertEqual(status, 1, lines)
                self.assertTrue(lines[0].startswith("REFUSED |") and "never kept in a design's folder" in lines[0], lines)
                self.assertFalse(os.path.exists(inside))

    def test_a_record_inside_any_designs_folder_is_refused(self):
        other = os.path.join(os.path.dirname(self.folder), "other")
        os.makedirs(other)
        with open(os.path.join(other, "o.kicad_pro"), "w", encoding="utf-8") as handle:
            handle.write(BASE_PROJECT)
        for path in (os.path.join(other, "r.json"), os.path.join(other, "deep", "er", "r.json")):
            with self.subTest(path=path):
                status, lines = self.record(record_path=path)
                self.assertEqual(status, 1, lines)
                self.assertTrue(lines[0].startswith(f"REFUSED | {path} |") and os.path.realpath(other) in lines[0], lines)
                self.assertFalse(os.path.exists(path))
        above = os.path.join(os.path.dirname(self.folder), "above.kicad_pro")
        with open(above, "w", encoding="utf-8") as handle:
            handle.write(BASE_PROJECT)
        status, lines = self.record()
        self.assertEqual(status, 1, lines)
        self.assertIn("never kept in a design's folder", lines[0])
        self.assertFalse(os.path.exists(self.record_path))

    def test_a_record_that_cannot_be_written_is_refused_whole(self):
        path = os.path.join(self.work, "no-such-folder", "b.record.json")
        status, lines = self.record(record_path=path)
        self.assertEqual(status, 1, lines)
        self.assertTrue(lines[0].startswith(f"REFUSED | {path} | the record cannot be written"), lines)
        self.assertEqual(lines[-1], "RESULT | REFUSED | no record was written")
        self.assertEqual(os.listdir(self.work), [])
        status, lines = self.record(record_path=self.work)
        self.assertEqual(status, 1, lines)
        self.assertTrue(os.path.isdir(self.work) and os.listdir(self.work) == [], os.listdir(self.work))

    def test_an_unlocked_critical_item_is_refused_and_named(self):
        self.write(layout(dict(ITEMS, via=ITEMS["via"].replace(" (locked yes)", "")).values()))
        status, lines = self.record()
        self.assertEqual(status, 1, lines)
        self.assertEqual(len(self.findings(lines, "UNLOCKED")), 1, lines)
        self.assertTrue(self.findings(lines, "UNLOCKED")[0][1].startswith("via [/GND_A] at (20, 20) mm"), lines)
        self.assertFalse(os.path.exists(self.record_path))

    def test_an_unlocked_item_off_the_critical_nets_is_not_refused(self):
        lines = self.recorded()
        self.assertTrue(lines[-1].startswith("RESULT | RECORDED | 4 locked items on 3 critical-class nets"), lines)


class Malformed(Board):
    """SOL-BOARD-RULES-AND-LOCKED-CRITICAL-ROUTING.C3: A tested check records critical-class copper before the routing round trip and fails the board after it on any missing, unlocked, changed or added item.

    A record or board that cannot be read fails rather than passes.
    """

    def assertFailsUnread(self, status, lines):
        self.assertEqual(status, 1, lines)
        self.assertTrue(any(line.startswith("UNREADABLE |") for line in lines), lines)
        self.assertNotIn("PASS", lines[-1])

    def test_a_board_that_cannot_be_read(self):
        self.recorded()
        boards = {
            "unbalanced": layout(ITEMS.values())[:-3],
            "not a layout": "(kicad_sch (version 20250114))\n",
            "a track with no width": layout(dict(ITEMS, track=ITEMS["track"].replace(" (width 0.5)", "")).values()),
            "a via position that is not a number": layout(dict(ITEMS, via=ITEMS["via"].replace("(at 20 20)", "(at x 20)")).values()),
            "a lock in another form": layout(dict(ITEMS, arc=ITEMS["arc"].replace("(locked yes)", "(locked)")).values()),
            "a zone with no outline": layout(dict(ITEMS, zone=ITEMS["zone"].split(" (polygon")[0] + ")").values()),
        }
        for what, text in boards.items():
            with self.subTest(board=what):
                self.write(text)
                self.assertFailsUnread(*self.compare())
                self.assertFailsUnread(*self.record(record_path=os.path.join(self.work, "other.json")))
        os.remove(self.board)
        self.assertFailsUnread(*self.compare())

    def test_a_record_that_cannot_be_read(self):
        lines = self.recorded()
        with open(self.record_path, encoding="utf-8") as handle:
            good = json.load(handle)
        tampered = copy.deepcopy(good)
        tampered["items"][0]["width" if "width" in tampered["items"][0] else "net"] = "wide"

        def edited(change):
            document = copy.deepcopy(good)
            change(document)
            return json.dumps(document)

        def first_item(name, value):
            return lambda document: document["items"][0].__setitem__(name, value)

        records = {
            "no nets": edited(lambda document: document.pop("nets")),
            "the nets of another class": edited(lambda document: document["nets"].__setitem__("Sense", [])),
            "the nets of one class left out": edited(lambda document: document["nets"].pop("Ground")),
            "a net that is not a name": edited(lambda document: document["nets"]["Power"].append(3)),
            "an item on a net no class holds": edited(first_item("net", "/LV")),
            "an item not locked": edited(first_item("locked", False)),
            "no board": edited(lambda document: document.pop("board")),
            "a board by a relative path": edited(lambda document: document.__setitem__("board", "b.kicad_pcb")),
            "a class named twice": edited(lambda document: document.__setitem__("classes", ["Power", "Power", "Ground"])),
            "a class that cannot be put to KiCad": edited(lambda document: (
                document.__setitem__("classes", ["Power", "Gro'und"]),
                document["nets"].__setitem__("Gro'und", document["nets"].pop("Ground")))),
            "a key recording does not write": edited(lambda document: document.__setitem__("project", "b.kicad_pro")),
            "not JSON": "{ not json",
            "another kind of file": json.dumps({"format": "something else", "classes": ["Power"], "items": []}),
            "no classes": json.dumps(dict(good, classes=[])),
            "an item in another form": json.dumps(tampered),
            "an item of an unknown kind": json.dumps(dict(good, items=[{"kind": "pad", "net": "/PWR", "uuid": "", "locked": True}])),
            "a key given twice": json.dumps(good)[:-1] + ', "items": []}',
        }
        for what, text in records.items():
            with self.subTest(record=what):
                with open(self.record_path, "w", encoding="utf-8") as handle:
                    handle.write(text)
                self.assertFailsUnread(*self.compare())
        os.remove(self.record_path)
        self.assertFailsUnread(*self.compare())

    def test_a_project_file_that_cannot_be_read(self):
        self.write(layout(ITEMS.values()), "{ not json")
        self.assertFailsUnread(*self.record())


class Locking(Board):
    """SOL-BOARD-RULES-AND-LOCKED-CRITICAL-ROUTING.C3: A tested check records critical-class copper before the routing round trip and fails the board after it on any missing, unlocked, changed or added item.

    The lock command marks every track, arc, via and zone on the named critical
    classes locked in the board file, where KiCad itself writes the lock, and
    changes nothing else in the file.
    """

    def test_every_critical_item_is_locked_and_nothing_else_changes(self):
        items = dict(UNLOCKED_ITEMS, via=ITEMS["via"].replace("(locked yes)", "(locked no)"))
        self.write(layout(items.values()))
        before = self.board_text()
        status, lines = self.on_classes("lock")
        self.assertEqual(status, 0, lines)
        after = self.board_text()
        self.assertEqual(after.replace("(locked yes) ", ""), before.replace("(locked no) ", ""))
        self.assertEqual(sexpr.dump(without_locks(sexpr.parse_one(after))),
                         sexpr.dump(without_locks(sexpr.parse_one(before))))
        locks = {item["net"] + " " + item["kind"]: item["locked"] for item in locked_copper.copper(sexpr.parse_one(after), self.board)}
        self.assertEqual(locks, {"/PWR track": True, "/GND_A arc": True, "/GND_A via": True, "/PWR zone": True,
                                 "/LV track": False})
        self.assertEqual(len(self.findings(lines, "LOCKED")), 4, lines)
        self.assertTrue(lines[-1].startswith("RESULT | LOCKED | 4 items locked now and 0 already locked"), lines)
        self.recorded()

    def test_kicad_reads_the_lock_where_it_writes_it(self):
        with open(os.path.join(os.path.dirname(PROOF_PROJECT), "gate-proof.kicad_pcb"), encoding="utf-8") as handle:
            text = handle.read()
        added = ('\t(via\n\t\t(at 30 12)\n\t\t(size 0.8)\n\t\t(drill 0.4)\n\t\t(layers "F.Cu" "B.Cu")\n'
                 '\t\t(net "/MAINS_N")\n\t\t(uuid "dee00000-0000-4000-8000-000000000003")\n\t)\n'
                 '\t(arc\n\t\t(start 10 20)\n\t\t(mid 12 22)\n\t\t(end 14 20)\n\t\t(width 0.5)\n\t\t(layer "B.Cu")\n'
                 '\t\t(net "/MAINS_L")\n\t\t(uuid "dee00000-0000-4000-8000-000000000004")\n\t)\n'
                 '\t(zone\n\t\t(net "/MAINS_N")\n\t\t(layers "F.Cu" "B.Cu")\n\t\t(uuid "dee00000-0000-4000-8000-000000000005")\n'
                 '\t\t(hatch edge 0.5)\n\t\t(connect_pads\n\t\t\t(clearance 3)\n\t\t)\n\t\t(min_thickness 0.25)\n'
                 '\t\t(filled_areas_thickness no)\n\t\t(fill\n\t\t\t(thermal_gap 0.5)\n\t\t\t(thermal_bridge_width 0.5)\n\t\t)\n'
                 '\t\t(polygon\n\t\t\t(pts\n\t\t\t\t(xy 26 14) (xy 29 14) (xy 29 17) (xy 26 17)\n\t\t\t)\n\t\t)\n\t)\n')
        at = text.rindex("\t(embedded_fonts")
        with open(PROOF_PROJECT, encoding="utf-8") as handle:
            self.write(text[:at] + added + text[at:], handle.read())

        def resave():
            done = subprocess.run([KICAD_CLI, "pcb", "upgrade", "--force", self.board], capture_output=True, text=True,
                                  timeout=120)
            self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
            return self.board_text()

        before = resave()
        status, lines = self.on_classes("lock", "Mains")
        self.assertEqual(status, 0, lines)
        locked = self.board_text()
        self.assertEqual(len(self.findings(lines, "LOCKED")), 6, lines)
        self.assertEqual(resave(), locked, "KiCad, loading and saving the locked board, writes it differently")
        changes = [line for line in difflib.ndiff(before.splitlines(), locked.splitlines()) if line[:1] in "+-"]
        self.assertEqual(changes, ["+ \t\t(locked yes)"] * 6)

    def test_an_already_locked_board_is_left_untouched(self):
        before = self.board_text()
        stamp = os.stat(self.board).st_mtime_ns
        status, lines = self.on_classes("lock")
        self.assertEqual(status, 0, lines)
        self.assertTrue(lines[-1].startswith("RESULT | LOCKED | 0 items locked now and 4 already locked"), lines)
        self.assertEqual((self.board_text(), os.stat(self.board).st_mtime_ns), (before, stamp))

    def test_a_board_that_cannot_be_read_is_not_changed(self):
        broken = layout(dict(UNLOCKED_ITEMS, via=UNLOCKED_ITEMS["via"].replace("(at 20 20)", "(at x 20)")).values())
        self.write(broken)
        status, lines = self.on_classes("lock")
        self.assertEqual(status, 1, lines)
        self.assertTrue(any(line.startswith("UNREADABLE |") for line in lines), lines)
        self.assertEqual(self.board_text(), broken)
