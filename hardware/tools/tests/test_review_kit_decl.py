#!/usr/bin/env python3
"""The review kit's declaration: loading and validating it, the schema derived from its tables, and its prompt templates.

Synthetic declarations only; nothing is started and nothing is read from a review folder.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import review_kit_fixtures as fx  # noqa: E402
from review_kit import decl, messages, results  # noqa: E402

FILE = "caller.json"


def refused(raw):
    try:
        decl.parse(json.dumps(raw), FILE)
    except decl.DeclarationError as error:
        return error
    raise AssertionError("the declaration was accepted")


def mutated(path, value):
    """The base declaration with one nested value replaced; a value of Ellipsis removes it."""
    raw = fx.declaration_dict()
    node = raw
    for key in path[:-1]:
        node = node[key]
    if value is Ellipsis:
        del node[path[-1]]
    else:
        node[path[-1]] = value
    return raw


class LoadTests(unittest.TestCase):
    def test_base_declaration_loads(self):
        # SOL-HW-REVIEW-KIT.C5: the declaration is a file the kit loads and validates
        with tempfile.TemporaryDirectory() as folder:
            path = fx.write(folder, "caller.json", fx.declaration_text())
            loaded = decl.load(path)
        self.assertEqual(list(loaded.units), ["u1", "u2", "u3", "u4"])
        self.assertEqual(loaded.units["u2"].couples_with, ("u3",))
        self.assertEqual(loaded.artefacts["facts.txt"].producer, "make_facts")
        self.assertEqual(loaded.needed, ["facts.txt", "guide.md", "view_a.png", "view_b.png"])
        self.assertEqual(loaded.budget.context_tokens, 100000)

    def test_unit_needing_an_unlisted_artefact_is_refused_naming_file_unit_and_artefact(self):
        # SOL-HW-REVIEW-KIT.C5: a unit that needs an artefact the declaration does not list is refused at load
        error = refused(mutated(["units", "u1", "needs"], ["guide.md", "view_zzz.png"]))
        line = "\n".join(error.lines)
        self.assertIn(FILE, line)
        self.assertIn("unit u1", line)
        self.assertIn("view_zzz.png", line)
        self.assertEqual(len(error.lines), 1)

    def test_unit_coupled_with_a_missing_unit_is_refused(self):
        # SOL-HW-REVIEW-KIT.C5: a unit coupled with a unit that does not exist is refused at load
        error = refused(mutated(["units", "u4", "couples_with"], ["u9"]))
        self.assertEqual(error.lines, [f"{FILE}: unit u4: unit u4 is coupled with 'u9', which is not a unit of the declaration"])

    def test_unit_coupled_with_itself_is_refused(self):
        # SOL-HW-REVIEW-KIT.C5: a unit coupled with a unit that does not exist is refused at load
        self.assertIn("coupled with itself", refused(mutated(["units", "u4", "couples_with"], ["u4"])).lines[0])

    def test_table_key_that_is_not_a_column_is_refused(self):
        # SOL-HW-REVIEW-KIT.C5: a table whose key is not one of its columns is refused at load
        raw = fx.declaration_dict()
        raw["schema"]["tables"][1]["key"] = "Nowhere"
        error = refused(raw)
        self.assertIn(FILE, error.lines[0])
        self.assertIn("table Findings", error.lines[0])
        self.assertIn("'Nowhere'", error.lines[0])

    def test_empty_verdict_set_is_refused(self):
        # SOL-HW-REVIEW-KIT.C5: a verdict set that is empty is refused at load
        raw = fx.declaration_dict()
        raw["schema"]["tables"][0]["verdicts"] = []
        error = refused(raw)
        self.assertIn("table Verdicts", error.lines[0])
        self.assertIn("verdict set is empty", error.lines[0])

    def test_verdicts_without_a_verdict_column_and_duplicate_verdicts_are_refused(self):
        # SOL-HW-REVIEW-KIT.C5: a verdict set that is empty is refused at load
        raw = fx.declaration_dict()
        raw["schema"]["tables"][1]["verdicts"] = ["pass"]
        self.assertIn("no verdict column", refused(raw).lines[0])
        raw = fx.declaration_dict()
        raw["schema"]["tables"][0]["verdicts"] = ["pass", "pass"]
        self.assertIn("holds a verdict twice", refused(raw).lines[0])

    def test_template_slot_the_unit_does_not_fill_is_refused(self):
        # SOL-HW-REVIEW-KIT.C5: a template slot the unit does not fill is refused at load
        error = refused(mutated(["units", "u3", "values"], {}))
        self.assertEqual(len(error.lines), 1)
        self.assertIn("unit u3", error.lines[0])
        self.assertIn("{area}", error.lines[0])
        self.assertIn("template 't'", error.lines[0])

    def test_value_with_no_slot_is_refused_naming_unit_and_slot(self):
        # SOL-HW-REVIEW-KIT.C5: a template with a value no slot takes is refused at load naming the unit and the slot
        raw = fx.declaration_dict()
        raw["units"]["u3"]["values"]["colour"] = "red"
        error = refused(raw)
        self.assertEqual(len(error.lines), 1)
        self.assertIn("unit u3", error.lines[0])
        self.assertIn("'colour'", error.lines[0])

    def test_built_in_slots_need_no_value_and_cannot_be_overridden(self):
        # SOL-HW-REVIEW-KIT.C5: a unit's prompt is built by filling the named slots with the unit's items and the declared values
        raw = fx.declaration_dict()
        raw["units"]["u3"]["values"]["items"] = "mine"
        self.assertIn("which the kit fills itself", refused(raw).lines[0])

    def test_unknown_template_and_malformed_braces_are_refused(self):
        # SOL-HW-REVIEW-KIT.C5: a template slot the unit does not fill is refused at load
        self.assertIn("'nope'", refused(mutated(["units", "u4", "template"], "nope")).lines[0])
        raw = fx.declaration_dict()
        raw["templates"]["t"] = "Judge {items and {area}"
        lines = refused(raw).lines
        self.assertTrue(all("braces that cannot be read" in line for line in lines))
        raw["templates"]["t"] = "Judge {items.x} {area}"
        self.assertIn("not a plain name", refused(raw).lines[0])

    def test_doubled_braces_are_literal_text_not_slots(self):
        # SOL-HW-REVIEW-KIT.C5: a unit's prompt is built from its template by filling the named slots
        raw = fx.declaration_dict()
        raw["templates"]["t"] = "Answer as {{\"tables\": {{}}}} for {area}: {items}"
        loaded = decl.parse(json.dumps(raw), FILE)
        self.assertEqual(messages.unit_prompt(loaded, "u4"), 'Answer as {"tables": {}} for delta: - m1')

    def test_every_problem_is_listed_not_only_the_first(self):
        # SOL-HW-REVIEW-KIT.C5: a slip is reported before any session is started
        raw = fx.declaration_dict()
        raw["units"]["u1"]["needs"] = ["gone.md"]
        raw["units"]["u4"]["couples_with"] = ["u9"]
        raw["schema"]["tables"][0]["key"] = "Nowhere"
        self.assertEqual(len(refused(raw).lines), 3)

    def test_malformed_files_are_refused_naming_the_file(self):
        # SOL-HW-REVIEW-KIT.C5: errors name the file
        for text, why in (("{", "not valid JSON"), ("[]", "not a JSON object"),
                          ('{"units": {}, "units": {}}', "twice")):
            with self.assertRaises(decl.DeclarationError) as raised:
                decl.parse(text, FILE)
            self.assertIn(FILE, raised.exception.lines[0])
            self.assertIn(why, raised.exception.lines[0])
        with self.assertRaises(decl.DeclarationError) as raised:
            decl.load("/nonexistent/caller.json")
        self.assertIn("/nonexistent/caller.json: cannot be read", raised.exception.lines[0])

    def test_artefact_rules(self):
        # SOL-HW-REVIEW-KIT.C5: an artefact has a kind, a source inside the review folder and, for an extract, a producer
        cases = [
            (["artefacts", "guide.md", "kind"], "pdf", "kind 'pdf'"),
            (["artefacts", "guide.md", "source"], "", "no source path"),
            (["artefacts", "facts.txt", "producer"], Ellipsis, "names no producer"),
            (["artefacts", "guide.md", "producer"], "make", "cannot have a producer"),
            (["artefacts", "guide.md", "tokens"], -1, "tokens as -1"),
            (["artefacts", "view_a.png", "tokens"], 5, "patch formula"),
            (["artefacts", "guide.md", "colour"], "x", "key 'colour'"),
        ]
        for path, value, expected in cases:
            with self.subTest(expected=expected):
                error = refused(mutated(path, value))
                self.assertIn(expected, "\n".join(error.lines))
                self.assertIn(FILE, error.lines[0])

    def test_unit_rules(self):
        # SOL-HW-REVIEW-KIT.C5: a unit declares its artefacts, coupled units, items, expected output and stakes
        cases = [
            (["units", "u1", "items"], [], "no list of items"),
            (["units", "u1", "items"], ["a", "a"], "lists an item twice"),
            (["units", "u1", "expected_output_tokens"], 0, "expected_output_tokens as 0"),
            (["units", "u1", "expected_output_tokens"], "10", "expected_output_tokens as '10'"),
            (["units", "u1", "stakes"], "huge", "stakes as 'huge'"),
            (["units", "u1", "bogus"], 1, "key 'bogus'"),
        ]
        for path, value, expected in cases:
            with self.subTest(expected=expected):
                self.assertIn(expected, "\n".join(refused(mutated(path, value)).lines))

    def test_budget_and_deny_rules(self):
        # SOL-HW-REVIEW-KIT.C5: a budget of a time target, a cost ceiling and a context budget
        self.assertIn("context_tokens as 1.5", "\n".join(refused(mutated(["budget", "context_tokens"], 1.5)).lines))
        self.assertIn("wall_s as 0", "\n".join(refused(mutated(["budget", "wall_s"], 0)).lines))
        self.assertIn("`deny`", "\n".join(refused(mutated(["deny"], "x")).lines))

    def test_paths_added_during_the_round_load_and_may_not_match_an_artefact(self):
        # SOL-HW-REVIEW-KIT.C5: a path the declaration lists as added during the round that matches an artefact of the shared context is refused at load, naming file and artefact
        loaded = decl.parse(json.dumps(fx.declaration_dict(added_during_round=["round/*", "notes.txt"])), FILE)
        self.assertEqual(loaded.added_during_round, ("round/*", "notes.txt"))
        self.assertEqual(decl.parse(fx.declaration_text(), FILE).added_during_round, ())
        for pattern, name in (("docs/*", "guide.md"), ("docs/guide.md", "guide.md"), ("*/guide.md", "guide.md"),
                              ("views/view_?.png", "view_a.png"), ("*", "guide.md")):
            with self.subTest(pattern=pattern):
                text = "\n".join(refused(fx.declaration_dict(added_during_round=[pattern])).lines)
                self.assertIn(FILE, text)
                self.assertIn(f"artefact '{name}'", text)
                self.assertIn(repr(pattern), text)
        for bad in ("round", ["/abs/*"], [""], [3]):
            with self.subTest(bad=bad):
                self.assertIn("`added_during_round`", "\n".join(refused(fx.declaration_dict(added_during_round=bad)).lines))


class SchemaTests(unittest.TestCase):
    def setUp(self):
        self.declaration = decl.parse(fx.declaration_text(), FILE)

    def test_tables_yield_the_answer_shape_the_results_module_checks(self):
        # SOL-HW-REVIEW-KIT.C5: the result schema is declared as tables with a key column, columns and verdict sets
        shape = self.declaration.shape
        self.assertIsInstance(shape, results.AnswerShape)
        verdicts = shape.table("Verdicts")
        self.assertEqual((verdicts.key, verdicts.verdict_column, verdicts.verdicts),
                         ("Item", "Verdict", ("pass", "fail", "cannot judge")))
        self.assertEqual(shape.table("Findings").numeric, ("No",))
        self.assertEqual(shape.findings.table, "Findings")
        self.assertEqual(shape.findings.citations, (("Verdicts", "Note"),))

    def test_json_schema_is_derived_from_the_same_tables(self):
        # SOL-HW-REVIEW-KIT.C5: the schema given to the sessions and the checks of the results module are both derived from the declared tables
        schema = json.loads(self.declaration.json_schema())
        verdict_table = schema["properties"]["tables"]["properties"]["Verdicts"]["items"]
        self.assertEqual(verdict_table["required"], ["Item", "Verdict", "Note"])
        self.assertEqual(verdict_table["properties"]["Verdict"]["enum"], ["pass", "fail", "cannot judge"])
        self.assertFalse(verdict_table["additionalProperties"])
        self.assertEqual(schema["properties"]["tables"]["properties"]["Findings"]["items"]["properties"]["No"],
                         {"type": "number"})
        self.assertEqual(schema["properties"]["tables"]["required"], ["Verdicts", "Findings"])

    def test_adding_a_verdict_changes_both_the_schema_and_the_check(self):
        # SOL-HW-REVIEW-KIT.C5: adding a verdict to a set changes both, and a verdict outside the set is classed as the results module classes it
        answer = {"tables": {"Verdicts": [{"Item": "j1", "Verdict": "n/a", "Note": ""}], "Findings": []}}
        before = results.assess(answer, "", self.declaration.shape, "u2", ["j1"])
        self.assertEqual([p.cls for p in before.problems], [results.LOCAL])
        self.assertIn("outside", before.problems[0].what)
        raw = fx.declaration_dict()
        raw["schema"]["tables"][0]["verdicts"].append("n/a")
        wider = decl.parse(json.dumps(raw), FILE)
        self.assertEqual(results.assess(answer, "", wider.shape, "u2", ["j1"]).problems, [])
        self.assertIn("n/a", json.loads(wider.json_schema())["properties"]["tables"]["properties"]["Verdicts"]["items"]
                      ["properties"]["Verdict"]["enum"])
        self.assertNotIn("n/a", self.declaration.json_schema())

    def test_adding_a_column_changes_both_the_schema_and_the_check(self):
        # SOL-HW-REVIEW-KIT.C5: adding a column to a table changes both, and a column the table lacks is classed as the results module classes it
        answer = {"tables": {"Verdicts": [{"Item": "j1", "Verdict": "pass", "Note": "", "Extra": "x"}], "Findings": []}}
        before = results.assess(answer, "", self.declaration.shape, "u2", ["j1"])
        self.assertEqual([p.cls for p in before.problems], [results.FATAL])
        self.assertIn("'Extra'", before.problems[0].what)
        raw = fx.declaration_dict()
        raw["schema"]["tables"][0]["columns"].append("Extra")
        wider = decl.parse(json.dumps(raw), FILE)
        self.assertIn("Extra", json.loads(wider.json_schema())["properties"]["tables"]["properties"]["Verdicts"]["items"]["properties"])
        lacking = results.assess(answer, "", wider.shape, "u2", ["j1"])
        self.assertEqual(lacking.problems, [])

    def test_schema_text_is_deterministic(self):
        # SOL-HW-REVIEW-KIT.C5: the same tables give the same schema text, which the session specification hashes
        again = decl.parse(fx.declaration_text(), FILE)
        self.assertEqual(self.declaration.json_schema(), again.json_schema())

    def test_findings_rules(self):
        # SOL-HW-REVIEW-KIT.C5: a slip in the declared tables is reported at load
        for change, expected in ((("table", "Nope"), "'Nope'"), (("number", "Zip"), "'Zip'"),
                                 (("citations", [["Verdicts", "Zip"]]), "['Verdicts', 'Zip']"),
                                 (("citation", "(unclosed"), "does not compile"), (("citation", "no group"), "`number` group")):
            raw = fx.declaration_dict()
            raw["schema"]["findings"][change[0]] = change[1]
            with self.subTest(expected=expected):
                self.assertIn(expected, "\n".join(refused(raw).lines))

    def test_table_rules(self):
        # SOL-HW-REVIEW-KIT.C5: a table has columns, a key among them, a verdict column among them, and numeric columns among them
        cases = [("columns", [], "distinct column names"), ("columns", ["A", "A"], "distinct column names"),
                 ("verdict_column", "Zip", "verdict column 'Zip'"), ("numeric", ["Zip"], "numeric columns")]
        for key, value, expected in cases:
            raw = fx.declaration_dict()
            raw["schema"]["tables"][0][key] = value
            with self.subTest(expected=expected):
                self.assertIn(expected, "\n".join(refused(raw).lines))
        raw = fx.declaration_dict()
        raw["schema"]["tables"].append(dict(raw["schema"]["tables"][1]))
        self.assertIn("declared twice", "\n".join(refused(raw).lines))
        raw = fx.declaration_dict()
        del raw["schema"]["tables"][0]["key"]
        self.assertIn("no key column", "\n".join(refused(raw).lines))

    def test_description_names_every_table_column_and_verdict(self):
        # SOL-HW-REVIEW-KIT.C5: each unit's prompt states its items, its area and the result schema in plain terms
        text = decl.describe(self.declaration.shape)
        for word in ("`Verdicts`", "`Findings`", "`Item`", "`Verdict`", "'cannot judge'", "`No`"):
            self.assertIn(word, text)


class PromptTests(unittest.TestCase):
    def setUp(self):
        self.declaration = decl.parse(fx.declaration_text(), FILE)

    def test_prompt_fills_the_named_slots_with_items_and_values(self):
        # SOL-HW-REVIEW-KIT.C5: a unit's prompt is built from its template by filling the named slots with the unit's items and the declared values
        prompt = messages.unit_prompt(self.declaration, "u1")
        self.assertTrue(prompt.startswith("Judge these items of alpha:\n- i1\n- i2\n\nAnswer with one JSON object"))
        self.assertIn("`Verdicts`", prompt)
        self.assertNotIn("{", prompt)

    def test_prompt_with_reordered_items_keeps_the_items(self):
        # SOL-HW-REVIEW-KIT.C5: a unit's prompt is built from its template by filling the named slots with the unit's items
        self.assertIn("- i2\n- i1", messages.unit_prompt(self.declaration, "u1", ["i2", "i1"]))
        with self.assertRaises(ValueError):
            messages.unit_prompt(self.declaration, "u1", ["i1"])

    def test_values_containing_braces_are_not_read_as_slots(self):
        # SOL-HW-REVIEW-KIT.C5: a unit's prompt is built from its template by filling the named slots with the declared values
        raw = fx.declaration_dict()
        raw["units"]["u4"]["values"]["area"] = "a {braced} area"
        loaded = decl.parse(json.dumps(raw), FILE)
        self.assertIn("items of a {braced} area:", messages.unit_prompt(loaded, "u4"))

    def test_group_prompt_names_each_unit_and_a_single_unit_is_its_own_prompt(self):
        # SOL-HW-REVIEW-KIT.C5: a unit's prompt states its items, its area and the result schema
        single = messages.group_prompt(self.declaration, ["u4"])
        self.assertEqual(single, messages.unit_prompt(self.declaration, "u4"))
        both = messages.group_prompt(self.declaration, ["u2", "u3"], framing="Hunt for failures.")
        self.assertTrue(both.startswith("Hunt for failures.\n\n## Unit u2\n"))
        self.assertIn("## Unit u3\n", both)
        self.assertIn("beta", both)
        self.assertIn("gamma", both)

    def test_repair_prompt_lists_the_problems(self):
        # SOL-HW-REVIEW-KIT.C5: the message of a repair turn names what is wrong
        text = messages.repair_prompt(["row 1 has the verdict 'x'", "item 'i2' has no verdict"])
        self.assertIn("- row 1 has the verdict 'x'", text)
        self.assertIn("- item 'i2' has no verdict", text)
        self.assertIn("whole corrected answer", text)


if __name__ == "__main__":
    unittest.main()
