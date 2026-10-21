#!/usr/bin/env python3
"""The review kit's scheduler over the stub: ordering, the bound, the record, and what a fatal, local or rate-limit result appends.

The stub plays the sessions and the clock is injected; no model, no network and no KiCad are used.
"""

from __future__ import annotations

import json
import os
import random
import sys
import tempfile
import threading
import time
import unittest
from dataclasses import replace

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import review_kit_fixtures as fx  # noqa: E402
from review_kit import executor as ex  # noqa: E402
from review_kit import catalogue, decl, planner, results, scheduler, store  # noqa: E402

NO_OBJECT = ex.Reply(text="I looked at the views and found them mostly fine.")


def with_ten_groups():
    raw = fx.declaration_dict()
    raw["units"] = {f"n{index}": {"items": [f"n{index}-item"], "template": "t", "needs": ["guide.md"],
                                  "expected_output_tokens": 100, "values": {"area": f"n{index}"}} for index in range(10)}
    return raw


class Tracking(ex.StubExecutor):
    """A stub whose sessions take a moment, and which counts how many are running at once."""

    active = 0
    peak = 0
    guard = threading.Lock()

    def execute(self, call):
        cls = type(self)
        with cls.guard:
            cls.active += 1
            cls.peak = max(cls.peak, cls.active)
        try:
            time.sleep(0.03 if call.label != "root" else 0)
            return super().execute(call)
        finally:
            with cls.guard:
                cls.active -= 1


class Jittered(ex.StubExecutor):
    """A stub whose sessions finish in an order set by a seed."""

    seed = 0

    def execute(self, call):
        time.sleep(random.Random(f"{type(self).seed}{call.label}").random() * 0.02)
        return super().execute(call)


def without_session_times(record):
    return json.loads(json.dumps(record))


class OrderingTests(unittest.TestCase):
    def test_shared_context_is_started_once_before_every_fork(self):
        # SOL-HW-REVIEW-KIT.C6: the shared context is started once and before every fork
        harness = fx.Harness(self)
        harness.fresh()
        calls = harness.executor.calls
        self.assertEqual(calls[0].label, "root")
        self.assertEqual([c.label for c in calls].count("root"), 1)
        root_session = [s for s in harness.executor.sessions][0]
        self.assertEqual(len(calls), 1 + 3)
        for call in calls[1:]:
            self.assertEqual((call.parent, call.fork), (root_session, True))
        self.assertIsNone(calls[0].parent)
        self.assertEqual(calls[0].message, harness.shared.message)

    def test_every_session_starts_from_one_specification(self):
        # SOL-HW-REVIEW-KIT.C6: only the message and the session forked from differ between the sessions of a review
        harness = fx.Harness(self, script={"G1.r1.a1": ex.Reply(structured={"tables": {"Verdicts": [], "Findings": []}}, text="x")})
        harness.fresh()
        self.assertGreater(len(harness.executor.calls), 4)  # the root, the forks and a repair turn
        self.assertEqual({c.spec.digest for c in harness.executor.calls}, {harness.spec.digest})

        def stripped(arguments):
            found = list(arguments)
            for flag in ("--resume", "--fork-session"):
                if flag in found:
                    at = found.index(flag)
                    del found[at:at + (2 if flag == "--resume" else 1)]
            return found

        self.assertEqual(len({tuple(stripped(a)) for a in harness.executor.arguments}), 1)

    def test_no_more_than_the_bound_run_at_once(self):
        # SOL-HW-REVIEW-KIT.C6: no more than the stated number of sessions run at once however many units there are
        for bound in (1, 3):
            with self.subTest(bound=bound):
                class Mine(Tracking):
                    active = 0
                    peak = 0
                    guard = threading.Lock()

                harness = fx.Harness(self, raw=with_ten_groups(), bound=bound, executor_class=Mine)
                self.assertEqual(len(harness.plan.groups), 10)
                harness.fresh()
                self.assertEqual(len(harness.executor.calls), 11)
                self.assertEqual(Mine.peak, bound)

    def test_a_bound_below_one_is_refused_before_any_session(self):
        # SOL-HW-REVIEW-KIT.C6: a bound below one is refused
        harness = fx.Harness(self)
        for bad in (0, -1):
            with self.subTest(bad=bad):
                with self.assertRaises(planner.BoundBelowOne):
                    scheduler.ThreadedConcurrency().run([lambda: 1], bad)
                with self.assertRaises(planner.BoundBelowOne):
                    scheduler.SerialConcurrency().run([lambda: 1], bad)
        with self.assertRaises(planner.BoundBelowOne):
            planner.make_plan(harness.declaration, catalogue.admit(harness.declaration, harness.review),
                              harness.shared, harness.spec, bound=0, cli_version="v", tool_commit="c")
        broken = replace(harness.plan, bound=0)
        with self.assertRaises(planner.BoundBelowOne):
            harness.scheduler.run(harness.declaration, broken, harness.shared, harness.spec)
        self.assertEqual(harness.executor.calls, [])

    def test_the_record_is_the_same_for_every_order_the_sessions_finish_in(self):
        # SOL-HW-REVIEW-KIT.C6: the record is the same for every order the stub finishes the sessions in
        script = {"G2.r1.a1": NO_OBJECT}
        records = []
        shared_base = tempfile.TemporaryDirectory()
        self.addCleanup(shared_base.cleanup)
        count = iter(range(100))

        def made(**kwargs):
            return fx.Harness(self, script=dict(script), replicas=2, base=shared_base.name, out_name=f"out{next(count)}", **kwargs)

        orders = [scheduler.SerialConcurrency(), scheduler.SerialConcurrency(lambda n: list(reversed(range(n)))),
                  scheduler.SerialConcurrency(lambda n: random.Random(5).sample(range(n), n))]
        for seed in (1, 2, 3):
            class Mine(Jittered):
                pass

            Mine.seed = seed
            harness = made(executor_class=Mine)
            records.append(without_session_times(harness.fresh()))
        for concurrency in orders:
            records.append(without_session_times(made(concurrency=concurrency).fresh()))
        for other in records[1:]:
            self.assertEqual(other, records[0])
        self.assertEqual(len({json.dumps(r, sort_keys=True) for r in records}), 1)


class AppendedNodeTests(unittest.TestCase):
    def test_fatal_result_appends_a_fresh_fork_of_the_same_parent_as_the_next_attempt(self):
        # SOL-HW-REVIEW-KIT.C6: a fatal result appends a fresh fork of the same parent as the next attempt of the unit
        harness = fx.Harness(self, script={"G1.r1.a1": NO_OBJECT})
        record = harness.fresh()
        nodes = [n for n in record["nodes"] if n["group"] == "G1"]
        self.assertEqual([(n["id"], n["role"], n["parent"], n["attempt"]) for n in nodes],
                         [("G1.r1.a1", "unit", "root", 1), ("G1.r1.a2", "unit", "root", 2)])
        first, second = [c for c in harness.executor.calls if c.label.startswith("G1.")]
        self.assertEqual((second.parent, second.fork), (first.parent, True))
        self.assertEqual(second.message, first.message)
        self.assertFalse(record["units"]["u1"]["failed"])
        attempts = [a for lane in record["lanes"] if lane["group"] == "G1" for a in lane["record"]["attempts"]]
        self.assertEqual([a["source"] for a in attempts], [results.NONE, results.STRUCTURED])
        self.assertEqual(attempts[0]["problems"][0]["class"], results.FATAL)
        self.assertIn("I looked at the views", attempts[0]["raw"])

    def test_error_exit_and_empty_answer_are_fatal_results(self):
        # SOL-HW-REVIEW-KIT.C6: an error or an empty answer is a fatal result
        for reply, kind in ((ex.Reply(exit_code=1, is_error=True, text="boom"), "error"),
                            (ex.Reply(text=""), "empty")):
            with self.subTest(kind=kind):
                harness = fx.Harness(self, script={"G3.r1.a1": reply})
                record = harness.fresh()
                nodes = [n for n in record["nodes"] if n["group"] == "G3"]
                self.assertEqual([(n["id"], n["kind"], n["parent"]) for n in nodes], [("G3.r1.a1", kind, "root"), ("G3.r1.a2", "ok", "root")])
                self.assertEqual(nodes[1]["role"], "unit")

    def test_local_problem_appends_a_repair_turn_in_the_units_own_session(self):
        # SOL-HW-REVIEW-KIT.C6: a local problem appends a repair turn in that unit's own session
        short = fx.good_answer(harness_decl(), ["u1"])
        short["tables"]["Verdicts"].pop()  # no verdict for i2
        harness = fx.Harness(self, script={"G1.r1.a1": ex.Reply(structured=short, text="x")})
        record = harness.fresh()
        nodes = [n for n in record["nodes"] if n["group"] == "G1"]
        self.assertEqual([(n["id"], n["role"], n["parent"], n["attempt"]) for n in nodes],
                         [("G1.r1.a1", "unit", "root", 1), ("G1.r1.a2", "repair", "G1.r1.a1", 2)])
        first, repair = [c for c in harness.executor.calls if c.label.startswith("G1.")]
        self.assertFalse(repair.fork)
        fork_session = [s for s, _ in harness.executor.sessions.items()][1]
        self.assertEqual(repair.parent, fork_session)
        self.assertNotEqual(repair.parent, first.parent)
        self.assertIn("gives no verdict for item 'i2'", repair.message)
        self.assertNotIn("--fork-session", repair.arguments)
        self.assertIn("--resume", repair.arguments)
        self.assertFalse(record["units"]["u1"]["failed"])

    def test_repair_turn_that_fixes_the_answer_stands_over_the_flawed_one(self):
        # SOL-HW-REVIEW-KIT.C6: a local problem appends a repair turn, and the attempt that stands is the one with no problems
        short = fx.good_answer(harness_decl(), ["u1"])
        short["tables"]["Verdicts"].pop()
        harness = fx.Harness(self, script={"G1.r1.a1": ex.Reply(structured=short, text="x")})
        record = harness.fresh()
        lane = [l for l in record["lanes"] if l["group"] == "G1"][0]
        self.assertEqual(lane["record"]["standing"], 1)
        self.assertEqual(len(lane["record"]["attempts"]), 2)
        self.assertEqual(len(lane["record"]["attempts"][0]["problems"]), 1)
        self.assertIsNone(lane["failure"])

    def test_cosmetic_problems_are_repaired_and_cost_no_attempt(self):
        # SOL-HW-REVIEW-KIT.C6: out of scope is classing the problems, which the results module does; a cosmetic one adds no node
        answer = fx.good_answer(harness_decl(), ["u1"])
        answer["tables"]["Verdicts"][0]["Note"] = "a | b"
        harness = fx.Harness(self, script={"G1.r1.a1": ex.Reply(structured=answer, text="x")})
        record = harness.fresh()
        self.assertEqual([n["id"] for n in record["nodes"] if n["group"] == "G1"], ["G1.r1.a1"])
        attempt = [l for l in record["lanes"] if l["group"] == "G1"][0]["record"]["attempts"][0]
        self.assertEqual(attempt["problems"], [])
        self.assertTrue(attempt["repairs"])

    def test_rate_limit_waits_on_the_clock_and_retries_the_same_node(self):
        # SOL-HW-REVIEW-KIT.C6: a rate limit waits on the clock and retries the same node
        limited = ex.Reply(is_error=True, api_error_status=429, exit_code=1, text="rate limit")
        harness = fx.Harness(self, script={"G3.r1.a1": [limited, limited, ex.Reply(structured=fx.good_answer(harness_decl(), ["u4"]), text="x")]})
        record = harness.fresh()
        nodes = [n for n in record["nodes"] if n["group"] == "G3"]
        self.assertEqual(len(nodes), 1)
        self.assertEqual((nodes[0]["id"], nodes[0]["kind"], nodes[0]["tries"], nodes[0]["waits"]), ("G3.r1.a1", "ok", 3, [10, 30]))
        self.assertEqual(harness.clock.slept, [10, 30])
        self.assertEqual(harness.executor.executions, 1 + 3 + 2)
        self.assertEqual(len(harness.executor.calls), 4)

    def test_rate_limit_that_outlasts_the_retries_is_a_failed_attempt(self):
        # SOL-HW-REVIEW-KIT.C6: a rate limit waits on the clock and retries; one that never clears is reported
        limited = ex.Reply(is_error=True, api_error_status=429, exit_code=1, text="rate limit")
        harness = fx.Harness(self, script={"G3.r1.a1": limited}, attempts=1)
        record = harness.fresh()
        self.assertEqual(harness.clock.slept, [10, 30])
        self.assertTrue(record["units"]["u4"]["failed"])
        self.assertIn("rate_limit", record["lanes"][2]["failure"]["problems"][0])

    def test_unit_still_holding_a_problem_is_reported_and_other_results_are_kept(self):
        # SOL-HW-REVIEW-KIT.C6: a unit still holding a problem after its stated number of attempts is reported naming the unit and what it returned while the other units' results are kept
        harness = fx.Harness(self, script={"G2.r1.a1": NO_OBJECT, "G2.r1.a2": NO_OBJECT, "G2.r1.a3": NO_OBJECT})
        record = harness.fresh()
        self.assertEqual(len([n for n in record["nodes"] if n["group"] == "G2"]), 3)
        failure = [l for l in record["lanes"] if l["failure"]]
        self.assertEqual(len(failure), 1)
        self.assertEqual(failure[0]["failure"]["units"], ["u2", "u3"])
        self.assertIn("I looked at the views", failure[0]["failure"]["returned"])
        self.assertIn("holds no object", failure[0]["failure"]["problems"][0])
        self.assertEqual({u: s["failed"] for u, s in record["units"].items()}, {"u1": False, "u2": True, "u3": True, "u4": False})
        for lane in record["lanes"]:
            if lane["group"] != "G2":
                self.assertEqual(lane["record"]["attempts"][lane["record"]["standing"]]["problems"], [])
                self.assertIsNotNone(lane["record"]["attempts"][0]["tables"])
        self.assertEqual(record["units"]["u2"]["problems"][0][:10], "replica 1:")

    def stray_item_answer(self):
        stray = fx.good_answer(harness_decl(), ["u1"])
        stray["tables"]["Findings"] = [{"No": 1, "Item": "i1 / i2", "Detail": "d"}]
        return stray

    def test_a_findings_row_outside_the_checklist_gets_a_repair_turn_and_the_run_merges(self):
        # SOL-HW-REVIEW-KIT.C6: a local problem, here a findings row naming two items in one cell, appends a repair turn listing the row, and the repaired answer stands
        fixed = fx.good_answer(harness_decl(), ["u1"])
        fixed["tables"]["Findings"] = [{"No": 1, "Item": "i1", "Detail": "d"}, {"No": 2, "Item": "i2", "Detail": "d"}]
        harness = fx.Harness(self, script={"G1.r1.a1": ex.Reply(structured=self.stray_item_answer(), text="x"),
                                           "G1.r1.a2": ex.Reply(structured=fixed, text="x")})
        record = harness.fresh()
        nodes = [n for n in record["nodes"] if n["group"] == "G1"]
        self.assertEqual([(n["id"], n["role"]) for n in nodes], [("G1.r1.a1", "unit"), ("G1.r1.a2", "repair")])
        repair = [c for c in harness.executor.calls if c.label == "G1.r1.a2"][0]
        self.assertFalse(repair.fork)
        self.assertIn("'i1 / i2'", repair.message)
        self.assertIn("'Item'", repair.message)
        self.assertIn("row 1", repair.message)
        self.assertIn("['i1', 'i2']", repair.message)
        lane = [l for l in record["lanes"] if l["group"] == "G1"][0]
        self.assertEqual(lane["record"]["standing"], 1)
        self.assertIsNone(lane["failure"])
        self.assertFalse(record["units"]["u1"]["failed"])

    def test_a_findings_row_outside_the_checklist_that_is_never_repaired_names_the_unit(self):
        # SOL-HW-REVIEW-KIT.C6: a unit still holding a problem after its attempts is reported naming the unit and the row, and the other units' results are kept
        stray = ex.Reply(structured=self.stray_item_answer(), text="x")
        harness = fx.Harness(self, script={"G1.r1.a1": stray, "G1.r1.a2": stray, "G1.r1.a3": stray})
        record = harness.fresh()
        self.assertEqual(len([n for n in record["nodes"] if n["group"] == "G1"]), 3)
        failures = [l["failure"] for l in record["lanes"] if l["failure"]]
        self.assertEqual(len(failures), 1)
        self.assertEqual(failures[0]["units"], ["u1"])
        self.assertIn("'i1 / i2'", failures[0]["problems"][0])
        self.assertTrue(record["units"]["u1"]["failed"])
        self.assertFalse(record["units"]["u4"]["failed"])

    def test_a_later_attempt_never_replaces_a_better_one(self):
        # SOL-HW-REVIEW-KIT.C6: every attempt is kept and a later attempt never replaces a better one
        short = fx.good_answer(harness_decl(), ["u1"])
        short["tables"]["Verdicts"].pop()
        script = {"G1.r1.a1": ex.Reply(structured=short, text="x"), "G1.r1.a2": NO_OBJECT, "G1.r1.a3": NO_OBJECT}
        harness = fx.Harness(self, script=script)
        record = harness.fresh()
        lane = [l for l in record["lanes"] if l["group"] == "G1"][0]
        self.assertEqual(lane["record"]["standing"], 0)
        self.assertEqual(len(lane["record"]["attempts"]), 3)
        self.assertEqual(lane["failure"]["problems"], [lane["record"]["attempts"][0]["problems"][0]["where"] + ": "
                                                       + lane["record"]["attempts"][0]["problems"][0]["what"]])
        # a fatal answer after a local one is a fresh fork of the root, not a repair
        self.assertEqual([n["role"] for n in record["nodes"] if n["group"] == "G1"], ["unit", "repair", "unit"])

    def test_start_report_that_shows_what_the_specification_excludes_fails_the_group_without_a_retry(self):
        # SOL-HW-REVIEW-KIT.C6: a unit still holding a problem is reported with the other units' results kept
        harness = fx.Harness(self, script={"G3.r1.a1": ex.Reply(structured=fx.good_answer(harness_decl(), ["u4"]), text="x", tools=["Bash"])})
        record = harness.fresh()
        nodes = [n for n in record["nodes"] if n["group"] == "G3"]
        self.assertEqual(len(nodes), 1)
        self.assertEqual(nodes[0]["kind"], "start-report")
        self.assertTrue(record["units"]["u4"]["failed"])
        self.assertIn("started with tools", record["lanes"][2]["failure"]["returned"])
        self.assertFalse(record["units"]["u1"]["failed"])

    def test_replicas_run_as_separate_forks_of_the_one_shared_context(self):
        # SOL-HW-REVIEW-KIT.C6: one fork per group and replica
        harness = fx.Harness(self, replicas=2, variants=["full", "terse"])
        record = harness.fresh()
        forks = [n for n in record["nodes"] if n["role"] == "unit"]
        self.assertEqual(len(forks), 6)
        self.assertEqual(len(record["lanes"]), 6)
        self.assertEqual({n["variant"] for n in forks}, {"full", "terse"})
        self.assertEqual(len([c for c in harness.executor.calls if c.label == "root"]), 1)

    def test_attempts_must_be_a_whole_number_of_one_or_more(self):
        # SOL-HW-REVIEW-KIT.C6: a unit gets a stated number of attempts
        for bad in (0, -1, 1.5, True):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    fx.Harness(self, attempts=bad)
        record = fx.Harness(self, attempts=1, script={"G1.r1.a1": NO_OBJECT}).fresh()
        self.assertEqual(len([n for n in record["nodes"] if n["group"] == "G1"]), 1)
        self.assertTrue(record["units"]["u1"]["failed"])


class ChecksOnTheStreamsTests(unittest.TestCase):
    def test_shared_context_that_narrates_is_flagged_in_the_record(self):
        # SOL-HW-REVIEW-KIT.C6: the shared context is a node whose stream is checked to be one
        harness = fx.Harness(self, root=ex.Reply(text="Let me read all of this first.", write=100))
        record = harness.fresh()
        self.assertEqual(len(record["nodes"][0]["flags"]), 1)
        self.assertIn("not the acknowledgement", record["nodes"][0]["flags"][0])
        clean = fx.Harness(self).fresh()
        self.assertEqual(clean["nodes"][0]["flags"], [])

    def test_fork_that_misses_the_cache_is_flagged_with_the_figures(self):
        # SOL-HW-REVIEW-KIT.C6: a fork whose first call reads less than the parent's prefix is flagged
        harness = fx.Harness(self, script={"G1.r1.a1": ex.Reply(structured=fx.good_answer(harness_decl(), ["u1"]), text="x", read=0, write=100)})
        record = harness.fresh()
        flagged = [n for n in record["nodes"] if n["flags"] and n["group"]]
        self.assertEqual([n["id"] for n in flagged], ["G1.r1.a1"])
        self.assertIn("100 tokens", flagged[0]["flags"][0])
        self.assertEqual([n["flags"] for n in record["nodes"] if n["id"] == "G3.r1.a1"], [[]])

    def test_a_shared_context_that_fails_stops_the_run_before_any_fork(self):
        # SOL-HW-REVIEW-KIT.C6: the shared context is started once and before every fork
        harness = fx.Harness(self, root=ex.Reply(exit_code=1, is_error=True, text="boom"))
        with self.assertRaises(scheduler.RootFailed) as raised:
            harness.fresh()
        self.assertIn("boom", str(raised.exception))
        self.assertEqual(len(harness.executor.calls), 1)
        self.assertFalse(os.path.exists(os.path.join(harness.out, store.RECORD_NAME)))
        self.assertFalse(os.path.exists(os.path.join(harness.out, store.LOCK_NAME)))


class CannotJudgeTurnTests(unittest.TestCase):
    def judged(self, verdict_rows, **options):
        """A harness whose G1 first answer gives `verdict_rows` (item, verdict, note) for u1, with `script` for later nodes."""
        script = dict(options.pop("script", {}))
        answer = fx.good_answer(harness_decl(), ["u1"])
        answer["tables"]["Verdicts"] = [{"Item": i, "Verdict": v, "Note": n} for i, v, n in verdict_rows]
        script["G1.r1.a1"] = ex.Reply(structured=answer, text="x")
        return fx.Harness(self, script=script, **options)

    def answer_of(self, rows):
        answer = fx.good_answer(harness_decl(), ["u1"])
        answer["tables"]["Verdicts"] = [{"Item": i, "Verdict": v, "Note": n} for i, v, n in rows]
        return ex.Reply(structured=answer, text="x")

    def g1(self, record):
        return [n for n in record["nodes"] if n["group"] == "G1"]

    def test_a_first_answer_with_a_cannot_judge_gets_exactly_one_repair_turn_naming_the_item_and_advising_retrieval(self):
        # SOL-HW-REVIEW-KIT.C6: A verdict row of cannot judge in a unit's first answer appends one repair turn in that unit's own session, advising it to retrieve a document its Why asks for with the retrieval tool the caller grants and otherwise to keep the cannot judge naming the view it needs
        harness = self.judged([("i1", "cannot judge", "needs the datasheet of U1"), ("i2", "pass", "fine")],
                              script={"G1.r1.a2": self.answer_of([("i1", "pass", "read"), ("i2", "pass", "fine")])})
        record = harness.fresh()
        nodes = self.g1(record)
        self.assertEqual([(n["id"], n["role"], n["parent"]) for n in nodes],
                         [("G1.r1.a1", "unit", "root"), ("G1.r1.a2", "repair", "G1.r1.a1")])
        first, turn = [c for c in harness.executor.calls if c.label.startswith("G1.")]
        self.assertFalse(turn.fork)
        self.assertIn("--resume", turn.arguments)
        self.assertNotIn("--fork-session", turn.arguments)
        for text in ("i1: needs the datasheet of U1", "published document", "retrieval tool you have", "re-judge",
                     "keep cannot judge and name the view needed"):
            self.assertIn(text, turn.message)
        self.assertNotIn("i2:", turn.message, "a row that judged is not listed")

    def test_a_repaired_answer_that_retrieves_and_judges_replaces_the_cannot_judge(self):
        # SOL-HW-REVIEW-KIT.C6: the repaired answer stands whatever it says
        harness = self.judged([("i1", "cannot judge", "needs the datasheet"), ("i2", "pass", "")],
                              script={"G1.r1.a2": self.answer_of([("i1", "pass", "read it"), ("i2", "pass", "")])})
        record = harness.fresh()
        lane = [l for l in record["lanes"] if l["group"] == "G1"][0]
        self.assertEqual(lane["record"]["standing"], 1)
        self.assertEqual({r["Item"]: r["Verdict"] for r in lane["record"]["attempts"][1]["tables"]["Verdicts"]}["i1"], "pass")
        self.assertTrue(lane["record"]["attempts"][0]["judge_asked"])
        self.assertFalse(lane["record"]["attempts"][1]["judge_asked"])
        self.assertIsNone(lane["failure"])

    def test_a_repaired_answer_that_still_says_cannot_judge_stands_and_is_not_a_failure(self):
        # SOL-HW-REVIEW-KIT.C6: the repaired answer stands whatever it says, so a cannot judge that remains is not a failed attempt and goes to the caller's resolution at the merge
        still = self.answer_of([("i1", "cannot judge", "needs crop-Y1: no view of it"), ("i2", "pass", "")])
        harness = self.judged([("i1", "cannot judge", "needs crop-Y1: no view of it"), ("i2", "pass", "")],
                              script={"G1.r1.a2": still})
        record = harness.fresh()
        self.assertEqual(len(self.g1(record)), 2, "no further turn")
        lane = [l for l in record["lanes"] if l["group"] == "G1"][0]
        self.assertEqual(lane["record"]["standing"], 1)
        self.assertIsNone(lane["failure"])
        self.assertFalse(record["units"]["u1"]["failed"])
        self.assertEqual(lane["record"]["attempts"][1]["problems"], [])

    def test_a_repaired_answer_that_gains_a_local_problem_leaves_the_first_answer_standing(self):
        # SOL-HW-REVIEW-KIT.C6: best-of does not choose a worse attempt: a repair turn that gains a local problem is handled by the existing order
        worse = self.answer_of([("i1", "pass", "read")])  # no verdict for i2
        harness = self.judged([("i1", "cannot judge", "needs the datasheet"), ("i2", "pass", "")],
                              script={"G1.r1.a2": worse, "G1.r1.a3": worse}, attempts=3)
        record = harness.fresh()
        lane = [l for l in record["lanes"] if l["group"] == "G1"][0]
        self.assertEqual(lane["record"]["standing"], 0)
        self.assertEqual(len(self.g1(record)), 3)

    def test_a_caller_declaring_no_cannot_judge_verdict_gets_no_turn(self):
        # SOL-HW-REVIEW-KIT.C6: a caller that declares no cannot-judge verdict gets no such turn
        harness = self.judged([("i1", "cannot judge", "needs the datasheet"), ("i2", "pass", "")])
        harness.scheduler.cannot_judge = None
        record = harness.fresh()
        self.assertEqual(len(self.g1(record)), 1)
        raw = fx.declaration_dict()
        raw["schema"]["tables"][0]["verdicts"] = ["pass", "fail"]
        shape = decl.parse(json.dumps(raw), "caller.json").shape
        rows = {"Verdicts": [{"Item": "i1", "Verdict": "cannot judge", "Note": "n"}]}
        self.assertEqual(results.cannot_judge_rows(rows, shape, "cannot judge"), [])
        self.assertEqual(results.cannot_judge_rows(rows, harness_decl().shape, "cannot judge"), [("i1", "n")])

    def test_a_cannot_judge_after_a_local_repair_gets_no_further_turn(self):
        # SOL-HW-REVIEW-KIT.C6: a verdict row of cannot judge in a unit's first answer appends one repair turn; a later answer's gets none
        first = self.answer_of([("i1", "pass", "")])  # a local problem: no verdict for i2
        second = self.answer_of([("i1", "cannot judge", "needs the datasheet"), ("i2", "pass", "")])
        harness = fx.Harness(self, script={"G1.r1.a1": first, "G1.r1.a2": second}, attempts=4)
        record = harness.fresh()
        self.assertEqual([n["role"] for n in self.g1(record)], ["unit", "repair"])
        lane = [l for l in record["lanes"] if l["group"] == "G1"][0]
        self.assertEqual(lane["record"]["standing"], 1)
        self.assertIsNone(lane["failure"])

    def test_a_first_answer_with_a_local_problem_and_a_cannot_judge_gets_one_turn_holding_both(self):
        # SOL-HW-REVIEW-KIT.C6: a verdict row of cannot judge in a unit's first answer appends one repair turn
        first = self.answer_of([("i1", "cannot judge", "needs the datasheet")])  # and no verdict for i2
        harness = fx.Harness(self, script={"G1.r1.a1": first,
                                           "G1.r1.a2": self.answer_of([("i1", "pass", "x"), ("i2", "pass", "")])})
        record = harness.fresh()
        turns = [c for c in harness.executor.calls if c.label == "G1.r1.a2"]
        self.assertEqual(len(turns), 1)
        self.assertIn("gives no verdict for item 'i2'", turns[0].message)
        self.assertIn("i1: needs the datasheet", turns[0].message)
        self.assertEqual(len(self.g1(record)), 2)

    def test_with_only_one_attempt_a_cannot_judge_gets_no_turn(self):
        # SOL-HW-REVIEW-KIT.C6: a group gets a stated number of attempts, repair turns included
        harness = self.judged([("i1", "cannot judge", "needs the datasheet"), ("i2", "pass", "")], attempts=1)
        self.assertEqual(len(self.g1(harness.fresh())), 1)


def harness_decl():
    return decl.parse(json.dumps(fx.declaration_dict()), "caller.json")


if __name__ == "__main__":
    unittest.main()
