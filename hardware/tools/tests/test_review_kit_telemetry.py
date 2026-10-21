#!/usr/bin/env python3
"""The review kit's figures for a session and a run, held to the recorded streams of the live runs.

The sessions made up here alter one figure of a recorded session, so each rule is shown to fail for the figure it names.
No model, no network and no KiCad are used.
"""

from __future__ import annotations

import copy
import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
sys.path.insert(0, TOOLS)

from review_kit import streams, telemetry  # noqa: E402

FIXTURES = os.path.join(HERE, "fixtures", "review_streams")
with open(os.path.join(FIXTURES, "manifest.json"), encoding="utf-8") as handle:
    MANIFEST = json.load(handle)
VALIDATION = MANIFEST["validation"]


def recorded(name):
    return streams.read_stream_file(os.path.join(FIXTURES, name))


def probe(name):
    return recorded(MANIFEST["probes"][name]["file"])


def validation_run():
    """Every session of the live validation, each fork with the root it was forked from."""
    figures = []
    for arm, root_file in VALIDATION["roots"].items():
        root = recorded(root_file)
        figures.append(telemetry.session_figures(root))
        figures.extend(telemetry.session_figures(recorded(f"validation/{name}.jsonl"), root) for name in VALIDATION["forks"][arm])
    return figures


class SessionFigures(unittest.TestCase):
    def test_a_forks_cost_and_time_are_its_reported_figures_less_the_parents(self):
        # SOL-HW-REVIEW-KIT.C4: a fork's cost, time and turns are its reported figures less the parent's
        root, fork = recorded(VALIDATION["roots"]["sonnet"]), recorded("validation/sonnet-FULL-area-EMI.jsonl")
        own = telemetry.session_figures(fork, root)
        self.assertEqual(root.result["total_cost_usd"], 1.1259003)
        self.assertEqual(fork.result["total_cost_usd"], 1.2077518)
        self.assertAlmostEqual(own.cost_usd, 1.2077518 - 1.1259003, places=6)
        self.assertEqual(own.api_ms, fork.result["duration_api_ms"] - root.result["duration_api_ms"])
        self.assertEqual(own.api_ms, 60825 - 19807)
        self.assertEqual(own.parent, root.session_id)
        # The root has no parent to take from, so its own figures are its reported ones.
        self.assertEqual(telemetry.session_figures(root).cost_usd, round(1.1259003, 6))

    def test_a_fork_of_a_fork_takes_the_figures_of_the_fork_above_it(self):
        # SOL-HW-REVIEW-KIT.C4: a fork's cost, time and turns are its reported figures less the parent's
        node, fork = probe("p6"), probe("p7")
        own = telemetry.session_figures(fork, node)
        self.assertAlmostEqual(own.cost_usd, fork.result["total_cost_usd"] - node.result["total_cost_usd"], places=6)
        self.assertAlmostEqual(own.cost_usd, 0.0392913 - 0.0352177, places=6)
        self.assertEqual(own.api_ms, fork.result["duration_api_ms"] - node.result["duration_api_ms"])

    def test_the_turns_are_the_reports_own_because_the_report_does_not_carry_the_parents(self):
        # SOL-HW-REVIEW-KIT.C4: a fork's turns, as the command line reports them
        root, fork = recorded(VALIDATION["roots"]["sonnet"]), recorded("validation/sonnet-FULL-area-EMI.jsonl")
        self.assertEqual((root.result["num_turns"], fork.result["num_turns"]), (1, 1))
        self.assertEqual(telemetry.session_figures(fork, root).turns, 1)
        self.assertEqual(telemetry.session_figures(root).turns, 1)

    def test_calls_are_counted_by_distinct_message_identifier(self):
        # SOL-HW-REVIEW-KIT.C4: calls are counted by distinct message identifier
        fork = recorded("validation/sonnet-FULL-area-EMI.jsonl")
        with open(os.path.join(FIXTURES, "validation/sonnet-FULL-area-EMI.jsonl"), encoding="utf-8") as handle:
            records = [json.loads(line) for line in handle]
        assistant = [record for record in records if record["type"] == "assistant"]
        self.assertEqual(len(assistant), 2)  # the thinking and the text of one call were printed as two records
        self.assertEqual(len({record["message"]["id"] for record in assistant}), 1)
        self.assertEqual(telemetry.session_figures(fork).calls, 1)

    def test_a_session_of_several_calls_counts_each_once_and_sums_their_tokens(self):
        # SOL-HW-REVIEW-KIT.C4: calls are counted by distinct message identifier, and tokens are split into read from the cache, written to it, fresh and generated
        figures = {"cache_read_input_tokens": 100, "cache_creation_input_tokens": 10, "input_tokens": 2}
        text = "\n".join(json.dumps(event) for event in [
            {"type": "assistant", "message": {"id": "a", "content": [{"type": "text", "text": "x"}], "usage": figures}},
            {"type": "assistant", "message": {"id": "a", "content": [{"type": "text", "text": "y"}], "usage": figures}},
            {"type": "assistant", "message": {"id": "b", "content": [{"type": "text", "text": "z"}], "usage": figures}},
            {"type": "result", "total_cost_usd": 1.0, "duration_api_ms": 5, "num_turns": 3, "usage": {"output_tokens": 40}}])
        own = telemetry.session_figures(streams.read_stream(text))
        self.assertEqual((own.calls, own.tokens), (2, {"cache_read": 200, "cache_write": 20, "fresh": 4, "generated": 40}))

    def test_the_tokens_are_split_and_the_generated_ones_come_from_the_result_report(self):
        # SOL-HW-REVIEW-KIT.C4: tokens are split into read from the cache, written to it, fresh and generated
        fork = recorded("validation/sonnet-FULL-area-EMI.jsonl")
        self.assertEqual(fork.calls[0].usage["output_tokens"], 2)  # the call's own record still counts the first tokens
        own = telemetry.session_figures(fork, recorded(VALIDATION["roots"]["sonnet"]))
        self.assertEqual(own.tokens, {"cache_read": 267515, "cache_write": 2454, "fresh": 2, "generated": 4528})
        self.assertEqual(own.first_call_read, 267515)
        root = telemetry.session_figures(recorded(VALIDATION["roots"]["sonnet"]))
        self.assertEqual(root.tokens, {"cache_read": 3633, "cache_write": 264552, "fresh": 2, "generated": 5})

    def test_wall_time_is_the_reports_own_duration(self):
        # SOL-HW-REVIEW-KIT.C4: a session's time
        own = telemetry.session_figures(recorded("validation/sonnet-FULL-area-EMI.jsonl"), recorded(VALIDATION["roots"]["sonnet"]))
        self.assertEqual(own.wall_s, 41.115)
        bare = copy.deepcopy(recorded("validation/sonnet-FULL-area-EMI.jsonl"))
        del bare.result["duration_ms"]
        self.assertEqual(telemetry.session_figures(bare).wall_s, 60.825)

    def test_a_report_that_lacks_a_figure_is_an_error_naming_the_session_and_the_figure(self):
        # SOL-HW-REVIEW-KIT.C4: a recorded session's figures are never defaulted
        fork = recorded("validation/sonnet-FULL-area-EMI.jsonl")
        for key, message in (("total_cost_usd", "total_cost_usd"), ("duration_api_ms", "duration_api_ms"), ("num_turns", "num_turns")):
            broken = copy.deepcopy(fork)
            del broken.result[key]
            with self.assertRaises(telemetry.FigureError) as caught:
                telemetry.session_figures(broken)
            self.assertIn(fork.session_id, str(caught.exception))
            self.assertIn(message, str(caught.exception))
        for damage in ({"usage": {}}, {"usage": None}, {"total_cost_usd": "1.2"}, {"num_turns": True}):
            broken = copy.deepcopy(fork)
            broken.result.update(damage)
            with self.assertRaises(telemetry.FigureError):
                telemetry.session_figures(broken)
        with self.assertRaises(telemetry.FigureError) as caught:
            telemetry.session_figures(streams.read_stream(""))
        self.assertIn("no result report", str(caught.exception))

    def test_a_fork_reported_below_its_parent_cannot_have_its_own_told(self):
        # SOL-HW-REVIEW-KIT.C4: a fork's cost and time are its reported figures less the parent's
        root, fork = recorded(VALIDATION["roots"]["sonnet"]), copy.deepcopy(recorded("validation/sonnet-FULL-area-EMI.jsonl"))
        fork.result["total_cost_usd"] = 1.0
        with self.assertRaises(telemetry.FigureError) as caught:
            telemetry.session_figures(fork, root)
        self.assertIn("reported cost 1.0 is below its parent's 1.1259003", str(caught.exception))
        fork = copy.deepcopy(recorded("validation/sonnet-FULL-area-EMI.jsonl"))
        fork.result["duration_api_ms"] = 5
        with self.assertRaises(telemetry.FigureError) as caught:
            telemetry.session_figures(fork, root)
        self.assertIn("API time", str(caught.exception))

    def test_a_forks_figures_equal_the_root_s_when_it_added_nothing(self):
        # SOL-HW-REVIEW-KIT.C4: a fork's own figures are zero when it reports the parent's
        root = recorded(VALIDATION["roots"]["haiku"])
        own = telemetry.session_figures(copy.deepcopy(root), root)
        self.assertEqual((own.cost_usd, own.api_ms), (0.0, 0))

    def test_the_figures_print_as_json(self):
        # SOL-HW-REVIEW-KIT.C4: the figures are available to the report as data
        own = telemetry.session_figures(recorded("validation/haiku-FULL-area-EMI.jsonl"), recorded(VALIDATION["roots"]["haiku"]))
        again = json.loads(json.dumps(own.as_dict()))
        self.assertEqual(again["tokens"], {"cache_read": 269057, "cache_write": 2458, "fresh": 2, "generated": 19453})
        self.assertEqual(again["session"], own.session)


class RunFigures(unittest.TestCase):
    def test_the_sum_of_the_sessions_own_cost_is_within_two_per_cent_of_the_reports(self):
        # SOL-HW-REVIEW-KIT.C4: over the recorded streams of the live runs the sum of the sessions' own cost is within two per cent of the cost the runs' reports give
        figures = validation_run()
        run = telemetry.run_figures(figures)
        reported = VALIDATION["reported_cost_usd"]
        self.assertEqual(run.sessions, 14)
        self.assertLessEqual(abs(run.cost_usd - reported["run"]) / reported["run"], 0.02)
        self.assertTrue(telemetry.within_report(run.cost_usd, reported["run"]))
        sonnet = sum(f.cost_usd for f in figures if f.session in {recorded(VALIDATION["roots"]["sonnet"]).session_id,
                                                                  *(recorded(f"validation/{n}.jsonl").session_id for n in VALIDATION["forks"]["sonnet"])})
        self.assertTrue(telemetry.within_report(sonnet, reported["sonnet_root"] + reported["sonnet_forks"]))
        # Taking each fork's cumulative report as its own would count the root eight times over.
        naive = sum(recorded(f"validation/{n}.jsonl").result["total_cost_usd"] for n in VALIDATION["forks"]["sonnet"])
        self.assertFalse(telemetry.within_report(naive + 1.1259, reported["sonnet_root"] + reported["sonnet_forks"]))

    def test_the_two_per_cent_bound_is_a_bound(self):
        # SOL-HW-REVIEW-KIT.C4: within two per cent
        self.assertTrue(telemetry.within_report(1.02, 1.0))
        self.assertTrue(telemetry.within_report(0.98, 1.0))
        self.assertFalse(telemetry.within_report(1.0201, 1.0))
        self.assertFalse(telemetry.within_report(0.9799, 1.0))
        self.assertFalse(telemetry.within_report(1.0, 0.0))
        self.assertTrue(telemetry.within_report(1.05, 1.0, tolerance=0.05))

    def test_the_run_totals_the_token_split_and_gives_the_sharing_ratio(self):
        # SOL-HW-REVIEW-KIT.C4: the run's figures give the sharing ratio
        run = telemetry.run_figures(validation_run())
        self.assertEqual(run.tokens["cache_read"], 3633 + 8 * 267515 + 3633 + 4 * 269057)
        self.assertEqual(run.tokens["cache_write"], sum(f.tokens["cache_write"] for f in validation_run()))
        self.assertEqual(run.sharing_ratio, round(run.tokens["cache_read"] / (run.tokens["cache_read"] + run.tokens["cache_write"]), 4))
        self.assertGreater(run.sharing_ratio, 0.8)
        self.assertEqual(telemetry.run_figures([]).sharing_ratio, None)

    def test_forks_that_read_their_prefix_write_nothing_twice(self):
        # SOL-HW-REVIEW-KIT.C4: the run's figures give the tokens written in more than one session
        self.assertEqual(telemetry.run_figures(validation_run()).duplicate_write_tokens, 0)
        chain = [telemetry.session_figures(probe("p4")), telemetry.session_figures(probe("p6"), probe("p4")),
                 telemetry.session_figures(probe("p7"), probe("p6"))]
        self.assertEqual(telemetry.run_figures(chain).duplicate_write_tokens, 0)

    def test_a_fork_that_missed_the_cache_wrote_its_parents_prefix_again(self):
        # SOL-HW-REVIEW-KIT.C4: the run's figures give the tokens written in more than one session
        pair = [telemetry.session_figures(probe("p1")), telemetry.session_figures(probe("p2"), probe("p1"))]
        run = telemetry.run_figures(pair)
        self.assertEqual(run.duplicate_write_tokens, 3261)
        self.assertEqual(run.tokens["cache_write"], 3261 + 7042)
        self.assertEqual(run.tokens["cache_read"], 3223)
        self.assertEqual(run.sharing_ratio, round(3223 / (3223 + 3261 + 7042), 4))

    def test_a_fork_that_read_part_of_the_prefix_wrote_the_rest_again(self):
        # SOL-HW-REVIEW-KIT.C4: the tokens written in more than one session
        shortened = copy.deepcopy(probe("p5"))
        shortened.calls[0].usage["cache_read_input_tokens"] = 6000
        run = telemetry.run_figures([telemetry.session_figures(probe("p4")), telemetry.session_figures(shortened, probe("p4"))])
        self.assertEqual(run.duplicate_write_tokens, 6644 - 6000)

    def test_a_fork_whose_parent_is_not_in_the_run_counts_no_duplicate(self):
        # SOL-HW-REVIEW-KIT.C4: the tokens written in more than one session
        orphan = telemetry.session_figures(probe("p2"), probe("p1"))
        self.assertEqual(telemetry.run_figures([orphan]).duplicate_write_tokens, 0)

    def test_the_critical_path_is_the_longest_chain_of_wall_time(self):
        # SOL-HW-REVIEW-KIT.C4: the run's figures give the critical-path time
        run = telemetry.run_figures(validation_run())
        slowest_haiku = max(recorded(f"validation/{n}.jsonl").result["duration_ms"] for n in VALIDATION["forks"]["haiku"]) / 1000
        self.assertEqual(run.critical_path_s, round(recorded(VALIDATION["roots"]["haiku"]).result["duration_ms"] / 1000 + slowest_haiku, 3))
        self.assertEqual(run.critical_path_s, 182.173)
        self.assertLess(run.critical_path_s, sum(f.wall_s for f in validation_run()))
        chain = [telemetry.session_figures(probe("p4")), telemetry.session_figures(probe("p6"), probe("p4")),
                 telemetry.session_figures(probe("p7"), probe("p6"))]
        self.assertEqual(telemetry.run_figures(chain).critical_path_s, round(sum(f.wall_s for f in chain), 3))

    def test_the_prediction_is_set_against_the_actual_time_and_cost(self):
        # SOL-HW-REVIEW-KIT.C4: the run's figures give the predicted against the actual time and cost
        figures = validation_run()
        actual = telemetry.run_figures(figures)
        run = telemetry.run_figures(figures, telemetry.Prediction(cost_usd=2.0, wall_s=100.0))
        self.assertEqual(run.actual, {"cost_usd": actual.cost_usd, "wall_s": 182.173})
        self.assertEqual(run.predicted, {"cost_usd": 2.0, "wall_s": 100.0, "cost_deviation": round((actual.cost_usd - 2.0) / 2.0, 4),
                                         "wall_deviation": 0.8217})
        self.assertIsNone(actual.predicted)
        self.assertEqual(telemetry.run_figures(figures, telemetry.Prediction(0.0, 0.0)).predicted["cost_deviation"], None)

    def test_two_sessions_with_one_identifier_are_an_error(self):
        # SOL-HW-REVIEW-KIT.C4: a run's figures are told per session
        one = telemetry.session_figures(probe("p1"))
        with self.assertRaises(telemetry.FigureError) as caught:
            telemetry.run_figures([one, one])
        self.assertIn("one identifier", str(caught.exception))

    def test_the_run_figures_print_as_json(self):
        # SOL-HW-REVIEW-KIT.C4: the run's figures are available to the report as data
        text = json.dumps(telemetry.run_figures(validation_run(), telemetry.Prediction(2.5, 150.0)).as_dict())
        again = json.loads(text)
        self.assertEqual(again["sessions"], 14)
        self.assertEqual(again["predicted"]["wall_s"], 150.0)
        self.assertEqual(again["duplicate_write_tokens"], 0)


if __name__ == "__main__":
    unittest.main()
