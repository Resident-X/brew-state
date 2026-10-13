#!/usr/bin/env python3
"""The locked-copper check, driven on synthetic boards against the real kicad-cli.

Each board here is written from text in a temporary directory: a few tracks,
an arc, a via and a zone on nets in critical classes, and copper on a net in
none. The check is run as its command runs it, through main(), so the class
membership it acts on is KiCad's own answer for the board and its project file.
Nothing is skipped when KiCad is absent: a check that cannot be exercised has
not been shown to work.
"""

from __future__ import annotations

import copy
import difflib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)

import board_check  # noqa: E402
import locked_copper  # noqa: E402
import sexpr  # noqa: E402

REPO = os.path.dirname(os.path.dirname(TOOLS))
KICAD_CLI = os.environ.get("KICAD_CLI") or "kicad-cli"
PROOF_PROJECT = os.path.join(REPO, "hardware", "proof", "gate-proof", "gate-proof.kicad_pro")


def setUpModule():
    board_check.require_kicad(KICAD_CLI)


#: The base board's items, by name, as KiCad 10 writes them. /PWR is in Power by
#: the project's assignment, /GND_A and /GND_B in Ground by its pattern, /LV in
#: no critical class. /GND_B reaches the board only on a pad, so it is a critical
#: net with no copper when recorded, as a net the router has yet to route is.
ITEMS = {
    "track": '(segment (start 0 0) (end 5 0) (width 0.5) (locked yes) (layer "F.Cu") (net "/PWR") '
             '(uuid "00000000-0000-4000-8000-000000000001"))',
    "arc": '(arc (start 0 10) (mid 2 12) (end 4 10) (width 0.5) (locked yes) (layer "F.Cu") (net "/GND_A") '
           '(uuid "00000000-0000-4000-8000-000000000002"))',
    "via": '(via (at 20 20) (size 0.8) (drill 0.4) (layers "F.Cu" "B.Cu") (locked yes) (net "/GND_A") '
           '(uuid "00000000-0000-4000-8000-000000000003"))',
    "zone": '(zone (net "/PWR") (locked yes) (layer "B.Cu") (uuid "00000000-0000-4000-8000-000000000004") '
            '(hatch edge 0.5) (connect_pads (clearance 0.5)) (min_thickness 0.25) '
            '(fill (thermal_gap 0.5) (thermal_bridge_width 0.5)) '
            '(polygon (pts (xy 30 30) (xy 40 30) (xy 40 40) (xy 30 40))))',
    "lv": '(segment (start 60 0) (end 65 0) (width 0.25) (layer "F.Cu") (net "/LV") '
          '(uuid "00000000-0000-4000-8000-000000000006"))',
    "pad": '(footprint "test:Pad" (layer "F.Cu") (uuid "00000000-0000-4000-8000-0000000000f0") (at 25 25) '
           '(property "Reference" "J1" (at 0 -2 0) (layer "F.SilkS") (uuid "00000000-0000-4000-8000-0000000000f1") '
           '(effects (font (size 1 1) (thickness 0.15)))) '
           '(pad "1" thru_hole circle (at 0 0) (size 1.7 1.7) (drill 1) (layers "*.Cu" "*.Mask") (net "/GND_B") '
           '(uuid "00000000-0000-4000-8000-0000000000f2")))',
}


def layout(items, extra: str = "") -> str:
    body = "".join(f"\t{item}\n" for item in items)
    return ('(kicad_pcb\n\t(version 20260206)\n\t(generator "pcbnew")\n\t(generator_version "10.0")\n'
            '\t(general (thickness 1.6))\n\t(paper "A4")\n'
            '\t(layers\n\t\t(0 "F.Cu" signal)\n\t\t(4 "In1.Cu" signal)\n\t\t(6 "In2.Cu" signal)\n'
            '\t\t(2 "B.Cu" signal)\n\t\t(25 "Edge.Cuts" user)\n\t)\n'
            + extra + body + ")\n")


def project(assignments=None, patterns=None, classes=("Power", "Ground"), mains="none") -> str:
    """A project file defining `classes` beside Default and declaring MAINS as `mains` (None: undeclared)."""
    with open(PROOF_PROJECT, encoding="utf-8") as handle:
        data = json.load(handle)
    settings = data["net_settings"]
    default, template = settings["classes"][0], settings["classes"][1]
    settings["classes"] = [default] + [dict(copy.deepcopy(template), name=name, priority=index)
                                       for index, name in enumerate(classes)]
    settings["netclass_assignments"] = assignments
    settings["netclass_patterns"] = patterns or []
    data["text_variables"] = {} if mains is None else {"MAINS": mains}
    return json.dumps(data, indent=1)


BASE_PROJECT = project({"/PWR": "Power"}, [{"netclass": "Ground", "pattern": "/GND_*"}])


class Board(unittest.TestCase):
    """A board and its project in their own folder, and a working folder outside it for the record."""

    def setUp(self):
        scratch = tempfile.TemporaryDirectory(prefix="locked-copper-test-")
        self.addCleanup(scratch.cleanup)
        self.folder = os.path.join(scratch.name, "design")
        self.work = os.path.join(scratch.name, "work")
        os.makedirs(self.folder)
        os.makedirs(self.work)
        self.board = os.path.join(self.folder, "b.kicad_pcb")
        self.project = os.path.join(self.folder, "b.kicad_pro")
        self.record_path = os.path.join(self.work, "b.record.json")
        self.write(layout(ITEMS.values()), BASE_PROJECT)

    def write(self, board_text: str, project_text: str = None):
        with open(self.board, "w", encoding="utf-8") as handle:
            handle.write(board_text)
        if project_text is not None:
            with open(self.project, "w", encoding="utf-8") as handle:
                handle.write(project_text)

    def run_check(self, *argv):
        out = io.StringIO()
        status = locked_copper.main(["--kicad-cli", KICAD_CLI, *argv], out=out)
        return status, out.getvalue().splitlines()

    def record(self, *classes, record_path=None):
        args = ["record", "--board", self.board, "--project", self.project, "--record", record_path or self.record_path]
        for name in classes or ("Power", "Ground"):
            args += ["--class", name]
        return self.run_check(*args)

    def on_classes(self, command, *classes):
        """Run `command` (confirm or lock) on the board with `classes`, Power and Ground by default."""
        args = [command, "--board", self.board, "--project", self.project]
        for name in classes or ("Power", "Ground"):
            args += ["--class", name]
        return self.run_check(*args)

    def board_text(self):
        with open(self.board, encoding="utf-8", newline="") as handle:
            return handle.read()

    def compare(self, record_path=None):
        return self.run_check("compare", "--board", self.board, "--project", self.project,
                              "--record", record_path or self.record_path)

    def recorded(self):
        status, lines = self.record()
        self.assertEqual(status, 0, lines)
        return lines

    def findings(self, lines, kind):
        return [line.split(" | ") for line in lines if line.startswith(kind + " | ")]


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


#: The base board's items with no lock on any of them.
UNLOCKED_ITEMS = {name: text.replace(" (locked yes)", "") for name, text in ITEMS.items()}

#: A track on a mains net, for the boards that declare mains.
AC_TRACK = ('(segment (start 0 40) (end 5 40) (width 0.5) (layer "F.Cu") (net "/AC") '
            '(uuid "00000000-0000-4000-8000-000000000007"))')

#: A custom rules file KiCad loads.
RULES = ('(version 1)\n(rule "Power width"\n\t(condition "A.hasNetclass(\'Power\')")\n'
         '\t(constraint track_width (min 0.4mm)))\n')


def without_locks(tree):
    """A parsed layout with every (locked ...) child taken out of its tracks, arcs, vias and zones."""
    return [[part for part in node if sexpr.head(part) != "locked"] if sexpr.head(node) in locked_copper.KIND_OF
            else node for node in tree]


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


if __name__ == "__main__":
    unittest.main()
