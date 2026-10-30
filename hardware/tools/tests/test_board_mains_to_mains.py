#!/usr/bin/env python3
"""The pre-order check's reading of the signed mains-to-mains spacing, driven on synthetic fixtures with no KiCad involved.

What is under test here is what the check decides for itself: whether a record
carries a whole mains_to_mains mapping, whether each of its figures stands at or
above the floor the record's own table rows give, whether the MAINS_ENTRY
declaration agrees with the layout's classes, and the rules the check appends to
hold a layout to the figures. What KiCad then finds is driven against the real
tool in test_board_check_kicad_mains_to_mains.py.
"""

from __future__ import annotations

import copy
import datetime
import os
import re
import sys
import tempfile
import unittest

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)

import board_check  # noqa: E402

REPO = os.path.dirname(os.path.dirname(TOOLS))
TODAY = datetime.date(2026, 10, 12)
RECORD = "hardware/m/separation-basis.yaml"
DESIGN = board_check.Design("hardware/m/board/board.kicad_pro")


def row(inputs: dict, **figure) -> dict:
    return {"citation": {"document": "synthetic table", "edition": "none", "locator": "row"}, "inputs": inputs, "figure": figure}


def basis(**changes) -> dict:
    """A mains-present record whose rows give exactly its signed figures, with `changes` set over it and a key set to None left out."""
    record = {
        "standard": "synthetic", "supply": "230 V", "working_voltage": "250 V rms", "pollution_degree": 2, "material_group": "IIIb",
        "environment": "indoors", "overvoltage_category": 2, "altitude_m": 2000, "barriers": [], "barrier_types": [],
        "mains_to_low_voltage": {"clearance_mm": 3.0, "creepage_mm": 4.0},
        "mains_to_mains": {"clearance_mm": 1.5, "terminal_clearance_mm": 2.0, "creepage_mm": 2.5,
                           "creepage_ahead_of_fuse_mm": 2.5, "entry_fuse": "F1", "held_at_reinforced": []},
        "table_rows": [row({"working_voltage_v": 250, "overvoltage_category": 2}, clearance_mm=3.0),
                       row({"working_voltage_v": 250, "pollution_degree": 2, "material_group": "IIIb"}, creepage_mm=4.0),
                       row({"working_voltage_v": 250, "insulation": "basic"}, clearance_mm=1.5, creepage_mm=2.5),
                       row({"working_voltage_v": 250, "insulation": "basic", "location": "terminal"}, clearance_mm=2.0)],
        "accepted_by": "maintainer", "accepted_on": "2026-10-01", "synthetic": True}
    record.update(changes)
    return {key: value for key, value in record.items() if value is not None}


def mapping(**changes) -> dict:
    """The mains_to_mains mapping of basis(), with `changes` set over it and a key set to None left out."""
    held = copy.deepcopy(basis()["mains_to_mains"])
    held.update(changes)
    return {key: value for key, value in held.items() if value is not None}


def read(data: dict):
    """What read_record finds of `data` written as a record in a temporary folder."""
    import yaml
    with tempfile.TemporaryDirectory() as folder:
        os.makedirs(os.path.join(folder, os.path.dirname(RECORD)))
        with open(os.path.join(folder, RECORD), "w", encoding="utf-8") as handle:
            yaml.safe_dump(data, handle)
        return board_check.read_record(yaml, folder, DESIGN, RECORD, True, TODAY)


def floor(data: dict):
    """The violations of a record's mains_to_mains figures against the floor its rows give, and the signed figures it was read as."""
    signed, problems = read(data)
    assert problems == [], [problem.line() for problem in problems]
    return [found for found in board_check.separation_floor(DESIGN, RECORD, signed) if "mains_to_mains" in found.location]


def only(found, key: str):
    return [v for v in found if v.location.endswith(f"mains_to_mains.{key}")]


class TheMappingIsRead(unittest.TestCase):
    def assertFails(self, data: dict, location_end: str, words: str):
        signed, problems = read(data)
        self.assertIsNone(signed)
        self.assertTrue(any(v.rule == "separation_basis" and location_end in v.location and words in v.message
                            for v in problems), [problem.line() for problem in problems])

    def test_a_complete_mapping_is_read_and_its_figures_kept(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-TO-MAINS-SPACING.C1: On a design that declares MAINS present, a record with no mains_to_mains mapping, or one lacking clearance_mm, terminal_clearance_mm, creepage_mm, creepage_ahead_of_fuse_mm or entry_fuse, fails separation_basis naming the key. A figure that is not a positive number, a creepage_mm below creepage_ahead_of_fuse_mm with no downstream_basis, a held_at_reinforced that is not a list of pairs of net names, a terminal_clearance_mm below clearance_mm, a creepage_ahead_of_fuse_mm below creepage_mm, an entry_fuse naming no reference of the layout, and a key inside the mapping that the basis decision does not name each fail it likewise. A design that declares MAINS none is out of scope and passes without the mapping.
        signed, problems = read(basis())
        self.assertEqual(problems, [])
        self.assertEqual((signed[0], signed[1]), (3.0, 4.0))
        self.assertEqual(signed.mains_to_mains, mapping())

    def test_a_record_with_no_mains_to_mains_mapping_fails_naming_it(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-TO-MAINS-SPACING.C1: On a design that declares MAINS present, a record with no mains_to_mains mapping, or one lacking clearance_mm, terminal_clearance_mm, creepage_mm, creepage_ahead_of_fuse_mm or entry_fuse, fails separation_basis naming the key. A figure that is not a positive number, a creepage_mm below creepage_ahead_of_fuse_mm with no downstream_basis, a held_at_reinforced that is not a list of pairs of net names, a terminal_clearance_mm below clearance_mm, a creepage_ahead_of_fuse_mm below creepage_mm, an entry_fuse naming no reference of the layout, and a key inside the mapping that the basis decision does not name each fail it likewise. A design that declares MAINS none is out of scope and passes without the mapping.
        self.assertFails(basis(mains_to_mains=None), "mains_to_mains", "lacks mains_to_mains")
        self.assertFails(basis(mains_to_mains="none"), "mains_to_mains", "is not a mapping")
        self.assertFails(basis(mains_to_mains={}), "mains_to_mains.clearance_mm", "lacks clearance_mm")

    def test_a_mapping_lacking_a_key_fails_naming_the_key(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-TO-MAINS-SPACING.C1: On a design that declares MAINS present, a record with no mains_to_mains mapping, or one lacking clearance_mm, terminal_clearance_mm, creepage_mm, creepage_ahead_of_fuse_mm or entry_fuse, fails separation_basis naming the key. A figure that is not a positive number, a creepage_mm below creepage_ahead_of_fuse_mm with no downstream_basis, a held_at_reinforced that is not a list of pairs of net names, a terminal_clearance_mm below clearance_mm, a creepage_ahead_of_fuse_mm below creepage_mm, an entry_fuse naming no reference of the layout, and a key inside the mapping that the basis decision does not name each fail it likewise. A design that declares MAINS none is out of scope and passes without the mapping.
        for key in ("clearance_mm", "terminal_clearance_mm", "creepage_mm", "creepage_ahead_of_fuse_mm", "entry_fuse",
                    "held_at_reinforced"):
            with self.subTest(key=key):
                self.assertFails(basis(mains_to_mains=mapping(**{key: None})), f"mains_to_mains.{key}", f"lacks {key}")

    def test_a_figure_that_is_not_a_positive_number_fails_naming_it(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-TO-MAINS-SPACING.C1: On a design that declares MAINS present, a record with no mains_to_mains mapping, or one lacking clearance_mm, terminal_clearance_mm, creepage_mm, creepage_ahead_of_fuse_mm or entry_fuse, fails separation_basis naming the key. A figure that is not a positive number, a creepage_mm below creepage_ahead_of_fuse_mm with no downstream_basis, a held_at_reinforced that is not a list of pairs of net names, a terminal_clearance_mm below clearance_mm, a creepage_ahead_of_fuse_mm below creepage_mm, an entry_fuse naming no reference of the layout, and a key inside the mapping that the basis decision does not name each fail it likewise. A design that declares MAINS none is out of scope and passes without the mapping.
        for key in ("clearance_mm", "terminal_clearance_mm", "creepage_mm", "creepage_ahead_of_fuse_mm"):
            for bad in (0, -1.5, "1.5", True, float("nan"), float("inf"), [2]):
                with self.subTest(key=key, bad=bad):
                    self.assertFails(basis(mains_to_mains=mapping(**{key: bad})), f"mains_to_mains.{key}", "not a positive number")

    def test_a_creepage_below_the_one_ahead_of_the_fuse_needs_its_downstream_basis(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-TO-MAINS-SPACING.C1: On a design that declares MAINS present, a record with no mains_to_mains mapping, or one lacking clearance_mm, terminal_clearance_mm, creepage_mm, creepage_ahead_of_fuse_mm or entry_fuse, fails separation_basis naming the key. A figure that is not a positive number, a creepage_mm below creepage_ahead_of_fuse_mm with no downstream_basis, a held_at_reinforced that is not a list of pairs of net names, a terminal_clearance_mm below clearance_mm, a creepage_ahead_of_fuse_mm below creepage_mm, an entry_fuse naming no reference of the layout, and a key inside the mapping that the basis decision does not name each fail it likewise. A design that declares MAINS none is out of scope and passes without the mapping.
        self.assertFails(basis(mains_to_mains=mapping(creepage_mm=2.0)), "mains_to_mains.creepage_mm", "downstream_basis")
        signed, problems = read(basis(mains_to_mains=mapping(creepage_mm=2.0, downstream_basis="a fault current and a fuse")))
        self.assertEqual(problems, [])
        self.assertEqual(signed.mains_to_mains["creepage_mm"], 2.0)
        # a creepage equal to the one ahead of the fuse needs none
        self.assertEqual(read(basis(mains_to_mains=mapping(creepage_mm=2.5)))[1], [])
        for blank in ("", "  ", 3):
            with self.subTest(blank=blank):
                self.assertFails(basis(mains_to_mains=mapping(creepage_mm=2.0, downstream_basis=blank)),
                                 "mains_to_mains.downstream_basis", "non-empty string")

    def test_a_terminal_clearance_below_the_clearance_and_a_creepage_ahead_of_the_fuse_below_the_creepage_fail(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-TO-MAINS-SPACING.C1: On a design that declares MAINS present, a record with no mains_to_mains mapping, or one lacking clearance_mm, terminal_clearance_mm, creepage_mm, creepage_ahead_of_fuse_mm or entry_fuse, fails separation_basis naming the key. A figure that is not a positive number, a creepage_mm below creepage_ahead_of_fuse_mm with no downstream_basis, a held_at_reinforced that is not a list of pairs of net names, a terminal_clearance_mm below clearance_mm, a creepage_ahead_of_fuse_mm below creepage_mm, an entry_fuse naming no reference of the layout, and a key inside the mapping that the basis decision does not name each fail it likewise. A design that declares MAINS none is out of scope and passes without the mapping.
        self.assertFails(basis(mains_to_mains=mapping(terminal_clearance_mm=1.4)), "mains_to_mains.terminal_clearance_mm",
                         "below clearance_mm")
        self.assertEqual(read(basis(mains_to_mains=mapping(terminal_clearance_mm=1.5)))[1], [])
        self.assertFails(basis(mains_to_mains=mapping(creepage_ahead_of_fuse_mm=2.4)),
                         "mains_to_mains.creepage_ahead_of_fuse_mm", "below creepage_mm")
        # a downstream_basis excuses a creepage below the figure ahead of the fuse, never the reverse
        self.assertFails(basis(mains_to_mains=mapping(creepage_ahead_of_fuse_mm=2.4, downstream_basis="a basis")),
                         "mains_to_mains.creepage_ahead_of_fuse_mm", "below creepage_mm")

    def test_a_held_at_reinforced_that_is_not_a_list_of_pairs_of_net_names_fails(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-TO-MAINS-SPACING.C1: On a design that declares MAINS present, a record with no mains_to_mains mapping, or one lacking clearance_mm, terminal_clearance_mm, creepage_mm, creepage_ahead_of_fuse_mm or entry_fuse, fails separation_basis naming the key. A figure that is not a positive number, a creepage_mm below creepage_ahead_of_fuse_mm with no downstream_basis, a held_at_reinforced that is not a list of pairs of net names, a terminal_clearance_mm below clearance_mm, a creepage_ahead_of_fuse_mm below creepage_mm, an entry_fuse naming no reference of the layout, and a key inside the mapping that the basis decision does not name each fail it likewise. A design that declares MAINS none is out of scope and passes without the mapping.
        for bad in ("/MAINS_L", {"a": "b"}, [["/MAINS_L"]], [["/MAINS_L", "/MAINS_N", "/MAINS_X"]], ["/MAINS_L"], [[1, 2]],
                    [["/MAINS_L", ""]], [["/MAINS_L", None]], [None]):
            with self.subTest(bad=bad):
                self.assertFails(basis(mains_to_mains=mapping(held_at_reinforced=bad)), "mains_to_mains.held_at_reinforced",
                                 "held_at_reinforced")
        signed, problems = read(basis(mains_to_mains=mapping(held_at_reinforced=[["/MAINS_L", "/MAINS_N"], ["/A", "/B"]])))
        self.assertEqual(problems, [])
        self.assertEqual(signed.mains_to_mains["held_at_reinforced"], [["/MAINS_L", "/MAINS_N"], ["/A", "/B"]])
        # a name a KiCad rule condition cannot carry is refused rather than written into one
        for name in ("/A'B", '/A"B', "/A\\B"):
            with self.subTest(name=name):
                self.assertFails(basis(mains_to_mains=mapping(held_at_reinforced=[["/MAINS_L", name]])),
                                 "mains_to_mains.held_at_reinforced[0]", "cannot carry")

    def test_a_key_inside_the_mapping_the_basis_decision_does_not_name_fails_naming_it(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-TO-MAINS-SPACING.C1: On a design that declares MAINS present, a record with no mains_to_mains mapping, or one lacking clearance_mm, terminal_clearance_mm, creepage_mm, creepage_ahead_of_fuse_mm or entry_fuse, fails separation_basis naming the key. A figure that is not a positive number, a creepage_mm below creepage_ahead_of_fuse_mm with no downstream_basis, a held_at_reinforced that is not a list of pairs of net names, a terminal_clearance_mm below clearance_mm, a creepage_ahead_of_fuse_mm below creepage_mm, an entry_fuse naming no reference of the layout, and a key inside the mapping that the basis decision does not name each fail it likewise. A design that declares MAINS none is out of scope and passes without the mapping.
        self.assertFails(basis(mains_to_mains=mapping(terminal_creepage_mm=3.0)), "mains_to_mains.terminal_creepage_mm",
                         "terminal_creepage_mm")
        self.assertFails(basis(mains_to_mains=mapping(accepted_exceptions=[])), "mains_to_mains.accepted_exceptions",
                         "accepted_exceptions")

    def test_an_entry_fuse_that_is_not_a_name_fails_and_one_the_layout_lacks_fails_in_the_layout_reading(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-TO-MAINS-SPACING.C1: On a design that declares MAINS present, a record with no mains_to_mains mapping, or one lacking clearance_mm, terminal_clearance_mm, creepage_mm, creepage_ahead_of_fuse_mm or entry_fuse, fails separation_basis naming the key. A figure that is not a positive number, a creepage_mm below creepage_ahead_of_fuse_mm with no downstream_basis, a held_at_reinforced that is not a list of pairs of net names, a terminal_clearance_mm below clearance_mm, a creepage_ahead_of_fuse_mm below creepage_mm, an entry_fuse naming no reference of the layout, and a key inside the mapping that the basis decision does not name each fail it likewise. A design that declares MAINS none is out of scope and passes without the mapping.
        self.assertFails(basis(mains_to_mains=mapping(entry_fuse="")), "mains_to_mains.entry_fuse", "non-empty string")
        self.assertFails(basis(mains_to_mains=mapping(entry_fuse=7)), "mains_to_mains.entry_fuse", "non-empty string")
        signed, _ = read(basis())
        found = board_check.mains_pairs(DESIGN, RECORD, signed, {"/MAINS_L"}, {"R1": [], "J1": []})
        self.assertEqual([(v.rule, v.location) for v in found], [("separation_basis", f"{RECORD} mains_to_mains.entry_fuse")])
        self.assertIn("'F1'", found[0].message)
        self.assertIn("J1, R1", found[0].message)
        self.assertEqual(board_check.mains_pairs(DESIGN, RECORD, signed, {"/MAINS_L"}, {"F1": []}), [])

    def test_the_mapping_is_not_asked_of_a_key_a_record_may_hold_anyway(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-TO-MAINS-SPACING.C1: On a design that declares MAINS present, a record with no mains_to_mains mapping, or one lacking clearance_mm, terminal_clearance_mm, creepage_mm, creepage_ahead_of_fuse_mm or entry_fuse, fails separation_basis naming the key. A figure that is not a positive number, a creepage_mm below creepage_ahead_of_fuse_mm with no downstream_basis, a held_at_reinforced that is not a list of pairs of net names, a terminal_clearance_mm below clearance_mm, a creepage_ahead_of_fuse_mm below creepage_mm, an entry_fuse naming no reference of the layout, and a key inside the mapping that the basis decision does not name each fail it likewise. A design that declares MAINS none is out of scope and passes without the mapping.
        # a further pair of distances for readers is still any mapping of exactly clearance_mm and creepage_mm
        signed, problems = read(basis(line_to_switched_line={"clearance_mm": 2.0, "creepage_mm": 2.0}))
        self.assertEqual(problems, [])


class TheFloorIsRead(unittest.TestCase):
    def test_figures_at_their_floors_pass(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-TO-MAINS-SPACING.C2: Each of the four figures is compared with the floor the basis decision sets for it, and a figure below it fails separation_floor naming the figure and the floor. A mains-present design with no applicable row for a figure fails naming it. A figure at its floor passes, and a derived row at the basis working voltage is read as the floor in place of the higher table row it was interpolated toward. The floor of the mains_to_low_voltage figures is out of scope and reads as before.
        self.assertEqual(floor(basis()), [])

    def test_a_figure_below_its_floor_fails_naming_the_figure_and_the_floor(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-TO-MAINS-SPACING.C2: Each of the four figures is compared with the floor the basis decision sets for it, and a figure below it fails separation_floor naming the figure and the floor. A mains-present design with no applicable row for a figure fails naming it. A figure at its floor passes, and a derived row at the basis working voltage is read as the floor in place of the higher table row it was interpolated toward. The floor of the mains_to_low_voltage figures is out of scope and reads as before.
        cases = (("clearance_mm", {"clearance_mm": 1.4}, 1.5, 1.4), ("terminal_clearance_mm", {"terminal_clearance_mm": 1.9}, 2.0, 1.9),
                 ("creepage_ahead_of_fuse_mm", {"creepage_ahead_of_fuse_mm": 2.4, "creepage_mm": 2.4}, 2.5, 2.4),
                 ("creepage_mm", {"creepage_ahead_of_fuse_mm": 2.4, "creepage_mm": 2.4}, 2.5, 2.4))
        for key, change, floor_mm, signed_mm in cases:
            with self.subTest(key=key):
                found = only(floor(basis(mains_to_mains=mapping(**change))), key)
                self.assertEqual([v.rule for v in found], ["separation_floor"])
                self.assertIn(f"mains_to_mains.{key} is {signed_mm:g} mm", found[0].message)
                self.assertIn(f"below the {floor_mm:g} mm floor", found[0].message)

    def test_a_mains_present_design_with_no_applicable_row_for_a_figure_fails_naming_it(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-TO-MAINS-SPACING.C2: Each of the four figures is compared with the floor the basis decision sets for it, and a figure below it fails separation_floor naming the figure and the floor. A mains-present design with no applicable row for a figure fails naming it. A figure at its floor passes, and a derived row at the basis working voltage is read as the floor in place of the higher table row it was interpolated toward. The floor of the mains_to_low_voltage figures is out of scope and reads as before.
        rows = basis()["table_rows"]
        cases = ((3, ["terminal_clearance_mm"]), (2, ["clearance_mm", "creepage_ahead_of_fuse_mm", "creepage_mm"]))
        for dropped, keys in cases:
            with self.subTest(dropped=dropped):
                found = floor(basis(table_rows=[r for index, r in enumerate(rows) if index != dropped]))
                self.assertEqual(sorted(v.location.rsplit(".", 1)[1] for v in found), sorted(keys))
                self.assertTrue(all("no table row" in v.message and v.rule == "separation_floor" for v in found), found)

    def test_a_row_must_state_the_insulation_and_the_location_the_figure_is_read_from(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-TO-MAINS-SPACING.C2: Each of the four figures is compared with the floor the basis decision sets for it, and a figure below it fails separation_floor naming the figure and the floor. A mains-present design with no applicable row for a figure fails naming it. A figure at its floor passes, and a derived row at the basis working voltage is read as the floor in place of the higher table row it was interpolated toward. The floor of the mains_to_low_voltage figures is out of scope and reads as before.
        rows = basis()["table_rows"]
        # a conductor row that states no insulation gives no floor to a mains-to-mains figure
        bare = copy.deepcopy(rows)
        del bare[2]["inputs"]["insulation"]
        self.assertEqual(sorted(v.location.rsplit(".", 1)[1] for v in floor(basis(table_rows=bare))),
                         ["clearance_mm", "creepage_ahead_of_fuse_mm", "creepage_mm"])
        # a row of reinforced insulation is not a basic row
        reinforced = copy.deepcopy(rows)
        reinforced[2]["inputs"]["insulation"] = "reinforced"
        self.assertEqual(len(floor(basis(table_rows=reinforced))), 3)
        # a terminal row does not raise the floor of a conductor, nor a conductor row the floor of a terminal
        terminal = rows + [row({"working_voltage_v": 250, "insulation": "basic", "location": "terminal"}, clearance_mm=9.0)]
        self.assertEqual([v.location.rsplit(".", 1)[1] for v in floor(basis(table_rows=terminal))], ["terminal_clearance_mm"])
        conductor = rows + [row({"working_voltage_v": 250, "insulation": "basic", "location": "conductor"}, clearance_mm=9.0)]
        self.assertEqual([v.location.rsplit(".", 1)[1] for v in floor(basis(table_rows=conductor))], ["clearance_mm"])
        # a row at a working voltage below the basis does not apply
        low = rows + [row({"working_voltage_v": 240, "insulation": "basic"}, clearance_mm=9.0)]
        self.assertEqual(floor(basis(table_rows=low)), [])

    def test_a_derived_row_at_the_basis_working_voltage_is_the_floor_in_place_of_the_higher_row(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-TO-MAINS-SPACING.C2: Each of the four figures is compared with the floor the basis decision sets for it, and a figure below it fails separation_floor naming the figure and the floor. A mains-present design with no applicable row for a figure fails naming it. A figure at its floor passes, and a derived row at the basis working voltage is read as the floor in place of the higher table row it was interpolated toward. The floor of the mains_to_low_voltage figures is out of scope and reads as before.
        rows = [r for r in basis()["table_rows"] if "insulation" not in r["inputs"] or r["inputs"].get("location")]
        rows[-1]["inputs"]["working_voltage_v"] = 253
        higher = row({"working_voltage_v": 320, "insulation": "basic"}, creepage_mm=5.0, clearance_mm=1.5)
        derived = row({"working_voltage_v": 253, "insulation": "basic"}, creepage_mm=4.1, clearance_mm=1.5)
        record = dict(working_voltage="253 V rms", mains_to_mains=mapping(creepage_mm=4.1, creepage_ahead_of_fuse_mm=4.1))
        # the higher row alone is the floor, and the signed 4.1 is below it
        found = floor(basis(table_rows=rows + [higher], **record))
        self.assertEqual(sorted(v.location.rsplit(".", 1)[1] for v in found), ["creepage_ahead_of_fuse_mm", "creepage_mm"])
        self.assertIn("below the 5 mm floor", found[0].message)
        # beside the derived row, the derived row is the floor and 4.1 stands
        self.assertEqual(floor(basis(table_rows=rows + [higher, derived], **record)), [])
        # and 4.0 is below it, naming the derived row
        low = floor(basis(table_rows=rows + [higher, derived], working_voltage="253 V rms",
                          mains_to_mains=mapping(creepage_mm=4.0, creepage_ahead_of_fuse_mm=4.0)))
        self.assertEqual(len(low), 2)
        self.assertTrue(all("below the 4.1 mm floor" in v.message and "table_rows[4]" in v.message for v in low), low)

    def test_a_derived_row_displaces_only_the_higher_rows_of_its_own_insulation_and_location(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-TO-MAINS-SPACING.C2: Each of the four figures is compared with the floor the basis decision sets for it, and a figure below it fails separation_floor naming the figure and the floor. A mains-present design with no applicable row for a figure fails naming it. A figure at its floor passes, and a derived row at the basis working voltage is read as the floor in place of the higher table row it was interpolated toward. The floor of the mains_to_low_voltage figures is out of scope and reads as before.
        rows = [r for r in basis()["table_rows"] if "insulation" not in r["inputs"] or r["inputs"].get("location")]
        terminal_higher = row({"working_voltage_v": 320, "insulation": "basic", "location": "terminal"}, clearance_mm=3.0)
        derived = row({"working_voltage_v": 253, "insulation": "basic"}, creepage_mm=2.5, clearance_mm=1.5)
        found = floor(basis(table_rows=rows + [terminal_higher, derived], working_voltage="253 V rms"))
        self.assertEqual([v.location.rsplit(".", 1)[1] for v in found], ["terminal_clearance_mm"])
        self.assertIn("below the 3 mm floor", found[0].message)

    def test_the_creepage_downstream_of_the_fuse_is_held_to_a_functional_row_only_with_a_downstream_basis(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-TO-MAINS-SPACING.C2: Each of the four figures is compared with the floor the basis decision sets for it, and a figure below it fails separation_floor naming the figure and the floor. A mains-present design with no applicable row for a figure fails naming it. A figure at its floor passes, and a derived row at the basis working voltage is read as the floor in place of the higher table row it was interpolated toward. The floor of the mains_to_low_voltage figures is out of scope and reads as before.
        functional = row({"working_voltage_v": 250, "insulation": "functional"}, creepage_mm=1.0)
        rows = basis()["table_rows"] + [functional]
        # with a downstream basis the functional row is the floor and the basic row is not
        held = mapping(creepage_mm=1.0, downstream_basis="a basis")
        self.assertEqual(floor(basis(table_rows=rows, mains_to_mains=held)), [])
        found = floor(basis(table_rows=rows, mains_to_mains=dict(held, creepage_mm=0.9)))
        self.assertEqual([v.location.rsplit(".", 1)[1] for v in found], ["creepage_mm"])
        self.assertIn("below the 1 mm floor", found[0].message)
        # and without one the functional row is not read: creepage_mm equal to the basic floor stands
        self.assertEqual(floor(basis(table_rows=rows)), [])
        # a downstream basis with no functional row leaves the figure without a floor
        self.assertEqual([v.location.rsplit(".", 1)[1] for v in floor(basis(mains_to_mains=held))], ["creepage_mm"])

    def test_the_floor_of_the_mains_to_low_voltage_figures_reads_as_before(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-TO-MAINS-SPACING.C2: Each of the four figures is compared with the floor the basis decision sets for it, and a figure below it fails separation_floor naming the figure and the floor. A mains-present design with no applicable row for a figure fails naming it. A figure at its floor passes, and a derived row at the basis working voltage is read as the floor in place of the higher table row it was interpolated toward. The floor of the mains_to_low_voltage figures is out of scope and reads as before.
        signed, _ = read(basis())
        lv = [v for v in board_check.separation_floor(DESIGN, RECORD, signed) if "mains_to_low_voltage" in v.location]
        self.assertEqual(lv, [])
        # a basic row of any size gives the low-voltage figures no floor: they are read at the strongest barrier
        rows = basis()["table_rows"] + [row({"working_voltage_v": 250, "insulation": "basic"}, clearance_mm=99.0, creepage_mm=99.0)]
        signed, _ = read(basis(table_rows=rows, barrier_types=[{"barrier": "a", "insulation": "reinforced", "earth_bonded": False,
                                                                 "touchable": [], "formed_by": "a slot"}], barriers=["a"]))
        lv = [v for v in board_check.separation_floor(DESIGN, RECORD, signed) if "mains_to_low_voltage" in v.location]
        self.assertEqual(lv, [])
        low = dict(basis(), mains_to_low_voltage={"clearance_mm": 2.0, "creepage_mm": 4.0})
        signed, _ = read(low)
        lv = [v for v in board_check.separation_floor(DESIGN, RECORD, signed) if "mains_to_low_voltage" in v.location]
        self.assertEqual([v.location.rsplit(".", 1)[1] for v in lv], ["clearance_mm"])

    def test_a_record_without_a_mapping_is_not_floor_read_as_one(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-TO-MAINS-SPACING.C2: Each of the four figures is compared with the floor the basis decision sets for it, and a figure below it fails separation_floor naming the figure and the floor. A mains-present design with no applicable row for a figure fails naming it. A figure at its floor passes, and a derived row at the basis working voltage is read as the floor in place of the higher table row it was interpolated toward. The floor of the mains_to_low_voltage figures is out of scope and reads as before.
        signed = board_check.Signed(3.0, 4.0, basis(mains_to_mains=None))
        self.assertEqual([v for v in board_check.separation_floor(DESIGN, RECORD, signed) if "mains_to_mains" in v.location], [])


class TheDeclarationIsRead(unittest.TestCase):
    def found(self, declared, ahead, mains):
        return [(v.rule, v.location, v.message) for v in board_check.entry_declaration(DESIGN, declared, set(ahead), set(mains))]

    def test_present_with_a_net_in_the_class_inside_mains_is_accepted_and_so_is_none_with_no_net(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-TO-MAINS-SPACING.C3: MAINS_ENTRY unset or holding anything but present or none fails; present with no net in the Mains_Entry class, or with a Mains_Entry net outside the Mains class, fails; none with a net in the Mains_Entry class fails. Each failure names the variable or the net. A design that declares MAINS none is out of scope and needs no MAINS_ENTRY.
        self.assertEqual(self.found("present", {"/MAINS_L"}, {"/MAINS_L", "/MAINS_N"}), [])
        self.assertEqual(self.found("none", set(), {"/MAINS_L"}), [])

    def test_present_with_no_net_in_the_mains_entry_class_fails_naming_the_variable(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-TO-MAINS-SPACING.C3: MAINS_ENTRY unset or holding anything but present or none fails; present with no net in the Mains_Entry class, or with a Mains_Entry net outside the Mains class, fails; none with a net in the Mains_Entry class fails. Each failure names the variable or the net. A design that declares MAINS none is out of scope and needs no MAINS_ENTRY.
        found = self.found("present", set(), {"/MAINS_L"})
        self.assertEqual([(rule, location) for rule, location, _ in found], [("mains_declaration", DESIGN.layout)])
        self.assertIn("MAINS_ENTRY is present", found[0][2])
        self.assertIn("Mains_Entry", found[0][2])

    def test_a_mains_entry_net_outside_the_mains_class_fails_naming_the_net(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-TO-MAINS-SPACING.C3: MAINS_ENTRY unset or holding anything but present or none fails; present with no net in the Mains_Entry class, or with a Mains_Entry net outside the Mains class, fails; none with a net in the Mains_Entry class fails. Each failure names the variable or the net. A design that declares MAINS none is out of scope and needs no MAINS_ENTRY.
        found = self.found("present", {"/MAINS_L", "/LV_A"}, {"/MAINS_L"})
        self.assertEqual(len(found), 1, found)
        self.assertEqual(found[0][0], "mains_declaration")
        self.assertIn("/LV_A", found[0][1])
        self.assertIn("net /LV_A", found[0][2])

    def test_none_with_a_net_in_the_mains_entry_class_fails_naming_the_variable_and_the_nets(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-TO-MAINS-SPACING.C3: MAINS_ENTRY unset or holding anything but present or none fails; present with no net in the Mains_Entry class, or with a Mains_Entry net outside the Mains class, fails; none with a net in the Mains_Entry class fails. Each failure names the variable or the net. A design that declares MAINS none is out of scope and needs no MAINS_ENTRY.
        found = self.found("none", {"/MAINS_N", "/MAINS_L"}, {"/MAINS_L", "/MAINS_N"})
        self.assertEqual(len(found), 1, found)
        self.assertTrue(found[0][1].endswith("text_variables.MAINS_ENTRY"))
        self.assertIn("MAINS_ENTRY is none", found[0][2])
        self.assertIn("/MAINS_L, /MAINS_N", found[0][2])

    def test_a_pair_held_at_reinforced_naming_a_net_outside_the_mains_class_fails_naming_it(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-TO-MAINS-SPACING.C8: On a seeded layout with two Mains-class nets listed in held_at_reinforced, a clearance between them below the signed mains_to_low_voltage clearance, and a surface path below its creepage, each fail with the layout rule check's violation naming both nets, though both distances exceed the mains_to_mains figures. A pair naming a net outside the Mains class fails mains_declaration. Pairs not listed are out of scope and keep the mains-to-mains figures.
        signed, _ = read(basis(mains_to_mains=mapping(held_at_reinforced=[["/MAINS_L", "/LV_A"], ["/MAINS_L", "/MAINS_N"]])))
        found = board_check.mains_pairs(DESIGN, RECORD, signed, {"/MAINS_L", "/MAINS_N"}, {"F1": []})
        self.assertEqual([(v.rule, v.location) for v in found],
                         [("mains_declaration", f"{RECORD} mains_to_mains.held_at_reinforced[0]")])
        self.assertIn("/LV_A", found[0].message)
        both = board_check.mains_pairs(DESIGN, RECORD, signed, {"/MAINS_L", "/MAINS_N", "/LV_A"}, {"F1": []})
        self.assertEqual(both, [])


class TheRulesAreAppendedLast(unittest.TestCase):
    def signed(self, **changes):
        return board_check.Signed(3.0, 4.0, basis(mains_to_mains=mapping(**changes)))

    def rules(self, signed):
        text = board_check.appended_rules(signed, "nonce")
        return {name: body for name, body in re.findall(r'\(rule "([^"]+)"(.*?)\n(?=\(rule|\Z)', text, re.S)}, text

    def test_the_signed_rules_follow_the_signed_mains_rule_in_the_one_order(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-TO-MAINS-SPACING.C4: A seeded layout with two Mains-class nets closer than the signed clearance, and another closer than the signed creepage, each fails with the layout rule check's clearance or creepage violation naming both nets; the same layouts fail when the design's own rules are looser, because the appended signed rules come last. Two items of one net are out of scope and never reported.
        _, text = self.rules(self.signed(held_at_reinforced=[["/A", "/B"], ["/C", "/D"]]))
        order = [board_check.SIGNED_RULE, board_check.MAINS_TO_MAINS_RULE, board_check.TERMINAL_RULE,
                 board_check.AHEAD_OF_FUSE_RULE, f"{board_check.REINFORCED_RULE} 1", f"{board_check.REINFORCED_RULE} 2"]
        positions = [text.index(f'(rule "{name}"') for name in order]
        self.assertEqual(positions, sorted(positions))
        self.assertLess(text.index(f'(rule "{board_check.marker_rule("nonce")}"'), positions[0])

    def test_two_mains_class_items_on_different_nets_are_held_to_the_signed_clearance_and_creepage(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-TO-MAINS-SPACING.C4: A seeded layout with two Mains-class nets closer than the signed clearance, and another closer than the signed creepage, each fails with the layout rule check's clearance or creepage violation naming both nets; the same layouts fail when the design's own rules are looser, because the appended signed rules come last. Two items of one net are out of scope and never reported.
        body = self.rules(self.signed())[0][board_check.MAINS_TO_MAINS_RULE]
        self.assertIn('(condition "A.hasNetclass(\'Mains\') && B.hasNetclass(\'Mains\')")', body)
        self.assertIn("(constraint clearance (min 1.5mm))", body)
        self.assertIn("(constraint creepage (min 2.5mm))", body)
        # the creepage is the one downstream of the fuse, which may be below the one ahead of it
        body = self.rules(self.signed(creepage_mm=2.2, downstream_basis="a basis"))[0][board_check.MAINS_TO_MAINS_RULE]
        self.assertIn("(constraint creepage (min 2.2mm))", body)

    def test_the_ahead_of_the_fuse_rule_holds_only_a_creepage_and_only_with_a_mains_class_item_opposite(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-TO-MAINS-SPACING.C5: A seeded layout with a Mains_Entry net and a Mains net at a creepage between the downstream and the ahead-of-fuse figures fails; the same distance between two nets outside Mains_Entry passes. Terminal-to-terminal pairs closer than terminal_clearance_mm fail, and conductor pairs between it and clearance_mm pass. Pairs between two nets that are both outside Mains_Entry are out of scope for the ahead-of-fuse figure.
        body = self.rules(self.signed())[0][board_check.AHEAD_OF_FUSE_RULE]
        self.assertIn('(condition "A.hasNetclass(\'Mains_Entry\') && B.hasNetclass(\'Mains\')")', body)
        self.assertIn("(constraint creepage (min 2.5mm))", body)
        # no clearance, and no pair with a low-voltage item, which the signed Mains rule governs at its own, larger figure
        self.assertNotIn("clearance", body)
        self.assertNotIn("!B", body)

    def test_the_terminal_rule_holds_only_a_clearance_between_two_pads_of_the_mains_class(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-TO-MAINS-SPACING.C5: A seeded layout with a Mains_Entry net and a Mains net at a creepage between the downstream and the ahead-of-fuse figures fails; the same distance between two nets outside Mains_Entry passes. Terminal-to-terminal pairs closer than terminal_clearance_mm fail, and conductor pairs between it and clearance_mm pass. Pairs between two nets that are both outside Mains_Entry are out of scope for the ahead-of-fuse figure.
        body = self.rules(self.signed(terminal_clearance_mm=2.2))[0][board_check.TERMINAL_RULE]
        self.assertIn("A.Type == 'Pad' && B.Type == 'Pad' && A.hasNetclass('Mains') && B.hasNetclass('Mains')", body)
        self.assertIn("(constraint clearance (min 2.2mm))", body)
        self.assertNotIn("creepage", body)

    def test_each_pair_held_at_reinforced_gets_a_rule_with_the_mains_to_low_voltage_figures(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-TO-MAINS-SPACING.C8: On a seeded layout with two Mains-class nets listed in held_at_reinforced, a clearance between them below the signed mains_to_low_voltage clearance, and a surface path below its creepage, each fail with the layout rule check's violation naming both nets, though both distances exceed the mains_to_mains figures. A pair naming a net outside the Mains class fails mains_declaration. Pairs not listed are out of scope and keep the mains-to-mains figures.
        rules, _ = self.rules(self.signed(held_at_reinforced=[["/MAINS_L", "/MAINS_N"]]))
        body = rules[f"{board_check.REINFORCED_RULE} 1"]
        self.assertIn("A.NetName == '/MAINS_L' && B.NetName == '/MAINS_N'", body)
        self.assertIn("(constraint clearance (min 3mm))", body)
        self.assertIn("(constraint creepage (min 4mm))", body)
        self.assertEqual([name for name in rules if name.startswith(board_check.REINFORCED_RULE)], [f"{board_check.REINFORCED_RULE} 1"])
        # no pair held at reinforced, no rule for one
        self.assertEqual([name for name in self.rules(self.signed())[0] if name.startswith(board_check.REINFORCED_RULE)], [])

    def test_figures_without_a_record_write_no_further_rule(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-TO-MAINS-SPACING.C4: A seeded layout with two Mains-class nets closer than the signed clearance, and another closer than the signed creepage, each fails with the layout rule check's clearance or creepage violation naming both nets; the same layouts fail when the design's own rules are looser, because the appended signed rules come last. Two items of one net are out of scope and never reported.
        rules, _ = self.rules((3.0, 4.0))
        self.assertEqual(sorted(rules), sorted([board_check.marker_rule("nonce"), board_check.SIGNED_RULE]))
        self.assertEqual(self.rules(None)[0].keys(), {board_check.marker_rule("nonce")})


class TheHardwareNotesStateThem(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(os.path.join(REPO, "hardware", "README.md"), encoding="utf-8") as handle:
            cls.text = handle.read()

    def section(self, heading: str) -> str:
        start = self.text.index(f"\n## {heading}")
        end = self.text.find("\n## ", start + 1)
        return self.text[start:end if end != -1 else len(self.text)]

    def test_the_record_key_list_names_the_mapping_and_every_key_of_it(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-TO-MAINS-SPACING.C7: Every tracked design passes the check, the throwaway ones with synthetic mains_to_mains figures and MAINS_ENTRY, in the build round for board changes and nightly on main. The hardware notes' record-key list, text-variable list, checks table and adopter section state mains_to_mains, MAINS_ENTRY, Mains_Entry and the floor reading. The signed record of the machine is out of scope; its leaf adds the real figures.
        design = self.section("What a design must satisfy")
        for word in ("mains_to_mains", "terminal_clearance_mm", "creepage_ahead_of_fuse_mm", "entry_fuse", "held_at_reinforced",
                     "downstream_basis", "`location`", "functional"):
            self.assertIn(word, design, word)

    def test_the_text_variable_and_the_net_class_are_stated_where_the_declaration_is(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-TO-MAINS-SPACING.C7: Every tracked design passes the check, the throwaway ones with synthetic mains_to_mains figures and MAINS_ENTRY, in the build round for board changes and nightly on main. The hardware notes' record-key list, text-variable list, checks table and adopter section state mains_to_mains, MAINS_ENTRY, Mains_Entry and the floor reading. The signed record of the machine is out of scope; its leaf adds the real figures.
        design = self.section("What a design must satisfy")
        self.assertRegex(design, r"project text variable `MAINS_ENTRY` set to `present` or `none`")
        self.assertIn("`Mains_Entry`", design)

    def test_the_checks_table_names_the_new_failures_under_their_report_names(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-TO-MAINS-SPACING.C7: Every tracked design passes the check, the throwaway ones with synthetic mains_to_mains figures and MAINS_ENTRY, in the build round for board changes and nightly on main. The hardware notes' record-key list, text-variable list, checks table and adopter section state mains_to_mains, MAINS_ENTRY, Mains_Entry and the floor reading. The signed record of the machine is out of scope; its leaf adds the real figures.
        table = self.section("The report")
        rows = {match.group(1): match.group(0) for match in re.finditer(r"^\| `([a-z_]+)` \|.*$", table, re.M)}
        self.assertIn("MAINS_ENTRY", rows["mains_declaration"])
        self.assertIn("Mains_Entry", rows["mains_declaration"])
        self.assertIn("held_at_reinforced", rows["mains_declaration"])
        self.assertIn("mains_to_mains", rows["separation_basis"])
        self.assertIn("mains_to_mains", rows["separation_floor"])
        record = re.search(r"^\| Separation basis record \|.*$", self.section("The one form each file is read in"), re.M).group(0)
        self.assertIn("mains_to_mains", record)

    def test_the_floor_reading_and_the_appended_rules_are_stated(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-TO-MAINS-SPACING.C7: Every tracked design passes the check, the throwaway ones with synthetic mains_to_mains figures and MAINS_ENTRY, in the build round for board changes and nightly on main. The hardware notes' record-key list, text-variable list, checks table and adopter section state mains_to_mains, MAINS_ENTRY, Mains_Entry and the floor reading. The signed record of the machine is out of scope; its leaf adds the real figures.
        design = self.section("What a design must satisfy")
        for word in ("derived row", "linear interpolation", "location", "signed terminal clearance", board_check.MAINS_TO_MAINS_RULE.split(": ")[1],
                     board_check.AHEAD_OF_FUSE_RULE.split(": ")[1], board_check.REINFORCED_RULE.split(": ")[1]):
            self.assertIn(word, design, word)

    def test_the_adopter_section_tells_them_to_recompute_the_new_figures_and_declare_the_entry(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-MAINS-TO-MAINS-SPACING.C7: Every tracked design passes the check, the throwaway ones with synthetic mains_to_mains figures and MAINS_ENTRY, in the build round for board changes and nightly on main. The hardware notes' record-key list, text-variable list, checks table and adopter section state mains_to_mains, MAINS_ENTRY, Mains_Entry and the floor reading. The signed record of the machine is out of scope; its leaf adds the real figures.
        adopter = self.section("Re-deriving the separation basis for a different supply or altitude")
        for word in ("mains_to_mains", "MAINS_ENTRY", "Mains_Entry", "entry_fuse", "downstream_basis", "held_at_reinforced"):
            self.assertIn(word, adopter, word)


if __name__ == "__main__":
    unittest.main()
