#!/usr/bin/env python3
"""The placement file in the assembler's frame, the two file sets and the parts list, driven on synthetic designs.

Nothing here is a real design: the board, the schematic, the parts specification record and the assembler's footprints are
small made-up files with made-up catalogue numbers, and no KiCad, gerbonara or network is used. What is under test is what the
three commands decide for themselves, and each of the faults the fit exists to catch.
"""

from __future__ import annotations

import contextlib
import csv
import io
import json
import math
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)

import board_check  # noqa: E402
import production_files  # noqa: E402

#: The assembler's footprint of the synthetic three-pad part, in its own frame (Y up, from its own origin, which is pad 1).
THREE_PADS = [("1", 0.0, 0.0), ("2", 2.0, 0.0), ("3", 1.0, -1.5)]
#: The same part as the board's footprint draws it (Y down, from the footprint's centre).
BOARD_THREE = [("1", -1.0, 0.0), ("2", 1.0, 0.0), ("3", 0.0, 1.5)]


def footprint(reference, side, x, y, rotation, lcsc, pads, attr="smd"):
    """A footprint as the layout file holds it."""
    layer = "F.Cu" if side == "top" else "B.Cu"
    text = [f'\t(footprint "Lib:{reference}"', f'\t\t(layer "{layer}")', f"\t\t(at {x} {y} {rotation})",
            f'\t\t(property "Reference" "{reference}")', f'\t\t(property "LCSC" "{lcsc}")']
    if attr:
        text.append(f"\t\t(attr {attr})")
    for number, px, py in pads:
        text.append(f'\t\t(pad "{number}" smd rect (at {px} {py}) (size 1 1) (layers "{layer}"))')
    return "\n".join(text) + "\n\t)\n"


def board_text(parts):
    return "(kicad_pcb\n" + "".join(parts) + ")\n"


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)
    return path


def asm_file(folder, lcsc, pads):
    return write(os.path.join(folder, f"{lcsc}.json"), json.dumps(
        {"lcsc": lcsc, "source": "synthetic", "read_on": "2030-01-01",
         "pads": [{"number": n, "x": x, "y": y} for n, x, y in pads]}))


def positions_csv(path, rows):
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(production_files.POSITION_COLUMNS)
        writer.writerows(rows)
    return path


def record_text(entries):
    lines = ["positions:"]
    for reference, lcsc, extra in entries:
        lines += [f"  - reference: {reference}", f"    lcsc: {lcsc}"] + [f"    {key}: {value}" for key, value in extra.items()]
    return "\n".join(lines) + "\n"


def run(argv):
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
        status = production_files.main(argv)
    return status, out.getvalue().splitlines()


def read_rows(path):
    with open(path, encoding="utf-8", newline="") as handle:
        return list(csv.reader(handle))


class Synthetic(unittest.TestCase):
    """A synthetic order: a rotated and shifted three-pad part U1, a resistor R1, a bottom-side capacitor C1, a through-hole
    connector J1, an owner-fitted part X1 and a part with no catalogue number M1."""

    def setUp(self):
        self.work = tempfile.mkdtemp(prefix="production-sets-")
        self.addCleanup(shutil.rmtree, self.work, True)
        self.kept = os.path.join(self.work, "kept")
        asm_file(self.kept, "C0001", THREE_PADS)
        asm_file(self.kept, "C0002", [("1", -0.75, 0.0), ("2", 0.75, 0.0)])
        asm_file(self.kept, "C0003", [("1", -0.75, 0.0), ("2", 0.75, 0.0)])
        asm_file(self.kept, "C0004", [("1", 0.0, 0.0), ("2", 2.54, 0.0)])
        self.board = write(os.path.join(self.work, "b.kicad_pcb"), board_text([
            footprint("U1", "top", 30, 20, 90, "C0001", BOARD_THREE),
            footprint("R1", "top", 10, 5, 0, "C0002", [("1", -0.75, 0), ("2", 0.75, 0)]),
            footprint("C1", "bottom", 12, 8, 180, "C0003", [("1", 0.75, 0), ("2", -0.75, 0)]),
            footprint("J1", "top", 40, 40, 0, "C0004", [("1", 0, 0), ("2", 2.54, 0)], attr="through_hole"),
            footprint("X1", "top", 50, 50, 0, "C0002", [("1", -0.75, 0), ("2", 0.75, 0)]),
            footprint("M1", "top", 60, 60, 0, "none", [("1", 0, 0)]),
        ]))
        self.positions = positions_csv(os.path.join(self.work, "positions.csv"), [
            ["U1", "x", "p", "30", "-20", "90", "top"], ["R1", "x", "p", "10", "-5", "0", "top"],
            ["C1", "x", "p", "12", "-8", "180", "bottom"], ["J1", "x", "p", "40", "-40", "0", "top"],
            ["X1", "x", "p", "50", "-50", "0", "top"], ["M1", "x", "p", "60", "-60", "0", "top"]])
        self.record = write(os.path.join(self.work, "parts-specification.yaml"), record_text([
            ("U1", "C0001", {"fitted_by": "assembler"}), ("R1", "C0002", {"fitted_by": "assembler"}),
            ("C1", "C0003", {"fitted_by": "assembler"}), ("J1", "C0004", {"fitted_by": "assembler"}),
            ("X1", "C0002", {"fitted_by": "owner"}), ("M1", "none", {"fitted_by": "none"})]))

    def none_unavailable(self):
        return write(os.path.join(self.work, "none-unavailable.yaml"),
                     "source: the assembler's catalogue\nread_on: 2030-01-02\nunavailable: []\n")

    def place(self, *extra, record=None, out="sets", fmt="text"):
        folder = os.path.join(self.work, out)
        if "--unavailable" not in extra and "--bare" not in extra:
            extra = (*extra, "--unavailable", self.none_unavailable())
        extra = tuple(e for e in extra if e != "--bare")
        return run(["placement", "--positions", self.positions, "--board", self.board, "--assembler-footprints", self.kept,
                    "--fitting", record or self.record, "--out", folder, "--format", fmt, *extra]) + (folder,)


class TheAssemblersFrame(Synthetic):
    """SOL-HW-CONTROLLER-BOARDS-ORDERED.C2: Each board's placement file gives every placed part's rotation and position in the assembler's own footprint frame"""

    def test_a_part_rotated_and_shifted_against_the_assemblers_footprint_is_brought_onto_it_exactly(self):
        # SOL-HW-CONTROLLER-BOARDS-ORDERED.C2: The placement step takes the assembler's published footprint for each placed part's catalogue number and finds the rotation and the shift that bring it onto the board's pads, matched by pad number
        status, lines, folder = self.place()
        self.assertEqual(status, 0, lines)
        rows = {row[0]: row for row in read_rows(os.path.join(folder, "placement-full.csv"))[1:]}
        # By hand: U1 sits at editor (30, 20) turned 90; its pad 1 is at editor (30, 21), pad 2 at (30, 19), pad 3 at (31.5, 20),
        # so in the export's frame (30, -21), (30, -19), (31.5, -20); the assembler's pad 1 is its origin and pad 2 is 2 mm to
        # its right, so the footprint is turned 90 degrees counter-clockwise about (30, -21).
        self.assertEqual(rows["U1"], ["U1", "30", "-21", "Top", "90"])
        # The resistor's footprints share an origin, so only the board's own position and rotation come through.
        self.assertEqual(rows["R1"], ["R1", "10", "-5", "Top", "0"])
        self.assertEqual(read_rows(os.path.join(folder, "placement-full.csv"))[0], ["Designator", "Mid X", "Mid Y", "Layer", "Rotation"])
        for reference in ("U1", "R1", "C1", "J1"):
            part = production_files.board_parts(self.board)[reference]
            row = rows[reference]
            self.assertLess(production_files.landing_error(
                float(row[4]), (float(row[1]), float(row[2])), part,
                production_files.read_assembler_footprint(self.kept, part.lcsc)), 1e-3, reference)

    def test_a_row_is_judged_against_the_pads_by_a_check_independent_of_the_fit(self):
        # SOL-HW-CONTROLLER-BOARDS-ORDERED.C2: A test over synthetic footprints holds that a part rotated and shifted against the assembler's footprint is brought onto it exactly
        part = production_files.board_parts(self.board)["U1"]
        asm = production_files.read_assembler_footprint(self.kept, "C0001")
        self.assertLess(production_files.landing_error(90, (30, -21), part, asm), 1e-9)
        for theta, shift in ((270, (30, -21)), (90, (30, 20)), (90, (30, -20)), (0, (30, -21))):
            with self.subTest(theta=theta, shift=shift):
                self.assertGreater(production_files.landing_error(theta, shift, part, asm), 0.5)

    def refused_by_a_fault(self, name, faulty, because):
        with mock.patch.object(production_files, name, faulty):
            status, lines, folder = self.place()
        self.assertEqual(status, 1, lines)
        self.assertTrue(any(line.startswith("REFUSED | ") and because in line for line in lines), lines)
        self.assertFalse(os.path.exists(folder))

    def test_a_wrong_rotation_sign_is_caught(self):
        # SOL-HW-CONTROLLER-BOARDS-ORDERED.C2: A test over synthetic footprints holds that each of a wrong rotation sign, a missing flip of the vertical axis and a dropped origin shift is caught
        self.refused_by_a_fault("row_angle", lambda theta: -theta, "U1's row (30, -21, Top, 270) does not land")

    def test_a_missing_flip_of_the_vertical_axis_is_caught(self):
        # SOL-HW-CONTROLLER-BOARDS-ORDERED.C2: A test over synthetic footprints holds that each of a wrong rotation sign, a missing flip of the vertical axis and a dropped origin shift is caught
        with mock.patch.object(production_files, "export_frame", lambda x, y: (x, y)):
            status, lines, folder = self.place()
        self.assertEqual(status, 1, lines)
        self.assertTrue(any("pads cannot all be matched" in line or "disagree" in line for line in lines), lines)

    def test_a_dropped_origin_shift_is_caught(self):
        # SOL-HW-CONTROLLER-BOARDS-ORDERED.C2: A test over synthetic footprints holds that each of a wrong rotation sign, a missing flip of the vertical axis and a dropped origin shift is caught
        self.refused_by_a_fault("row_position", lambda part, shift: (part.x, part.y), "U1's row (30, -20, Top, 90) does not land")

    def test_a_bottom_side_part_is_fitted_with_the_assemblers_footprint_mirrored(self):
        # SOL-HW-CONTROLLER-BOARDS-ORDERED.C2: The file carries each part's corrected rotation and the position of the assembler's footprint origin
        status, lines, folder = self.place()
        self.assertEqual(status, 0, lines)
        row = {r[0]: r for r in read_rows(os.path.join(folder, "placement-full.csv"))[1:]}["C1"]
        self.assertEqual(row[3], "Bottom")
        part = production_files.board_parts(self.board)["C1"]
        self.assertLess(production_files.landing_error(float(row[4]), (float(row[1]), float(row[2])), part,
                                                       production_files.read_assembler_footprint(self.kept, "C0003")), 1e-3)

    def test_a_part_with_an_unmatched_pad_is_refused_by_name(self):
        # SOL-HW-CONTROLLER-BOARDS-ORDERED.C2: A part whose pads cannot all be matched is refused, naming the part, and enters the file only through a recorded per-part override with its reason
        asm_file(self.kept, "C0001", THREE_PADS[:2] + [("4", 1.0, -1.5)])
        status, lines, folder = self.place()
        self.assertEqual(status, 1, lines)
        self.assertTrue(any("U1's pads cannot all be matched" in line and "only through a recorded override" in line
                            for line in lines), lines)
        self.assertEqual(lines[-1], "RESULT | REFUSED | nothing was written")
        self.assertFalse(os.path.exists(folder))

    def test_a_pad_off_its_place_beyond_the_tolerance_is_refused_and_one_within_it_is_not(self):
        # SOL-HW-CONTROLLER-BOARDS-ORDERED.C2: A part whose pads cannot all be matched is refused, naming the part
        asm_file(self.kept, "C0001", [("1", 0.0, 0.0), ("2", 2.0, 0.0), ("3", 1.0, -1.7)])
        status, lines, _ = self.place()
        self.assertEqual(status, 1, lines)
        self.assertTrue(any("U1's pads cannot all be matched: no turn" in line for line in lines), lines)
        asm_file(self.kept, "C0001", [("1", 0.0, 0.0), ("2", 2.0, 0.0), ("3", 1.0, -1.55)])
        self.assertEqual(self.place(out="again")[0], 0)

    def test_a_missing_assembler_footprint_is_refused_naming_the_number(self):
        # SOL-HW-CONTROLLER-BOARDS-ORDERED.C2: The assembler's footprints are fetched once for each catalogue number and kept outside the repository
        os.remove(os.path.join(self.kept, "C0004.json"))
        status, lines, _ = self.place()
        self.assertEqual(status, 1, lines)
        self.assertTrue(any("no footprint of the assembler's is kept for C0004" in line for line in lines), lines)

    def test_an_override_with_its_reason_admits_the_part_and_is_listed(self):
        # SOL-HW-CONTROLLER-BOARDS-ORDERED.C2: A part whose pads cannot all be matched enters the file only through a recorded per-part override with its reason
        asm_file(self.kept, "C0004", [("1", 0.0, 0.0), ("9", 2.54, 0.0)])
        overrides = write(os.path.join(self.work, "overrides.yaml"),
                          "overrides:\n  - {reference: J1, x: 41.5, y: -40, rotation: 450, reason: the housing is keyed on pad 9}\n")
        status, lines, folder = self.place("--overrides", overrides)
        self.assertEqual(status, 0, lines)
        self.assertIn("OVERRIDE | J1 | the housing is keyed on pad 9", lines)
        self.assertEqual({r[0]: r for r in read_rows(os.path.join(folder, "placement-full.csv"))[1:]}["J1"],
                         ["J1", "41.5", "-40", "Top", "90"])

    def test_an_override_without_a_reason_a_stale_one_and_one_for_an_unplaced_part_are_refused(self):
        # SOL-HW-CONTROLLER-BOARDS-ORDERED.C2: A part whose pads cannot all be matched enters the file only through a recorded per-part override with its reason
        for text, because in (
                ("overrides:\n  - {reference: J1, x: 1, y: 2, rotation: 0, reason: ' '}\n", "gives no reason"),
                ("overrides:\n  - {reference: U1, x: 1, y: 2, rotation: 0, reason: why}\n", "the override for U1 is stale"),
                ("overrides:\n  - {reference: Q9, x: 1, y: 2, rotation: 0, reason: why}\n", "names a part that is not placed"),
                ("overrides:\n  - {reference: U1, x: 1, rotation: 0, reason: why}\n", "exactly the keys")):
            with self.subTest(because=because):
                path = write(os.path.join(self.work, "o.yaml"), text)
                status, lines, _ = self.place("--overrides", path, out="o")
                self.assertEqual(status, 1, lines)
                self.assertTrue(any(because in line for line in lines), lines)

    def test_an_override_cannot_admit_an_owner_fitted_part_or_one_the_export_omits(self):
        # SOL-HW-CONTROLLER-BOARDS-ORDERED.C2: A part whose pads cannot all be matched enters the file only through a recorded per-part override with its reason
        asm_file(self.kept, "C0004", [("1", 0.0, 0.0), ("9", 2.54, 0.0)])
        positions_csv(self.positions, [["U1", "x", "p", "30", "-20", "90", "top"], ["R1", "x", "p", "10", "-5", "0", "top"],
                                       ["C1", "x", "p", "12", "-8", "180", "bottom"], ["X1", "x", "p", "50", "-50", "0", "top"],
                                       ["M1", "x", "p", "60", "-60", "0", "top"]])
        for reference, because in (("X1", "names a part that is not placed in the full set"),
                                   ("M1", "names a part that is not placed in the full set"),
                                   ("J1", "J1 is marked for the assembler but the position export lists no row for it")):
            with self.subTest(reference=reference):
                path = write(os.path.join(self.work, "o.yaml"),
                             f"overrides:\n  - {{reference: {reference}, x: 1, y: 2, rotation: 0, reason: why}}\n")
                status, lines, folder = self.place("--overrides", path, out="o" + reference)
                self.assertEqual(status, 1, lines)
                self.assertTrue(any(because in line for line in lines), lines)
                self.assertFalse(os.path.exists(folder))

    def test_a_footprint_file_with_no_source_or_read_date_is_refused(self):
        # SOL-HW-CONTROLLER-BOARDS-ORDERED.C2: The assembler's footprints are fetched once for each catalogue number, with the source and read date in each kept file
        for key, value in (("source", None), ("read_on", None), ("source", "  "), ("read_on", ""), ("source", 5)):
            with self.subTest(key=key, value=value):
                path = os.path.join(self.kept, "C0004.json")
                with open(path, encoding="utf-8") as handle:
                    kept = json.load(handle)
                if value is None:
                    del kept[key]
                else:
                    kept[key] = value
                write(path, json.dumps(kept))
                status, lines, _ = self.place(out="f" + key + str(value).strip())
                self.assertEqual(status, 1, lines)
                self.assertTrue(any(f"states no {key}" in line and "C0004.json" in line for line in lines), lines)
                asm_file(self.kept, "C0004", [("1", 0.0, 0.0), ("2", 2.54, 0.0)])

    def test_a_position_export_that_disagrees_with_the_board_is_refused(self):
        # SOL-HW-CONTROLLER-BOARDS-ORDERED.C2: The file carries each part's corrected rotation and the position of the assembler's footprint origin
        positions_csv(self.positions, [["U1", "x", "p", "31", "-20", "90", "top"]])
        status, lines, _ = self.place()
        self.assertEqual(status, 1, lines)
        self.assertTrue(any("the position export and the board disagree on U1" in line for line in lines), lines)

    def test_the_footprints_are_fetched_once_each_a_pace_apart_and_not_into_the_repository(self):
        # SOL-HW-CONTROLLER-BOARDS-ORDERED.C2: The assembler's footprints are fetched once for each catalogue number, at a pace its service accepts, and kept outside the repository
        service = {"result": {"packageDetail": {"dataStr": {"head": {"x": 4000, "y": 3000}, "shape": [
            "PAD~RECT~4002.966~3000~3~3~1~~2~0~", "PAD~RECT~3997.034~3000~3~3~1~~1~0~", "TRACK~1~3~~4000 3000"]}}}}
        calls, naps = [], []
        out = os.path.join(self.work, "fetched")
        status, lines = 0, io.StringIO()
        status = production_files.fetch_footprints(self.board, out, self.record, 1.0, "text", lines,
                                                   lambda number: calls.append(number) or json.dumps(service), naps.append)
        self.assertEqual(status, 0, lines.getvalue())
        self.assertEqual(calls, ["C0001", "C0002", "C0003", "C0004"], "M1 has no number and X1's owner fits it, yet C0002 is R1's")
        self.assertEqual(naps, [1.0, 1.0, 1.0], "one pause between two requests")
        with open(os.path.join(out, "C0002.json"), encoding="utf-8") as handle:
            kept = json.load(handle)
        self.assertEqual([(p["number"], p["x"], p["y"]) for p in kept["pads"]], [("2", 0.7534, 0.0), ("1", -0.7534, 0.0)])
        calls.clear()
        again = io.StringIO()
        self.assertEqual(production_files.fetch_footprints(self.board, out, self.record, 1.0, "text", again,
                                                           lambda number: calls.append(number) or "", naps.append), 0)
        self.assertEqual(calls, [], "a number already kept is not fetched again")
        inside = io.StringIO()
        self.assertEqual(production_files.fetch_footprints(self.board, os.path.join(production_files.TOOLS, "kept"), self.record, 0,
                                                           "text", inside, lambda n: "", lambda s: None), 1)
        self.assertIn("is inside the repository", inside.getvalue())
        self.assertFalse(os.path.exists(os.path.join(production_files.TOOLS, "kept")))

    def test_the_fetch_report_is_json_on_request_and_the_fitting_record_is_required(self):
        # SOL-HW-CONTROLLER-BOARDS-ORDERED.C2: The assembler's footprints are fetched once for each catalogue number; only the assembler-fitted parts' numbers are fetched
        service = {"result": {"packageDetail": {"dataStr": {"head": {"x": 4000, "y": 3000}, "shape": ["PAD~RECT~4002.966~3000~3~3~1~~2~0~"]}}}}
        out = os.path.join(self.work, "jsonfetch")
        stream = io.StringIO()
        status = production_files.fetch_footprints(self.board, out, self.record, 0, "json", stream,
                                                   lambda number: json.dumps(service), lambda seconds: None)
        document = json.loads(stream.getvalue())
        self.assertEqual((status, document["result"], document["fetched"], document["kept"]),
                         (0, "WRITTEN", ["C0001", "C0002", "C0003", "C0004"], []))
        again = io.StringIO()
        production_files.fetch_footprints(self.board, out, self.record, 0, "json", again, lambda number: "", lambda seconds: None)
        self.assertEqual(json.loads(again.getvalue())["kept"], ["C0001", "C0002", "C0003", "C0004"])
        refused = io.StringIO()
        self.assertEqual(production_files.fetch_footprints(self.board, os.path.join(self.work, "bad"), self.record, 0, "json", refused,
                                                           lambda number: "not json", lambda seconds: None), 1)
        document = json.loads(refused.getvalue())
        self.assertEqual(document["result"], "REFUSED")
        self.assertTrue(any("C0001" in why for why in document["refused"]), document)
        with self.assertRaises(SystemExit) as stopped:
            run(["fetch-footprints", "--board", self.board, "--out", os.path.join(self.work, "nofit")])
        self.assertNotEqual(stopped.exception.code, 0)
        self.assertFalse(os.path.exists(os.path.join(self.work, "nofit")))

    def test_an_answer_with_no_pad_or_unreadable_is_refused_naming_the_number(self):
        # SOL-HW-CONTROLLER-BOARDS-ORDERED.C2: The assembler's footprints are fetched once for each catalogue number
        for text in ("not json", json.dumps({"result": {}}),
                     json.dumps({"result": {"packageDetail": {"dataStr": {"head": {"x": 0, "y": 0}, "shape": ["TRACK~1"]}}}})):
            with self.subTest(text=text[:20]):
                with self.assertRaises(production_files.Refused) as caught:
                    production_files.footprint_from_service(text, "C9")
                self.assertIn("C9", str(caught.exception))


class TheTwoSets(Synthetic):
    """SOL-HW-CONTROLLER-BOARDS-ORDERED.C7: Each part carries a recorded choice of who fits it"""

    def test_the_two_sets_differ_by_exactly_the_through_hole_parts_and_an_owner_fitted_part_is_in_neither(self):
        # SOL-HW-CONTROLLER-BOARDS-ORDERED.C7: A test over a synthetic design holds that the two sets differ by exactly the through-hole parts and that a part marked owner-fitted is in neither
        status, lines, folder = self.place()
        self.assertEqual(status, 0, lines)
        full = [r[0] for r in read_rows(os.path.join(folder, "placement-full.csv"))[1:]]
        smd = [r[0] for r in read_rows(os.path.join(folder, "placement-smd.csv"))[1:]]
        self.assertEqual(full, ["U1", "R1", "C1", "J1"])
        self.assertEqual(sorted(set(full) - set(smd)), ["J1"])
        self.assertEqual(set(smd) - set(full), set())
        for reference in ("X1", "M1"):
            self.assertNotIn(reference, full + smd)
        self.assertIn("OMITTED | X1 | fitted by the owner", lines)
        self.assertIn("OMITTED | M1 | not a part to be fitted", lines)

    def test_a_part_the_assembler_lists_as_unavailable_is_in_neither_set(self):
        # SOL-HW-CONTROLLER-BOARDS-ORDERED.C7: A part with no catalogue number, or one the assembler lists as unavailable for assembly, is in neither set
        gone = write(os.path.join(self.work, "unavailable.yaml"),
                     "source: the assembler's catalogue\nread_on: 2030-01-02\nunavailable: [C0003]\n")
        status, lines, folder = self.place("--unavailable", gone)
        self.assertEqual(status, 0, lines)
        self.assertNotIn("C1", [r[0] for r in read_rows(os.path.join(folder, "placement-full.csv"))[1:]])
        self.assertIn("OMITTED | C1 | C0003 is unavailable for assembly", lines)

    def test_an_unreadable_availability_record_is_refused(self):
        # SOL-HW-CONTROLLER-BOARDS-ORDERED.C7: A part with no catalogue number, or one the assembler lists as unavailable for assembly, is in neither set
        bad = write(os.path.join(self.work, "unavailable.yaml"), "unavailable: [C0003]\n")
        status, lines, _ = self.place("--unavailable", bad)
        self.assertEqual(status, 1, lines)
        self.assertTrue(any("lacks unavailable" in line for line in lines), lines)

    def test_a_part_with_no_recorded_choice_is_refused_naming_it(self):
        # SOL-HW-CONTROLLER-BOARDS-ORDERED.C7: The parts specification records for every part whether the assembler or the owner fits it
        record = write(os.path.join(self.work, "no-choice.yaml"), record_text([
            ("U1", "C0001", {}), ("R1", "C0002", {"fitted_by": "somebody"}), ("C1", "C0003", {"fitted_by": "assembler"}),
            ("J1", "C0004", {"fitted_by": "assembler"}), ("X1", "C0002", {"fitted_by": "owner"}), ("M1", "none", {"fitted_by": "owner"})]))
        status, lines, folder = self.place(record=record)
        self.assertEqual(status, 1, lines)
        self.assertTrue(any("gives U1 no fitted_by" in line for line in lines), lines)
        self.assertTrue(any("gives R1 no fitted_by of assembler or owner or none, only 'somebody'" in line for line in lines), lines)
        self.assertFalse(os.path.exists(folder))

    def test_a_position_the_record_lacks_and_a_number_that_differs_are_refused(self):
        # SOL-HW-CONTROLLER-BOARDS-ORDERED.C7: The parts specification records for every part whether the assembler or the owner fits it
        record = write(os.path.join(self.work, "short.yaml"), record_text([
            ("U1", "C9999", {"fitted_by": "assembler"}), ("R1", "C0002", {"fitted_by": "assembler"}),
            ("C1", "C0003", {"fitted_by": "assembler"}), ("J1", "C0004", {"fitted_by": "assembler"}), ("X1", "C0002", {"fitted_by": "owner"})]))
        status, lines, _ = self.place(record=record)
        self.assertEqual(status, 1, lines)
        self.assertTrue(any("U1's catalogue number is C0001 on the board and C9999 in the parts specification record" in line
                            for line in lines), lines)
        self.assertTrue(any("lists no position for M1" in line for line in lines), lines)

    def test_a_part_for_the_assembler_with_no_placement_row_and_one_with_no_mounting_are_refused(self):
        # SOL-HW-CONTROLLER-BOARDS-ORDERED.C7: From the one design the files are written as two sets, each corrected as the placement file's criterion requires
        write(self.board, board_text([
            footprint("U1", "top", 30, 20, 90, "C0001", BOARD_THREE, attr="smd exclude_from_pos_files"),
            footprint("R1", "top", 10, 5, 0, "C0002", [("1", -0.75, 0), ("2", 0.75, 0)], attr=""),
            footprint("C1", "bottom", 12, 8, 180, "C0003", [("1", 0.75, 0), ("2", -0.75, 0)]),
            footprint("J1", "top", 40, 40, 0, "C0004", [("1", 0, 0), ("2", 2.54, 0)], attr="through_hole"),
            footprint("X1", "top", 50, 50, 0, "C0002", [("1", -0.75, 0), ("2", 0.75, 0)]),
            footprint("M1", "top", 60, 60, 0, "none", [("1", 0, 0)])]))
        status, lines, _ = self.place()
        self.assertEqual(status, 1, lines)
        self.assertTrue(any("U1 is marked for the assembler but its footprint is excluded" in line for line in lines), lines)
        self.assertTrue(any("R1 is marked for the assembler but its footprint is neither" in line for line in lines), lines)

    def test_a_part_marked_do_not_populate_is_in_neither_set_and_the_report_is_json_on_request(self):
        # SOL-HW-CONTROLLER-BOARDS-ORDERED.C7: A part with no catalogue number, or one the assembler lists as unavailable for assembly, is in neither set
        record = write(os.path.join(self.work, "dnp.yaml"), record_text([
            ("U1", "C0001", {"fitted_by": "assembler"}), ("R1", "C0002", {"fitted": "'no'"}), ("C1", "C0003", {"fitted_by": "assembler"}),
            ("J1", "C0004", {"fitted_by": "assembler"}), ("X1", "C0002", {"fitted_by": "owner"}), ("M1", "none", {"fitted_by": "owner"})]))
        status, lines, folder = self.place(record=record, fmt="json")
        self.assertEqual(status, 0, lines)
        document = json.loads("\n".join(lines))
        self.assertEqual(document["result"], "WRITTEN")
        self.assertEqual([row[0] for row in document["sets"]["full"]], ["U1", "C1", "J1"])
        self.assertEqual([row[0] for row in document["sets"]["smd"]], ["U1", "C1"])
        self.assertIn({"reference": "R1", "reason": "not fitted (do not populate)"}, document["omitted"])

    def test_a_refusal_is_one_json_document_and_an_existing_folder_is_not_written_into(self):
        # SOL-HW-CONTROLLER-BOARDS-ORDERED.C7: Which set is uploaded is decided at order time
        asm_file(self.kept, "C0001", [("1", 0, 0)])
        status, lines, folder = self.place(fmt="json")
        document = json.loads("\n".join(lines))
        self.assertEqual((status, document["result"]), (1, "REFUSED"))
        self.assertTrue(any("U1's pads cannot all be matched" in why for why in document["refused"]), document)
        os.makedirs(folder)
        write(os.path.join(folder, "left"), "x")
        status, lines, _ = self.place()
        self.assertEqual(status, 1)
        self.assertTrue(any("already holds files" in line for line in lines), lines)

    def test_the_record_accepts_the_two_fitters_and_no_other_value(self):
        # SOL-HW-CONTROLLER-BOARDS-ORDERED.C7: The parts specification records for every part whether the assembler or the owner fits it
        self.assertEqual(board_check.FITTERS, ("assembler", "owner"))
        self.assertEqual(board_check.FITTED_BY_VALUES, ("assembler", "owner", "none"))
        self.assertIn("fitted_by", board_check.POSITION_KEYS)

    def test_a_position_that_is_not_a_part_is_in_neither_placement_set_nor_parts_list_whether_or_not_drawn(self):
        # SOL-HW-CONTROLLER-BOARDS-ORDERED.C7: A part with no catalogue number, or one the assembler lists as unavailable for assembly, is in neither set
        record = write(os.path.join(self.work, "nopart.yaml"), record_text([
            ("U1", "C0001", {"fitted_by": "assembler"}), ("R1", "C0002", {"fitted_by": "assembler"}), ("C1", "C0003", {"fitted_by": "assembler"}),
            ("J1", "C0004", {"fitted_by": "assembler"}), ("X1", "C0002", {"fitted_by": "owner"}), ("M1", "none", {"fitted_by": "none"})]))
        status, lines, _ = self.place(record=record, fmt="json")
        self.assertEqual(status, 0, lines)
        document = json.loads("\n".join(lines))
        self.assertNotIn("M1", [row[0] for row in document["sets"]["full"]])
        self.assertIn({"reference": "M1", "reason": "not a part to be fitted"}, document["omitted"])
        self.assertEqual(production_files.classify("M1", production_files.board_parts(self.board)["M1"], {"fitted_by": "none", "lcsc": "none"}, set())[0], "none")

    def test_a_numbered_part_marked_none_or_an_unnumbered_position_marked_assembler_is_refused_naming_it_in_text_and_json(self):
        # SOL-HW-CONTROLLER-BOARDS-ORDERED.C7: A part with no catalogue number, or one the assembler lists as unavailable for assembly, is in neither set
        cases = [("R1", "C0002", "none", "R1 fitted_by is none but its catalogue number is C0002"),
                 ("M1", "none", "assembler", "M1 fitted_by is assembler but it has no catalogue number")]
        base = {"U1": "C0001", "R1": "C0002", "C1": "C0003", "J1": "C0004", "X1": "C0002", "M1": "none"}
        for reference, number, who, said in cases:
            rows = [(ref, num, {"fitted_by": who if ref == reference else ("none" if num == "none" else "assembler")}) for ref, num in base.items()]
            record = write(os.path.join(self.work, f"bad-{reference}.yaml"), record_text(rows))
            for fmt in ("text", "json"):
                with self.subTest(reference=reference, fmt=fmt):
                    status, lines, _ = self.place(record=record, out=f"o-{reference}-{fmt}", fmt=fmt)
                    self.assertEqual(status, 1, lines)
                    self.assertTrue(any(said in line for line in lines), lines)
            with self.assertRaises(production_files.Refused):
                production_files.classify(reference, production_files.board_parts(self.board)[reference],
                                          {"fitted_by": who, "lcsc": number}, set())


def schematic_text(symbols):
    out = ['(kicad_sch (lib_symbols (symbol "Lib:R" (property "Value" "lib")))']
    for reference, value, lcsc, extra in symbols:
        out.append(f'(symbol (lib_id "Lib:R") {extra} (property "Reference" "{reference}") (property "Value" "{value}") '
                   f'(property "Footprint" "Lib:F") (property "LCSC" "{lcsc}") '
                   f'(instances (project "b" (path "/1" (reference "{reference}") (unit 1)))))')
    return "\n".join(out) + ")\n"


def catalogue_text(entries):
    """A catalogue extract holding `entries`, each (number, comment or None for none stated)."""
    out = ["entries:"]
    for number, comment in entries:
        out.append(f"- lcsc: {number}")
        if comment is not None:
            out.append(f"  comment: {json.dumps(comment)}")
        out += ["  library_class: basic", "  stock: 5", "  unit_price: 0.01"]
    return "\n".join(out) + "\n"


COMMENTS = [("C0001", "triac"), ("C0002", "resistor 10 kohm"), ("C0003", "capacitor 100 nF"), ("C0004", "pin header")]


class TheParts(Synthetic):
    """SOL-HW-CONTROLLER-BOARDS-ORDERED.C6: Each board's parts list gives one comment for each catalogue number"""

    def setUp(self):
        super().setUp()
        self.schematic = os.path.join(self.work, "b.kicad_sch")
        self.catalogue = os.path.join(self.work, "catalogue-extract.yaml")
        write(self.catalogue, catalogue_text(COMMENTS))

    def list(self, symbols, fmt="text", out="list", bare=False):
        write(self.schematic, schematic_text(symbols))
        folder = os.path.join(self.work, out)
        more = [] if bare else ["--unavailable", self.none_unavailable()]
        return run(["parts-list", "--schematic", self.schematic, "--board", self.board, "--fitting", self.record,
                    "--catalogue", self.catalogue, "--out", folder, "--format", fmt, *more]) + (folder,)

    def fitted_record(self):
        write(self.record, record_text([
            ("U1", "C0001", {"fitted_by": "assembler"}), ("R1", "C0002", {"fitted_by": "assembler"}), ("C1", "C0003", {"fitted_by": "assembler"}),
            ("J1", "C0004", {"fitted_by": "assembler"}), ("X1", "C0002", {"fitted_by": "assembler"}), ("M1", "none", {"fitted_by": "owner"})]))

    def clean(self):
        return [("U1", "tri", "C0001", ""), ("R1", "10k", "C0002", ""), ("C1", "100n", "C0003", ""), ("J1", "hdr", "C0004", ""),
                ("X1", "10k", "C0002", ""), ("M1", "shield", "none", "")]

    def refused(self, fmt):
        status, lines, folder = self.list(self.clean(), fmt=fmt)
        self.assertEqual(status, 1, lines)
        self.assertFalse(os.path.exists(folder))
        if fmt == "json":
            document = json.loads("\n".join(lines))
            self.assertEqual(document["result"], "REFUSED")
            return document["refused"]
        self.assertEqual(lines[-1], "RESULT | REFUSED | nothing was written")
        return lines

    def test_a_number_the_extract_gives_no_entry_for_is_refused_naming_it_in_text_and_json(self):
        # SOL-HW-CONTROLLER-BOARDS-ORDERED.C6: A test over a synthetic design holds that each of a missing entry, a blank comment and a duplicated entry fails the export
        self.fitted_record()
        write(self.catalogue, catalogue_text([c for c in COMMENTS if c[0] != "C0003"]))
        for fmt in ("text", "json"):
            self.assertTrue(any("no entry for the catalogue number C0003" in line for line in self.refused(fmt)), fmt)

    def test_a_number_whose_extract_comment_is_missing_or_blank_is_refused_naming_it_in_text_and_json(self):
        # SOL-HW-CONTROLLER-BOARDS-ORDERED.C6: A test over a synthetic design holds that each of a missing entry, a blank comment and a duplicated entry fails the export
        self.fitted_record()
        for comment in (None, "", "   "):
            write(self.catalogue, catalogue_text([(n, comment if n == "C0002" else c) for n, c in COMMENTS]))
            for fmt in ("text", "json"):
                found = self.refused(fmt)
                self.assertTrue(any("no comment for the catalogue number C0002" in line for line in found), (comment, fmt, found))
                self.assertFalse(any("C0001" in line for line in found), found)

    def test_a_comma_joined_multi_line_or_non_text_comment_is_refused_by_number_in_text_and_json(self):
        # SOL-HW-CONTROLLER-BOARDS-ORDERED.C6: The parts list takes each row's comment from the one entry the board's catalogue record holds for that row's catalogue number, and the export fails, naming the catalogue number, when a number has no entry, an entry with no comment, or more than one entry
        self.fitted_record()
        for comment in ("100 nF, 100n", "two\nlines"):
            write(self.catalogue, catalogue_text([(n, comment if n == "C0002" else c) for n, c in COMMENTS]))
            for fmt in ("text", "json"):
                found = self.refused(fmt)
                self.assertTrue(any("C0002" in line and "one line of plain text" in line for line in found), (comment, fmt, found))
        write(self.catalogue, catalogue_text(COMMENTS).replace('comment: "resistor 10 kohm"', "comment: 12"))
        for fmt in ("text", "json"):
            self.assertTrue(any("C0002" in line and "one line of plain text" in line for line in self.refused(fmt)), fmt)

    def test_an_extract_entry_with_no_catalogue_number_is_refused_by_its_place_in_the_file_in_text_and_json(self):
        # SOL-HW-CONTROLLER-BOARDS-ORDERED.C6: The parts list takes each row's comment from the one entry the board's catalogue record holds for that row's catalogue number, and the export fails, naming the catalogue number, when a number has no entry, an entry with no comment, or more than one entry
        self.fitted_record()
        good = catalogue_text(COMMENTS)
        for bad in ("- comment: no number here\n  library_class: basic\n", "- lcsc: \"  \"\n  comment: blank\n", "- lcsc: 12\n  comment: numeric\n"):
            write(self.catalogue, good + bad + bad)
            for fmt in ("text", "json"):
                found = self.refused(fmt)
                self.assertTrue(any("entry 4 (counting from 0) has no lcsc number" in line for line in found), (bad, fmt, found))
                self.assertFalse(any("more than once" in line for line in found), found)

    def test_a_number_the_extract_holds_twice_is_refused_naming_it_in_text_and_json(self):
        # SOL-HW-CONTROLLER-BOARDS-ORDERED.C6: A test over a synthetic design holds that each of a missing entry, a blank comment and a duplicated entry fails the export
        self.fitted_record()
        write(self.catalogue, catalogue_text(COMMENTS + [("C0004", "another comment")]))
        for fmt in ("text", "json"):
            self.assertTrue(any("holds the catalogue number C0004 more than once" in line for line in self.refused(fmt)), fmt)

    def test_a_schematic_spelling_of_the_value_no_longer_matters_the_extract_comment_is_the_row_comment(self):
        # SOL-HW-CONTROLLER-BOARDS-ORDERED.C6: A test over a synthetic design holds that differing value text under one number does not change the row's comment
        symbols = self.clean()
        symbols[4] = ("X1", "TEMP_C", "C0002", "")
        self.fitted_record()
        status, lines, folder = self.list(symbols)
        self.assertEqual(status, 0, lines)
        by_number = {row[3]: row for row in read_rows(os.path.join(folder, "parts-list-full.csv"))[1:]}
        self.assertEqual(by_number["C0002"], ["resistor 10 kohm", "R1, X1", "Lib:F", "C0002"])

    def test_an_extract_that_cannot_be_read_is_refused(self):
        # SOL-HW-CONTROLLER-BOARDS-ORDERED.C6: The parts list takes each row's comment from the one entry the board's catalogue record holds for that row's catalogue number, and the export fails, naming the catalogue number, when a number has no entry, an entry with no comment, or more than one entry
        self.fitted_record()
        write(self.catalogue, "read_on: 2030-01-01\n")
        status, lines, _ = self.list(self.clean())
        self.assertEqual(status, 1, lines)
        self.assertTrue(any("lacks entries" in line for line in lines), lines)

    def test_every_row_of_a_clean_export_carries_one_comment_and_no_comma_joined_values(self):
        # SOL-HW-CONTROLLER-BOARDS-ORDERED.C6: A test over a synthetic schematic holds that every row of a clean export carries one comment and no comma-joined values
        write(self.record, record_text([
            ("U1", "C0001", {"fitted_by": "assembler"}), ("R1", "C0002", {"fitted_by": "assembler"}), ("C1", "C0003", {"fitted_by": "assembler"}),
            ("J1", "C0004", {"fitted_by": "assembler"}), ("X1", "C0002", {"fitted_by": "assembler"}), ("M1", "none", {"fitted_by": "owner"})]))
        status, lines, folder = self.list(self.clean())
        self.assertEqual(status, 0, lines)
        full = read_rows(os.path.join(folder, "parts-list-full.csv"))
        self.assertEqual(full[0], ["Comment", "Designator", "Footprint", "LCSC"])
        numbers = [row[3] for row in full[1:]]
        self.assertEqual(len(numbers), len(set(numbers)), "one row for each catalogue number")
        by_number = {row[3]: row for row in full[1:]}
        self.assertEqual(by_number["C0002"], ["resistor 10 kohm", "R1, X1", "Lib:F", "C0002"])
        for row in full[1:]:
            self.assertNotIn(",", row[0], row)
        self.assertNotIn("none", numbers)

    def test_the_two_parts_lists_follow_the_two_placement_sets(self):
        # SOL-HW-CONTROLLER-BOARDS-ORDERED.C7: one holding every part the assembler's catalogue states it can place, through-hole parts included, and one holding only the surface-mount parts, with every through-hole part in neither the parts list nor the placement file
        status, lines, folder = self.list(self.clean(), fmt="json")
        self.assertEqual(status, 0, lines)
        document = json.loads("\n".join(lines))
        designators = lambda rows: sorted(ref for row in rows for ref in row[1].split(", "))  # noqa: E731
        self.assertEqual(designators(document["sets"]["full"]), ["C1", "J1", "R1", "U1"])
        self.assertEqual(designators(document["sets"]["smd"]), ["C1", "R1", "U1"])
        self.assertIn({"reference": "X1", "reason": "fitted by the owner"}, document["omitted"])
        self.assertEqual(read_rows(os.path.join(folder, "parts-list-smd.csv"))[0], ["Comment", "Designator", "Footprint", "LCSC"])

    def test_a_part_with_no_catalogue_number_field_a_differing_one_and_a_part_missing_from_the_board_are_refused(self):
        # SOL-HW-CONTROLLER-BOARDS-ORDERED.C6: The design carries one spelling of the value for each number
        symbols = self.clean()
        symbols[1] = ("R1", "10k", "", "")
        symbols[2] = ("C1", "100n", "C7777", "")
        symbols.append(("Q9", "q", "C0001", ""))
        status, lines, _ = self.list(symbols)
        self.assertEqual(status, 1, lines)
        self.assertTrue(any("R1 carries no LCSC field in the schematic" in line for line in lines), lines)
        self.assertTrue(any("C1's catalogue number is C7777 in the schematic and C0003 in the parts specification record" in line
                            for line in lines), lines)
        self.assertTrue(any("Q9 is not on the board" in line for line in lines), lines)

    def test_a_part_drawn_not_to_be_fitted_or_left_out_of_the_bill_is_not_listed(self):
        # SOL-HW-CONTROLLER-BOARDS-ORDERED.C6: The parts list takes each row's comment from the one entry the board's catalogue record holds for that row's catalogue number, and the export fails, naming the catalogue number, when a number has no entry, an entry with no comment, or more than one entry
        symbols = self.clean()
        symbols[1] = ("R1", "wrong spelling", "C0002", "(dnp yes)")
        symbols.append(("TP1", "tp", "C0002", "(in_bom no)"))
        symbols.append(("#PWR01", "gnd", "", ""))
        write(self.record, record_text([
            ("U1", "C0001", {"fitted_by": "assembler"}), ("R1", "C0002", {"fitted": "'no'"}), ("C1", "C0003", {"fitted_by": "assembler"}),
            ("J1", "C0004", {"fitted_by": "assembler"}), ("X1", "C0002", {"fitted_by": "owner"}), ("M1", "none", {"fitted_by": "owner"})]))
        status, lines, _ = self.list(symbols)
        self.assertEqual(status, 0, lines)

    def test_a_sheet_below_the_root_is_read_and_an_unreadable_file_is_refused(self):
        # SOL-HW-CONTROLLER-BOARDS-ORDERED.C6: The parts list takes each row's comment from the one entry the board's catalogue record holds for that row's catalogue number, and the export fails, naming the catalogue number, when a number has no entry, an entry with no comment, or more than one entry
        write(self.schematic, '(kicad_sch (sheet (property "Sheetname" "s") (property "Sheetfile" "sub.kicad_sch")))\n')
        write(os.path.join(self.work, "sub.kicad_sch"), schematic_text([("R1", "10k", "C0002", "")]))
        self.assertEqual(set(production_files.schematic_parts(self.schematic)), {"R1"})
        os.remove(os.path.join(self.work, "sub.kicad_sch"))
        with self.assertRaises(production_files.Refused):
            production_files.schematic_parts(self.schematic)

    def test_parts_list_without_the_availability_record_is_refused_naming_the_flag_in_text_and_json(self):
        # SOL-HW-CONTROLLER-BOARDS-ORDERED.C7: A part with no catalogue number, or one the assembler lists as unavailable for assembly, is in neither set
        self.fitted_record()
        for fmt in ("text", "json"):
            status, lines, folder = self.list(self.clean(), fmt=fmt, out="bare-" + fmt, bare=True)
            self.assertEqual(status, 1, lines)
            self.assertFalse(os.path.exists(folder))
            self.assertIn("--unavailable is required", "\n".join(lines), fmt)


class TheMethodNamesTheCommands(unittest.TestCase):
    def test_the_ordering_step_names_the_three_commands_as_they_are_run(self):
        # SOL-HW-CONTROLLER-BOARDS-ORDERED.C2: The placement step takes the assembler's published footprint for each placed part's catalogue number
        method = os.path.join(production_files.TOOLS, os.pardir, os.pardir, "docs", "board-design-method.md")
        with open(method, encoding="utf-8") as handle:
            text = handle.read()
        for command in ("production_files.py fetch-footprints --board", "production_files.py placement --positions",
                        "production_files.py parts-list --schematic"):
            self.assertIn(command, text)


if __name__ == "__main__":
    unittest.main()


class TheAvailabilityRecordIsRequired(Synthetic):
    """SOL-HW-CONTROLLER-BOARDS-ORDERED.C7: A part with no catalogue number, or one the assembler lists as unavailable for assembly, is in neither set"""

    def test_placement_without_the_availability_record_is_refused_naming_the_flag_in_text_and_json(self):
        # SOL-HW-CONTROLLER-BOARDS-ORDERED.C7: A part with no catalogue number, or one the assembler lists as unavailable for assembly, is in neither set
        for fmt in ("text", "json"):
            status, lines, folder = self.place("--bare", out="bare-" + fmt, fmt=fmt)
            self.assertEqual(status, 1, lines)
            self.assertFalse(os.path.exists(folder))
            self.assertIn("--unavailable is required", "\n".join(lines), fmt)
            if fmt == "json":
                self.assertEqual(json.loads("\n".join(lines))["result"], "REFUSED")

    def test_a_tolerance_other_than_the_default_is_noted_in_text_and_carried_in_json(self):
        # SOL-HW-CONTROLLER-BOARDS-ORDERED.C2: A part whose pads cannot all be matched is refused by name
        status, lines, _ = self.place("--tolerance", "0.2", out="wide")
        self.assertEqual(status, 0, lines)
        self.assertTrue(any(line.startswith("NOTE | the pad-match tolerance is 0.2 mm") for line in lines), lines)
        status, lines, _ = self.place("--tolerance", "0.2", out="widej", fmt="json")
        self.assertEqual(json.loads("\n".join(lines))["tolerance"], 0.2)
        status, lines, _ = self.place(out="default")
        self.assertFalse(any(line.startswith("NOTE") for line in lines), lines)
