#!/usr/bin/env python3
"""The parts check's own decisions, driven on synthetic designs with no KiCad involved.

What is under test is everything the parts check decides for itself: which
schematic symbols are positions the design places, what each failure names, and
whether the specification record and the catalogue extract are usable. Each of
these can be wrong while the check still reports a pass, which is the failure
worth a test. The check run against KiCad and the seeded-fault proof are in
test_board_check_kicad.py.
"""

from __future__ import annotations

import datetime
import os
import socket
import sys
import tempfile
import unittest
from unittest import mock

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)

import board_check  # noqa: E402

REPO = os.path.dirname(os.path.dirname(TOOLS))
TODAY = datetime.date(2026, 10, 12)

RECORD = """\
positions:
  - reference: R1
    value: 10k
    package: R_0603_1608Metric
    rating: 0.1W
    lcsc: C100
  - reference: U1
    value: CHIP
    lcsc: C200
  - reference: R2
    value: 1k
    lcsc: C100
"""

EXTRACT = """\
source: a synthetic reading
read_on: 2026-10-01
max_age_days: 30
entries:
  - lcsc: C100
    library_class: basic
    stock: 500
    unit_price: 0.002
  - lcsc: C200
    library_class: extended
    stock: 3
    unit_price: 1.5
"""


def symbol(lib_id, reference, value, footprint="", lcsc=None, rating=None, unit=1, on_board="yes", project="board",
           instance=True) -> str:
    fields = [("Reference", reference), ("Value", value), ("Footprint", footprint)]
    fields += [("LCSC", lcsc)] if lcsc is not None else []
    fields += [("Rating", rating)] if rating is not None else []
    body = "".join(f'\t\t(property "{name}" "{text}")\n' for name, text in fields)
    instances = (f'\t\t(instances (project "{project}" (path "/root" (reference "{reference}") (unit {unit}))))\n'
                 if instance else "")
    return f'\t(symbol\n\t\t(lib_id "{lib_id}")\n\t\t(unit {unit})\n\t\t(on_board {on_board})\n{body}{instances}\t)\n'


def sheet_file(*symbols: str, power=("power:GND",)) -> str:
    library = "".join(f'\t\t(symbol "{name}" (power global))\n' for name in power)
    return f'(kicad_sch\n\t(version 20250114)\n\t(lib_symbols\n{library}\t\t(symbol "Device:R")\n\t)\n' + "".join(symbols) + ")\n"


GOOD = (symbol("Device:R", "R1", "10k", "Resistor_SMD:R_0603_1608Metric", "C100", "0.1W")
        + symbol("Chip:CHIP", "U1", "CHIP", "Package:QFN", "C200")
        + symbol("Device:R", "R2", "1k", "Resistor_SMD:R_0402", "C100"))


class Design(unittest.TestCase):
    """A synthetic repository tracking every file in it, holding one design under hw/machine/board/."""

    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory()
        self.addCleanup(self.scratch.cleanup)
        self.root = self.scratch.name
        self.yaml = board_check.require_yaml()
        self.folder = "hw/machine/board"
        self.design = board_check.Design(f"{self.folder}/board.kicad_pro")
        self.write(self.design.project, "{}")
        self.write(self.design.layout, "")
        self.write(self.design.schematic, sheet_file(GOOD))
        self.write("hw/machine/parts-specification.yaml", RECORD + "synthetic: true\n")
        self.write("hw/machine/catalogue-extract.yaml", EXTRACT + "synthetic: true\n")

    def write(self, path, text):
        full = os.path.join(self.root, path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as handle:
            handle.write(text)

    def schematic(self, *symbols, **more):
        self.write(self.design.schematic, sheet_file(*symbols, **more))

    def remove(self, path):
        os.remove(os.path.join(self.root, path))

    def run_check(self, not_for_manufacture=True, today=TODAY):
        files = [os.path.relpath(os.path.join(d, n), self.root).replace(os.sep, "/")
                 for d, _, names in os.walk(self.root) for n in names]
        repository = board_check.Repository(self.root, files)
        return board_check.check_parts(self.yaml, self.root, self.design, repository, today, not_for_manufacture)

    def lines(self, **more):
        return [v.line() for v in self.run_check(**more)]

    def rules(self, **more):
        return sorted({v.rule for v in self.run_check(**more)})

    def only(self, **more):
        found = self.lines(**more)
        self.assertEqual(len(found), 1, found)
        return found[0]


class PartsAgainstTheRecord(Design):
    def test_a_design_matching_its_record_and_extract_passes(self):
        # SOL-HW-PARTS-CHECK.C1: A part whose stated properties or catalogue number differ from the specification record fails the check
        self.assertEqual(self.lines(), [])

    def test_a_different_value_fails_naming_the_position_property_and_both_values(self):
        # SOL-HW-PARTS-CHECK.C1: A part whose stated properties or catalogue number differ from the specification record fails the check
        self.schematic(GOOD.replace('"10k"', '"22k"'))
        line = self.only()
        self.assertEqual(line, "VIOLATION | hw/machine/board/board.kicad_pro | parts_part | R1 value | the position R1 value "
                               "differs: the record states '10k' and the design has '22k'")

    def test_a_different_package_fails(self):
        # SOL-HW-PARTS-CHECK.C1: A part whose stated properties or catalogue number differ from the specification record fails the check
        self.schematic(GOOD.replace("R_0603_1608Metric", "R_0805_2012Metric"))
        line = self.only()
        self.assertIn("| R1 package |", line)
        self.assertIn("record states 'R_0603_1608Metric' and the design has 'R_0805_2012Metric'", line)

    def test_a_package_is_the_footprints_library_item_name_without_its_library(self):
        # SOL-HW-PARTS-CHECK.C1: A part whose stated properties or catalogue number differ from the specification record fails the check
        self.schematic(GOOD.replace("Resistor_SMD:R_0603_1608Metric", "OtherLibrary:R_0603_1608Metric"))
        self.assertEqual(self.lines(), [])

    def test_a_part_with_no_footprint_fails_a_record_that_states_a_package(self):
        # SOL-HW-PARTS-CHECK.C1: A part whose stated properties or catalogue number differ from the specification record fails the check
        self.schematic(GOOD.replace("Resistor_SMD:R_0603_1608Metric", ""))
        self.assertIn("and the design has ''", self.only())

    def test_a_different_rating_fails(self):
        # SOL-HW-PARTS-CHECK.C1: A part whose stated properties or catalogue number differ from the specification record fails the check
        self.schematic(GOOD.replace('"0.1W"', '"0.25W"'))
        self.assertIn("R1 rating differs: the record states '0.1W' and the design has '0.25W'", self.only())

    def test_a_part_with_no_rating_field_fails_a_record_that_states_one(self):
        # SOL-HW-PARTS-CHECK.C1: A part whose stated properties or catalogue number differ from the specification record fails the check
        self.schematic(GOOD.replace('\t\t(property "Rating" "0.1W")\n', ""))
        self.assertIn("R1 rating differs: the record states '0.1W' and the design has '(absent)'", self.only())

    def test_a_property_the_record_leaves_unstated_is_not_compared(self):
        # SOL-HW-PARTS-CHECK.C1: A part whose stated properties or catalogue number differ from the specification record fails the check
        self.write("hw/machine/parts-specification.yaml", RECORD.replace("    rating: 0.1W\n", "").replace("    value: 10k\n", "")
                   + "synthetic: true\n")
        self.schematic(GOOD.replace('"10k"', '"anything"').replace('"0.1W"', '"9W"'))
        self.assertEqual(self.lines(), [])

    def test_a_part_with_no_lcsc_field_fails(self):
        # SOL-HW-PARTS-CHECK.C1: A part whose stated properties or catalogue number differ from the specification record fails the check
        self.schematic(GOOD.replace('\t\t(property "LCSC" "C200")\n', ""))
        self.assertIn("| U1 lcsc | the position U1 lcsc differs: the record states 'C200' and the design has '(absent)'", self.only())

    def test_a_different_lcsc_number_fails(self):
        # SOL-HW-PARTS-CHECK.C1: A part whose stated properties or catalogue number differ from the specification record fails the check
        self.schematic(GOOD.replace('"C200"', '"C100"'))
        self.assertIn("U1 lcsc differs: the record states 'C200' and the design has 'C100'", self.only())

    def test_a_placed_position_the_record_omits_fails(self):
        # SOL-HW-PARTS-CHECK.C1: A part whose stated properties or catalogue number differ from the specification record fails the check
        self.schematic(GOOD, symbol("Device:C", "C1", "1u", "Capacitor_SMD:C_0603", "C100"))
        line = self.only()
        self.assertIn("parts_part | C1 |", line)
        self.assertIn("places the position C1 and the parts specification record does not list it", line)

    def test_every_difference_is_reported_not_only_the_first(self):
        # SOL-HW-PARTS-CHECK.C1: A part whose stated properties or catalogue number differ from the specification record fails the check
        self.schematic(GOOD.replace('"10k"', '"22k"').replace('"C200"', '"C100"'))
        self.assertEqual(len(self.lines()), 2)

    def test_power_symbols_and_symbols_off_the_board_are_no_position(self):
        # SOL-HW-PARTS-CHECK.C1: A part whose stated properties or catalogue number differ from the specification record fails the check
        self.schematic(GOOD, symbol("power:GND", "#PWR01", "GND"), symbol("power:GND", "GND1", "GND"),
                       symbol("Device:R", "R9", "1", on_board="no"))
        self.assertEqual(self.lines(), [])

    def test_a_multi_unit_symbol_is_one_position(self):
        # SOL-HW-PARTS-CHECK.C1: A part whose stated properties or catalogue number differ from the specification record fails the check
        units = "".join(symbol("Chip:CHIP", "U1", "CHIP", "Package:QFN", "C200", unit=n) for n in (1, 2, 3))
        self.schematic(GOOD.replace(symbol("Chip:CHIP", "U1", "CHIP", "Package:QFN", "C200"), ""), units)
        self.assertEqual(self.lines(), [])
        self.schematic(GOOD.replace(symbol("Chip:CHIP", "U1", "CHIP", "Package:QFN", "C200"), ""),
                       units.replace('"CHIP")', '"OTHER")'))
        self.assertEqual(len(self.lines()), 1, "one position, reported once however many units it has")

    def test_units_of_one_reference_disagreeing_on_a_property_fail_naming_it(self):
        # SOL-HW-PARTS-CHECK.C1: A part whose stated properties or catalogue number differ from the specification record fails the check
        chip = symbol("Chip:CHIP", "U1", "CHIP", "Package:QFN", "C200")
        variants = {
            "LCSC": symbol("Chip:CHIP", "U1", "CHIP", "Package:QFN", "C999", unit=2),
            "Value": symbol("Chip:CHIP", "U1", "OTHER", "Package:QFN", "C200", unit=2),
            "Footprint": symbol("Chip:CHIP", "U1", "CHIP", "Package:SOIC", "C200", unit=2),
            "Rating": symbol("Chip:CHIP", "U1", "CHIP", "Package:QFN", "C200", rating="1W", unit=2),
        }
        for name, second in variants.items():
            with self.subTest(name=name):
                self.schematic(GOOD, second)
                found = [line for line in self.lines() if f"disagree on {name}" in line]
                self.assertEqual(len(found), 1, self.lines())
                self.assertEqual(found[0].split(" | ")[2:4], ["parts_part", f"U1 {name}"])
        self.schematic(GOOD, symbol("Chip:CHIP", "U1", "CHIP", "Package:QFN", "C200", unit=2))
        self.assertEqual(self.lines(), [])
        self.assertIn(chip, GOOD)

    def test_a_property_absent_on_one_unit_fails(self):
        # SOL-HW-PARTS-CHECK.C1: A part whose stated properties or catalogue number differ from the specification record fails the check
        self.schematic(GOOD, symbol("Chip:CHIP", "U1", "CHIP", "Package:QFN", None, unit=2))
        found = [line for line in self.lines() if "disagree on LCSC" in line]
        self.assertEqual(len(found), 1, self.lines())
        self.assertIn("(absent)", found[0])

    def test_a_symbol_in_a_hierarchical_sheet_is_a_position(self):
        # SOL-HW-PARTS-CHECK.C1: A part whose stated properties or catalogue number differ from the specification record fails the check
        self.write(self.design.schematic, sheet_file(
            GOOD.replace(symbol("Chip:CHIP", "U1", "CHIP", "Package:QFN", "C200"), "")
            + f'\t(sheet (at 0 0) (property "Sheetname" "s") (property "Sheetfile" "sub.kicad_sch"))\n'))
        self.write(f"{self.folder}/sub.kicad_sch", sheet_file(symbol("Chip:CHIP", "U1", "CHIP", "Package:QFN", "C200")))
        self.assertEqual(self.lines(), [])
        self.write(f"{self.folder}/sub.kicad_sch", sheet_file(symbol("Chip:CHIP", "U1", "BAD", "Package:QFN", "C200")))
        self.assertIn("U1 value differs", self.only())

    def test_a_sheet_used_twice_places_each_reference_its_instances_give(self):
        # SOL-HW-PARTS-CHECK.C1: A part whose stated properties or catalogue number differ from the specification record fails the check
        twice = symbol("Chip:CHIP", "U1", "CHIP", "Package:QFN", "C200", instance=False).replace(
            "\t)\n", '\t\t(instances (project "board" (path "/a" (reference "U1") (unit 1)) (path "/b" (reference "U2") (unit 1))))\n\t)\n')
        self.schematic(GOOD.replace(symbol("Chip:CHIP", "U1", "CHIP", "Package:QFN", "C200"), ""), twice)
        found = self.lines()
        self.assertEqual(len(found), 1, found)
        self.assertIn("the design places the position U2", found[0])

    def test_two_symbols_carrying_one_reference_fail_naming_the_reference(self):
        # SOL-HW-PARTS-CHECK.C1: A part whose stated properties or catalogue number differ from the specification record fails the check
        chip = symbol("Chip:CHIP", "U1", "CHIP", "Package:QFN", "C200")
        same_unit_again = symbol("Chip:CHIP", "U1", "CHIP", "Package:QFN", "C200", unit=2).replace("(unit 2)\n", "(unit 1)\n", 1)
        other_part = symbol("Device:R", "U1", "CHIP", "Package:QFN", "C200", unit=2)
        for second in (chip, same_unit_again, other_part):
            with self.subTest(second=second):
                self.schematic(GOOD, second)
                found = self.lines()
                self.assertEqual(len(found), 1, found)
                self.assertEqual(found[0].split(" | ")[2:4], ["parts_part", "U1"])
                self.assertIn("more than one symbol carries the reference U1", found[0])

    def test_a_reference_repeated_in_another_sheet_fails(self):
        # SOL-HW-PARTS-CHECK.C1: A part whose stated properties or catalogue number differ from the specification record fails the check
        self.write(self.design.schematic, sheet_file(
            GOOD + '\t(sheet (at 0 0) (property "Sheetname" "s") (property "Sheetfile" "sub.kicad_sch"))\n'))
        self.write(f"{self.folder}/sub.kicad_sch", sheet_file(symbol("Chip:CHIP", "U1", "CHIP", "Package:QFN", "C200")))
        self.assertIn("more than one symbol carries the reference U1", self.only())

    def test_a_non_power_symbol_with_a_hash_reference_is_a_position(self):
        # SOL-HW-PARTS-CHECK.C1: A part whose stated properties or catalogue number differ from the specification record fails the check
        self.schematic(GOOD, symbol("Device:R", "#R9", "1k", "Resistor_SMD:R_0402", "C100"))
        self.assertIn("the design places the position #R9", self.only())
        self.write("hw/machine/parts-specification.yaml", RECORD + "  - reference: '#R9'\n    value: 2k\n    lcsc: C100\nsynthetic: true\n")
        self.assertIn("#R9 value differs: the record states '2k' and the design has '1k'", self.only())

    def test_a_power_symbol_is_excluded_by_what_it_is_however_its_reference_is_written(self):
        # SOL-HW-PARTS-CHECK.C1: A part whose stated properties or catalogue number differ from the specification record fails the check
        self.schematic(GOOD, symbol("power:GND", "GND1", "GND"), symbol("power:GND", "#PWR01", "GND"))
        self.assertEqual(self.lines(), [])

    def test_a_position_the_record_lists_twice_fails(self):
        # SOL-HW-PARTS-CHECK.C3: A design with no usable specification record or catalogue extract fails, and a synthetic one passes only a design not for manufacture
        self.write("hw/machine/parts-specification.yaml", RECORD + "  - reference: R1\n    lcsc: C100\nsynthetic: true\n")
        self.assertIn("the position R1 is listed more than once", self.only())


class PartsAgainstTheExtract(Design):
    def test_a_number_absent_from_the_extract_fails_naming_the_position(self):
        # SOL-HW-PARTS-CHECK.C2: A part the catalogue extract does not show in stock fails the check, and so does an extract past its age limit
        self.schematic(GOOD.replace('"C200"', '"C999"'))
        self.write("hw/machine/parts-specification.yaml", RECORD.replace("C200", "C999") + "synthetic: true\n")
        line = self.only()
        self.assertEqual(line, "VIOLATION | hw/machine/board/board.kicad_pro | parts_catalogue | U1 lcsc | the position U1 has "
                               "the catalogue number C999, which the catalogue extract does not list")

    def test_a_part_with_no_stock_fails(self):
        # SOL-HW-PARTS-CHECK.C2: A part the catalogue extract does not show in stock fails the check, and so does an extract past its age limit
        self.write("hw/machine/catalogue-extract.yaml", EXTRACT.replace("stock: 3", "stock: 0") + "synthetic: true\n")
        self.assertIn("U1 has the catalogue number C200, which the catalogue extract shows with no stock", self.only())

    def test_a_stock_that_is_not_a_whole_number_of_zero_or_more_is_a_malformed_extract(self):
        # SOL-HW-PARTS-CHECK.C2: A part the catalogue extract does not show in stock fails the check, and so does an extract past its age limit
        for stock in ("-2", "2.5", "many", "true", "null"):
            with self.subTest(stock=stock):
                self.write("hw/machine/catalogue-extract.yaml", EXTRACT.replace("stock: 3", f"stock: {stock}") + "synthetic: true\n")
                found = [v for v in self.run_check() if v.rule == "parts_catalogue"]
                self.assertEqual(len(found), 1, found)
                self.assertIn("entries[1].stock", found[0].location)
                self.assertIn("not a whole number of zero or more", found[0].message)

    def test_an_entry_showing_zero_stock_that_no_part_uses_passes(self):
        # SOL-HW-PARTS-CHECK.C2: A part the catalogue extract does not show in stock fails the check, and so does an extract past its age limit
        self.write("hw/machine/catalogue-extract.yaml", EXTRACT + "  - lcsc: C300\n    library_class: basic\n    stock: 0\n    unit_price: 1\nsynthetic: true\n")
        self.assertEqual(self.lines(), [])

    def test_an_entry_showing_zero_stock_fails_only_the_part_using_it(self):
        # SOL-HW-PARTS-CHECK.C2: A part the catalogue extract does not show in stock fails the check, and so does an extract past its age limit
        self.write("hw/machine/catalogue-extract.yaml", EXTRACT.replace("stock: 500", "stock: 0") + "synthetic: true\n")
        found = self.lines()
        self.assertEqual(len(found), 2, found)
        self.assertTrue(all("parts_catalogue" in line and "shows with no stock" in line for line in found))
        self.assertEqual({line.split(" | ")[3] for line in found}, {"R1 lcsc", "R2 lcsc"})

    def test_two_entries_carrying_one_catalogue_number_are_a_malformed_extract_naming_the_number(self):
        # SOL-HW-PARTS-CHECK.C2: A part the catalogue extract does not show in stock fails the check, and so does an extract past its age limit
        for stock in (0, 9):
            with self.subTest(stock=stock):
                self.write("hw/machine/catalogue-extract.yaml", EXTRACT + "  - lcsc: C200\n    library_class: basic\n    stock: %d\n    unit_price: 1\nsynthetic: true\n" % stock)
                found = [v for v in self.run_check() if v.rule == "parts_catalogue" and "entries[" in v.location]
                self.assertEqual(len(found), 1, found)
                self.assertIn("entries[2].lcsc", found[0].location)
                self.assertIn("C200, which another entry also carries", found[0].message)

    def test_an_extract_past_its_own_age_limit_fails(self):
        # SOL-HW-PARTS-CHECK.C2: A part the catalogue extract does not show in stock fails the check, and so does an extract past its age limit
        line = self.only(today=datetime.date(2026, 11, 1))
        self.assertIn("parts_catalogue | " + "hw/machine/catalogue-extract.yaml read_on", line)
        self.assertIn("31 days before today (2026-11-01), past the 30 days it allows itself", line)

    def test_an_extract_exactly_at_its_age_limit_passes(self):
        # SOL-HW-PARTS-CHECK.C2: A part the catalogue extract does not show in stock fails the check, and so does an extract past its age limit
        self.assertEqual(self.lines(today=datetime.date(2026, 10, 31)), [])

    def test_an_extract_dated_later_than_today_fails(self):
        # SOL-HW-PARTS-CHECK.C2: A part the catalogue extract does not show in stock fails the check, and so does an extract past its age limit
        self.assertIn("is dated 2026-10-01, later than today (2026-09-30)", self.only(today=datetime.date(2026, 9, 30)))

    def test_the_catalogue_is_never_fetched(self):
        # SOL-HW-PARTS-CHECK.C2: A part the catalogue extract does not show in stock fails the check, and so does an extract past its age limit
        def refuse(*args, **kwargs):
            raise AssertionError("the parts check opened a network connection")
        with mock.patch.object(socket.socket, "connect", refuse), mock.patch.object(socket, "create_connection", refuse):
            self.assertEqual(self.lines(), [])
            self.schematic(GOOD.replace('"C200"', '"C999"'))
            self.assertTrue(self.lines())


class UsableRecords(Design):
    def test_a_design_with_no_specification_record_fails(self):
        # SOL-HW-PARTS-CHECK.C3: A design with no usable specification record or catalogue extract fails, and a synthetic one passes only a design not for manufacture
        self.remove("hw/machine/parts-specification.yaml")
        line = self.only()
        self.assertIn("parts_record", line)
        self.assertIn("there is no parts-specification.yaml in the design's folder or any folder above it", line)

    def test_a_design_with_no_catalogue_extract_fails(self):
        # SOL-HW-PARTS-CHECK.C3: A design with no usable specification record or catalogue extract fails, and a synthetic one passes only a design not for manufacture
        self.remove("hw/machine/catalogue-extract.yaml")
        self.assertIn("there is no catalogue-extract.yaml in the design's folder or any folder above it", self.only())

    def test_the_record_is_found_at_or_above_the_design_and_the_nearest_wins(self):
        # SOL-HW-PARTS-CHECK.C3: A design with no usable specification record or catalogue extract fails, and a synthetic one passes only a design not for manufacture
        self.write(f"{self.folder}/parts-specification.yaml", "positions:\n  - reference: Z9\n    lcsc: C100\nsynthetic: true\n")
        self.assertEqual(self.rules(), ["parts_part"], "the nearer record lists only Z9, so every placed part is omitted from it")
        self.assertIn("hw/machine/board/parts-specification.yaml", board_check.find_record(
            self.root, self.folder, set(), board_check.PARTS_RECORD_NAME))

    def test_a_file_that_cannot_be_parsed_fails(self):
        # SOL-HW-PARTS-CHECK.C3: A design with no usable specification record or catalogue extract fails, and a synthetic one passes only a design not for manufacture
        for name in ("parts-specification.yaml", "catalogue-extract.yaml"):
            with self.subTest(name=name):
                self.write(f"hw/machine/{name}", "positions: [unclosed\n")
                found = [v for v in self.run_check() if "cannot be parsed" in v.message]
                self.assertEqual(len(found), 1, found)
                self.assertEqual(found[0].rule, "parts_record")
                self.setUp()

    def test_a_file_that_is_not_a_mapping_fails(self):
        # SOL-HW-PARTS-CHECK.C3: A design with no usable specification record or catalogue extract fails, and a synthetic one passes only a design not for manufacture
        self.write("hw/machine/parts-specification.yaml", "- reference: R1\n")
        self.assertIn("it is not a mapping of keys", self.only())

    def test_a_key_given_twice_fails(self):
        # SOL-HW-PARTS-CHECK.C3: A design with no usable specification record or catalogue extract fails, and a synthetic one passes only a design not for manufacture
        self.write("hw/machine/catalogue-extract.yaml", EXTRACT + "max_age_days: 99999\n")
        self.assertIn("gives the key 'max_age_days' more than once", self.only())

    def test_a_record_missing_a_required_key_fails(self):
        # SOL-HW-PARTS-CHECK.C3: A design with no usable specification record or catalogue extract fails, and a synthetic one passes only a design not for manufacture
        cases = [("parts-specification.yaml", RECORD, "    lcsc: C200\n", "", "lacks lcsc"),
                 ("parts-specification.yaml", RECORD, "  - reference: U1\n    value: CHIP\n", "  - value: CHIP\n", "lacks reference"),
                 ("parts-specification.yaml", RECORD, "positions:", "position:", "lacks positions"),
                 ("catalogue-extract.yaml", EXTRACT, "read_on: 2026-10-01\n", "", "lacks read_on"),
                 ("catalogue-extract.yaml", EXTRACT, "max_age_days: 30\n", "", "lacks max_age_days"),
                 ("catalogue-extract.yaml", EXTRACT, "entries:", "entry:", "lacks entries"),
                 ("catalogue-extract.yaml", EXTRACT, "    unit_price: 1.5\n", "", "lacks unit_price"),
                 ("catalogue-extract.yaml", EXTRACT, "    stock: 3\n", "", "lacks stock"),
                 ("catalogue-extract.yaml", EXTRACT, "    library_class: extended\n", "", "lacks library_class")]
        for name, base, old, new, said in cases:
            with self.subTest(name=name, said=said):
                self.setUp()
                self.write(f"hw/machine/{name}", base.replace(old, new, 1) + "synthetic: true\n")
                found = [v for v in self.run_check() if v.rule == "parts_record"]
                self.assertTrue(any(said in v.message for v in found), [v.line() for v in found])

    def test_a_misspelled_key_in_a_position_fails_rather_than_going_uncompared(self):
        # SOL-HW-PARTS-CHECK.C3: A design with no usable specification record or catalogue extract fails, and a synthetic one passes only a design not for manufacture
        self.write("hw/machine/parts-specification.yaml", RECORD.replace("value: 10k", "valeu: 10k") + "synthetic: true\n")
        self.assertIn("holds the key 'valeu', which is not one a position has", self.only())

    def test_a_record_and_an_extract_that_list_nothing_fail(self):
        # SOL-HW-PARTS-CHECK.C3: A design with no usable specification record or catalogue extract fails, and a synthetic one passes only a design not for manufacture
        self.write("hw/machine/parts-specification.yaml", "positions: []\nsynthetic: true\n")
        self.assertIn("lists no positions", [v for v in self.run_check() if v.rule == "parts_record"][0].message)
        self.setUp()
        self.write("hw/machine/catalogue-extract.yaml", "read_on: 2026-10-01\nmax_age_days: 30\nentries: []\nsynthetic: true\n")
        self.assertIn("lists no entries", self.only())

    def test_a_design_that_places_nothing_still_needs_a_record_listing_something(self):
        # SOL-HW-PARTS-CHECK.C3: A design with no usable specification record or catalogue extract fails, and a synthetic one passes only a design not for manufacture
        self.schematic()
        self.write("hw/machine/parts-specification.yaml", "positions: []\nsynthetic: true\n")
        self.assertEqual(self.rules(), ["parts_record"])

    def test_an_age_limit_that_is_not_a_whole_number_above_zero_fails(self):
        # SOL-HW-PARTS-CHECK.C3: A design with no usable specification record or catalogue extract fails, and a synthetic one passes only a design not for manufacture
        for limit in ("0", "-1", "1.5", "soon"):
            with self.subTest(limit=limit):
                self.write("hw/machine/catalogue-extract.yaml", EXTRACT.replace("max_age_days: 30", f"max_age_days: {limit}") + "synthetic: true\n")
                self.assertIn("max_age_days is", self.only())

    def test_a_date_that_is_not_a_calendar_date_fails(self):
        # SOL-HW-PARTS-CHECK.C3: A design with no usable specification record or catalogue extract fails, and a synthetic one passes only a design not for manufacture
        self.write("hw/machine/catalogue-extract.yaml", EXTRACT.replace("2026-10-01", "'01/10/2026'") + "synthetic: true\n")
        self.assertIn("is not a valid calendar date", self.only())

    def test_a_synthetic_record_or_extract_passes_only_a_design_not_for_manufacture(self):
        # SOL-HW-PARTS-CHECK.C3: A design with no usable specification record or catalogue extract fails, and a synthetic one passes only a design not for manufacture
        found = self.lines(not_for_manufacture=False)
        self.assertEqual(len(found), 2, found)
        self.assertTrue(any("the parts specification record is marked synthetic" in line for line in found))
        self.assertTrue(any("the catalogue extract is marked synthetic" in line for line in found))
        self.assertEqual(self.lines(not_for_manufacture=True), [])

    def test_a_record_and_extract_that_are_not_synthetic_pass_an_orderable_design(self):
        # SOL-HW-PARTS-CHECK.C3: A design with no usable specification record or catalogue extract fails, and a synthetic one passes only a design not for manufacture
        self.write("hw/machine/parts-specification.yaml", RECORD)
        self.write("hw/machine/catalogue-extract.yaml", EXTRACT + "synthetic: false\n")
        self.assertEqual(self.lines(not_for_manufacture=False), [])

    def test_a_synthetic_marker_that_is_not_a_boolean_fails(self):
        # SOL-HW-PARTS-CHECK.C3: A design with no usable specification record or catalogue extract fails, and a synthetic one passes only a design not for manufacture
        self.write("hw/machine/parts-specification.yaml", RECORD + "synthetic: yes please\n")
        self.assertIn("synthetic is 'yes please'", self.only())

    def test_a_record_the_repository_does_not_track_fails(self):
        # SOL-HW-PARTS-CHECK.C3: A design with no usable specification record or catalogue extract fails, and a synthetic one passes only a design not for manufacture
        files = [os.path.relpath(os.path.join(d, n), self.root).replace(os.sep, "/")
                 for d, _, names in os.walk(self.root) for n in names]
        files.remove("hw/machine/parts-specification.yaml")
        with mock.patch.object(board_check.Repository, "untracked", return_value="is not tracked in the repository"):
            found = board_check.check_parts(self.yaml, self.root, self.design, board_check.Repository(self.root, files),
                                            TODAY, True)
        self.assertEqual([v.rule for v in found], ["parts_record"])
        self.assertIn("is not tracked in the repository", found[0].message)

    def test_an_unusable_record_is_reported_without_hiding_the_extracts_findings(self):
        # SOL-HW-PARTS-CHECK.C3: A design with no usable specification record or catalogue extract fails, and a synthetic one passes only a design not for manufacture
        self.remove("hw/machine/parts-specification.yaml")
        self.write("hw/machine/catalogue-extract.yaml", EXTRACT.replace("stock: 3", "stock: 0") + "synthetic: true\n")
        self.assertEqual(self.rules(), ["parts_catalogue", "parts_record"])


class WhatTheRoundReads(Design):
    def test_a_designs_reads_include_its_specification_record_and_extract_wherever_they_sit(self):
        # SOL-HW-PARTS-CHECK.C5: Every board design the repository tracks, both throwaway designs included, carries a synthetic specification record and a synthetic catalogue extract and passes the parts check, and the round gate runs its board tier on a change to any specification record or catalogue extract
        import subprocess
        subprocess.run(["git", "init", "-q", self.root], check=True)
        subprocess.run(["git", "-C", self.root, "add", "-A"], check=True)
        reads = board_check.design_reads(self.root, board_check.tracked_files("git", self.root))
        self.assertIn("hw/machine/parts-specification.yaml", reads)
        self.assertIn("hw/machine/catalogue-extract.yaml", reads)

    def test_every_tracked_design_in_the_repository_passes_the_parts_check(self):
        # SOL-HW-PARTS-CHECK.C5: Every board design the repository tracks, both throwaway designs included, carries a synthetic specification record and a synthetic catalogue extract and passes the parts check, and the round gate runs its board tier on a change to any specification record or catalogue extract
        files = board_check.tracked_files("git", REPO)
        repository = board_check.Repository(REPO, files)
        designs, _, _ = board_check.discover(REPO, files)
        self.assertGreaterEqual(len(designs), 2)
        for design in designs:
            with self.subTest(design=design.project):
                self.assertEqual(board_check.check_parts(self.yaml, REPO, design, repository, datetime.date.today(), True), [])


if __name__ == "__main__":
    unittest.main()
