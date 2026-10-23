#!/usr/bin/env python3
"""The locked-copper check, driven on synthetic boards against the real kicad-cli: the recording part.

One of the files the original test file is divided into by topic; the tests are unchanged and only live elsewhere.
"""

from __future__ import annotations

import json
import os
import sys
from unittest import mock

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import board_check  # noqa: E402
from locked_copper_fixtures import Board, ITEMS, layout, project, setUpModule  # noqa: E402,F401


class RecordingAndComparing(Board):
    """SOL-BOARD-RULES-AND-LOCKED-CRITICAL-ROUTING.C3: A tested check records critical-class copper before the routing round trip and fails the board after it on any missing, unlocked, changed or added item.

    Recording takes every track, arc, via and zone on a critical-class net with
    its properties and lock state; comparing passes the untouched board and
    fails, naming each item and its changed property, on every departure.
    """

    def test_an_untouched_board_passes(self):
        self.recorded()
        with open(self.record_path, encoding="utf-8") as handle:
            document = json.load(handle)
        self.assertEqual(sorted(item["kind"] for item in document["items"]), ["arc", "track", "via", "zone"])
        self.assertTrue(all(item["locked"] for item in document["items"]))
        status, lines = self.compare()
        self.assertEqual(status, 0, lines)
        self.assertTrue(lines[-1].startswith("RESULT | PASS | all 4 recorded items"), lines)

    def test_each_kind_recorded_by_its_properties(self):
        self.recorded()
        with open(self.record_path, encoding="utf-8") as handle:
            items = {item["kind"]: item for item in json.load(handle)["items"]}
        self.assertEqual(items["track"]["layer"], "F.Cu")
        self.assertEqual((items["track"]["start"], items["track"]["end"], items["track"]["width"]),
                         ([0, 0], [5_000_000, 0], 500_000))
        self.assertEqual(items["arc"]["mid"], [2_000_000, 12_000_000])
        self.assertEqual((items["via"]["at"], items["via"]["diameter"], items["via"]["drill"], items["via"]["layers"]),
                         ([20_000_000, 20_000_000], [800_000], 400_000, ["B.Cu", "F.Cu"]))
        self.assertEqual((items["zone"]["net"], items["zone"]["layers"]), ("/PWR", ["B.Cu"]))
        self.assertEqual(items["zone"]["outline"], [[[30_000_000, 30_000_000], [40_000_000, 30_000_000],
                                                    [40_000_000, 40_000_000], [30_000_000, 40_000_000]]])

    def test_a_missing_item_fails_by_name(self):
        self.recorded()
        for name in ("track", "arc", "via", "zone"):
            with self.subTest(item=name):
                self.write(layout(text for other, text in ITEMS.items() if other != name))
                status, lines = self.compare()
                self.assertEqual(status, 1, lines)
                missing = self.findings(lines, "MISSING")
                self.assertEqual(len(missing), 1, lines)
                self.assertTrue(missing[0][1].startswith(name), lines)
                self.assertEqual(self.findings(lines, "ADDED") + self.findings(lines, "CHANGED"), [], lines)

    def test_an_item_no_longer_locked_fails_by_name(self):
        self.recorded()
        for name in ("track", "arc", "via", "zone"):
            with self.subTest(item=name):
                items = dict(ITEMS, **{name: ITEMS[name].replace(" (locked yes)", "")})
                self.write(layout(items.values()))
                status, lines = self.compare()
                self.assertEqual(status, 1, lines)
                unlocked = self.findings(lines, "UNLOCKED")
                self.assertEqual(len(unlocked), 1, lines)
                self.assertTrue(unlocked[0][1].startswith(name), lines)
                self.assertIn("not locked now", unlocked[0][2])

    def test_a_changed_item_fails_naming_the_property(self):
        self.recorded()
        changes = [
            ("track", "(width 0.5)", "(width 0.3)", "width 0.5 mm -> 0.3 mm"),
            ("track", "(end 5 0)", "(end 6 0)", "end (5, 0) mm -> (6, 0) mm"),
            ("track", '(layer "F.Cu")', '(layer "B.Cu")', "layer F.Cu -> B.Cu"),
            ("arc", "(mid 2 12)", "(mid 2 12.5)", "mid (2, 12) mm -> (2, 12.5) mm"),
            ("arc", "(start 0 10)", "(start 0 9)", "start (0, 10) mm -> (0, 9) mm"),
            ("arc", "(end 4 10)", "(end 4 11)", "end (4, 10) mm -> (4, 11) mm"),
            ("via", '(layers "F.Cu" "B.Cu")', '(layers "F.Cu" "In1.Cu")', "layers B.Cu F.Cu -> F.Cu In1.Cu"),
            ("track", '(net "/PWR")', '(net "/GND_A")', "net /PWR -> /GND_A"),
            ("via", "(drill 0.4)", "(drill 0.3)", "drill 0.4 mm -> 0.3 mm"),
            ("via", "(size 0.8)", "(size 0.9)", "diameter 0.8 mm -> 0.9 mm"),
            ("via", "(at 20 20)", "(at 20 21)", "at (20, 20) mm -> (20, 21) mm"),
            ("zone", "(xy 40 40)", "(xy 41 40)", "outline (30, 30) (40, 30) (40, 40) (30, 40) mm -> (30, 30) (40, 30) (41, 40) (30, 40) mm"),
            ("zone", '(layer "B.Cu")', '(layer "F.Cu")', "layers B.Cu -> F.Cu"),
        ]
        for name, old, new, said in changes:
            with self.subTest(item=name, change=new):
                self.write(layout(dict(ITEMS, **{name: ITEMS[name].replace(old, new)}).values()))
                status, lines = self.compare()
                self.assertEqual(status, 1, lines)
                changed = self.findings(lines, "CHANGED")
                self.assertEqual(len(changed), 1, lines)
                self.assertTrue(changed[0][1].startswith(name), lines)
                self.assertEqual(changed[0][2], said)

    def test_a_track_moved_off_the_critical_nets_is_missing(self):
        self.recorded()
        self.write(layout(dict(ITEMS, track=ITEMS["track"].replace('(net "/PWR")', '(net "/LV")')).values()))
        status, lines = self.compare()
        self.assertEqual(status, 1, lines)
        missing = self.findings(lines, "MISSING")
        self.assertEqual(len(missing), 1, lines)
        self.assertTrue(missing[0][1].startswith("track [/PWR]"), lines)

    def test_a_change_with_a_new_uuid_is_still_reported_as_a_change(self):
        self.recorded()
        moved = ITEMS["track"].replace("(width 0.5)", "(width 0.3)").replace("000000000001", "0000000000a1")
        self.write(layout(dict(ITEMS, track=moved).values()))
        status, lines = self.compare()
        self.assertEqual(status, 1, lines)
        self.assertEqual([finding[2] for finding in self.findings(lines, "CHANGED")], ["width 0.5 mm -> 0.3 mm"], lines)

    def test_an_added_item_fails_even_when_identical_to_a_recorded_one(self):
        self.recorded()
        additions = {
            "a new track": '(segment (start 0 5) (end 5 5) (width 0.5) (layer "F.Cu") (net "/PWR") '
                           '(uuid "00000000-0000-4000-8000-0000000000b1"))',
            "an identical locked copy": ITEMS["track"].replace("000000000001", "0000000000b2"),
            "an identical unlocked copy": ITEMS["track"].replace(" (locked yes)", "").replace("000000000001", "0000000000b3"),
            "a via on a critical net that had no copper": '(via (at 25 25) (size 0.8) (drill 0.4) (layers "F.Cu" "B.Cu") '
                                                         '(net "/GND_B") (uuid "00000000-0000-4000-8000-0000000000b4"))',
            "an arc": ITEMS["arc"].replace("(mid 2 12)", "(mid 2 8)").replace("000000000002", "0000000000b5"),
            "a zone": ITEMS["zone"].replace("(xy 30 30) (xy 40 30)", "(xy 30 30) (xy 35 30)").replace(
                "000000000004", "0000000000b6"),
        }
        for what, text in additions.items():
            with self.subTest(addition=what):
                # Ahead of the original, so a copy is not matched first merely by coming first.
                self.write(layout([text] + list(ITEMS.values())))
                status, lines = self.compare()
                self.assertEqual(status, 1, lines)
                self.assertEqual(len(self.findings(lines, "ADDED")), 1, lines)
                self.assertEqual(self.findings(lines, "UNLOCKED") + self.findings(lines, "CHANGED")
                                 + self.findings(lines, "MISSING"), [], lines)

    def test_a_change_confined_to_non_critical_nets_passes(self):
        self.recorded()
        lv = ITEMS["lv"].replace("(end 65 0)", "(end 66 1)")
        extra = ('(segment (start 70 0) (end 75 0) (width 0.25) (layer "F.Cu") (net "/LV") '
                 '(uuid "00000000-0000-4000-8000-0000000000c1"))',
                 '(via (at 70 0) (size 0.6) (drill 0.3) (layers "F.Cu" "B.Cu") (net "/LV") '
                 '(uuid "00000000-0000-4000-8000-0000000000c2"))')
        self.write(layout([ITEMS[name] for name in ("track", "arc", "via", "zone")] + [lv, *extra]))
        status, lines = self.compare()
        self.assertEqual(status, 0, lines)

    def test_several_failures_are_each_named(self):
        self.recorded()
        items = dict(ITEMS, track=ITEMS["track"].replace("(width 0.5)", "(width 0.3)"),
                     via=ITEMS["via"].replace(" (locked yes)", ""))
        del items["arc"]
        self.write(layout(list(items.values()) + [ITEMS["arc"].replace("000000000002", "0000000000d1")
                                                  .replace("(mid 2 12)", "(mid 2 14)")
                                                  .replace("(start 0 10)", "(start 0 9)")]))
        status, lines = self.compare()
        self.assertEqual(status, 1, lines)
        self.assertEqual(sorted(line.split(" | ")[0] for line in lines[:-1]), ["CHANGED", "CHANGED", "UNLOCKED"], lines)
        self.assertTrue(lines[-1].startswith("RESULT | FAIL | 3 differences"), lines)


class Membership(Board):
    """SOL-BOARD-RULES-AND-LOCKED-CRITICAL-ROUTING.C3: A tested check records critical-class copper before the routing round trip and fails the board after it on any missing, unlocked, changed or added item.

    Membership is KiCad's own answer for the board with its project file: by
    the project's assignment, by its pattern, and by a class the layout file
    carries, never by reading either file alone.
    """

    def classes(self, lines):
        return {fields[1]: fields[3].split(", ") if len(fields) > 3 else [] for fields in self.findings(lines, "CLASS")}

    def test_by_assignment_and_by_pattern(self):
        lines = self.recorded()
        self.assertEqual(self.classes(lines), {"Power": ["/PWR"], "Ground": ["/GND_A", "/GND_B"]})

    def test_by_a_class_the_layout_file_carries(self):
        block = '\t(net_class "Sense" "written by an older KiCad" (clearance 0.2) (add_net "/S1"))\n'
        sense = ('(segment (start 50 0) (end 55 0) (width 0.25) (locked yes) (layer "F.Cu") (net "/S1") '
                 '(uuid "00000000-0000-4000-8000-000000000005"))')
        self.write(layout([sense, ITEMS["lv"]], extra=block), project(classes=()))
        status, lines = self.record("Sense")
        self.assertEqual(status, 0, lines)
        self.assertEqual(self.classes(lines), {"Sense": ["/S1"]})
        with open(self.record_path, encoding="utf-8") as handle:
            self.assertEqual([item["net"] for item in json.load(handle)["items"]], ["/S1"])
        self.write(layout([sense.replace("(end 55 0)", "(end 56 0)"), ITEMS["lv"]], extra=block))
        status, lines = self.compare()
        self.assertEqual(status, 1, lines)
        self.assertEqual(len(self.findings(lines, "CHANGED")), 1, lines)

    def test_a_pattern_counts_for_a_net_the_record_never_held(self):
        self.recorded()
        added = ('(segment (start 0 30) (end 5 30) (width 0.25) (layer "F.Cu") (net "/GND_NEW") '
                 '(uuid "00000000-0000-4000-8000-0000000000e1"))')
        self.write(layout(list(ITEMS.values()) + [added]))
        status, lines = self.compare()
        self.assertEqual(status, 1, lines)
        self.assertIn("/GND_NEW", self.findings(lines, "ADDED")[0][1])

    def test_a_class_the_design_does_not_define_is_refused(self):
        status, lines = self.record("Power", "Sensing")
        self.assertEqual(status, 1, lines)
        self.assertTrue(any(line.startswith("REFUSED | Sensing | the design defines no net class") for line in lines), lines)
        self.assertFalse(os.path.exists(self.record_path))

    def test_a_class_named_twice_is_refused(self):
        status, lines = self.record("Power", "Power")
        self.assertEqual(status, 1, lines)
        self.assertFalse(os.path.exists(self.record_path))

    def test_an_unloaded_probe_fails_rather_than_finding_no_nets(self):
        with mock.patch.object(board_check, "run_report", return_value=({"violations": []}, "")):
            status, lines = self.record()
        self.assertEqual(status, 1, lines)
        self.assertTrue(any(line.startswith("UNREADABLE") and "did not load" in line for line in lines), lines)
        self.assertFalse(os.path.exists(self.record_path))
        self.recorded()
        with mock.patch.object(board_check, "run_report", return_value=({"violations": []}, "")):
            status, lines = self.compare()
        self.assertEqual(status, 1, lines)
        self.assertNotIn("PASS", lines[-1])


class MembershipChangesBetweenRecordingAndComparing(Board):
    """SOL-BOARD-RULES-AND-LOCKED-CRITICAL-ROUTING.C3: A tested check records critical-class copper before the routing round trip and fails the board after it on any missing, unlocked, changed or added item.

    The critical nets at comparison are every net the record names as well as
    every net the critical classes hold then, and a class the record names that
    the design no longer defines fails, so a project file rewritten or replaced
    between recording and comparing cannot hide added copper.
    """

    VIA_ON_GND_B = ('(via (at 25 25) (size 0.8) (drill 0.4) (layers "F.Cu" "B.Cu") (net "/GND_B") '
                    '(uuid "00000000-0000-4000-8000-0000000000b4"))')
    TRACK_ON_PWR = ('(segment (start 0 5) (end 5 5) (width 0.5) (layer "F.Cu") (net "/PWR") '
                    '(uuid "00000000-0000-4000-8000-0000000000b1"))')

    def test_a_net_that_leaves_its_class_still_has_its_added_copper_found(self):
        self.recorded()
        cases = {
            "the pattern dropped": (project({"/PWR": "Power"}, []), self.VIA_ON_GND_B, "/GND_B"),
            "the assignment dropped": (project({}, [{"netclass": "Ground", "pattern": "/GND_*"}]), self.TRACK_ON_PWR, "/PWR"),
        }
        for what, (project_text, added, net) in cases.items():
            with self.subTest(change=what):
                self.write(layout(ITEMS.values()), project_text)
                status, lines = self.compare()
                self.assertEqual(status, 0, lines)
                self.write(layout(list(ITEMS.values()) + [added]))
                status, lines = self.compare()
                self.assertEqual(status, 1, lines)
                added_found = self.findings(lines, "ADDED")
                self.assertEqual(len(added_found), 1, lines)
                self.assertIn(f"[{net}]", added_found[0][1])
                self.assertNotIn("PASS", lines[-1])

    def test_a_class_the_design_no_longer_defines_fails(self):
        self.recorded()
        self.write(layout(list(ITEMS.values()) + [self.VIA_ON_GND_B]), project({"/PWR": "Power"}, [], classes=("Power",)))
        status, lines = self.compare()
        self.assertEqual(status, 1, lines)
        self.assertEqual([finding[1] for finding in self.findings(lines, "UNDEFINED")], ["Ground"], lines)
        self.assertEqual(len(self.findings(lines, "ADDED")), 1, lines)
        self.write(layout(ITEMS.values()))
        status, lines = self.compare()
        self.assertEqual(status, 1, lines)
        self.assertEqual(sorted(line.split(" | ")[0] for line in lines[:-1]), ["UNDEFINED"], lines)


class OneBoardsRecord(Board):
    """SOL-BOARD-RULES-AND-LOCKED-CRITICAL-ROUTING.C3: A tested check records critical-class copper before the routing round trip and fails the board after it on any missing, unlocked, changed or added item.

    Recording and comparing each take the board with its own project file, and
    a board is compared only with the record taken of it, so neither another
    project file nor another board's record can stand in.
    """

    def test_a_project_file_not_the_boards_own_is_refused_and_fails(self):
        self.recorded()
        for elsewhere in (os.path.join(self.work, "b.kicad_pro"), os.path.join(self.folder, "other.kicad_pro")):
            with self.subTest(project=elsewhere):
                with open(elsewhere, "w", encoding="utf-8") as handle:
                    handle.write(project({"/PWR": "Power"}, []))
                status, lines = self.run_check("record", "--board", self.board, "--project", elsewhere,
                                               "--class", "Power", "--record", os.path.join(self.work, "other.json"))
                self.assertEqual(status, 1, lines)
                self.assertTrue(any(line.startswith(f"REFUSED | {elsewhere} | KiCad opens") for line in lines), lines)
                self.assertFalse(os.path.exists(os.path.join(self.work, "other.json")))
                self.write(layout(list(ITEMS.values()) + [MembershipChangesBetweenRecordingAndComparing.VIA_ON_GND_B]))
                status, lines = self.run_check("compare", "--board", self.board, "--project", elsewhere,
                                               "--record", self.record_path)
                self.assertEqual(status, 1, lines)
                self.assertTrue(any(line.startswith(f"MISMATCH | {elsewhere} |") for line in lines), lines)
                self.assertNotIn("PASS", lines[-1])
                self.write(layout(ITEMS.values()))

    def test_another_boards_record_fails(self):
        self.recorded()
        twin = os.path.join(os.path.dirname(self.folder), "twin")
        os.makedirs(twin)
        for name in ("b.kicad_pcb", "b.kicad_pro"):
            with open(os.path.join(self.folder, name), encoding="utf-8") as source, \
                    open(os.path.join(twin, name), "w", encoding="utf-8") as copy_of:
                copy_of.write(source.read())
        status, lines = self.run_check("compare", "--board", os.path.join(twin, "b.kicad_pcb"),
                                       "--project", os.path.join(twin, "b.kicad_pro"), "--record", self.record_path)
        self.assertEqual(status, 1, lines)
        self.assertTrue(any(line.startswith(f"MISMATCH | {self.record_path} | the record was taken of") for line in lines),
                        lines)
        self.assertNotIn("PASS", lines[-1])
