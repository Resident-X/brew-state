#!/usr/bin/env python3
"""The pre-order check's do-not-populate rule, driven on synthetic designs with no KiCad involved.

The layout marks a part do-not-populate with its footprint's attribute, the
schematic with its symbol's attribute, and the parts specification record with
a position's `fitted` key. The rule holds the three to one answer, and fails a
symbol whose text field named dnp disagrees with its attribute. Every design
here is written from text, with generic references.
"""

from __future__ import annotations

import os
import sys
import unittest

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import board_check  # noqa: E402
import board_fixtures  # noqa: E402
import sexpr  # noqa: E402
import test_board_parts as parts  # noqa: E402
import test_severity_policy as policy_tests  # noqa: E402
import test_workmanship_acceptance as acceptance_tests  # noqa: E402

RULE = "dnp_agreement"


def footprint(reference, dnp=False, x=10):
    attributes = "(attr smd dnp)" if dnp else "(attr smd)"
    return (f'(footprint "synth:R" (layer "F.Cu") (uuid {board_fixtures.uuid()}) (at {x} 10) {attributes} '
            f'(property "Reference" "{reference}" (at 0 -2) (layer "F.SilkS") (uuid {board_fixtures.uuid()})))')


def symbol(reference, dnp="no", text=None, unit=1, field="dnp"):
    """A symbol of `reference` whose do-not-populate attribute is `dnp` and whose text field `field` says `text`, if any."""
    extra = f'\t\t(property "{field}" "{text}")\n' if text is not None else ""
    return (f'\t(symbol\n\t\t(lib_id "Device:R")\n\t\t(unit {unit})\n\t\t(on_board yes)\n\t\t(dnp {dnp})\n'
            f'\t\t(property "Reference" "{reference}")\n\t\t(property "Value" "1k")\n{extra}'
            f'\t\t(instances (project "board" (path "/root" (reference "{reference}") (unit {unit}))))\n\t)\n')


def record(*positions):
    """A parts specification record of `positions`, each (reference, fitted) with fitted '' for the key left out."""
    lines = ["positions:"]
    for reference, fitted in positions:
        lines += [f"  - reference: {reference}", "    lcsc: C1"] + ([f"    fitted: {fitted}"] if fitted else [])
    return "\n".join(lines) + "\nsynthetic: true\n"


class Agreement(parts.Design):
    def setUp(self):
        super().setUp()
        self.footprints = []

    def judge(self, footprints, symbols, records="", sheets=None):
        """The lines of the rule for a design of `footprints` and `symbols`, with the parts record `records` ('' for none)."""
        self.write(self.design.schematic, parts.sheet_file(*symbols))
        for path, text in (sheets or {}).items():
            self.write(f"{self.folder}/{path}", text)
        if records:
            self.write("hw/machine/parts-specification.yaml", records)
        elif os.path.exists(os.path.join(self.root, "hw/machine/parts-specification.yaml")):
            self.remove("hw/machine/parts-specification.yaml")
        files = [os.path.relpath(os.path.join(d, n), self.root).replace(os.sep, "/")
                 for d, _, names in os.walk(self.root) for n in names]
        tree = sexpr.parse_one(board_fixtures.layout(footprints))
        return board_check.dnp_agreement(self.design, tree, self.yaml, self.root, board_check.Repository(self.root, files), True)

    def named(self, found, reference):
        return [v for v in found if v.rule == RULE and v.location.startswith(reference)]


class LayoutAndSchematicDisagree(Agreement):
    def test_a_part_the_layout_marks_and_the_schematic_leaves_fitted_fails_naming_the_part_and_the_sources(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-DO-NOT-POPULATE-TO-ONE-ANSWER.C1: A part the layout marks do-not-populate and the schematic does not, or the reverse, fails the design, naming the part
        found = self.judge([footprint("R1", True), footprint("R2")], [symbol("R1"), symbol("R2")])
        self.assertEqual([v.location for v in found], ["R1"])
        self.assertIn("the layout marks it not populated", found[0].message)
        self.assertIn("the schematic marks it fitted", found[0].message)

    def test_a_part_the_schematic_marks_and_the_layout_leaves_fitted_fails_naming_the_part(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-DO-NOT-POPULATE-TO-ONE-ANSWER.C1: A part the layout marks do-not-populate and the schematic does not, or the reverse, fails the design, naming the part
        found = self.judge([footprint("R1"), footprint("R2")], [symbol("R1", "yes"), symbol("R2")])
        self.assertEqual([v.location for v in found], ["R1"])
        self.assertIn("the schematic marks it not populated", found[0].message)
        self.assertIn("the layout marks it fitted", found[0].message)

    def test_every_disagreeing_part_is_named_once_and_a_part_a_source_does_not_list_is_not_judged_by_it(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-DO-NOT-POPULATE-TO-ONE-ANSWER.C1: A part the layout marks do-not-populate and the schematic does not, or the reverse, fails the design, naming the part
        found = self.judge([footprint("R1", True), footprint("R2"), footprint("R3", True)],
                           [symbol("R1"), symbol("R2", "yes"), symbol("R9", "yes")])
        self.assertEqual(sorted(v.location for v in found), ["R1", "R2"])

    def test_a_symbol_on_a_further_sheet_is_read_and_any_unit_marked_marks_the_part(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-DO-NOT-POPULATE-TO-ONE-ANSWER.C1: A part the layout marks do-not-populate and the schematic does not, or the reverse, fails the design, naming the part
        sheet = ('\t(sheet (at 0 0) (size 10 10)\n\t\t(property "Sheetname" "second")\n'
                 '\t\t(property "Sheetfile" "second.kicad_sch")\n\t)\n')
        second = parts.sheet_file(symbol("R4", "yes"))
        found = self.judge([footprint("R4"), footprint("R5", True)], [sheet, symbol("R5", "yes", unit=1)],
                           sheets={"second.kicad_sch": second})
        self.assertEqual([v.location for v in found], ["R4"])
        self.assertEqual(self.judge([footprint("R4", True)], [sheet], sheets={"second.kicad_sch": second}), [])

    def test_units_of_one_part_that_differ_fail_and_one_marked_unit_marks_the_part(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-DO-NOT-POPULATE-TO-ONE-ANSWER.C1: A part the layout marks do-not-populate and the schematic does not, or the reverse, fails the design, naming the part
        found = self.judge([footprint("U1", True)], [symbol("U1", "yes", unit=1), symbol("U1", "no", unit=2)])
        self.assertEqual([v.location for v in found], ["U1"])
        self.assertIn("units of U1 disagree", found[0].message)
        self.assertEqual(self.judge([footprint("U1", True)], [symbol("U1", "yes", unit=1), symbol("U1", "yes", unit=2)]), [])


class TheRecordAgrees(Agreement):
    def test_a_position_the_record_marks_not_fitted_while_the_layout_and_schematic_fit_it_fails_naming_it(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-DO-NOT-POPULATE-TO-ONE-ANSWER.C2: A part the parts record states as not fitted and the layout or the schematic marks as fitted, or the reverse, fails the design, naming the part
        found = self.judge([footprint("R1")], [symbol("R1")], record(("R1", '"no"')))
        self.assertEqual([v.location for v in found], ["R1"])
        self.assertIn("the parts record marks it not populated", found[0].message)
        self.assertIn("the layout marks it fitted", found[0].message)

    def test_a_part_both_the_layout_and_the_schematic_mark_that_the_record_leaves_fitted_fails(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-DO-NOT-POPULATE-TO-ONE-ANSWER.C2: A part the parts record states as not fitted and the layout or the schematic marks as fitted, or the reverse, fails the design, naming the part
        found = self.judge([footprint("R1", True)], [symbol("R1", "yes")], record(("R1", "")))
        self.assertEqual([v.location for v in found], ["R1"])
        self.assertIn("the parts record marks it fitted", found[0].message)

    def test_the_record_alone_against_one_of_the_two_fails_and_the_other_two_agreeing_does_not_hide_it(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-DO-NOT-POPULATE-TO-ONE-ANSWER.C2: A part the parts record states as not fitted and the layout or the schematic marks as fitted, or the reverse, fails the design, naming the part
        for footprints, symbols in (([footprint("R1", True)], [symbol("R1")]), ([footprint("R1")], [symbol("R1", "yes")])):
            with self.subTest(layout=len(footprints[0]) and "dnp" in footprints[0]):
                found = self.judge(footprints, symbols, record(("R1", '"no"')))
                self.assertEqual([v.location for v in found], ["R1"])

    def test_a_design_with_no_record_is_judged_on_the_layout_and_the_schematic_alone(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-DO-NOT-POPULATE-TO-ONE-ANSWER.C2: A part the parts record states as not fitted and the layout or the schematic marks as fitted, or the reverse, fails the design, naming the part
        self.assertEqual(self.judge([footprint("R1", True)], [symbol("R1", "yes")]), [])
        self.assertEqual([v.location for v in self.judge([footprint("R1", True)], [symbol("R1")])], ["R1"])

    def test_the_fitted_key_takes_the_string_no_and_nothing_else_a_bare_yaml_no_and_a_yes_included(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-DO-NOT-POPULATE-TO-ONE-ANSWER.C2: A part the parts record states as not fitted and the layout or the schematic marks as fitted, or the reverse, fails the design, naming the part
        for written, said in (("'yes'", "'yes'"), ("'false'", "'false'"), ("no", "False"), ("true", "True")):
            with self.subTest(written=written):
                self.write("hw/machine/parts-specification.yaml", record(("R1", written)))
                found = [v for v in parts.board_check.check_parts(self.yaml, self.root, self.design,
                         board_check.Repository(self.root, ["hw/machine/parts-specification.yaml",
                                                            "hw/machine/catalogue-extract.yaml", self.design.project,
                                                            self.design.layout, self.design.schematic]),
                         parts.TODAY, True) if v.rule == "parts_record"]
                self.assertTrue(any("positions[0].fitted" in v.location and said in v.message for v in found),
                                [v.line() for v in found])

    def test_a_record_that_cannot_be_read_is_no_source_and_the_other_two_are_still_compared(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-DO-NOT-POPULATE-TO-ONE-ANSWER.C2: A part the parts record states as not fitted and the layout or the schematic marks as fitted, or the reverse, fails the design, naming the part
        found = self.judge([footprint("R1", True)], [symbol("R1")], "positions: [unclosed\n")
        self.assertEqual([v.location for v in found], ["R1"])
        self.assertNotIn("the parts record marks", found[0].message)


class TheTextFieldAgreesWithTheAttribute(Agreement):
    def test_a_symbol_whose_text_field_says_do_not_populate_while_its_attribute_says_fitted_fails_naming_it(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-DO-NOT-POPULATE-TO-ONE-ANSWER.C3: A schematic symbol whose text field says do-not-populate while its attribute says fitted fails the design
        found = self.judge([footprint("R1")], [symbol("R1", "no", "true")])
        self.assertEqual([v.location for v in found], ["R1 unit 1"])
        self.assertIn("text field dnp that says do not populate while its do-not-populate attribute says fitted", found[0].message)

    def test_the_field_is_found_in_any_case_and_the_reverse_difference_fails_too(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-DO-NOT-POPULATE-TO-ONE-ANSWER.C3: A schematic symbol whose text field says do-not-populate while its attribute says fitted fails the design
        for field in ("DNP", "Dnp"):
            found = self.judge([footprint("R1")], [symbol("R1", "no", "YES", field=field)])
            self.assertEqual([v.location for v in found], ["R1 unit 1"], field)
        found = self.judge([footprint("R1", True)], [symbol("R1", "yes", "false")])
        self.assertEqual([v.location for v in found], ["R1 unit 1"])
        self.assertIn("says fitted while its do-not-populate attribute says do not populate", found[0].message)

    def test_a_field_that_agrees_with_the_attribute_or_a_field_with_another_name_passes(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-DO-NOT-POPULATE-TO-ONE-ANSWER.C3: A schematic symbol whose text field says do-not-populate while its attribute says fitted fails the design
        self.assertEqual(self.judge([footprint("R1", True), footprint("R2")],
                                    [symbol("R1", "yes", "true"), symbol("R2", "no", "false")]), [])
        self.assertEqual(self.judge([footprint("R1")], [symbol("R1", "no", "true", field="dnp_note")]), [])


class AgreeingDesignsPass(Agreement):
    def test_a_design_whose_layout_schematic_and_record_agree_passes_with_and_without_parts_not_fitted(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-DO-NOT-POPULATE-TO-ONE-ANSWER.C4: A design whose layout, schematic and parts record agree passes
        self.assertEqual(self.judge([footprint("R1"), footprint("R2")], [symbol("R1"), symbol("R2")],
                                    record(("R1", ""), ("R2", ""))), [])
        self.assertEqual(self.judge([footprint("R1", True), footprint("R2")],
                                    [symbol("R1", "yes", "true"), symbol("R2", "no", "false")],
                                    record(("R1", '"no"'), ("R2", ""))), [])


class NoRecordWaivesADisagreement(policy_tests.Policed):
    def line(self):
        return board_check.Violation(acceptance_tests.PROJECT, RULE, "R1", "R1 is not held to one answer on do not populate")

    def test_a_workmanship_acceptance_entry_for_the_rule_covers_nothing_and_fails_naming_the_rules_it_accepts(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-DO-NOT-POPULATE-TO-ONE-ANSWER.C5: No acceptance record waives a do-not-populate disagreement
        self.assertNotIn(RULE, board_check.ACCEPTABLE_WORKMANSHIP)
        left, accepted = self.judge([self.line()], [acceptance_tests.entry(rule=RULE, scope="R1")])
        self.assertEqual(accepted, [])
        self.assertIn("R1", [v.location for v in left if v.rule == RULE])
        failures = [v for v in left if v.rule == "workmanship_acceptance"]
        self.assertEqual(len(failures), 1)
        self.assertIn(f"names the rule {RULE}, which the record does not accept", failures[0].message)

    def test_a_severity_policy_entry_for_the_rule_is_refused_and_the_line_stays_a_violation_with_no_warning(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-DO-NOT-POPULATE-TO-ONE-ANSWER.C5: No acceptance record waives a do-not-populate disagreement
        self.assertNotIn(RULE, board_check.POLICY_CLASSES)
        for severity in ("WARNING", "ERROR"):
            with self.subTest(severity=severity):
                left, warnings, _ = self.run_policy([self.line()], [policy_tests.entry(RULE, severity)])
                self.assertEqual(warnings, [])
                self.assertIn(RULE, [v.rule for v in left])
                self.assertIn("severity_policy", [v.rule for v in left])


class TheHardwareNotesStateTheRule(unittest.TestCase):
    def test_the_notes_and_the_verify_task_state_the_rule_and_the_three_sources_it_compares(self):
        # SOL-PRE-ORDER-CHECK-HOLDS-DO-NOT-POPULATE-TO-ONE-ANSWER.C7: The hardware notes state the rule and the three sources it compares
        repository = os.path.dirname(os.path.dirname(TOOLS))
        with open(os.path.join(repository, "hardware", "README.md"), encoding="utf-8") as handle:
            notes = handle.read()
        with open(os.path.join(repository, "Taskfile.yml"), encoding="utf-8") as handle:
            taskfile = handle.read()
        verify = taskfile[taskfile.index("  hw:verify:"):]
        verify = verify[: verify.index("\n\n")]
        paragraph = notes[notes.index("**Do not populate** (`dnp_agreement`)"):]
        paragraph = paragraph[: paragraph.index("\n")]
        for words in ("the layout", "the schematic", "the parts specification record", "`fitted: \"no\"`", "naming the reference",
                      "text field named `dnp`", "No acceptance record waives it"):
            self.assertIn(words, paragraph)
        self.assertIn("| `dnp_agreement` |", notes)
        self.assertIn("`fitted`", notes[notes.index("**The specification record**"):])
        self.assertIn("dnp_agreement", notes[notes.index("task hw:prove` adds"):])
        for words in ("do-not-populate footprints", "do-not-populate symbols", "whose `fitted` key is `\"no\"`", "no acceptance record waives that"):
            self.assertIn(words, verify)
        import yaml
        with open(os.path.join(repository, "Taskfile.yml"), encoding="utf-8") as handle:
            parsed = yaml.safe_load(handle)
        self.assertIn("whose `fitted` key is", parsed["tasks"]["hw:verify"]["desc"])


if __name__ == "__main__":
    unittest.main()
