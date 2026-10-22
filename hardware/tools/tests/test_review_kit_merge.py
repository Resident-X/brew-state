#!/usr/bin/env python3
"""The review kit's merge: the tables enforced, this round's findings renumbered, replicas merged any-fail, adjudication notes only.

Synthetic shapes and results; no model, no file.
"""

from __future__ import annotations

import copy
import itertools
import json
import os
import random
import sys
import unittest

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import review_kit_fixtures as fx  # noqa: E402
from review_kit import decl, merge, results  # noqa: E402


def shape_of(**schema):
    raw = fx.declaration_dict()
    raw["schema"] = copy.deepcopy(raw["schema"])
    raw["schema"].update(schema)
    return decl.parse(json.dumps(raw), "caller.json").shape


PLAIN = shape_of()
ROUNDED = shape_of(findings={"table": "Findings", "number": "No", "citations": [["Verdicts", "Note"]],
                             "citation": "finding (?P<round>[a-z0-9]+)/(?P<number>\\d+)"})
NO_FINDINGS = shape_of(findings=None)
SELF_CITING = shape_of(findings={"table": "Findings", "number": "No", "citations": [["Verdicts", "Note"], ["Findings", "Detail"]],
                                 "citation": "finding (?P<number>\\d+)"})


def verdict(item, value="pass", note=""):
    return {"Item": item, "Verdict": value, "Note": note}


def finding(no, item, detail):
    return {"No": no, "Item": item, "Detail": detail}


def tables(verdicts=(), findings=()):
    return {"Verdicts": list(verdicts), "Findings": list(findings)}


def place(row):
    return row["Detail"].split("@")[1] if "@" in row["Detail"] else None


RULES = merge.Rules(("i1", "i2", "j1", "k1"), place)


def refusal(case, shape, rules, order, units, **kwargs):
    with case.assertRaises(merge.Refused) as caught:
        merge.merge(shape, rules, order, units, **kwargs)
    return "\n".join(caught.exception.causes)


class Tables(unittest.TestCase):
    # SOL-HW-REVIEW-KIT.C8: the merge rejects a table with a column the declared table lacks and a verdict outside the declared set
    def test_a_column_the_declared_table_lacks_is_refused_naming_the_unit_and_replica(self):
        row = dict(verdict("i1"), Extra="x")
        text = refusal(self, PLAIN, RULES, ["u1"], {"u1": {"r1": tables([row])}})
        self.assertIn("unit u1 replica r1", text)
        self.assertIn("'Extra'", text)

    def test_a_missing_column_is_refused(self):
        text = refusal(self, PLAIN, RULES, ["u1"], {"u1": {"r1": tables([{"Item": "i1", "Verdict": "pass"}])}})
        self.assertIn("lacks the column ['Note']", text)

    def test_a_verdict_outside_the_declared_set_is_refused_in_any_replica(self):
        units = {"u1": {"r1": tables([verdict("i1")]), "r2": tables([verdict("i1", "maybe")])}}
        text = refusal(self, PLAIN, RULES, ["u1"], units)
        self.assertIn("unit u1 replica r2", text)
        self.assertIn("'maybe'", text)

    def test_a_verdict_that_is_not_text_a_table_nobody_declared_and_a_cell_that_is_not_text_are_refused(self):
        self.assertIn("has the verdict ['pass'], outside", refusal(self, PLAIN, RULES, ["u"], {"u": {"r": tables([verdict("i1", ["pass"])])}}))
        self.assertIn("table 'Extra'", refusal(self, PLAIN, RULES, ["u"], {"u": {"r": {"Extra": []}}}))
        self.assertIn("not text or a finite number", refusal(self, PLAIN, RULES, ["u"], {"u": {"r": tables([verdict("i1", note=float("nan"))])}}))
        self.assertIn("not a mapping of table name", refusal(self, PLAIN, RULES, ["u"], {"u": {"r": ["x"]}}))

    def test_a_row_that_is_not_a_mapping_and_rows_that_are_not_a_list_are_refused(self):
        self.assertIn("row 1 is not a mapping", refusal(self, PLAIN, RULES, ["u"], {"u": {"r": {"Verdicts": ["x"]}}}))
        self.assertIn("is not a list of rows", refusal(self, PLAIN, RULES, ["u"], {"u": {"r": {"Verdicts": {}}}}))

    def test_a_unit_with_no_result_a_result_for_no_unit_and_a_unit_with_no_replica_are_refused(self):
        text = refusal(self, PLAIN, RULES, ["u1", "u2"], {"u1": {"r1": tables()}, "u3": {"r1": tables()}})
        self.assertIn("unit u2 has no result", text)
        self.assertIn("unit u3 has a result and is no unit", text)
        self.assertIn("unit u1 has no replica", refusal(self, PLAIN, RULES, ["u1"], {"u1": {}}))

    def test_a_finding_on_no_checklist_item_a_repeated_number_and_a_bad_number_are_refused(self):
        units = {"u": {"r": tables([], [finding(1, "zz", "a"), finding(1, "i1", "b"), finding(0, "i1", "c")])}}
        text = refusal(self, PLAIN, RULES, ["u"], units)
        self.assertIn("'zz', which is no item of the checklist", text)
        self.assertIn("numbered two findings 1", text)
        self.assertIn("numbered a finding 0", text)

    def test_a_citation_of_a_finding_the_unit_did_not_raise_is_refused(self):
        units = {"u": {"r": tables([verdict("i1", "fail", "see finding 4")], [finding(1, "i1", "a")])}}
        self.assertIn("cites a finding 4 the unit did not raise", refusal(self, PLAIN, RULES, ["u"], units))


class Renumbering(unittest.TestCase):
    def units(self):
        return {
            "u1": {"r1": tables([verdict("i1", "fail", "see finding 2"), verdict("i2", "fail", "see finding 1 and finding 2")],
                                [finding(1, "i2", "d2"), finding(2, "i1", "d1")])},
            "u2": {"r1": tables([verdict("j1", "fail", "see finding 1")], [finding(1, "j1", "d3")])},
        }

    # SOL-HW-REVIEW-KIT.C8: replaces every finding number a reviewer wrote with the number the checklist's order gives and rewrites the citations of them in the verdict rows
    def test_findings_are_numbered_in_the_checklists_order_and_their_citations_rewritten(self):
        record = merge.merge(PLAIN, RULES, ["u1", "u2"], self.units())
        found = record["tables"]["Findings"]["rows"]
        self.assertEqual([(row["No"], row["Item"]) for row in found], [(1, "i1"), (2, "i2"), (3, "j1")])
        notes = {row["Item"]: row["Note"] for row in record["tables"]["Verdicts"]["rows"]}
        self.assertEqual(notes, {"i1": "see finding 1", "i2": "see finding 2 and finding 1", "j1": "see finding 3"})

    def test_a_citation_digit_inside_other_text_is_the_only_thing_that_changes(self):
        units = {"u": {"r": tables([verdict("i1", "fail", "10 mm; see finding 1 (of 12)")], [finding(1, "i1", "a")])}}
        units["u"]["r"]["Findings"][0]["No"] = 1
        record = merge.merge(PLAIN, merge.Rules(("i1",), first=7), ["u"], units)
        self.assertEqual(record["tables"]["Verdicts"]["rows"][0]["Note"], "10 mm; see finding 7 (of 12)")

    def test_the_first_number_of_a_round_is_the_callers(self):
        record = merge.merge(PLAIN, merge.Rules(RULES.checklist, place, first=41), ["u1", "u2"], self.units())
        self.assertEqual([row["No"] for row in record["tables"]["Findings"]["rows"]], [41, 42, 43])
        self.assertEqual(record["tables"]["Verdicts"]["rows"][0]["Note"], "see finding 41")

    def test_a_finding_that_cites_another_finding_in_its_own_table_is_rewritten_too(self):
        units = {"u": {"r": tables([], [finding(1, "i2", "as finding 2"), finding(2, "i1", "see finding 1")])}}
        record = merge.merge(SELF_CITING, RULES, ["u"], units)
        self.assertEqual([(row["No"], row["Detail"]) for row in record["tables"]["Findings"]["rows"]],
                         [(1, "see finding 2"), (2, "as finding 1")])

    # SOL-HW-REVIEW-KIT.C8: For a caller with no findings table nothing is renumbered
    def test_a_caller_with_no_findings_table_has_nothing_renumbered(self):
        units = {"u": {"r": {"Verdicts": [verdict("i1", "fail", "see finding 9")], "Findings": [finding(9, "i1", "a")]}}}
        record = merge.merge(NO_FINDINGS, RULES, ["u"], units)
        self.assertEqual(record["tables"]["Verdicts"]["rows"][0]["Note"], "see finding 9")
        self.assertEqual(record["tables"]["Findings"]["rows"][0]["No"], 9)
        self.assertEqual(record["same_place"], [])

    def test_a_round_with_no_findings_at_all_merges_to_empty_tables(self):
        record = merge.merge(PLAIN, RULES, ["u1"], {"u1": {"r1": tables([verdict("i1")])}})
        self.assertEqual(record["tables"]["Findings"]["rows"], [])
        self.assertEqual(record["tables"]["Verdicts"]["rows"][0]["Verdict"], "pass")


class Rounds(unittest.TestCase):
    def rules(self, earlier=(("r1", 1), ("r1", 2)), current="r2"):
        return merge.Rules(RULES.checklist, place, current, frozenset(earlier))

    def units(self, note):
        return {"u": {"a": tables([verdict("i1", "fail", note), verdict("i2", "fail", "also finding r2/2")],
                                  [finding(1, "i2", "x"), finding(2, "i1", "y")])}}

    # SOL-HW-REVIEW-KIT.C8: leaves a citation of an earlier round's finding as written, tells the two by the round each citation carries against the round the caller names as this one
    def test_a_cell_citing_this_rounds_finding_and_an_earlier_rounds_renumbers_only_this_rounds(self):
        record = merge.merge(ROUNDED, self.rules(), ["u"], self.units("again finding r1/1 and finding r2/1"))
        notes = {row["Item"]: row["Note"] for row in record["tables"]["Verdicts"]["rows"]}
        self.assertEqual(notes["i1"], "again finding r1/1 and finding r2/2")
        self.assertEqual(notes["i2"], "also finding r2/1")

    def test_an_earlier_rounds_citation_is_left_while_the_unit_owns_a_finding_of_the_same_number(self):
        record = merge.merge(ROUNDED, self.rules(), ["u"], self.units("finding r1/2"))
        self.assertEqual(record["tables"]["Verdicts"]["rows"][0]["Note"], "finding r1/2")

    # SOL-HW-REVIEW-KIT.C8: refuses a citation of an earlier round's finding that the review folder's earlier rounds do not hold
    def test_a_citation_of_an_earlier_round_the_review_folder_does_not_hold_is_refused_naming_the_cell(self):
        text = refusal(self, ROUNDED, self.rules(), ["u"], self.units("finding r1/9"))
        self.assertIn("'finding r1/9'", text)
        self.assertIn("round r1", text)
        self.assertIn("this round is r2", text)

    def test_a_citation_of_a_round_with_no_findings_held_at_all_is_refused(self):
        text = refusal(self, ROUNDED, self.rules(earlier=()), ["u"], self.units("finding r1/1"))
        self.assertIn("earlier rounds do not hold (this round is r2)", text)

    def test_a_this_round_citation_of_a_finding_not_raised_is_refused_under_a_round_pattern(self):
        text = refusal(self, ROUNDED, self.rules(), ["u"], self.units("finding r2/7"))
        self.assertIn("cites a finding 7 the unit did not raise", text)


class SamePlace(unittest.TestCase):
    # SOL-HW-REVIEW-KIT.C8: reports two findings the caller's key assigns to the same item or place keeping both
    def test_two_findings_at_one_place_are_reported_and_both_kept(self):
        units = {"u1": {"r1": tables([], [finding(1, "i1", "crack @P1")])},
                 "u2": {"r1": tables([], [finding(1, "j1", "gap @P1"), finding(2, "j1", "gap @P2")])}}
        record = merge.merge(PLAIN, RULES, ["u1", "u2"], units)
        self.assertEqual(len(record["tables"]["Findings"]["rows"]), 3)
        self.assertEqual(record["same_place"], [{"key": "P1", "findings": [1, 2], "units": ["u1", "u2"]}])

    def test_a_finding_with_no_place_is_never_reported_as_at_a_place(self):
        units = {"u1": {"r1": tables([], [finding(1, "i1", "no place"), finding(2, "i1", "no place")])}}
        self.assertEqual(merge.merge(PLAIN, RULES, ["u1"], units)["same_place"], [])

    def test_a_place_function_that_raises_or_returns_a_non_text_place_is_refused_naming_it(self):
        units = {"u1": {"r1": tables([], [finding(1, "i1", "a")])}}

        def boom(row):
            raise KeyError("x")
        text = refusal(self, PLAIN, merge.Rules(RULES.checklist, boom, caller="the caller demo"), ["u1"], units)
        self.assertIn("the caller demo's place function raised KeyError", text)
        text = refusal(self, PLAIN, merge.Rules(RULES.checklist, lambda row: 5), ["u1"], units)
        self.assertIn("returned 5", text)


class Order(unittest.TestCase):
    def units(self):
        return {
            "u1": {"r1": tables([verdict("i1", "fail", "finding 1"), verdict("i2")], [finding(1, "i1", "a @P1")]),
                   "r2": tables([verdict("i1", "pass"), verdict("i2", "fail", "finding 1")], [finding(1, "i2", "b @P1")]),
                   "r10": tables([verdict("i1", "cannot judge"), verdict("i2")], [finding(1, "i1", "a @P1")])},
            "u2": {"r1": tables([verdict("j1", "fail", "finding 2")], [finding(2, "j1", "c @P3"), finding(1, "j1", "d @P2")])},
            "u3": {"r1": tables([verdict("k1")], [])},
        }

    # SOL-HW-REVIEW-KIT.C8: gives the same record for every order the units arrive in; the merged table is the same for every order the replicas arrive in
    def test_the_record_is_the_same_for_every_order_the_units_and_replicas_arrive_in(self):
        order = ["u1", "u2", "u3"]
        wanted = json.dumps(merge.merge(PLAIN, RULES, order, self.units()), sort_keys=False)
        base = self.units()
        for units in itertools.permutations(base):
            for replicas in itertools.permutations(base["u1"]):
                arrived = {unit: ({rid: base[unit][rid] for rid in replicas} if unit == "u1" else base[unit]) for unit in units}
                self.assertEqual(json.dumps(merge.merge(PLAIN, RULES, order, arrived)), wanted)

    def test_replica_ids_are_ordered_naturally_so_r2_comes_before_r10(self):
        record = merge.merge(PLAIN, RULES, ["u1"], {"u1": self.units()["u1"]})
        by = {row["Item"]: by for row, by in zip(record["tables"]["Verdicts"]["rows"], record["tables"]["Verdicts"]["raised_by"])}
        self.assertEqual(by["i1"], ["r1"])
        self.assertEqual(merge.natural("r2") < merge.natural("r10"), True)


class Replicas(unittest.TestCase):
    def merged(self, *answers, shape=PLAIN, rules=RULES):
        return merge.merge(shape, rules, ["u"], {"u": {f"r{n}": a for n, a in enumerate(answers, 1)}})

    def verdicts(self, record):
        table = record["tables"]["Verdicts"]
        return {row["Item"]: (row["Verdict"], by, dissent) for row, by, dissent in zip(table["rows"], table["raised_by"], table["dissent"])}

    # SOL-HW-REVIEW-KIT.C8: an item that any replica fails is a fail in the merged table, an item no replica fails that any could not judge is a cannot judge, and every other item is a pass; each row lists the replicas that raised its verdict
    def test_an_item_any_replica_fails_is_a_fail_with_the_replicas_that_raised_it(self):
        record = self.merged(tables([verdict("i1", "pass")]), tables([verdict("i1", "fail", "bad")]),
                             tables([verdict("i1", "cannot judge")]))
        self.assertEqual(self.verdicts(record)["i1"], ("fail", ["r2"], [["r1", "pass"], ["r3", "cannot judge"]]))
        self.assertEqual(record["tables"]["Verdicts"]["rows"][0]["Note"], "bad")

    def test_an_item_no_replica_fails_that_any_could_not_judge_is_a_cannot_judge(self):
        record = self.merged(tables([verdict("i1", "pass")]), tables([verdict("i1", "cannot judge")]))
        self.assertEqual(self.verdicts(record)["i1"], ("cannot judge", ["r2"], [["r1", "pass"]]))

    def test_every_other_item_is_a_pass_raised_by_all_the_replicas(self):
        record = self.merged(tables([verdict("i1")]), tables([verdict("i1")]), tables([verdict("i1")]))
        self.assertEqual(self.verdicts(record)["i1"], ("pass", ["r1", "r2", "r3"], []))

    def test_a_single_replica_is_the_single_reviewer(self):
        record = self.merged(tables([verdict("i1", "fail"), verdict("i2")]))
        self.assertEqual(self.verdicts(record)["i1"], ("fail", ["r1"], []))
        self.assertEqual(self.verdicts(record)["i2"], ("pass", ["r1"], []))

    def test_replicas_that_disagree_on_a_verdict_neither_fail_nor_cannot_judge_take_the_first_declared(self):
        shape = shape_of(tables=[{"name": "Verdicts", "columns": ["Item", "Verdict", "Note"], "key": "Item", "verdict_column": "Verdict",
                                  "verdicts": ["pass", "fail", "not applicable", "cannot judge"]},
                                 {"name": "Findings", "columns": ["No", "Item", "Detail"], "key": "Item", "numeric": ["No"]}])
        record = self.merged(tables([verdict("i1", "not applicable")]), tables([verdict("i1", "pass")]), shape=shape)
        self.assertEqual(self.verdicts(record)["i1"][0], "pass")
        record = self.merged(tables([verdict("i1", "not applicable")]), tables([verdict("i1", "not applicable")]), shape=shape)
        self.assertEqual(self.verdicts(record)["i1"][0], "not applicable")

    def test_an_item_one_replica_left_out_is_judged_by_the_others_alone(self):
        record = self.merged(tables([verdict("i1", "pass")]), tables([verdict("i1", "pass"), verdict("i2", "fail")]))
        self.assertEqual(self.verdicts(record)["i2"], ("fail", ["r2"], []))

    # SOL-HW-REVIEW-KIT.C8: findings for the same item and place are one finding with the replicas that raised it, and differing findings are all kept
    def test_findings_for_the_same_item_and_place_are_one_finding_with_their_raisers(self):
        record = self.merged(tables([], [finding(1, "i1", "crack @P1")]), tables([], [finding(4, "i1", "crack wider @P1")]),
                             tables([], [finding(1, "i1", "other @P2")]))
        table = record["tables"]["Findings"]
        self.assertEqual([(row["No"], row["Detail"]) for row in table["rows"]], [(1, "crack @P1"), (2, "other @P2")])
        self.assertEqual(table["raised_by"], [["r1", "r2"], ["r3"]])

    def test_findings_at_one_place_on_different_items_are_both_kept_and_reported(self):
        record = self.merged(tables([], [finding(1, "i1", "a @P1")]), tables([], [finding(1, "i2", "b @P1")]))
        self.assertEqual(len(record["tables"]["Findings"]["rows"]), 2)
        self.assertEqual(record["same_place"][0]["key"], "P1")

    def test_one_replicas_two_findings_at_one_place_are_not_folded_into_one(self):
        record = self.merged(tables([], [finding(1, "i1", "a @P1"), finding(2, "i1", "b @P1")]))
        self.assertEqual(len(record["tables"]["Findings"]["rows"]), 2)

    def test_with_no_place_function_findings_with_the_same_cells_are_one_finding(self):
        rules = merge.Rules(RULES.checklist)
        record = self.merged(tables([], [finding(1, "i1", "same")]), tables([], [finding(2, "i1", "same"), finding(3, "i1", "diff")]),
                             rules=rules)
        self.assertEqual([by for by in record["tables"]["Findings"]["raised_by"]], [["r1", "r2"], ["r2"]])

    def test_a_citation_in_a_replicas_verdict_row_follows_its_finding_to_the_merged_number(self):
        record = self.merged(tables([verdict("i1", "pass")], [finding(1, "i2", "x @A"), finding(2, "i1", "y @P1")]),
                             tables([verdict("i1", "fail", "see finding 3")], [finding(3, "i1", "y2 @P1")]))
        row = record["tables"]["Verdicts"]["rows"][0]
        self.assertEqual(row["Note"], "see finding 1")
        table = record["tables"]["Findings"]
        self.assertEqual([(r["No"], r["Item"]) for r in table["rows"]], [(1, "i1"), (2, "i2")])
        self.assertEqual(table["raised_by"], [["r1", "r2"], ["r1"]])

    def test_a_table_with_no_verdicts_keeps_identical_rows_once_with_all_their_raisers(self):
        shape = shape_of(tables=[{"name": "Verdicts", "columns": ["Item", "Verdict", "Note"], "key": "Item", "verdict_column": "Verdict",
                                  "verdicts": ["pass", "fail", "cannot judge"]},
                                 {"name": "Findings", "columns": ["No", "Item", "Detail"], "key": "Item", "numeric": ["No"]},
                                 {"name": "Log", "columns": ["Line"]}], findings=None)
        one, two = tables(), tables()
        one["Log"], two["Log"] = [{"Line": "a"}, {"Line": "b"}], [{"Line": "b"}, {"Line": "c"}]
        record = self.merged(one, two, shape=shape)
        self.assertEqual(record["tables"]["Log"]["rows"], [{"Line": "a"}, {"Line": "b"}, {"Line": "c"}])
        self.assertEqual(record["tables"]["Log"]["raised_by"], [["r1"], ["r1", "r2"], ["r2"]])

    def test_the_merged_rows_render_with_the_replicas_and_a_cell_with_a_bar_reads_back_as_written(self):
        record = self.merged(tables([verdict("i1", "fail", "a | b\nc")]), tables([verdict("i1", "fail", "x")]))
        lines = merge.table_markdown(record["tables"]["Verdicts"])
        self.assertEqual(lines[0], "| Item | Verdict | Note | Raised by |")
        cells = [part.strip() for part in lines[2].strip("|").split(" | ")]
        self.assertEqual(results.unescape_cell(cells[2]), "a | b\nc")
        self.assertEqual(cells[3], "r1, r2")
        self.assertEqual(len(merge.table_markdown(record["tables"]["Verdicts"], raised_by=False)[0].split("|")),
                         len(PLAIN.table("Verdicts").columns) + 2)


class Checks(unittest.TestCase):
    # SOL-HW-REVIEW-KIT.C8: the merge enforces the tables and hands the caller's checks the merged tables
    def test_the_callers_checks_see_the_merged_tables_and_a_problem_refuses_the_merge(self):
        seen = []

        def checks(found):
            seen.append(found)
            return ["a table is wrong"]
        text = refusal(self, PLAIN, RULES, ["u"], {"u": {"r1": tables([verdict("i1")])}}, checks=checks)
        self.assertEqual(text, "a table is wrong")
        self.assertEqual(seen[0]["Verdicts"]["rows"][0]["Item"], "i1")
        self.assertEqual(seen[0]["Verdicts"]["raised_by"], [["r1"]])

    def test_checks_that_raise_or_return_other_than_text_are_refused_naming_the_function(self):
        def boom(found):
            raise RuntimeError("no")
        units = {"u": {"r1": tables()}}
        self.assertIn("checks function raised RuntimeError", refusal(self, PLAIN, RULES, ["u"], units, checks=boom))
        self.assertIn("not a list of problems", refusal(self, PLAIN, RULES, ["u"], units, checks=lambda found: "bad"))
        self.assertEqual(merge.merge(PLAIN, RULES, ["u"], units, checks=lambda found: [])["same_place"], [])


class Adjudication(unittest.TestCase):
    def record(self):
        units = {"u1": {"r1": tables([verdict("i1", "fail", "finding 1"), verdict("i2", "pass"), verdict("j1", "cannot judge")],
                                     [finding(1, "i1", "a @P1")]),
                        "r2": tables([verdict("i1", "pass"), verdict("i2", "fail", "finding 1"), verdict("j1", "pass")],
                                     [finding(1, "i2", "b @P2")])}}
        return merge.merge(PLAIN, RULES, ["u1"], units)

    # SOL-HW-REVIEW-KIT.C8: each adjudicated finding carries the adjudicator's note and the session that wrote it
    def test_a_note_is_attached_to_the_finding_with_the_session_that_wrote_it(self):
        record = self.record()
        found = merge.read_adjudication("a1", {"notes": [{"finding": 2, "note": "the part is not there", "false_positive": True},
                                                          {"finding": 1, "note": "plausible"}]})
        self.assertEqual(found.problems, [])
        after = merge.adjudicate(PLAIN, record, [found])
        self.assertEqual(after["tables"]["Findings"]["notes"][1],
                         [{"note": "the part is not there", "false_positive": True, "session": "a1"}])
        self.assertEqual(after["tables"]["Findings"]["notes"][0][0]["false_positive"], False)
        self.assertEqual(record["tables"]["Findings"]["notes"], [[], []], "the record it was given is not changed")

    def test_two_adjudications_of_one_finding_both_attach_in_the_order_of_their_sessions(self):
        record = self.record()
        first = merge.read_adjudication("a2", {"notes": [{"finding": 1, "note": "two"}]})
        second = merge.read_adjudication("a1", {"notes": [{"finding": 1, "note": "one"}]})
        after = merge.adjudicate(PLAIN, record, [first, second])
        self.assertEqual([note["session"] for note in after["tables"]["Findings"]["notes"][0]], ["a1", "a2"])

    # SOL-HW-REVIEW-KIT.C8: an adjudication that tries to change a verdict is recorded as a problem and ignored
    def test_an_adjudication_that_tries_to_change_a_verdict_is_recorded_as_a_problem_and_ignored(self):
        record = self.record()
        found = merge.read_adjudication("a1", {"verdicts": [{"item": "i1", "verdict": "pass"}],
                                               "notes": [{"finding": 1, "note": "fine", "verdict": "pass"},
                                                         {"finding": 2, "note": "ok", "false_positive": True}]})
        after = merge.adjudicate(PLAIN, record, [found])
        self.assertEqual(after["tables"]["Verdicts"], record["tables"]["Verdicts"])
        self.assertEqual(merge.failing_items(PLAIN, RULES, after), merge.failing_items(PLAIN, RULES, record))
        problems = after["adjudication"]["problems"]
        self.assertTrue(any("tries to change a verdict through 'verdicts'" in line for line in problems))
        self.assertTrue(any("note 1 tries to change a verdict through 'verdict'" in line for line in problems))
        self.assertEqual(after["tables"]["Findings"]["notes"][0], [])
        self.assertEqual(after["tables"]["Findings"]["notes"][1][0]["note"], "ok")

    def test_malformed_notes_and_notes_on_no_finding_are_recorded_and_ignored(self):
        record = self.record()
        cases = [("x", "not a mapping"), ({"notes": "x"}, "`notes` is not a list"), ({"junk": 1}, "'junk'"),
                 ({"notes": ["x"]}, "note 1 is not a mapping"), ({"notes": [{"finding": 0, "note": "n"}]}, "not a finding number"),
                 ({"notes": [{"finding": 1, "note": " "}]}, "no note text"),
                 ({"notes": [{"finding": 1, "note": "n", "false_positive": "yes"}]}, "not true or false"),
                 ({"notes": [{"finding": 1, "note": "n", "extra": 1}]}, "'extra'"),
                 ({"notes": [{"finding": 9, "note": "n"}]}, "does not hold")]
        for answer, expected in cases:
            after = merge.adjudicate(PLAIN, record, [merge.read_adjudication("a1", answer)])
            self.assertTrue(any(expected in line for line in after["adjudication"]["problems"]), (answer, after["adjudication"]))
            self.assertEqual(after["tables"]["Findings"]["notes"], [[], []], answer)

    def test_notes_for_a_review_with_no_findings_table_are_recorded_and_ignored(self):
        record = merge.merge(NO_FINDINGS, RULES, ["u"], {"u": {"r1": tables([verdict("i1", "fail")])}})
        after = merge.adjudicate(NO_FINDINGS, record, [merge.read_adjudication("a1", {"notes": [{"finding": 1, "note": "n"}]})])
        self.assertIn("no findings table", after["adjudication"]["problems"][0])

    # SOL-HW-REVIEW-KIT.C8: over generated adjudication results, including ones that call every finding a false positive, the merged tables after the adjudication fail exactly the items they failed before it
    def test_over_generated_adjudications_the_failing_items_are_unchanged(self):
        generator = random.Random(8)
        items = ["i1", "i2", "j1", "k1"]
        for round_number in range(150):
            replicas = {}
            for rid in range(generator.randint(1, 3)):
                verdicts, raised = [], []
                for item in items:
                    value = generator.choice(["pass", "fail", "fail", "cannot judge"])
                    verdicts.append(verdict(item, value, f"finding {len(raised) + 1}" if value == "fail" else ""))
                    if value == "fail":
                        raised.append(finding(len(raised) + 1, item, f"d{round_number}{rid}{item} @P{generator.randint(1, 3)}"))
                replicas[f"r{rid + 1}"] = tables(verdicts, raised)
            record = merge.merge(PLAIN, RULES, ["u"], {"u": replicas})
            count = len(record["tables"]["Findings"]["rows"])
            adjudications = []
            for number in range(generator.randint(0, 3)):
                kind = generator.choice(["everything", "random", "verdicts", "mixed"])
                if kind == "everything":
                    answer = {"notes": [{"finding": n, "note": "false positive", "false_positive": True} for n in range(1, count + 1)]}
                elif kind == "random":
                    answer = {"notes": [{"finding": generator.randint(0, count + 2), "note": "n",
                                         "false_positive": generator.random() < 0.5} for _ in range(generator.randint(0, 5))]}
                elif kind == "verdicts":
                    answer = {"verdicts": [{"item": item, "verdict": "pass"} for item in items], "tables": {"Verdicts": []}}
                else:
                    answer = {"notes": [{"finding": 1, "note": "n", "verdict": "pass"}], "item_verdicts": {"i1": "pass"},
                              "Verdict": "pass"}
                adjudications.append(merge.read_adjudication(f"a{number}", answer))
            after = merge.adjudicate(PLAIN, record, adjudications)
            self.assertEqual(merge.failing_items(PLAIN, RULES, after), merge.failing_items(PLAIN, RULES, record))
            self.assertEqual(after["tables"]["Verdicts"], record["tables"]["Verdicts"])
            self.assertEqual([row for row in after["tables"]["Findings"]["rows"]], record["tables"]["Findings"]["rows"])



class SeveralKeyColumns(unittest.TestCase):
    SHAPE = decl.parse(json.dumps(fx.keyed_declaration_dict()), "caller.json").shape

    @staticmethod
    def part(item, part, value="pass", note=""):
        return {"Item": item, "Part": part, "Verdict": value, "Note": note}

    def merged(self, *answers):
        replicas = {f"r{n}": {"Verdicts": list(rows), "Findings": []} for n, rows in enumerate(answers, 1)}
        return merge.merge(self.SHAPE, RULES, ["u"], {"u": replicas})

    def by_combination(self, record):
        table = record["tables"]["Verdicts"]
        return {(row["Item"], row["Part"]): (row["Verdict"], by, dissent)
                for row, by, dissent in zip(table["rows"], table["raised_by"], table["dissent"])}

    def test_replicas_are_merged_any_fail_for_each_combination_of_one_item(self):
        # SOL-HW-REVIEW-KIT.C14: replicas are merged any-fail per combination
        record = self.merged([self.part("i1", "x"), self.part("i1", "y", "fail", "bad")],
                             [self.part("i1", "x", "fail"), self.part("i1", "y")])
        found = self.by_combination(record)
        self.assertEqual(2, len(found))
        self.assertEqual(("fail", ["r2"], [["r1", "pass"]]), found[("i1", "x")])
        self.assertEqual(("fail", ["r1"], [["r2", "pass"]]), found[("i1", "y")])

    def test_a_combination_one_replica_passes_stays_a_pass_beside_a_failed_sibling(self):
        # SOL-HW-REVIEW-KIT.C14: replicas are merged any-fail per combination
        record = self.merged([self.part("i1", "x"), self.part("i1", "y", "fail")],
                             [self.part("i1", "x"), self.part("i1", "y", "cannot judge")])
        found = self.by_combination(record)
        self.assertEqual(("pass", ["r1", "r2"], []), found[("i1", "x")])
        self.assertEqual(("fail", ["r1"], [["r2", "cannot judge"]]), found[("i1", "y")])

    def test_a_single_column_key_is_still_merged_per_item(self):
        # SOL-HW-REVIEW-KIT.C14: a single-column key behaves as before
        record = merge.merge(PLAIN, RULES, ["u"], {"u": {"r1": tables([verdict("i1", "pass"), verdict("i2")]),
                                                      "r2": tables([verdict("i1", "fail"), verdict("i2")])}})
        rows = record["tables"]["Verdicts"]
        self.assertEqual([("i1", "fail"), ("i2", "pass")], [(r["Item"], r["Verdict"]) for r in rows["rows"]])



class NamedFailVerdict(unittest.TestCase):
    PLAIN = decl.parse(json.dumps(fx.verdict_declaration_dict()), "caller.json").shape
    KEYED = decl.parse(json.dumps(fx.verdict_declaration_dict(keyed=True)), "caller.json").shape
    NAMED = merge.Rules(("i1", "i2"), None, fail="differs")

    @staticmethod
    def row(item, value, part=None):
        found = {"Item": item, "Verdict": value, "Note": ""}
        return dict(found, Part=part) if part else found

    def merged(self, shape, rules, *answers, part=False):
        replicas = {f"r{n}": {"Verdicts": list(rows), "Findings": []} for n, rows in enumerate(answers, 1)}
        return merge.merge(shape, rules, ["u"], {"u": replicas})

    def test_replicas_are_merged_any_fail_with_the_named_verdict_standing_over_a_passing_one(self):
        # SOL-HW-REVIEW-KIT.C15: Over synthetic declarations and a stub executor, a caller may name which of its verdicts is its fail verdict, a verdict of the verdict set of a table it declares; the kit then treats that verdict exactly as it treats fail: replicas are merged any-fail with it standing over a passing verdict, and no repair turn, cannot-judge turn or rerun clears it, the refusal naming the item and the verdict. A caller naming none keeps fail as its fail verdict, and a caller that names fail behaves as one that names none. A name carried by the verdict set of at least one table that has a key and a verdict column is accepted, a table whose verdict set lacks the name having no fail to hold. A name outside the verdicts of every such table is refused before any session starts, the refusal naming it and listing each verdict table with its verdict set, or saying that the declaration has no verdict table. A name that is not text or is blank is refused when the caller loads, naming the caller and the attribute, and so is the name cannot judge, naming the attribute, since the merge and the cannot-judge turn would otherwise collapse the two verdicts. Out of scope: any real caller.
        record = self.merged(self.PLAIN, self.NAMED, [self.row("i1", "matches"), self.row("i2", "matches")],
                             [self.row("i1", "differs"), self.row("i2", "matches")])
        table = record["tables"]["Verdicts"]
        self.assertEqual([("i1", "differs"), ("i2", "matches")], [(r["Item"], r["Verdict"]) for r in table["rows"]])
        self.assertEqual([["r2"], ["r1", "r2"]], table["raised_by"])
        self.assertEqual([[["r1", "matches"]], []], table["dissent"])
        self.assertEqual([("Verdicts", "i1")], merge.failing_items(self.PLAIN, self.NAMED, record))

    def test_the_named_verdict_stands_over_a_cannot_judge_and_a_cannot_judge_over_a_pass(self):
        # SOL-HW-REVIEW-KIT.C15: Over synthetic declarations and a stub executor, a caller may name which of its verdicts is its fail verdict, a verdict of the verdict set of a table it declares; the kit then treats that verdict exactly as it treats fail: replicas are merged any-fail with it standing over a passing verdict, and no repair turn, cannot-judge turn or rerun clears it, the refusal naming the item and the verdict. A caller naming none keeps fail as its fail verdict, and a caller that names fail behaves as one that names none. A name carried by the verdict set of at least one table that has a key and a verdict column is accepted, a table whose verdict set lacks the name having no fail to hold. A name outside the verdicts of every such table is refused before any session starts, the refusal naming it and listing each verdict table with its verdict set, or saying that the declaration has no verdict table. A name that is not text or is blank is refused when the caller loads, naming the caller and the attribute, and so is the name cannot judge, naming the attribute, since the merge and the cannot-judge turn would otherwise collapse the two verdicts. Out of scope: any real caller.
        record = self.merged(self.PLAIN, self.NAMED, [self.row("i1", "cannot judge"), self.row("i2", "cannot judge")],
                             [self.row("i1", "differs"), self.row("i2", "matches")])
        self.assertEqual(["differs", "cannot judge"], [r["Verdict"] for r in record["tables"]["Verdicts"]["rows"]])

    def test_a_caller_naming_none_does_not_hold_another_verdict_standing(self):
        # SOL-HW-REVIEW-KIT.C15: Over synthetic declarations and a stub executor, a caller may name which of its verdicts is its fail verdict, a verdict of the verdict set of a table it declares; the kit then treats that verdict exactly as it treats fail: replicas are merged any-fail with it standing over a passing verdict, and no repair turn, cannot-judge turn or rerun clears it, the refusal naming the item and the verdict. A caller naming none keeps fail as its fail verdict, and a caller that names fail behaves as one that names none. A name carried by the verdict set of at least one table that has a key and a verdict column is accepted, a table whose verdict set lacks the name having no fail to hold. A name outside the verdicts of every such table is refused before any session starts, the refusal naming it and listing each verdict table with its verdict set, or saying that the declaration has no verdict table. A name that is not text or is blank is refused when the caller loads, naming the caller and the attribute, and so is the name cannot judge, naming the attribute, since the merge and the cannot-judge turn would otherwise collapse the two verdicts. Out of scope: any real caller.
        record = self.merged(self.PLAIN, merge.Rules(("i1", "i2")), [self.row("i1", "matches"), self.row("i2", "matches")],
                             [self.row("i1", "differs"), self.row("i2", "matches")])
        self.assertEqual("matches", record["tables"]["Verdicts"]["rows"][0]["Verdict"])
        self.assertEqual([], merge.failing_items(self.PLAIN, merge.Rules(("i1", "i2")), record))

    def test_a_caller_naming_fail_merges_as_one_naming_none(self):
        # SOL-HW-REVIEW-KIT.C15: Over synthetic declarations and a stub executor, a caller may name which of its verdicts is its fail verdict, a verdict of the verdict set of a table it declares; the kit then treats that verdict exactly as it treats fail: replicas are merged any-fail with it standing over a passing verdict, and no repair turn, cannot-judge turn or rerun clears it, the refusal naming the item and the verdict. A caller naming none keeps fail as its fail verdict, and a caller that names fail behaves as one that names none. A name carried by the verdict set of at least one table that has a key and a verdict column is accepted, a table whose verdict set lacks the name having no fail to hold. A name outside the verdicts of every such table is refused before any session starts, the refusal naming it and listing each verdict table with its verdict set, or saying that the declaration has no verdict table. A name that is not text or is blank is refused when the caller loads, naming the caller and the attribute, and so is the name cannot judge, naming the attribute, since the merge and the cannot-judge turn would otherwise collapse the two verdicts. Out of scope: any real caller.
        shape = decl.parse(json.dumps(fx.declaration_dict()), "caller.json").shape
        answers = ([self.row("i1", "pass"), self.row("i2", "fail")], [self.row("i1", "fail"), self.row("i2", "pass")])
        named = self.merged(shape, merge.Rules(("i1", "i2"), None, fail="fail"), *answers)
        none = self.merged(shape, merge.Rules(("i1", "i2")), *answers)
        self.assertEqual(json.dumps(named, sort_keys=True), json.dumps(none, sort_keys=True))

    def test_the_named_verdict_is_merged_any_fail_per_combination_of_a_several_column_key(self):
        # SOL-HW-REVIEW-KIT.C15: Over synthetic declarations and a stub executor, a caller may name which of its verdicts is its fail verdict, a verdict of the verdict set of a table it declares; the kit then treats that verdict exactly as it treats fail: replicas are merged any-fail with it standing over a passing verdict, and no repair turn, cannot-judge turn or rerun clears it, the refusal naming the item and the verdict. A caller naming none keeps fail as its fail verdict, and a caller that names fail behaves as one that names none. A name carried by the verdict set of at least one table that has a key and a verdict column is accepted, a table whose verdict set lacks the name having no fail to hold. A name outside the verdicts of every such table is refused before any session starts, the refusal naming it and listing each verdict table with its verdict set, or saying that the declaration has no verdict table. A name that is not text or is blank is refused when the caller loads, naming the caller and the attribute, and so is the name cannot judge, naming the attribute, since the merge and the cannot-judge turn would otherwise collapse the two verdicts. Out of scope: any real caller.
        record = self.merged(self.KEYED, self.NAMED,
                             [self.row("i1", "matches", "x"), self.row("i1", "matches", "y"), self.row("i2", "matches", "x")],
                             [self.row("i1", "matches", "x"), self.row("i1", "differs", "y"), self.row("i2", "matches", "x")])
        table = record["tables"]["Verdicts"]
        self.assertEqual([("i1", "x", "matches"), ("i1", "y", "differs"), ("i2", "x", "matches")],
                         [(r["Item"], r["Part"], r["Verdict"]) for r in table["rows"]])
        self.assertEqual([("Verdicts", ("i1", "y"))], merge.failing_items(self.KEYED, self.NAMED, record))


if __name__ == "__main__":
    unittest.main()
