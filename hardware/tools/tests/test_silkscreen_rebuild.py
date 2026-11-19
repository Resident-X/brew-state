"""The silkscreen command's rebuild of a board's silkscreen: placement, the table's choices, the unplaced report and determinism.

Every board is a small synthetic one built by silkscreen_fixtures and loaded by the real KiCad interpreter (KICAD_PYTHON);
the placement packages (numpy, shapely, Pillow) are the ones the command itself imports.
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


class Rebuild(fx.Work):
    def build(self, text, table=None, tag="a", as_json=True, name="in"):
        """Build the board `text` in the folder `tag`: (exit status, report or text lines, output path, input path)."""
        board = self.write(f"{tag}/{name}.kicad_pcb", text)
        out = self.path(f"{tag}/out.kicad_pcb")
        argv = ["build", "--board", board, "--out", out, "--kicad-python", PYTHON, "--work", self.path(f"{tag}/work")]
        if table is not None:
            argv += ["--table", self.write(f"{tag}/silkscreen.yaml", table)]
        status, result = (self.run_json if as_json else self.run_tool)(silkscreen.main, *argv)
        return status, result, out, board

    def dump(self, path, tag="x"):
        """The extract of the board at `path`: its silkscreen items, pads and parts, as KiCad reads them."""
        return silkscreen.extract(PYTHON, path, self.work, f"{tag}.json")

    def free_texts(self, data):
        return sorted(s["text"] for s in data["silk"] if s["owner"] == "free" and s["is_text"])

    def labels(self, data):
        return {s["owner"]: s for s in data["silk"] if s["kind"] == "field:Reference"}


class Companions(Rebuild):
    # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C6: Run twice over the same synthetic board and the same table, the command writes boards whose silkscreen is identical in both runs. Tests cover several parts, a part with an override in the table, a part whose label cannot be placed, which is listed in the unplaced report, and an empty board, in text and in JSON. This does not cover the choice of text heights and legends, which the board's table holds.
    def test_build_names_the_project_and_rules_files_it_copied_beside_the_output_in_text_and_in_json(self):
        original = fx.small_board()
        for as_json in (True, False):
            tag = "j" if as_json else "t"
            self.write(f"{tag}/in.kicad_pro", '{"meta": {"filename": "in.kicad_pro"}}')
            self.write(f"{tag}/in.kicad_dru", "(version 1)\n")
            status, result, out, _ = self.build(original, tag=tag, as_json=as_json)
            self.assertEqual(status, 0, result)
            stem = os.path.splitext(out)[0]
            self.assertEqual(self.read(stem + ".kicad_pro"), '{"meta": {"filename": "in.kicad_pro"}}')
            if as_json:
                self.assertEqual(result["copied"], [stem + ".kicad_pro", stem + ".kicad_dru"])
            else:
                copied = [line for line in result if line.startswith("COPIED | ")]
                self.assertEqual(len(copied), 2, result)
                self.assertIn(stem + ".kicad_dru", copied[1])

    # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C6: Run twice over the same synthetic board and the same table, the command writes boards whose silkscreen is identical in both runs. Tests cover several parts, a part with an override in the table, a part whose label cannot be placed, which is listed in the unplaced report, and an empty board, in text and in JSON. This does not cover the choice of text heights and legends, which the board's table holds.
    def test_build_copies_nothing_and_reports_none_when_the_board_has_no_project_files(self):
        status, report, out, _ = self.build(fx.small_board())
        self.assertEqual((status, report["copied"]), (0, []))
        self.assertFalse(os.path.exists(os.path.splitext(out)[0] + ".kicad_pro"))

    # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C6: Run twice over the same synthetic board and the same table, the command writes boards whose silkscreen is identical in both runs. Tests cover several parts, a part with an override in the table, a part whose label cannot be placed, which is listed in the unplaced report, and an empty board, in text and in JSON. This does not cover the choice of text heights and legends, which the board's table holds.
    def test_build_refuses_a_different_project_file_already_beside_the_output_and_writes_nothing(self):
        original = fx.small_board()
        for as_json in (True, False):
            tag = "rj" if as_json else "rt"
            self.write(f"{tag}/in.kicad_pro", '{"meta": 1}')
            existing = self.write(f"{tag}/out.kicad_pro", '{"meta": 2}')
            status, result, out, _ = self.build(original, tag=tag, as_json=as_json)
            self.assertEqual(status, 1, result)
            self.assertFalse(os.path.exists(out), "nothing is written")
            self.assertEqual(self.read(existing), '{"meta": 2}', "the existing file is left as it was")
            if as_json:
                self.assertEqual(result["result"], "REFUSED")
                self.assertIn("a different out.kicad_pro is already beside the output", result["findings"][0]["detail"])
            else:
                self.assertTrue(any(l.startswith("REFUSED | ") and "a different out.kicad_pro" in l for l in result), result)
        tag = "same"
        self.write(f"{tag}/in.kicad_pro", '{"meta": 3}')
        self.write(f"{tag}/out.kicad_pro", '{"meta": 3}')
        status, result, out, _ = self.build(original, tag=tag)
        self.assertEqual((status, len(result["copied"])), (0, 1), "an identical file already there is no conflict")


class Several(Rebuild):
    # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C6: Run twice over the same synthetic board and the same table, the command writes boards whose silkscreen is identical in both runs. Tests cover several parts, a part with an override in the table, a part whose label cannot be placed, which is listed in the unplaced report, and an empty board, in text and in JSON. This does not cover the choice of text heights and legends, which the board's table holds.
    def test_several_parts_each_get_a_label_beside_them_and_the_names_the_board_gives_them(self):
        original = fx.small_board()
        status, report, out, board = self.build(original)
        self.assertEqual(status, 0, report)
        self.assertEqual(report["result"], "WRITTEN")
        self.assertEqual((report["references"], report["references_on_silk"], report["unplaced"], report["checks"]), (7, 7, [], {}))
        data = self.dump(out)
        labels = self.labels(data)
        self.assertEqual(sorted(labels), ["F1", "J1", "R1", "R2", "R3", "TP1", "U1"])
        for ref, item in labels.items():
            self.assertEqual((item["text"], item["side"], item["size"]), (ref, "F", 1.0), ref)
        self.assertEqual(self.free_texts(data), ["Net_A", "POWER IN", "T10A 250V"])
        self.assertEqual(self.read(board), original, "the input board is never written")
        self.assertNotEqual(self.read(out), original)
        notes = [f for f in report["findings"] if f["finding"] == "NOTE"]
        self.assertEqual([n["item"] for n in notes], ["F1"])

    # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C6: Run twice over the same synthetic board and the same table, the command writes boards whose silkscreen is identical in both runs. Tests cover several parts, a part with an override in the table, a part whose label cannot be placed, which is listed in the unplaced report, and an empty board, in text and in JSON. This does not cover the choice of text heights and legends, which the board's table holds.
    def test_two_runs_write_identical_boards_in_text_and_in_json_and_a_rebuilt_board_is_rebuilt_to_itself(self):
        original = fx.small_board()
        status1, lines, out1, _ = self.build(original, tag="a", as_json=False)
        status2, report, out2, _ = self.build(original, tag="b")
        self.assertEqual((status1, status2), (0, 0))
        self.assertTrue(any(line.startswith("RESULT | WRITTEN | wrote ") for line in lines), lines)
        self.assertTrue(any(line.startswith("NOTE | F1 | ") for line in lines), lines)
        first, second = self.read(out1), self.read(out2)
        self.assertEqual(first, second)
        self.assertEqual(report["sha256"], silkscreen_patch.sha(first))
        self.assertEqual(silkscreen_patch.difference(first, second), [])
        status3, again, out3, _ = self.build(first, tag="c", name="rebuilt")
        self.assertEqual(status3, 0)
        self.assertEqual(self.read(out3), first, "the silkscreen of a rebuilt board is rebuilt to the same bytes")

    # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C6: Run twice over the same synthetic board and the same table, the command writes boards whose silkscreen is identical in both runs. Tests cover several parts, a part with an override in the table, a part whose label cannot be placed, which is listed in the unplaced report, and an empty board, in text and in JSON. This does not cover the choice of text heights and legends, which the board's table holds.
    def test_parts_on_the_back_and_turned_parts_are_labelled_on_their_own_side_and_read_upright(self):
        parts = [fx.resistor("R1", 8, 8), fx.resistor("R2", 8, 12, 90, "B"), fx.resistor("R3", 14, 8, 90), fx.resistor("R4", 14, 13, 180, "B"),
                 fx.part("U1", "SOIC-4", 14, 22, rot=90, body=(4, 3),
                         pads=[fx.pad(1, -1.5, -1, 1.0, 0.6, "A"), fx.pad(2, -1.5, 1, 1.0, 0.6, "B"), fx.pad(3, 1.5, 1, 1.0, 0.6, "C"),
                               fx.pad(4, 1.5, -1, 1.0, 0.6, "D")])]
        status, report, out, _ = self.build(fx.board_text(parts))
        self.assertEqual((status, report["references_on_silk"], report["unplaced"], report["checks"]), (0, 5, [], {}), report)
        import silkscreen_check
        data = self.dump(out)
        labels = self.labels(data)
        self.assertEqual({r: labels[r]["side"] for r in labels}, {"R1": "F", "R2": "B", "R3": "F", "R4": "B", "U1": "F"})
        for ref, item in labels.items():
            self.assertIn(silkscreen_check.reading_angle(item), (0.0, 90.0), f"{ref} does not read upright")
        self.assertTrue(all(labels[r]["mirror"] for r in ("R2", "R4")), "labels on the back are mirrored the way the back shows them")

    # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C6: Run twice over the same synthetic board and the same table, the command writes boards whose silkscreen is identical in both runs. Tests cover several parts, a part with an override in the table, a part whose label cannot be placed, which is listed in the unplaced report, and an empty board, in text and in JSON. This does not cover the choice of text heights and legends, which the board's table holds.
    def test_a_part_with_an_override_in_the_table_takes_it_and_the_others_do_not(self):
        original = fx.small_board()
        table = ("parts:\n  R1: {reference_sizes: [0.8]}\n  R2: {reference: skip}\n  U1: {name: BRAIN}\n  TP1: {name: skip}\n"
                 "  R3: {pin1: mark}\n")
        status, report, out, board = self.build(original, table)
        self.assertEqual(status, 0, report)
        data = self.dump(out)
        labels = self.labels(data)
        self.assertEqual((labels["R1"]["size"], labels["R3"]["size"]), (0.8, 1.0))
        self.assertEqual(silkscreen_patch.references(self.read(out))["R2"].text, silkscreen_patch.references(original)["R2"].text,
                         "a skipped Reference is left exactly as it was")
        self.assertEqual(self.free_texts(data), ["1", "BRAIN", "POWER IN", "T10A 250V"])
        broken = {f["item"].split(": ")[1].split(" ")[0] for f in report["findings"] if f["finding"] == "CHECK"}
        self.assertEqual(broken, {"R2"}, "only the label the table left where it was breaks a measure")


class Dense(Rebuild):
    def board(self):
        parts = [fx.resistor("R%d" % (r * 7 + c + 1), 4 + c * 3.6, 3 + r * 3.0, 90 if (r + c) % 3 == 0 else 0) for r in range(4) for c in range(7)]
        return fx.board_text(parts, box=(0, 0, 33.2, 18))

    # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C6: Run twice over the same synthetic board and the same table, the command writes boards whose silkscreen is identical in both runs. Tests cover several parts, a part with an override in the table, a part whose label cannot be placed, which is listed in the unplaced report, and an empty board, in text and in JSON. This does not cover the choice of text heights and legends, which the board's table holds.
    def test_a_crowded_board_that_needs_the_ejection_search_is_rebuilt_to_the_same_bytes_and_lists_what_still_fails(self):
        import silkscreen_engine
        import silkscreen_place
        original = silkscreen_place.min_conflicts
        searches = []

        def counting(solver, fail, **kwargs):
            searches.append(len(fail))
            return original(solver, fail, **kwargs)
        with mock.patch.object(silkscreen_place, "min_conflicts", counting):
            status1, first, out1, _ = self.build(self.board(), tag="a")
            status2, second, out2, _ = self.build(self.board(), tag="b", as_json=False)
        self.assertEqual((status1, status2), (0, 0))
        self.assertEqual(len(searches), 2, "each run needed the randomised search")
        self.assertEqual(self.read(out1), self.read(out2))
        self.assertEqual(first["references"], 28)
        self.assertGreaterEqual(first["references_on_silk"] + len(first["unplaced"]), 28)
        self.assertEqual(first["checks"], {})
        self.assertTrue(any(line.startswith("UNPLACED | ") for line in second) == bool(first["unplaced"]))


class Unplaced(Rebuild):
    def board(self):
        big = fx.part("BIG1", "Lib:Big", 6, 4, body=(10.4, 6.4), pads=[fx.pad(1, 0, 0, 10.4, 6.4, "A")], silk_body=False)
        wall = fx.part("WALL", "Lib:Wall", 12.75, 4, body=(2.5, 7), pads=[fx.pad(1, 0, 0, 2.5, 7, "B")], silk_body=False)
        return fx.board_text([big, wall, fx.resistor("R1", 30, 4)], box=(0, 0, 40, 8))

    # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C6: Run twice over the same synthetic board and the same table, the command writes boards whose silkscreen is identical in both runs. Tests cover several parts, a part with an override in the table, a part whose label cannot be placed, which is listed in the unplaced report, and an empty board, in text and in JSON. This does not cover the choice of text heights and legends, which the board's table holds.
    def test_a_label_with_no_free_place_is_not_drawn_and_is_listed_in_text_and_in_json(self):
        table = "parts: {WALL: {reference: skip}}\n"
        status, report, out, _ = self.build(self.board(), table, tag="a")
        self.assertEqual(status, 0, report)
        self.assertEqual((report["references"], report["references_on_silk"]), (3, 1))
        self.assertEqual([row["ref"] for row in report["unplaced"]], ["BIG1"])
        row = report["unplaced"][0]
        self.assertEqual((row["side"], row["nearest"][0]["ref"]), ("F", "WALL"))
        listed = [f for f in report["findings"] if f["finding"] == "UNPLACED"]
        self.assertEqual([f["item"] for f in listed], ["BIG1"])
        self.assertIn("1 unplaced", report["detail"])
        self.assertIn('"F.Fab"', silkscreen_patch.references(self.read(out))["BIG1"].text, "its Reference moves to the fab layer")
        self.assertNotIn('"F.SilkS"', silkscreen_patch.references(self.read(out))["BIG1"].text.split("(effects")[0])
        self.assertEqual(sorted(self.labels(self.dump(out))), ["R1", "WALL"], "WALL's label is the one the table left where it was")
        status, lines, _out, _ = self.build(self.board(), table, tag="b", as_json=False)
        self.assertEqual(status, 0)
        self.assertTrue(any(line.startswith("UNPLACED | BIG1 | ") for line in lines), lines)
        self.assertTrue(lines[-1].startswith("RESULT | WRITTEN | ") and "1 unplaced" in lines[-1], lines[-1])


class Empty(Rebuild):
    # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C6: Run twice over the same synthetic board and the same table, the command writes boards whose silkscreen is identical in both runs. Tests cover several parts, a part with an override in the table, a part whose label cannot be placed, which is listed in the unplaced report, and an empty board, in text and in JSON. This does not cover the choice of text heights and legends, which the board's table holds.
    def test_a_board_with_no_parts_is_written_as_it_was_in_text_and_in_json(self):
        original = fx.board_text([])
        status, report, out, _ = self.build(original, tag="a")
        self.assertEqual(status, 0, report)
        self.assertEqual((report["result"], report["references"], report["references_on_silk"], report["unplaced"], report["findings"]),
                         ("WRITTEN", 0, 0, [], []))
        self.assertEqual(self.read(out), original)
        status, lines, out2, _ = self.build(original, tag="b", as_json=False)
        self.assertEqual(status, 0)
        self.assertEqual(len(lines), 1)
        self.assertTrue(lines[0].startswith("RESULT | WRITTEN | ") and "0 of 0 references" in lines[0], lines)
        self.assertEqual(self.read(out2), original)

    # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C6: Run twice over the same synthetic board and the same table, the command writes boards whose silkscreen is identical in both runs. Tests cover several parts, a part with an override in the table, a part whose label cannot be placed, which is listed in the unplaced report, and an empty board, in text and in JSON. This does not cover the choice of text heights and legends, which the board's table holds.
    def test_an_empty_board_still_carries_the_fixed_texts_of_its_table_and_names_a_legend_it_cannot_place(self):
        table = ("fixed_texts:\n  - {id: title, text: HELLO, size: 1.5, at: [20, 15]}\n"
                 "legends:\n  - {id: danger, region: mains, lines: [{text: DANGER, size: 1.0}]}\n")
        status, report, out, _ = self.build(fx.board_text([]), table)
        self.assertEqual(status, 0, report)
        self.assertEqual(self.free_texts(self.dump(out)), ["HELLO"])
        self.assertEqual(report["fixed"]["title"]["kept_position"], True)
        self.assertEqual(report["fixed"]["danger"], None)
        notes = {f["item"]: f["detail"] for f in report["findings"]}
        self.assertIn("no rule area named 'mains'", notes["danger"])


class Table(Rebuild):
    # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C6: Run twice over the same synthetic board and the same table, the command writes boards whose silkscreen is identical in both runs. Tests cover several parts, a part with an override in the table, a part whose label cannot be placed, which is listed in the unplaced report, and an empty board, in text and in JSON. This does not cover the choice of text heights and legends, which the board's table holds.
    def test_a_legend_stands_inside_its_rule_area_a_taken_fixed_text_moves_and_pin_1_markings_are_drawn(self):
        table = ("pin1: {dot: [U1], mark: [J1]}\n"
                 "legends:\n  - {id: danger, region: mains, symbol: hazard-triangle, symbol_size: 4, prefer: [32, 14], lines: [{text: DANGER, size: 1.0}]}\n"
                 "fixed_texts:\n  - {id: title, text: TITLE, size: 1.0, at: [20, 27]}\n  - {id: taken, text: TAKEN, size: 1.0, at: [30, 22]}\n")
        status, report, out, _ = self.build(fx.small_board(), table)
        self.assertEqual(status, 0, report)
        self.assertEqual(report["checks"], {}, report["findings"])
        self.assertEqual(report["fixed"]["title"]["kept_position"], True)
        self.assertEqual(report["fixed"]["taken"]["kept_position"], False)
        moved = [f for f in report["findings"] if f["finding"] == "MOVED"]
        self.assertEqual([m["item"] for m in moved], ["taken"])
        data = self.dump(out)
        self.assertEqual(self.free_texts(data), sorted(["1", "DANGER", "POWER IN", "T10A 250V", "TAKEN", "TITLE", "Net_A"]))
        danger = next(s for s in data["silk"] if s["text"] == "DANGER")
        xs = [x for ring in danger["rings"] for x, _y in ring[0][:]]
        self.assertTrue(26 < min(xs) and max(xs) < 38, "the legend stands inside the mains area, x 26 to 38")
        shapes = [s for s in data["silk"] if s["owner"] == "free" and not s["is_text"]]
        self.assertGreaterEqual(len(shapes), 3, "the triangle, its bolt and the pin-1 dot are drawn")

    # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C6: Run twice over the same synthetic board and the same table, the command writes boards whose silkscreen is identical in both runs. Tests cover several parts, a part with an override in the table, a part whose label cannot be placed, which is listed in the unplaced report, and an empty board, in text and in JSON. This does not cover the choice of text heights and legends, which the board's table holds.
    def test_the_free_silkscreen_of_the_input_is_rebuilt_and_not_added_to(self):
        text = fx.board_text([fx.resistor("R1", 8, 8)], [fx.free_text("OLD", 20, 20), fx.free_text("OLDB", 22, 22, "B.SilkS")])
        status, report, out, _ = self.build(text)
        self.assertEqual(status, 0, report)
        self.assertEqual(self.free_texts(self.dump(out)), [])
        self.assertEqual(report["references_on_silk"], 1)

    # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C6: Run twice over the same synthetic board and the same table, the command writes boards whose silkscreen is identical in both runs. Tests cover several parts, a part with an override in the table, a part whose label cannot be placed, which is listed in the unplaced report, and an empty board, in text and in JSON. This does not cover the choice of text heights and legends, which the board's table holds.
    def test_inputs_that_cannot_be_used_are_refused_naming_why_and_nothing_is_written(self):
        board = self.write("in.kicad_pcb", fx.small_board())
        out = self.path("out.kicad_pcb")
        status, report = self.run_json(silkscreen.main, "build", "--board", self.path("missing.kicad_pcb"), "--out", out)
        self.assertEqual((status, report["result"], report["findings"][0]["finding"]), (1, "REFUSED", "UNREADABLE"))
        table = self.write("bad.yaml", "colour: red\n")
        status, report = self.run_json(silkscreen.main, "build", "--board", board, "--out", out, "--table", table)
        self.assertEqual(status, 1)
        self.assertIn("colour", report["findings"][0]["detail"])
        status, lines = self.run_tool(silkscreen.main, "build", "--board", board, "--out", board)
        self.assertEqual(status, 1)
        self.assertTrue(lines[0].startswith("REFUSED | ") and "the output is the input board" in lines[0], lines)
        status, report = self.run_json(silkscreen.main, "build", "--board", board, "--out", out, "--resolution", "0")
        self.assertEqual(status, 1)
        self.assertIn("--resolution", report["findings"][0]["item"])
        self.assertFalse(os.path.exists(out))
        self.assertEqual(self.read(board), fx.small_board())


if __name__ == "__main__":
    unittest.main()
