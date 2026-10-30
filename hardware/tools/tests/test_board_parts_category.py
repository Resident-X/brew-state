#!/usr/bin/env python3
"""The decoupling pin-type rule's reading of the catalogue extract's category, driven on synthetic designs with no KiCad.

What is under test is which integrated circuits the rule skips for having no
supply pin, and that every other case is refused as before: the skip must fail
closed, or the defect the rule exists for, a real integrated circuit whose
supply pads are untyped, would be silenced. The check run against KiCad and the
seeded-fault proof are in the test_board_check_kicad_*.py files.
"""

from __future__ import annotations

import datetime
import os
import sys
import tempfile
import unittest

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import board_check  # noqa: E402
import sexpr  # noqa: E402
import test_board_parts as parts  # noqa: E402

TODAY = datetime.date(2026, 10, 12)
TRIAC = "Triac, SCR Output Optoisolators"
PHOTO = "Transistor, Photovoltaic Output Optoisolators"
REGULATOR = "Linear Voltage Regulators"
GATE_DRIVE = "Gate Drive Optocouplers"


def extract(category: str = "", synthetic: bool = False, number: str = "C9000001") -> str:
    """A catalogue extract with an entry for `number` carrying `category` text as written (nothing where empty)."""
    return ("source: a synthetic reading\nread_on: 2026-10-01\nmax_age_days: 30\nentries:\n"
            f"  - lcsc: {number}\n    library_class: basic\n    stock: 5\n    unit_price: 0.01\n{category}"
            + ("synthetic: true\n" if synthetic else ""))


def line(category: str) -> str:
    return f"    category: {category}\n"


def footprint(reference: str, kind: str = "passive") -> str:
    pads = " ".join(f'(pad "{n}" smd rect (at {n} 0) (size 1 1) (layers "F.Cu" "F.Mask") (net "/N{n}") (pintype "{k}"))'
                    for n, k in (("1", kind), ("2", "passive")))
    return f'(footprint "lib:p" (layer "F.Cu") (at 0 0) (property "Reference" "{reference}" (at 0 0 0)) {pads})'


def layout(*items: str) -> list:
    return sexpr.parse_one("(kicad_pcb (version 20260206) " + " ".join(items) + ")")


class TheCategorySkipsOnlyAPartThatHasNoSupply(parts.Design):
    """An orderable design, a usable extract and a U-referenced part with netted pads and none typed power."""

    def setUp(self):
        super().setUp()
        self.schematic(parts.symbol("Chip:OPTO", "U1", "OPTO", "Package:SOP", "C9000001"))
        self.record("hw/machine/parts-specification.yaml", "positions:\n  - reference: U1\n    lcsc: C9000001\n")

    def record(self, path, text):
        self.write(path, text)

    def catalogue(self, text):
        self.write("hw/machine/catalogue-extract.yaml", text)

    def found(self, *items, hardware=True):
        files = [os.path.relpath(os.path.join(d, n), self.root).replace(os.sep, "/")
                 for d, _, names in os.walk(self.root) for n in names]
        repository = board_check.Repository(self.root, files)
        tree = layout(*(items or (footprint("U1"),)))
        return board_check.untyped_circuits_by_category(self.yaml, self.root, repository, self.design, tree, TODAY,
                                                        not hardware)

    def refused(self, *items):
        return [(v.rule, v.location) for v in self.found(*items)]

    def test_a_circuit_in_each_closed_list_category_with_no_power_typed_pad_is_not_refused(self):
        # SOL-PRE-ORDER-CHECK-DECOUPLING-PINTYPE-SKIPS-PART-WITH-NO-SUPPLY.C1: A U-referenced part whose catalogue entry's category is in the closed no-supply list and none of whose pads is typed power is not refused by decoupling_pintype
        for category in (TRIAC, PHOTO):
            with self.subTest(category=category):
                self.catalogue(extract(line(f'"{category}"')))
                self.assertEqual(self.refused(), [])

    def test_the_closed_list_holds_exactly_the_two_strings(self):
        # SOL-PRE-ORDER-CHECK-DECOUPLING-PINTYPE-SKIPS-PART-WITH-NO-SUPPLY.C10: The closed no-supply list holds exactly the two category strings read from the supplier's records, recorded with their sources in the hardware notes
        self.assertEqual(board_check.NO_SUPPLY_CATEGORIES, (PHOTO, TRIAC))

    def test_a_skipped_category_with_a_power_typed_pad_fails_naming_the_position(self):
        # SOL-PRE-ORDER-CHECK-DECOUPLING-PINTYPE-SKIPS-PART-WITH-NO-SUPPLY.C2: A part whose entry's category is in the closed list and whose footprint has a pad typed power input or power output fails decoupling_pintype naming the position
        for category in (TRIAC, PHOTO):
            for kind in ("power_in", "power_out"):
                with self.subTest(category=category, kind=kind):
                    self.catalogue(extract(line(f'"{category}"')))
                    found = self.found(footprint("U1", kind))
                    self.assertEqual([(v.rule, v.location) for v in found], [("decoupling_pintype", "U1 at (0, 0) mm")])
                    self.assertIn("the layout contradicts the category", found[0].message)

    def test_a_category_outside_the_list_fails_with_the_advice_to_record_the_category(self):
        # SOL-PRE-ORDER-CHECK-DECOUPLING-PINTYPE-SKIPS-PART-WITH-NO-SUPPLY.C3: An integrated circuit whose entry carries a category outside the closed list fails decoupling_pintype naming the position
        for category in (REGULATOR, GATE_DRIVE, "Optoisolators", TRIAC.lower(), TRIAC + " "):
            with self.subTest(category=category):
                self.catalogue(extract(line(f'"{category}"')))
                found = self.found()
                self.assertEqual([(v.rule, v.location) for v in found], [("decoupling_pintype", "U1 at (0, 0) mm")])
                self.assertIn("U1 has netted pads and none typed power input or power output", found[0].message)
                self.assertIn("record the part's category in the catalogue extract", found[0].message)
                self.assertIn("type U1's supply pads from its symbol's pin types", found[0].message)

    def test_a_circuit_that_cannot_be_matched_to_a_category_fails_naming_the_position(self):
        # SOL-PRE-ORDER-CHECK-DECOUPLING-PINTYPE-SKIPS-PART-WITH-NO-SUPPLY.C4: An integrated circuit that cannot be matched to a category fails decoupling_pintype naming the position
        refused = [("decoupling_pintype", "U1 at (0, 0) mm")]
        in_list = line(f'"{TRIAC}"')
        cases = {
            "an entry with no category": lambda: self.catalogue(extract()),
            "a number absent from the extract": lambda: self.catalogue(extract(in_list, number="C9000002")),
            "a position whose lcsc is none": lambda: self.schematic(parts.symbol("Chip:OPTO", "U1", "OPTO", "Package:SOP", "none")),
            "a position with no lcsc field": lambda: self.schematic(parts.symbol("Chip:OPTO", "U1", "OPTO", "Package:SOP")),
            "a position not in the schematic": lambda: self.schematic(),
            "no extract": lambda: os.remove(os.path.join(self.root, "hw/machine/catalogue-extract.yaml")),
            "an extract that cannot be parsed": lambda: self.catalogue("entries: [unclosed\n"),
            "an extract lacking a required key": lambda: self.catalogue(extract(in_list).replace("max_age_days: 30\n", "")),
            "an extract marked synthetic on an orderable design": lambda: self.catalogue(extract(in_list, synthetic=True)),
        }
        for name, change in cases.items():
            with self.subTest(case=name):
                self.catalogue(extract(in_list))
                change()
                self.assertEqual(self.refused(), refused)

    def test_a_number_with_spaces_is_matched_as_the_extract_matches_it(self):
        # SOL-PRE-ORDER-CHECK-DECOUPLING-PINTYPE-SKIPS-PART-WITH-NO-SUPPLY.C1: A U-referenced part whose catalogue entry's category is in the closed no-supply list and none of whose pads is typed power is not refused by decoupling_pintype
        self.catalogue(extract(line(f'"{PHOTO}"')))
        self.schematic(parts.symbol("Chip:OPTO", "U1", "OPTO", "Package:SOP", " C9000001 "))
        self.assertEqual(self.refused(), [])

    def test_an_empty_or_non_string_category_fails_the_extract_read_naming_the_entry_and_skips_nothing(self):
        # SOL-PRE-ORDER-CHECK-DECOUPLING-PINTYPE-SKIPS-PART-WITH-NO-SUPPLY.C5: A category that is an empty string or is not a string fails the catalogue extract read naming the entry, and the part is not skipped
        for text in ('""', '"  "', "5", "true", "[a]", "{a: b}", "null"):
            with self.subTest(category=text):
                self.catalogue(extract(line(text)))
                read, problems = board_check.read_extract(self.yaml, self.root, board_check.Repository(self.root, [
                    "hw/machine/catalogue-extract.yaml"]), self.design, TODAY, False)
                self.assertIsNone(read)
                self.assertEqual([(v.rule, v.location.split(" ", 1)[1]) for v in problems],
                                 [("parts_record", "entries[0].category")])
                self.assertIn("entries[0].category is", problems[0].message)
                self.assertEqual(self.refused(), [("decoupling_pintype", "U1 at (0, 0) mm")])

    def test_a_well_formed_category_is_accepted_by_the_extract_read(self):
        # SOL-PRE-ORDER-CHECK-DECOUPLING-PINTYPE-SKIPS-PART-WITH-NO-SUPPLY.C5: A category that is an empty string or is not a string fails the catalogue extract read naming the entry, and the part is not skipped
        self.catalogue(extract(line(f'"{TRIAC}"')))
        read, problems = board_check.read_extract(self.yaml, self.root, board_check.Repository(self.root, [
            "hw/machine/catalogue-extract.yaml"]), self.design, TODAY, False)
        self.assertEqual(problems, [])
        self.assertEqual(read.category, {"C9000001": TRIAC})

    def test_the_category_key_changes_no_other_circuits_measurement_and_no_passing_design_fails(self):
        # SOL-PRE-ORDER-CHECK-DECOUPLING-PINTYPE-SKIPS-PART-WITH-NO-SUPPLY.C6: With the category key present or absent on entries, the decoupling measurement of every circuit not skipped is unchanged, and every design that passed the pre-order check before this change still passes
        typed = layout(footprint("U1", "power_in"), footprint("U2", "power_in"))
        before = board_check.decoupling_paths(typed, {"GND"})
        for text in (extract(), extract(line(f'"{TRIAC}"')), extract(line(f'"{REGULATOR}"'))):
            with self.subTest(extract=text[-40:]):
                self.catalogue(text)
                self.assertEqual(board_check.decoupling_paths(typed, {"GND"}), before)
                typed_refused = self.refused(footprint("U1", "power_in"), footprint("U2", "power_in"))
                self.assertEqual(typed_refused, [("decoupling_pintype", "U1 at (0, 0) mm")] if TRIAC in text else [])
        self.catalogue(extract(line(f'"{TRIAC}"')))
        mixed = self.found(footprint("U1"), footprint("U2"))
        self.assertEqual([v.location for v in mixed], ["U2 at (0, 0) mm"], "only the skipped circuit is excused")
        self.assertEqual(self.found(footprint("U1"), hardware=False), [], "a design not for manufacture is not refused")
        self.assertEqual(self.refused(footprint("R1")), [], "a part not beginning with U is no circuit")


if __name__ == "__main__":
    unittest.main()
