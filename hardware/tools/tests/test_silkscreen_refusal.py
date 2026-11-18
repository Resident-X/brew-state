"""The silkscreen command's proof that a board it writes differs from its input in nothing but silkscreen.

`build` is run with the step that edits the board seeded to also change a track, move a part or change a zone; `prove`
is run on pairs of boards written by the test. The proof itself reads text only; `build` needs KiCad and the placement
packages, as the command does.
"""

from __future__ import annotations

import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import silkscreen_fixtures as fx  # noqa: E402

PYTHON = None


def setUpModule():
    global PYTHON
    PYTHON = fx.require_tools()


import silkscreen  # noqa: E402
import silkscreen_patch  # noqa: E402

TRACK = ("(end 20 20)", "(end 20 21)")
PART = ("(at 8 8 0)", "(at 8 9 0)")
ZONE = ("(xy 12 29)", "(xy 13 29)")


def edit(old, new):
    """A replacement for the board-editing step that does what it does and then also changes `old` to `new`."""
    real = silkscreen.make_board

    def seeded(text, plan, footprints):
        done = real(text, plan, footprints)
        assert old in done, old
        return done.replace(old, new, 1)
    return seeded


def add_silk(extra):
    """A replacement for the board-editing step that also appends `extra` item text to the board."""
    real = silkscreen.make_board

    def seeded(text, plan, footprints):
        done = real(text, plan, footprints)
        end = done.rstrip().rfind(")")
        return done[:end] + extra + done[end:]
    return seeded


class Refusal(fx.Work):
    def build(self, replacement, as_json=True, out_exists=False):
        board = self.write("in.kicad_pcb", fx.small_board())
        out = self.path("out.kicad_pcb")
        if out_exists:
            self.write("out.kicad_pcb", "an earlier output\n")
        before = self.read(board)
        argv = ["build", "--board", board, "--out", out, "--kicad-python", PYTHON]
        with mock.patch.object(silkscreen, "make_board", replacement):
            status, result = (self.run_json if as_json else self.run_tool)(silkscreen.main, *argv)
        self.assertEqual(self.read(board), before, "the input board is left untouched")
        return status, result, out

    # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C7: When the board the command would write differs from its input in anything other than silkscreen, the command refuses to write it, names what differs and leaves the input untouched. Tests seed a changed track, a moved part and a changed zone in turn and check each is refused, and check that a silkscreen-only change is written. This does not cover judging the neatness of the silkscreen, which pictures settle.
    def test_a_changed_track_is_refused_naming_it_and_nothing_is_written(self):
        status, report, out = self.build(edit(*TRACK), out_exists=True)
        self.assertEqual((status, report["result"], report["written"]), (1, "REFUSED", None))
        self.assertEqual([f["finding"] for f in report["findings"]], ["DIFFERS"])
        self.assertIn("segment on net VIN from (10, 20) to (20, 20)", report["findings"][0]["item"])
        self.assertEqual(self.read(out), "an earlier output\n", "an output that was already there is left as it was")

    # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C7: When the board the command would write differs from its input in anything other than silkscreen, the command refuses to write it, names what differs and leaves the input untouched. Tests seed a changed track, a moved part and a changed zone in turn and check each is refused, and check that a silkscreen-only change is written. This does not cover judging the neatness of the silkscreen, which pictures settle.
    def test_a_moved_part_is_refused_naming_it_in_text(self):
        status, lines, out = self.build(edit(*PART), as_json=False)
        self.assertEqual(status, 1)
        self.assertFalse(os.path.exists(out))
        self.assertEqual(lines[0], "DIFFERS | footprint R1 differs | changed outside the silkscreen")
        self.assertTrue(lines[-1].startswith("RESULT | REFUSED | ") and "nothing was written" in lines[-1], lines)

    # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C7: When the board the command would write differs from its input in anything other than silkscreen, the command refuses to write it, names what differs and leaves the input untouched. Tests seed a changed track, a moved part and a changed zone in turn and check each is refused, and check that a silkscreen-only change is written. This does not cover judging the neatness of the silkscreen, which pictures settle.
    def test_a_changed_zone_is_refused_naming_it(self):
        status, report, out = self.build(edit(*ZONE))
        self.assertEqual((status, report["result"]), (1, "REFUSED"))
        self.assertEqual([f["item"] for f in report["findings"]], ["zone pour differs"])
        self.assertFalse(os.path.exists(out))

    # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C7: When the board the command would write differs from its input in anything other than silkscreen, the command refuses to write it, names what differs and leaves the input untouched. Tests seed a changed track, a moved part and a changed zone in turn and check each is refused, and check that a silkscreen-only change is written. This does not cover judging the neatness of the silkscreen, which pictures settle.
    def test_every_difference_is_named_not_only_the_first(self):
        real = silkscreen.make_board
        def three(text, plan, footprints):
            done = real(text, plan, footprints)
            for old, new in (TRACK, PART, ZONE):
                done = done.replace(old, new, 1)
            return done
        status, report, _out = self.build(three)
        self.assertEqual(status, 1)
        self.assertEqual(sorted(f["item"] for f in report["findings"]),
                         ["footprint R1 differs", "segment on net VIN from (10, 20) to (20, 20) differs", "zone pour differs"])
        self.assertIn("3 places", report["detail"])

    # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C7: When the board the command would write differs from its input in anything other than silkscreen, the command refuses to write it, names what differs and leaves the input untouched. Tests seed a changed track, a moved part and a changed zone in turn and check each is refused, and check that a silkscreen-only change is written. This does not cover judging the neatness of the silkscreen, which pictures settle.
    def test_a_silkscreen_only_change_is_written(self):
        extra = fx.free_text("EXTRA", 20, 27)
        status, report, out = self.build(add_silk(extra))
        self.assertEqual((status, report["result"], report["written"]), (0, "WRITTEN", out))
        self.assertTrue(os.path.exists(out))
        self.assertIn('(gr_text "EXTRA"', self.read(out))

    # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C7: When the board the command would write differs from its input in anything other than silkscreen, the command refuses to write it, names what differs and leaves the input untouched. Tests seed a changed track, a moved part and a changed zone in turn and check each is refused, and check that a silkscreen-only change is written. This does not cover judging the neatness of the silkscreen, which pictures settle.
    def test_the_commands_own_edit_passes_the_proof_it_is_judged_by(self):
        text = fx.small_board()
        plan = {"refs": {"R1": dict(layer="F.SilkS", x=8.5, y=6.0, angle=0, size=1.0, thick=0.15), "R2": dict(fab=True)},
                "texts": [dict(text="HI", side="F", x=20, y=20, angle=0, size=1.0, thick=0.15)], "polys": [], "circles": []}
        footprints = {"R1": dict(x=8, y=8, rot=0, side="F"), "R2": dict(x=8, y=12, rot=0, side="F")}
        written = silkscreen_patch.apply_plan(text, plan, footprints)
        self.assertNotEqual(written, text)
        self.assertEqual(silkscreen_patch.difference(text, written), [])
        self.assertIn('(at 0.5 -2 0)', written)
        self.assertIn('(layer "F.Fab"', silkscreen_patch.references(written)["R2"].text)


class Prove(fx.Work):
    def pair(self, old, new):
        text = fx.small_board()
        return self.write("a.kicad_pcb", text), self.write("b.kicad_pcb", text.replace(old, new, 1))

    def prove(self, first, second):
        status, report = self.run_json(silkscreen.main, "prove", "--input", first, "--output", second)
        status_text, lines = self.run_tool(silkscreen.main, "prove", "--input", first, "--output", second)
        self.assertEqual(status, status_text)
        return status, report, lines

    # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C7: When the board the command would write differs from its input in anything other than silkscreen, the command refuses to write it, names what differs and leaves the input untouched. Tests seed a changed track, a moved part and a changed zone in turn and check each is refused, and check that a silkscreen-only change is written. This does not cover judging the neatness of the silkscreen, which pictures settle.
    def test_boards_that_differ_only_in_silkscreen_pass_and_anything_else_fails_in_text_and_in_json(self):
        first, second = self.pair("(at 0 -2.1 0)", "(at 3 4 90)")
        status, report, lines = self.prove(first, second)
        self.assertEqual((status, report["result"], report["findings"]), (0, "SILKSCREEN ONLY", []))
        self.assertTrue(lines[0].startswith("RESULT | SILKSCREEN ONLY | "), lines)
        for old_new, name in ((TRACK, "segment on net VIN"), (PART, "footprint R1"), (ZONE, "zone pour")):
            first, second = self.pair(*old_new)
            status, report, lines = self.prove(first, second)
            self.assertEqual((status, report["result"]), (1, "DIFFERS"), name)
            self.assertIn(name, report["findings"][0]["item"])
            self.assertTrue(lines[0].startswith("DIFFERS | ") and name in lines[0], lines)

    # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C7: When the board the command would write differs from its input in anything other than silkscreen, the command refuses to write it, names what differs and leaves the input untouched. Tests seed a changed track, a moved part and a changed zone in turn and check each is refused, and check that a silkscreen-only change is written. This does not cover judging the neatness of the silkscreen, which pictures settle.
    def test_items_added_removed_or_renamed_outside_the_silkscreen_are_differences(self):
        text = fx.small_board()
        a = self.write("a.kicad_pcb", text)
        end = text.rstrip().rfind(")")
        added = self.write("added.kicad_pcb", text[:end] + fx.segment("GND", 1, 1, 2, 2) + text[end:])
        status, report, _ = self.prove(a, added)
        self.assertEqual(status, 1)
        self.assertIn("is only in the output", report["findings"][0]["item"])
        status, report, _ = self.prove(added, a)
        self.assertIn("is only in the input", report["findings"][0]["item"])
        renamed = self.write("renamed.kicad_pcb", text.replace('(property "Reference" "R1"', '(property "Reference" "R9"', 1))
        status, report, _ = self.prove(a, renamed)
        self.assertEqual(status, 1, "a part renamed is a change of the part, not of the silkscreen")
        self.assertIn("footprint", report["findings"][0]["item"])
        courtyard = self.write("court.kicad_pcb", text.replace('(layer "F.CrtYd")', '(layer "F.Fab")', 1))
        status, report, _ = self.prove(a, courtyard)
        self.assertEqual(status, 1, "a courtyard is not silkscreen")
        footprint_silk = self.write("fpsilk.kicad_pcb", text.replace("(width 0.12)", "(width 0.2)", 1))
        status, report, _ = self.prove(a, footprint_silk)
        self.assertEqual(status, 0, "a footprint's own silkscreen graphic is silkscreen")

    # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C7: When the board the command would write differs from its input in anything other than silkscreen, the command refuses to write it, names what differs and leaves the input untouched. Tests seed a changed track, a moved part and a changed zone in turn and check each is refused, and check that a silkscreen-only change is written. This does not cover judging the neatness of the silkscreen, which pictures settle.
    def test_a_board_that_cannot_be_read_or_is_not_well_formed_is_refused(self):
        a = self.write("a.kicad_pcb", fx.small_board())
        status, report, lines = self.prove(a, self.path("missing.kicad_pcb"))
        self.assertEqual((status, report["result"], report["findings"][0]["finding"]), (1, "REFUSED", "UNREADABLE"))
        self.assertTrue(lines[0].startswith("UNREADABLE | "), lines)
        broken = self.write("broken.kicad_pcb", fx.small_board().rstrip()[:-3])
        status, report, lines = self.prove(a, broken)
        self.assertEqual((status, report["result"]), (1, "REFUSED"))
        self.assertEqual(report["findings"][0]["finding"], "UNREADABLE")


if __name__ == "__main__":
    unittest.main()
