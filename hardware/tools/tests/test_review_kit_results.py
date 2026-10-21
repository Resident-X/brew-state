#!/usr/bin/env python3
"""The review kit's reading of an answer: the tolerant parse, the problem classes, the cell round trip and the best attempt.

The parse is run over answers recorded from the live layout-review runs (kept in the fixtures folder, with the tables
each recorded as kept), and the classes over small synthetic answers. No model is used.
"""

from __future__ import annotations

import json
import os
import random
import re
import sys
import unittest

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)

import board_history  # noqa: E402  (the review record history command's reader)
import board_placement  # noqa: E402
from review_kit import results as rs  # noqa: E402

CORPUS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "review_answers", "answers.json")

#: The tables the recorded answers were given against.
RECORDED_SHAPE = rs.AnswerShape((
    rs.TableShape("Verdicts", ("Item", "Kind", "Severity", "Verdict", "Rests on", "Why"), key="Item",
                  verdict_column="Verdict", verdicts=("pass", "fail", "not applicable", "cannot judge")),
    rs.TableShape("Plan and free pass", ("Note",)),
    rs.TableShape("Findings", ("Finding", "Item", "Raised by", "Severity", "What and where", "Rule", "Added as",
                               "Planning shortfall", "Closed by"), key="Finding", numeric=("Finding",))))

SHAPE = rs.AnswerShape(
    (rs.TableShape("Verdicts", ("Item", "Verdict", "Rests on"), key="Item", verdict_column="Verdict",
                   verdicts=("pass", "fail")),
     rs.TableShape("Findings", ("Finding", "Item", "What"), key="Finding", numeric=("Finding",))),
    rs.FindingShape("Findings", "Finding", (("Verdicts", "Rests on"),), re.compile(r"(?<![\w-])F(?P<number>\d+)\b")))
ITEMS = ("A-1", "A-2")


def verdict(item, outcome="pass", rests="read", ):
    return {"Item": item, "Verdict": outcome, "Rests on": rests}


def answer(verdicts=None, findings=None, extra=None):
    tables = {"Verdicts": [verdict("A-1"), verdict("A-2")] if verdicts is None else verdicts,
              "Findings": [] if findings is None else findings}
    tables.update(extra or {})
    return {"tables": tables}


def assess(obj, items=ITEMS, **kwargs):
    return rs.assess(None, json.dumps(obj), SHAPE, "u", items, **kwargs)


def load_corpus():
    with open(CORPUS, encoding="utf-8") as handle:
        return json.load(handle)


WRAPPERS = {
    "bare": "{answer}",
    "prose before": "I have read every view and checked the rules.\n\n{answer}",
    "prose before with braces": "Checked {the {nets}} and the rule (rule {x}) now.\n{answer}",
    "fence": "```json\n{answer}\n```",
    "fence with prose": "Here is the result:\n```json\n{answer}\n```\nLet me know if anything is unclear.",
    "trailing remark": "{answer}\n\nNote: the Plan table is empty because nothing was seen.",
    "second object without tables": "{answer}\n\n{{\"note\": \"all done\", \"count\": 3}}",
    "first object without tables": "{{\"status\": \"ready\"}}\n{answer}",
    "leading and trailing space": "\n\n   {answer}   \n\n",
}


class ParseTests(unittest.TestCase):
    # SOL-HW-REVIEW-KIT.C3: over a corpus of answers recorded from the live runs, an answer is read as the one object holding a
    # tables key; no recorded correct answer is discarded
    def test_every_recorded_answer_is_read_with_the_tables_it_was_recorded_with(self):
        corpus = load_corpus()
        self.assertGreaterEqual(len(corpus), 8)
        for entry in corpus:
            with self.subTest(entry["name"]):
                parsed = rs.read_answer(None, entry["raw"])
                self.assertEqual(parsed.source, rs.EXTRACTED)
                self.assertEqual({name: len(rows) for name, rows in parsed.obj["tables"].items()}, entry["rows"])
                found = rs.assess(None, entry["raw"], RECORDED_SHAPE, entry["name"])
                self.assertEqual(found.fatal, [], "a recorded answer that was correct is not discarded")
                self.assertIsNotNone(found.tables)
                self.assertEqual(found.raw, entry["raw"])

    # SOL-HW-REVIEW-KIT.C3: an answer that has prose before the object, a code fence around it, a trailing remark, or a second
    # object without a tables key is read as the one object holding a tables key
    def test_each_recorded_answer_survives_every_kind_of_surround(self):
        for entry in load_corpus():
            body = entry["raw"][entry["raw"].find("{"):]
            decoder = json.JSONDecoder()
            expected, end = decoder.raw_decode(body)
            body = body[:end]
            for name, wrapper in WRAPPERS.items():
                with self.subTest(entry=entry["name"], surround=name):
                    text = wrapper.replace("{{", "\0").replace("}}", "\1").replace("{answer}", body).replace("\0", "{").replace("\1", "}")
                    parsed = rs.read_answer(None, text)
                    self.assertEqual(parsed.source, rs.EXTRACTED)
                    self.assertEqual(parsed.obj, expected)
                    self.assertEqual(parsed.note, "")

    # SOL-HW-REVIEW-KIT.C3: an answer returned as structured output is read from it
    def test_a_structured_answer_is_read_from_the_structured_output(self):
        structured = answer()
        parsed = rs.read_answer(structured, json.dumps(answer(verdicts=[verdict("Z-9")])))
        self.assertEqual((parsed.source, parsed.obj), (rs.STRUCTURED, structured))
        self.assertEqual(rs.read_answer(structured, "").source, rs.STRUCTURED)
        found = rs.assess(structured, "prose that is ignored", SHAPE, "u", ITEMS)
        self.assertEqual((found.source, found.problems), (rs.STRUCTURED, []))
        self.assertEqual(json.loads(found.raw), structured)

    def test_a_structured_output_without_a_tables_mapping_falls_back_to_the_text(self):
        for structured in ({"kind": "ack"}, {"tables": []}, [answer()], "text"):
            parsed = rs.read_answer(structured, "Done.\n" + json.dumps(answer()))
            self.assertEqual(parsed.source, rs.EXTRACTED, structured)
        self.assertEqual(rs.read_answer({"kind": "ack"}, "no object").source, rs.NONE)

    # SOL-HW-REVIEW-KIT.C3: an answer with no such object is typed as holding none
    def test_an_answer_with_no_object_holding_tables_is_typed_as_holding_none(self):
        for text in ("", "   ", "I could not finish.", "[1, 2, 3]", '{"note": "no tables here"}', '{"tables": "not a mapping"}',
                     '{"tables": [1]}', '{"answer": {"tables": {}}}', '{"tables": {"Verdicts": [', "{ unbalanced", "null",
                     '"tables"'):
            with self.subTest(text=text):
                parsed = rs.read_answer(None, text)
                self.assertEqual((parsed.obj, parsed.source), (None, rs.NONE))
        self.assertEqual(rs.read_answer(None, None).source, rs.NONE)

    def test_of_two_objects_with_tables_the_last_stands_and_the_note_says_so(self):
        first, second = answer(verdicts=[verdict("A-1", "fail")]), answer()
        parsed = rs.read_answer(None, f"Draft:\n{json.dumps(first)}\nFinal:\n{json.dumps(second)}")
        self.assertEqual(parsed.obj, second)
        self.assertIn("2 objects", parsed.note)

    def test_deeply_nested_text_does_not_raise(self):
        self.assertEqual(rs.read_answer(None, "{\"a\":" * 3000).source, rs.NONE)


class CosmeticTests(unittest.TestCase):
    # SOL-HW-REVIEW-KIT.C3: over synthetic answers, a cell holding a vertical bar or a line break, a column name differing in
    # case or space, and a number given as text are each classed cosmetic, repaired and listed in the unit's record
    def test_a_cell_with_a_vertical_bar_or_a_line_break_is_cosmetic_and_kept_as_written(self):
        for text in ("a | b", "line one\nline two", "carriage\r\nreturn", "|", "\n"):
            with self.subTest(text=text):
                found = assess(answer([verdict("A-1", rests=text), verdict("A-2")]))
                self.assertEqual(found.problems, [])
                self.assertEqual([repair.cls for repair in found.repairs], [rs.COSMETIC])
                self.assertIn("'Rests on'", found.repairs[0].what)
                self.assertIn("row 1", found.repairs[0].where)
                self.assertEqual(found.tables["Verdicts"][0]["Rests on"], text, "the unit's text is kept as it wrote it")

    def test_a_column_name_differing_in_case_or_space_is_read_as_the_declared_one(self):
        rows = [{"item": "A-1", " Verdict ": "pass", "REST  ON": "read"}, {"Item": "A-2", "Verdict": "pass", "Rests on": "read"}]
        rows[0] = {"item": "A-1", " Verdict ": "pass", "Rests  on": "read"}
        found = assess(answer(rows))
        self.assertEqual(found.problems, [])
        self.assertEqual(found.tables["Verdicts"][0], verdict("A-1"))
        what = " ".join(repair.what for repair in found.repairs)
        self.assertIn("'item' read as 'Item'", what)
        self.assertIn("' Verdict ' read as 'Verdict'", what)
        self.assertIn("'Rests  on' read as 'Rests on'", what)
        self.assertEqual(len(found.repairs), 3, "the second row, already right, lists none")

    def test_a_table_named_in_other_case_is_read_as_the_declared_table(self):
        found = assess({"tables": {"verdicts": [verdict("A-1"), verdict("A-2")], "FINDINGS ": []}})
        self.assertEqual(found.problems, [])
        self.assertEqual(sorted(found.tables), ["Findings", "Verdicts"])
        self.assertEqual(len(found.repairs), 2)

    def test_a_number_given_as_text_becomes_a_number(self):
        found = assess(answer(findings=[{"Finding": "1", "Item": "A-1", "What": "w"}, {"Finding": " 2 ", "Item": "A-2", "What": "w"},
                                        {"Finding": "3", "Item": "A-2", "What": "w"}, {"Finding": 4, "Item": "A-2", "What": "w"}]))
        self.assertEqual([row["Finding"] for row in found.tables["Findings"]], [1, 2, 3, 4])
        self.assertEqual([type(row["Finding"]) for row in found.tables["Findings"]], [int] * 4)
        self.assertEqual(len(found.repairs), 3)
        self.assertTrue(all("as text" in repair.what for repair in found.repairs))
        self.assertEqual(found.problems, [])
        fractional = assess(answer(findings=[{"Finding": "2.5", "Item": "A-1", "What": "w"}]))
        self.assertEqual(fractional.tables["Findings"][0]["Finding"], 2.5)
        self.assertEqual([problem.cls for problem in fractional.problems], [rs.LOCAL], "a repaired 2.5 is still no finding number")

    # SOL-HW-REVIEW-KIT.C3: a round is never refused for a cosmetic problem
    def test_a_cosmetic_problem_alone_leaves_an_answer_with_no_problem(self):
        found = assess(answer([verdict("A-1", rests="x | y"), {"ITEM": "A-2", "verdict": "pass", "Rests on": "r"}],
                              [{"Finding": "1", "Item": "A-1", "What": "w\nx"}]))
        self.assertEqual(found.problems, [])
        self.assertEqual(len(found.repairs), 5)
        self.assertEqual(rs.standing([found]), 0)

    def test_the_repairs_are_listed_in_the_unit_record(self):
        found = assess(answer([verdict("A-1", rests="x | y"), verdict("A-2")]))
        record = found.as_dict()
        self.assertEqual(len(record["repairs"]), 1)
        self.assertIn("row 1", record["repairs"][0])


class LocalAndFatalTests(unittest.TestCase):
    def whats(self, found, cls):
        return [problem.what for problem in found.problems if problem.cls == cls]

    # SOL-HW-REVIEW-KIT.C3: a citation of a finding the unit did not raise is classed local
    def test_a_citation_of_a_finding_the_unit_did_not_raise_is_local(self):
        found = assess(answer([verdict("A-1", "fail", "see F1 and F7"), verdict("A-2")],
                              [{"Finding": 1, "Item": "A-1", "What": "w"}]))
        self.assertEqual([problem.cls for problem in found.problems], [rs.LOCAL])
        self.assertIn("finding 7", found.problems[0].what)
        self.assertIn("row 1", found.problems[0].where)
        self.assertIsNotNone(found.tables)
        self.assertEqual(assess(answer([verdict("A-1", "fail", "see F1"), verdict("A-2")],
                                       [{"Finding": 1, "Item": "A-1", "What": "w"}])).problems, [])

    def test_a_citation_naming_a_round_is_judged_only_for_this_round(self):
        shape = rs.AnswerShape(SHAPE.tables, rs.FindingShape("Findings", "Finding", (("Verdicts", "Rests on"),),
                                                             re.compile(r"(?<![\w.])(?P<round>\d+)\.(?P<number>\d+)\b")))
        text = json.dumps(answer([verdict("A-1", "fail", "2.1 and 1.9"), verdict("A-2")], [{"Finding": 1, "Item": "A-1", "What": "w"}]))
        self.assertEqual(rs.assess(None, text, shape, "u", ITEMS, round_label="2").problems, [])
        found = rs.assess(None, text, shape, "u", ITEMS, round_label="1")
        self.assertEqual(len(found.problems), 1, "with this round named 1, citation 2.1 is another round's and is left as written")
        self.assertIn("finding 9", found.problems[0].what)

    # SOL-HW-REVIEW-KIT.C3: an item with no verdict or two is classed local
    def test_an_item_with_no_verdict_or_two_is_local(self):
        none = assess(answer([verdict("A-1")]))
        self.assertEqual([problem.cls for problem in none.problems], [rs.LOCAL])
        self.assertIn("no verdict for item 'A-2'", none.problems[0].what)
        two = assess(answer([verdict("A-1"), verdict("A-1", "fail"), verdict("A-2")]))
        self.assertEqual([problem.cls for problem in two.problems], [rs.LOCAL])
        self.assertIn("'A-1' 2 verdicts", two.problems[0].what)
        empty = assess(answer([]))
        self.assertEqual(len(empty.problems), 2)
        foreign = assess(answer([verdict("A-1"), verdict("A-2"), verdict("Z-9")]))
        self.assertIn("'Z-9'", foreign.problems[0].what)
        self.assertEqual([problem.cls for problem in foreign.problems], [rs.LOCAL])

    # SOL-HW-REVIEW-KIT.C3: a verdict outside the declared set is classed local
    def test_a_verdict_outside_the_declared_set_is_local(self):
        for outcome in ("Pass", "maybe", "", 3):
            with self.subTest(outcome=outcome):
                found = assess(answer([verdict("A-1", outcome), verdict("A-2")]))
                self.assertEqual([problem.cls for problem in found.problems], [rs.LOCAL])
                self.assertIn("outside ['pass', 'fail']", found.problems[0].what)
                self.assertIn("row 1", found.problems[0].where)

    # SOL-HW-REVIEW-KIT.C3: a findings row or verdict row whose item is not one of the unit's items is classed local, naming the row, the cell and the allowed items
    def test_a_findings_row_naming_two_items_in_one_cell_is_local(self):
        shape = rs.AnswerShape(
            (SHAPE.tables[0], rs.TableShape("Findings", ("Finding", "Item", "What"), key="Item", numeric=("Finding",))),
            SHAPE.findings)
        rows = [{"Finding": 1, "Item": "A-1", "What": "w"}, {"Finding": 2, "Item": "A-1 / A-2", "What": "w"}]
        found = rs.assess(None, json.dumps(answer(findings=rows)), shape, "u", ITEMS)
        self.assertEqual([problem.cls for problem in found.problems], [rs.LOCAL])
        self.assertIsNotNone(found.tables)
        self.assertIn("row 2", found.problems[0].where)
        self.assertIn("'A-1 / A-2'", found.problems[0].what)
        self.assertIn("'Item'", found.problems[0].what)
        self.assertIn("['A-1', 'A-2']", found.problems[0].what)
        fixed = [{"Finding": 1, "Item": "A-1", "What": "w"}, {"Finding": 2, "Item": "A-2", "What": "w"}]
        self.assertEqual(rs.assess(None, json.dumps(answer(findings=fixed)), shape, "u", ITEMS).problems, [])

    def test_a_verdict_row_with_an_unknown_item_is_local_and_names_row_cell_and_items(self):
        found = assess(answer([verdict("A-1"), verdict("A-2"), verdict("A-1 / A-2")]))
        self.assertEqual([problem.cls for problem in found.problems], [rs.LOCAL])
        self.assertIn("row 3", found.problems[0].where)
        self.assertIn("'A-1 / A-2'", found.problems[0].what)
        self.assertIn("'Item'", found.problems[0].what)
        self.assertIn("['A-1', 'A-2']", found.problems[0].what)

    def test_finding_numbers_must_be_whole_numbers_from_one_and_distinct(self):
        for numbers, text in (([0], "0"), ([1, 1], "two findings 1"), ([-2], "-2"), ([2.5], "2.5"), (["x"], "'x'")):
            with self.subTest(numbers=numbers):
                rows = [{"Finding": n, "Item": "A-1", "What": "w"} for n in numbers]
                found = assess(answer(findings=rows))
                self.assertTrue(any(text in what for what in self.whats(found, rs.LOCAL)) or found.fatal, found.problems)

    # SOL-HW-REVIEW-KIT.C3: an answer with no object is classed fatal
    def test_an_answer_with_no_object_is_fatal(self):
        found = rs.assess(None, "I looked at the board and it seems fine.", SHAPE, "u", ITEMS)
        self.assertEqual([problem.cls for problem in found.problems], [rs.FATAL])
        self.assertIn("no object", found.problems[0].what)
        self.assertIsNone(found.tables)
        self.assertEqual(found.source, rs.NONE)
        self.assertEqual(found.raw, "I looked at the board and it seems fine.")

    # SOL-HW-REVIEW-KIT.C3: one whose tables cannot be mapped to the declared schema is classed fatal
    def test_tables_that_cannot_be_mapped_are_fatal(self):
        extra_column = [{**verdict("A-1"), "Extra": "x"}, verdict("A-2")]
        missing_column = [{"Item": "A-1", "Verdict": "pass"}, verdict("A-2")]
        twice = [{"Item": "A-1", "item": "A-1", "Verdict": "pass", "Rests on": "r"}, verdict("A-2")]
        cases = {"a column the table lacks": answer(extra_column), "a missing column": answer(missing_column),
                 "a column twice": answer(twice), "an unknown table": answer(extra={"Notes": []}),
                 "rows not a list": {"tables": {"Verdicts": {"A-1": "pass"}}},
                 "a row not a mapping": answer(["A-1: pass"]),
                 "a list cell": answer([{**verdict("A-1"), "Rests on": ["a", "b"]}, verdict("A-2")]),
                 "a null cell": answer([{**verdict("A-1"), "Rests on": None}, verdict("A-2")]),
                 "a boolean cell": answer([{**verdict("A-1"), "Rests on": True}, verdict("A-2")]),
                 "an infinite cell": {"tables": {"Verdicts": [{**verdict("A-1"), "Rests on": float("inf")}, verdict("A-2")]}},
                 "a non-number in a number column": answer(findings=[{"Finding": "one", "Item": "A-1", "What": "w"}]),
                 "a table twice": {"tables": {"Verdicts": [], "verdicts": []}}}
        for name, obj in cases.items():
            with self.subTest(name):
                text = json.dumps(obj) if name != "an infinite cell" else json.dumps(obj, allow_nan=True)
                found = rs.assess(None, text, SHAPE, "u", ITEMS)
                self.assertTrue(found.fatal, found.problems)
                self.assertTrue(all(problem.cls == rs.FATAL for problem in found.problems), found.problems)
                self.assertIsNone(found.tables)
                self.assertIn("unit u", found.problems[0].where)

    def test_one_unmappable_table_does_not_hide_the_others_problems(self):
        found = assess(answer(extra={"Notes": []}))
        self.assertEqual(len(found.fatal), 1)
        self.assertIn("'Notes'", found.fatal[0].where)


class RoundTripTests(unittest.TestCase):
    COLUMNS = ["Item", "Text", "Tail"]

    def round_trip(self, texts):
        rows = [{"Item": f"R-{n}", "Text": text, "Tail": "end"} for n, text in enumerate(texts)]
        lines = ["intro", ""] + rs.table_lines(self.COLUMNS, rows) + ["", "after"]
        index, read, faults = board_history.table(lines, self.COLUMNS)
        self.assertEqual(faults, [], faults)
        self.assertIsNotNone(index)
        self.assertEqual(len(read), len(rows), "every row reads back as one row")
        return [rs.unescape_cell(row[1]) for row in read], [rs.unescape_cell(row[2]) for row in read]

    # SOL-HW-REVIEW-KIT.C3: over generated strings, including vertical bars, line breaks, leading and trailing space, backticks
    # and non-ASCII text, a cell rendered into a record table and read back through the reader the review record history
    # command uses gives the string as the unit wrote it
    def test_chosen_strings_read_back_as_written(self):
        texts = ["", " ", "plain", "a | b", "|", "||", "a\nb", "a\r\nb", "\n", "\t tab", " lead", "trail ", "  both  ", "`code`",
                 "``` fence ```", "café 日本語 \U0001f600", "&", "&amp;", "&#124;", "&#10;", "a&b|c", " nbsp",
                 " line sep ", "\x85next", "\x1f unit sep", "\x00nul", "end\\", "| leading bar", "trailing bar |",
                 "# heading", "- item", "| a | b |", "<b>x</b>", "​zero width"]
        written, tails = self.round_trip(texts)
        self.assertEqual(written, texts)
        self.assertEqual(tails, ["end"] * len(texts))

    def test_generated_strings_read_back_as_written(self):
        rng = random.Random(20261021)
        alphabet = ["a", "Z", "0", " ", " ", "|", "|", "\n", "\r", "\t", "`", "&", "#", ";", "é", "日", "\U0001f600",
                    " ", " ", "\x85", "\x1f", "\\", "[", "]", "<", "-", ":"]
        texts = ["".join(rng.choice(alphabet) for _ in range(rng.randint(0, 24))) for _ in range(400)]
        written, _ = self.round_trip(texts)
        self.assertEqual(written, texts)

    def test_a_rendered_cell_holds_nothing_the_reader_would_split_or_trim(self):
        for text in ("a | b", "x\ny", " s ", " ", "\x85"):
            cell = rs.escape_cell(text)
            self.assertNotIn("|", cell)
            self.assertEqual(cell, cell.strip())
            self.assertFalse(any(char in cell for char in "\r\n\t  \x85 "))
            self.assertEqual(board_placement.cells(f"| {cell} | x |"), [cell, "x"])
            self.assertEqual(rs.unescape_cell(cell), text)

    def test_numbers_render_as_their_text(self):
        self.assertEqual(rs.escape_cell(3), "3")
        self.assertEqual(rs.escape_cell(2.5), "2.5")

    # SOL-HW-REVIEW-KIT.C3: and the unit's kept result holds the raw text
    def test_the_kept_result_holds_the_raw_text_and_the_text_as_the_unit_wrote_it(self):
        raw_text = "Prose first.\n" + json.dumps(answer([verdict("A-1", rests="a | b\nc"), verdict("A-2")]))
        found = rs.assess(None, raw_text, SHAPE, "u", ITEMS)
        self.assertEqual(found.raw, raw_text)
        self.assertEqual(found.as_dict()["raw"], raw_text)
        written = found.tables["Verdicts"][0]["Rests on"]
        self.assertEqual(written, "a | b\nc")
        lines = rs.table_lines(["Item", "Verdict", "Rests on"], found.tables["Verdicts"])
        _, read, faults = board_history.table(lines, ["Item", "Verdict", "Rests on"])
        self.assertEqual(faults, [])
        self.assertEqual(rs.unescape_cell(read[0][2]), written)
        structured = rs.assess(answer([verdict("A-1", rests="x | y"), verdict("A-2")]), "", SHAPE, "u", ITEMS)
        self.assertEqual(json.loads(structured.raw)["tables"]["Verdicts"][0]["Rests on"], "x | y")


CLEAR_SHAPE = rs.AnswerShape((
    rs.TableShape("Verdicts", ("Item", "Verdict"), key="Item", verdict_column="Verdict",
                  verdicts=("pass", "fail", "cannot judge")),))
CLEAR_ITEMS = ("A-1", "A-2", "A-3")


def clear_attempt(rows, asked=False):
    tables = {"Verdicts": [{"Item": item, "Verdict": outcome} for item, outcome in rows]}
    found = rs.Assessment(rs.STRUCTURED, "", tables, judge_asked=asked)
    found.problems = rs.local_problems(tables, CLEAR_SHAPE, "u", CLEAR_ITEMS)
    return found


class RepairNeverClearsAFailTests(unittest.TestCase):
    def marked(self, first_rows, later_rows):
        first, later = clear_attempt(first_rows, asked=True), clear_attempt(later_rows)
        rs.mark_cleared([first], later, CLEAR_SHAPE, "fail", CLEAR_ITEMS, "u")
        return first, later

    def test_a_later_answer_that_passes_a_first_answer_fail_carries_a_local_problem_naming_the_item(self):
        # SOL-HW-REVIEW-KIT.C6: a repaired answer that clears a fail the first answer raised, by passing the item, carries a local problem naming the item, so the first answer stands over it
        first, later = self.marked([("A-1", "fail"), ("A-2", "cannot judge"), ("A-3", "pass")],
                                   [("A-1", "pass"), ("A-2", "pass"), ("A-3", "pass")])
        self.assertEqual(later.cleared, ["A-1"])
        self.assertEqual([p.cls for p in later.problems], [rs.LOCAL])
        self.assertIn("'A-1'", later.problems[0].what)
        self.assertEqual(rs.standing([first, later]), 0)

    def test_a_later_answer_that_leaves_a_first_answer_fail_out_carries_a_local_problem_naming_the_item(self):
        # SOL-HW-REVIEW-KIT.C6: a repaired answer that clears a fail the first answer raised, by leaving the item out, carries a local problem naming the item
        first, later = self.marked([("A-1", "pass"), ("A-2", "fail"), ("A-3", "cannot judge")], [("A-1", "pass"), ("A-3", "pass")])
        self.assertEqual(later.cleared, ["A-2"])
        self.assertTrue(any("'A-2'" in p.line() for p in later.problems))
        self.assertEqual(rs.standing([first, later]), 0)

    def test_a_later_answer_that_keeps_the_fail_and_adds_fails_or_fixes_a_cannot_judge_is_untouched(self):
        # SOL-HW-REVIEW-KIT.C6: a repaired answer that merely adds fails or changes a cannot judge is untouched
        first, later = self.marked([("A-1", "fail"), ("A-2", "cannot judge"), ("A-3", "pass")],
                                   [("A-1", "fail"), ("A-2", "fail"), ("A-3", "fail")])
        self.assertEqual((later.cleared, later.problems), ([], []))
        self.assertEqual(rs.standing([first, later]), 1)

    def test_an_invalid_first_answer_row_is_not_a_fail_a_repair_can_clear(self):
        # SOL-HW-REVIEW-KIT.C6: an item whose row in the first answer was invalid (off-checklist, two items in a cell) is not a valid fail to carry
        first, later = self.marked([("A-1", "pass"), ("A-2", "pass"), ("A-3", "pass"), ("B-9", "fail"), ("A-1 and A-2", "fail")],
                                   [("A-1", "pass"), ("A-2", "pass"), ("A-3", "pass")])
        self.assertEqual(later.cleared, [])
        self.assertEqual(later.problems, [])
        self.assertEqual(rs.standing([first, later]), 1)

    def test_a_fatal_or_tableless_later_answer_is_not_marked(self):
        # SOL-HW-REVIEW-KIT.C6: a repair never clears a fail; an answer with no tables has no verdicts to compare
        first = clear_attempt([("A-1", "fail"), ("A-2", "pass"), ("A-3", "pass")], asked=True)
        later = rs.Assessment(rs.NONE, "", None, problems=[rs.Problem(rs.FATAL, "u", "no object")])
        rs.mark_cleared([first], later, CLEAR_SHAPE, "fail", CLEAR_ITEMS, "u")
        self.assertEqual((later.cleared, len(later.problems)), ([], 1))

    def test_over_generated_attempt_pairs_the_standing_attempt_never_holds_fewer_valid_fails_than_the_first(self):
        # SOL-HW-REVIEW-KIT.C6: a repair never clears a fail: the items failing in the standing attempt are never fewer than the valid items failing in the first
        rng = random.Random(20261022)
        names = list(CLEAR_ITEMS) + ["B-9", "A-1 and A-2", "A-1"]
        verdicts = ("pass", "fail", "cannot judge")

        def rows():
            return [(rng.choice(names), rng.choice(verdicts)) for _ in range(rng.randint(0, 6))]

        for _ in range(400):
            first_rows, later_rows = rows(), rows()
            first, later = clear_attempt(first_rows, asked=rng.random() < 0.5), clear_attempt(later_rows)
            rs.mark_cleared([first], later, CLEAR_SHAPE, "fail", CLEAR_ITEMS, "u")
            stood = [first, later][rs.standing([first, later])]
            valid_first = {i for i, v in first_rows if v == "fail" and i in CLEAR_ITEMS}
            failing = {row["Item"] for row in stood.tables["Verdicts"] if row["Verdict"] == "fail"}
            self.assertTrue(valid_first <= failing, (first_rows, later_rows))


class AttemptTests(unittest.TestCase):
    def attempt(self, locals_=0, fatal=False, covered=0, label=""):
        problems = [rs.Problem(rs.LOCAL, f"w{n}", "local") for n in range(locals_)]
        problems += [rs.Problem(rs.FATAL, "w", "no object")] if fatal else []
        return rs.Assessment(rs.EXTRACTED, label, None if fatal else {}, problems=problems, items_covered=covered)

    # SOL-HW-REVIEW-KIT.C3: over attempts of one unit, the standing attempt is the one with no problems, else the fewest local
    # problems, else the most items covered, else the first
    def test_the_standing_attempt_follows_the_order(self):
        a = self.attempt
        self.assertEqual(rs.standing([a(2, covered=9), a(0, covered=1), a(1, covered=9)]), 1, "no problems")
        self.assertEqual(rs.standing([a(3, covered=9), a(1, covered=2), a(2, covered=9)]), 1, "fewest local problems")
        self.assertEqual(rs.standing([a(1, covered=2), a(1, covered=7), a(1, covered=5)]), 1, "most items covered")
        self.assertEqual(rs.standing([a(1, covered=4), a(1, covered=4), a(1, covered=4)]), 0, "the first")
        self.assertEqual(rs.standing([a(0, covered=3), a(0, covered=30)]), 0, "the first with no problems, not the fuller")

    def test_a_fatal_attempt_stands_only_when_nothing_else_does(self):
        a = self.attempt
        self.assertEqual(rs.standing([a(fatal=True), a(5, covered=1)]), 1)
        self.assertEqual(rs.standing([a(5, covered=1), a(fatal=True)]), 0)
        self.assertEqual(rs.standing([a(fatal=True, covered=0), a(fatal=True, covered=0)]), 0)
        self.assertEqual(rs.standing([a(2, fatal=True, covered=1), a(1, fatal=True, covered=1)]), 1)

    # SOL-HW-REVIEW-KIT.C3: a later attempt with more problems than a kept one does not replace it, and every attempt remains in
    # the unit's record
    def test_the_shape_in_which_a_worse_retry_once_replaced_a_better_attempt(self):
        record = rs.UnitRecord("area-A")
        first = rs.assess(None, json.dumps(answer([verdict("A-1", "fail", "see F9"), verdict("A-2")])), SHAPE, "area-A", ITEMS)
        worse = rs.assess(None, "I am sorry, I could not produce the table.", SHAPE, "area-A", ITEMS)
        fewer_items = rs.assess(None, json.dumps(answer([verdict("A-1", "fail", "see F9")])), SHAPE, "area-A", ITEMS)
        self.assertEqual(len(first.problems), 1)
        self.assertEqual(record.add(first), 0)
        self.assertEqual(record.add(worse), 0, "a retry with no object does not replace a kept answer with one local problem")
        self.assertEqual(record.add(fewer_items), 0, "more problems does not replace it either")
        self.assertEqual(record.standing, first)
        self.assertEqual(len(record.attempts), 3, "every attempt remains")
        dumped = record.as_dict()
        self.assertEqual(dumped["standing"], 0)
        self.assertEqual([a["raw"] for a in dumped["attempts"]], [first.raw, worse.raw, fewer_items.raw])
        better = rs.assess(None, json.dumps(answer([verdict("A-1", "fail", "see F1"), verdict("A-2")],
                                                   [{"Finding": 1, "Item": "A-1", "What": "w"}])), SHAPE, "area-A", ITEMS)
        self.assertEqual(record.add(better), 3, "a later attempt with fewer problems does stand")
        self.assertEqual(len(record.as_dict()["attempts"]), 4)

    def test_items_covered_counts_the_distinct_items_with_a_verdict(self):
        self.assertEqual(assess(answer([verdict("A-1")])).items_covered, 1)
        self.assertEqual(assess(answer([verdict("A-1"), verdict("A-1"), verdict("A-2")])).items_covered, 2)
        self.assertEqual(assess(answer([verdict("A-1"), verdict("Z-9")])).items_covered, 1, "an item the unit was not given is not covered")
        self.assertEqual(assess(answer([])).items_covered, 0)

    def test_a_unit_with_no_attempt_has_none_that_stands(self):
        with self.assertRaises(ValueError):
            rs.standing([])
        self.assertIsNone(rs.UnitRecord("u").as_dict()["standing"])



class SeveralKeyColumnTests(unittest.TestCase):
    KEYED = rs.AnswerShape((
        rs.TableShape("Verdicts", ("Item", "Part", "Verdict"), key="Item", verdict_column="Verdict",
                      verdicts=("pass", "fail"), extra_key=("Part",)),))

    @staticmethod
    def row(item, part, outcome="pass"):
        return {"Item": item, "Part": part, "Verdict": outcome}

    def check(self, rows, items=ITEMS, fmt="text"):
        assessed = rs.assess(None, json.dumps({"tables": {"Verdicts": rows}}), self.KEYED, "u", items)
        return [problem.line() if fmt == "text" else {"where": problem.where, "what": problem.what}
                for problem in assessed.problems]

    def test_a_verdict_for_each_combination_of_each_item_is_accepted(self):
        # SOL-HW-REVIEW-KIT.C14: a unit's answer gives a verdict to each combination once
        rows = [self.row("A-1", "x"), self.row("A-1", "y"), self.row("A-2", "x")]
        self.assertEqual([], self.check(rows))

    def test_a_combination_given_twice_is_refused_naming_it(self):
        # SOL-HW-REVIEW-KIT.C14: a unit's answer gives a verdict to each combination once and refuses a combination twice
        found = self.check([self.row("A-1", "x"), self.row("A-1", "x", "fail"), self.row("A-2", "x")])
        self.assertEqual(1, len(found))
        self.assertIn("['A-1', 'x']", found[0])
        self.assertIn("2 verdicts", found[0])
        structured = self.check([self.row("A-1", "x"), self.row("A-1", "x"), self.row("A-2", "x")], fmt="json")
        self.assertEqual("unit u table 'Verdicts'", structured[0]["where"])

    def test_an_item_of_the_unit_with_no_row_is_refused_even_when_other_items_have_several(self):
        # SOL-HW-REVIEW-KIT.C14: a unit's answer refuses an item of the unit with no row
        found = self.check([self.row("A-1", "x"), self.row("A-1", "y")])
        self.assertEqual(["unit u table 'Verdicts': gives no verdict for item 'A-2'"], found)

    def test_a_row_whose_item_is_not_the_units_is_refused_whatever_its_other_key_cells(self):
        # SOL-HW-REVIEW-KIT.C14: a unit's answer refuses a row whose item is not the unit's
        found = self.check([self.row("A-1", "x"), self.row("A-2", "x"), self.row("B-9", "x")])
        self.assertEqual(1, len(found))
        self.assertIn("'B-9'", found[0])
        self.assertIn("not one of the unit's items", found[0])

    def test_the_second_key_cell_is_not_read_as_the_item(self):
        # SOL-HW-REVIEW-KIT.C14: a unit's answer refuses a row whose item is not the unit's
        found = self.check([self.row("A-1", "A-2"), self.row("A-2", "A-1")])
        self.assertEqual([], found)

    KEYED_FAILS = rs.AnswerShape((
        rs.TableShape("Verdicts", ("Item", "Part", "Why", "Verdict"), key="Item", verdict_column="Verdict",
                      verdicts=("pass", "fail", "cannot judge"), extra_key=("Part",)),))

    @classmethod
    def keyed(cls, rows):
        tables = {"Verdicts": [{"Item": i, "Part": p, "Why": w, "Verdict": v} for i, p, v, w in rows]}
        return rs.Assessment(rs.STRUCTURED, "", tables)

    def test_one_combination_cleared_while_a_sibling_of_the_same_item_still_fails_is_named(self):
        # SOL-HW-REVIEW-KIT.C14: a fail stands per combination; a later answer that passes one combination of an item whose other combination still fails clears that combination's fail
        first = self.keyed([("A-1", "x", "fail", ""), ("A-1", "y", "fail", "")])
        later = self.keyed([("A-1", "x", "pass", ""), ("A-1", "y", "fail", "")])
        self.assertEqual(['["A-1", "x"]'], rs.cleared_fails(first, later, self.KEYED_FAILS, "fail", ["A-1"]))
        rs.mark_cleared([first], later, self.KEYED_FAILS, "fail", ["A-1"], "u")
        self.assertEqual(['["A-1", "x"]'], later.cleared)
        self.assertIn('combination ["A-1", "x"] of [\'Item\', \'Part\']', later.problems[0].what)
        self.assertEqual(0, rs.standing([first, later]))

    def test_a_combination_left_out_while_a_sibling_still_fails_is_cleared_and_one_still_failing_is_not(self):
        # SOL-HW-REVIEW-KIT.C14: a fail stands per combination, whether the later answer passes the combination or leaves it out
        first = self.keyed([("A-1", "x", "fail", ""), ("A-1", "y", "fail", "")])
        left_out = self.keyed([("A-1", "y", "fail", "")])
        same = self.keyed([("A-1", "x", "fail", ""), ("A-1", "y", "fail", "")])
        self.assertEqual(['["A-1", "x"]'], rs.cleared_fails(first, left_out, self.KEYED_FAILS, "fail", ["A-1"]))
        self.assertEqual([], rs.cleared_fails(first, same, self.KEYED_FAILS, "fail", ["A-1"]))

    def test_the_cannot_judge_turn_names_each_combination_not_the_item_twice(self):
        # SOL-HW-REVIEW-KIT.C14: the cannot-judge rows name the combination each is on, whether or not the table has a Why column
        held = self.keyed([("A-1", "x", "cannot judge", "needs the datasheet"), ("A-1", "y", "cannot judge", "needs the plan"),
                           ("A-2", "x", "pass", "")])
        found = rs.cannot_judge_rows(held.tables, self.KEYED_FAILS, "cannot judge")
        self.assertEqual([('["A-1", "x"]', "needs the datasheet"), ('["A-1", "y"]', "needs the plan")], found)
        prompt = rs.judge_prompt(found)
        self.assertIn('- ["A-1", "x"]: needs the datasheet', prompt)
        self.assertIn('- ["A-1", "y"]: needs the plan', prompt)
        bare = rs.AnswerShape((rs.TableShape("Verdicts", ("Item", "Part", "Note", "Verdict"), key="Item", verdict_column="Verdict",
                                             verdicts=("pass", "cannot judge"), extra_key=("Part",)),))
        rows = {"Verdicts": [{"Item": "A-1", "Part": "x", "Note": "n", "Verdict": "cannot judge"}]}
        self.assertEqual([('["A-1", "x"]', "n")], rs.cannot_judge_rows(rows, bare, "cannot judge"))

    def test_coverage_counts_the_combinations_answered_so_the_fuller_attempt_ranks_first(self):
        # SOL-HW-REVIEW-KIT.C14: an attempt that answers more combinations of the unit's items covers more
        def covered(rows):
            return rs.assess(None, json.dumps({"tables": {"Verdicts": [
                {"Item": i, "Part": p, "Why": "", "Verdict": "pass"} for i, p in rows]}}), self.KEYED_FAILS, "u", ["A-1"]).items_covered
        self.assertEqual(1, covered([("A-1", "x")]))
        self.assertEqual(2, covered([("A-1", "x"), ("A-1", "y")]))
        self.assertEqual(1, covered([("A-1", "x"), ("Z-9", "x")]))

    def test_a_single_column_key_still_refuses_an_item_given_twice(self):
        # SOL-HW-REVIEW-KIT.C14: a single-column key behaves as before
        found = [p.what for p in assess(answer([verdict("A-1"), verdict("A-1"), verdict("A-2")])).problems]
        self.assertEqual(["gives item 'A-1' 2 verdicts"], found)


if __name__ == "__main__":
    unittest.main()
