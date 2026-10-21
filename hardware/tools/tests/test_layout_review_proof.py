#!/usr/bin/env python3
"""The layout review proof command and the tap between the fan-out command and the agent command line, against the stub.

The stub plays the agent command line, so no model and no KiCad is used. The seeded copy, its views and its seed list are
synthetic stand-ins for what the seeding command writes, placed where the proof command expects them.
"""

from __future__ import annotations

import io
import json
import os
import shutil
import stat
import sys
import tempfile
import unittest
from unittest import mock

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import layout_fixtures as fx  # noqa: E402
import layout_review_proof as proof  # noqa: E402
import review_agent_tap  # noqa: E402
import review_caller_layout  # noqa: E402
import review_fan_out  # noqa: E402
import review_seed  # noqa: E402

STUB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "review_fan_out_stub.py")
SINGLE_ANSWER = """## Round 1

- **Board judged**: the design files in this folder.

### Verdicts

| Item | Kind | Severity | Verdict | Rests on | Why |
|---|---|---|---|---|---|
| FLOOR-1 | judgement | function | fail | classes | Finding 1.1. |
| CLOCK-1 | judgement | function | pass | crop-U4 | Fine. |

### Plan and free pass

Compared the plan.

### Findings

| Finding | Raised by | Severity | What and where | Rule | Added as | Planning shortfall | Closed by |
|---|---|---|---|---|---|---|---|
| 1.1 | FLOOR-1 | function | classes at (1, 1): wrong | no | | — | |
| 1.2 | free pass | quality | layer-F.Cu at (2, 2): a stray mark | no | | — | |
"""
SEEDS = [{"id": "S1", "item": "FLOOR-1"}, {"id": "S2", "item": "CLOCK-1"}, {"id": "S3", "item": "GROUND-1"}]


class Stubbed(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="layout-proof-test-")
        self.addCleanup(shutil.rmtree, self.root, True)
        self.work = os.path.join(self.root, "work")
        os.makedirs(self.work)
        self.log = os.path.join(self.root, "stub-log")
        os.makedirs(self.log)
        self.scenario_path = os.path.join(self.root, "scenario.json")
        self.program = os.path.join(self.root, "agent")
        fx.write(self.program, f'#!/bin/sh\nexec "{sys.executable}" "{STUB}" "$@"\n')
        os.chmod(self.program, os.stat(self.program).st_mode | stat.S_IXUSR)
        patcher = mock.patch.dict(os.environ, {review_fan_out.AGENT_ENV: self.program, "STUB_SCENARIO": self.scenario_path,
                                               "STUB_LOG": self.log})
        patcher.start()
        self.addCleanup(patcher.stop)

    def scenario(self, content):
        fx.write(self.scenario_path, json.dumps(content))

    def review_folder(self, **how):
        return fx.write_review_folder(self.root, **how)

    def full_scenario(self, folder, **changes):
        """Every unit returns a passing verdict for each item, the plan unit a note; a lone reviewer returns the Markdown round."""
        tables = {unit: ({"Verdicts": [{"Item": item, "Kind": "judgement", "Severity": "function", "Verdict": "pass",
                                        "Rests on": "layer-F.Cu", "Why": "ok"} for item in items]} if items else
                         {"Verdicts": [], "Plan and free pass": [{"Note": "Compared."}], "Findings": []})
                  for unit, items in review_caller_layout.unit_items(folder).items()}
        scenario = {"setup": {"reads": ["docs/board-design-method.md"], "cost": 0.05},
                    "single": {"answer": SINGLE_ANSWER, "cost": 0.5, "turns": 3}, "tables": tables}
        scenario.update(changes)
        self.scenario(scenario)
        return scenario


class TheTap(Stubbed):
    def call(self, phase, prompt, *, fork=False, resume=None, tools=("Read",), cwd=None):
        with proof.tapped(self.work, phase) as log:
            program = review_fan_out.require_agent()
            session = review_fan_out.call_agent(program, prompt, tools, cwd or self.root, resume=resume, fork=fork)
        return session, proof.tap_calls(log)

    def test_the_tap_passes_the_call_on_unchanged_and_logs_it(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C8: Run the single-reviewer form and the fanned-out form on one seeded copy of the layout review proof design from the review folder the folder command assembles with the design from the seeded copy's repository and commit kept by the seeding command's opt-in flag, both forms with the same four tools, in sessions with no record of the seeds, the fanned-out form at the full unit count with the reviewers running together. The fanned-out form reports every seeded defect as a finding against the catalogue item that covers it, and every seed the single reviewer reports; the findings that match no seed and the verdicts item by item are compared and a difference explained. Record for the setup and each unit and for each run the wall time, the tokens read, written and generated, the cost, the document retrievals and any that failed, and any call refused for a rate limit, and set the layout caller's bound on reviewers at once from that. The fanned-out run takes no more time and costs no more than the single-reviewer run. A seed not reported is closed where the gap lies, a catalogue amendment, a correction to the review step or to what it gives a reviewer, and the run repeated in a new session. The evidence names the exact model and the commit. Out of scope: the schematic, critical-routing and production-files proofs.
        self.scenario({"setup": {"answer": "an answer", "cost": 0.25}})
        session, calls = self.call("one", "no unit here")
        self.assertTrue(session.succeeded)
        self.assertEqual(session.text, "an answer")
        self.assertAlmostEqual(review_fan_out.figures(session)["cost_usd"], 0.25)
        self.assertEqual(len(calls), 1)
        self.assertEqual((calls[0]["resume"], calls[0]["fork"], calls[0]["exit"], calls[0]["rate_limited"], calls[0]["retrievals"]),
                         (False, False, 0, False, []))
        self.assertEqual(calls[0]["session"], session.id)
        self.assertLessEqual(calls[0]["began"], calls[0]["ended"])
        self.assertEqual(os.environ[review_fan_out.AGENT_ENV], self.program, "the environment is put back")
        self.assertNotIn(review_agent_tap.LOG_ENV, os.environ)

    def stub_calls(self):
        found = []
        for name in sorted(os.listdir(self.log)):
            if name.endswith(".json"):
                with open(os.path.join(self.log, name), encoding="utf-8") as handle:
                    found.append(json.load(handle))
        return found

    def test_a_prompt_sent_on_standard_input_reaches_the_program_through_the_tap(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C8: Run the single-reviewer form and the fanned-out form on one seeded copy of the layout review proof design from the review folder the folder command assembles with the design from the seeded copy's repository and commit kept by the seeding command's opt-in flag, both forms with the same four tools, in sessions with no record of the seeds, the fanned-out form at the full unit count with the reviewers running together. The fanned-out form reports every seeded defect as a finding against the catalogue item that covers it, and every seed the single reviewer reports; the findings that match no seed and the verdicts item by item are compared and a difference explained. Record for the setup and each unit and for each run the wall time, the tokens read, written and generated, the cost, the document retrievals and any that failed, and any call refused for a rate limit, and set the layout caller's bound on reviewers at once from that. The fanned-out run takes no more time and costs no more than the single-reviewer run. A seed not reported is closed where the gap lies, a catalogue amendment, a correction to the review step or to what it gives a reviewer, and the run repeated in a new session. The evidence names the exact model and the commit. Out of scope: the schematic, critical-routing and production-files proofs.
        self.scenario({"setup": {"answer": "an answer"}})
        text = "the documents of the review\n=== method.md ===\nthe method \u00e9\n"
        with proof.tapped(self.work, "stdin") as log:
            program = review_fan_out.require_agent()
            session = review_fan_out.call_agent(program, "", ("Read",), self.root, stdin_text=text)
        self.assertTrue(session.succeeded)
        sent = self.stub_calls()
        self.assertEqual([call["stdin"] for call in sent], [text], "the program saw the text on its standard input")
        self.assertTrue(sent[0]["args"][1].startswith("--"), "and no prompt argument")
        self.assertEqual(len(proof.tap_calls(log)), 1, "and the call is still logged")

    def test_a_call_with_no_standard_input_reaches_the_program_with_none(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C8: Run the single-reviewer form and the fanned-out form on one seeded copy of the layout review proof design from the review folder the folder command assembles with the design from the seeded copy's repository and commit kept by the seeding command's opt-in flag, both forms with the same four tools, in sessions with no record of the seeds, the fanned-out form at the full unit count with the reviewers running together. The fanned-out form reports every seeded defect as a finding against the catalogue item that covers it, and every seed the single reviewer reports; the findings that match no seed and the verdicts item by item are compared and a difference explained. Record for the setup and each unit and for each run the wall time, the tokens read, written and generated, the cost, the document retrievals and any that failed, and any call refused for a rate limit, and set the layout caller's bound on reviewers at once from that. The fanned-out run takes no more time and costs no more than the single-reviewer run. A seed not reported is closed where the gap lies, a catalogue amendment, a correction to the review step or to what it gives a reviewer, and the run repeated in a new session. The evidence names the exact model and the commit. Out of scope: the schematic, critical-routing and production-files proofs.
        self.scenario({"setup": {"answer": "an answer"}})
        with proof.tapped(self.work, "argument"):
            program = review_fan_out.require_agent()
            review_fan_out.call_agent(program, "no unit here", ("Read",), self.root)
        sent = self.stub_calls()
        self.assertEqual([(call["stdin"], call["args"][1]) for call in sent], [(None, "no unit here")])

    def test_a_retrieval_and_whether_it_failed_are_logged_with_the_session_that_made_it(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C8: Run the single-reviewer form and the fanned-out form on one seeded copy of the layout review proof design from the review folder the folder command assembles with the design from the seeded copy's repository and commit kept by the seeding command's opt-in flag, both forms with the same four tools, in sessions with no record of the seeds, the fanned-out form at the full unit count with the reviewers running together. The fanned-out form reports every seeded defect as a finding against the catalogue item that covers it, and every seed the single reviewer reports; the findings that match no seed and the verdicts item by item are compared and a difference explained. Record for the setup and each unit and for each run the wall time, the tokens read, written and generated, the cost, the document retrievals and any that failed, and any call refused for a rate limit, and set the layout caller's bound on reviewers at once from that. The fanned-out run takes no more time and costs no more than the single-reviewer run. A seed not reported is closed where the gap lies, a catalogue amendment, a correction to the review step or to what it gives a reviewer, and the run repeated in a new session. The evidence names the exact model and the commit. Out of scope: the schematic, critical-routing and production-files proofs.
        uses = [{"name": "WebFetch", "input": {"url": "https://example.invalid/a"}, "failed": False},
                {"name": "WebFetch", "input": {"url": "https://example.invalid/b"}, "failed": True}, "Grep"]
        self.scenario({"setup": {"uses": uses}})
        session, calls = self.call("two", "no unit here")
        self.assertEqual(calls[0]["retrievals"], [{"url": "https://example.invalid/a", "failed": False},
                                                   {"url": "https://example.invalid/b", "failed": True}])
        self.assertEqual(proof.retrievals(calls), {"retrieved": 2, "failed": 1})
        self.assertEqual(proof.retrievals(calls, [session.id]), {"retrieved": 2, "failed": 1})
        self.assertEqual(proof.retrievals(calls, ["another session"]), {"retrieved": 0, "failed": 0})

    def test_a_call_refused_for_a_rate_limit_is_logged_though_the_command_retries_it(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C8: Run the single-reviewer form and the fanned-out form on one seeded copy of the layout review proof design from the review folder the folder command assembles with the design from the seeded copy's repository and commit kept by the seeding command's opt-in flag, both forms with the same four tools, in sessions with no record of the seeds, the fanned-out form at the full unit count with the reviewers running together. The fanned-out form reports every seeded defect as a finding against the catalogue item that covers it, and every seed the single reviewer reports; the findings that match no seed and the verdicts item by item are compared and a difference explained. Record for the setup and each unit and for each run the wall time, the tokens read, written and generated, the cost, the document retrievals and any that failed, and any call refused for a rate limit, and set the layout caller's bound on reviewers at once from that. The fanned-out run takes no more time and costs no more than the single-reviewer run. A seed not reported is closed where the gap lies, a catalogue amendment, a correction to the review step or to what it gives a reviewer, and the run repeated in a new session. The evidence names the exact model and the commit. Out of scope: the schematic, critical-routing and production-files proofs.
        folder = self.review_folder()
        scenario = self.full_scenario(folder)
        scenario["units"] = {"area-CLOCK": [{"rate_limit": True}, {}]}
        self.scenario(scenario)
        fanned = proof.run_fanned(folder, self.work, None, 4, 0.0)
        self.assertEqual(fanned["status"], 0, fanned["report"].get("refusals"))
        self.assertEqual(fanned["rate_limited_calls"], 1, "the driver retried the refused call, and the tap kept the refusal")
        self.assertEqual(fanned["report"]["result"], "WRITTEN")

    def test_the_peak_is_the_most_calls_running_at_once(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C8: Run the single-reviewer form and the fanned-out form on one seeded copy of the layout review proof design from the review folder the folder command assembles with the design from the seeded copy's repository and commit kept by the seeding command's opt-in flag, both forms with the same four tools, in sessions with no record of the seeds, the fanned-out form at the full unit count with the reviewers running together. The fanned-out form reports every seeded defect as a finding against the catalogue item that covers it, and every seed the single reviewer reports; the findings that match no seed and the verdicts item by item are compared and a difference explained. Record for the setup and each unit and for each run the wall time, the tokens read, written and generated, the cost, the document retrievals and any that failed, and any call refused for a rate limit, and set the layout caller's bound on reviewers at once from that. The fanned-out run takes no more time and costs no more than the single-reviewer run. A seed not reported is closed where the gap lies, a catalogue amendment, a correction to the review step or to what it gives a reviewer, and the run repeated in a new session. The evidence names the exact model and the commit. Out of scope: the schematic, critical-routing and production-files proofs.
        def at(began, ended):
            return {"began": began, "ended": ended}
        self.assertEqual(proof.peak([]), 0)
        self.assertEqual(proof.peak([at(0, 1), at(1, 2), at(2, 3)]), 1, "a call that ends as another begins does not overlap it")
        self.assertEqual(proof.peak([at(0, 5), at(1, 3), at(2, 4), at(6, 7)]), 3)
        self.assertEqual(proof.peak([at(0, 1), at(0, 1), at(0, 1), at(0, 1)]), 4)

    def test_the_tap_passes_the_login_check_through_and_without_a_log_runs_the_program_alone(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C8: Run the single-reviewer form and the fanned-out form on one seeded copy of the layout review proof design from the review folder the folder command assembles with the design from the seeded copy's repository and commit kept by the seeding command's opt-in flag, both forms with the same four tools, in sessions with no record of the seeds, the fanned-out form at the full unit count with the reviewers running together. The fanned-out form reports every seeded defect as a finding against the catalogue item that covers it, and every seed the single reviewer reports; the findings that match no seed and the verdicts item by item are compared and a difference explained. Record for the setup and each unit and for each run the wall time, the tokens read, written and generated, the cost, the document retrievals and any that failed, and any call refused for a rate limit, and set the layout caller's bound on reviewers at once from that. The fanned-out run takes no more time and costs no more than the single-reviewer run. A seed not reported is closed where the gap lies, a catalogue amendment, a correction to the review step or to what it gives a reviewer, and the run repeated in a new session. The evidence names the exact model and the commit. Out of scope: the schematic, critical-routing and production-files proofs.
        self.scenario({"auth": 1})
        with proof.tapped(self.work, "login"):
            with self.assertRaises(review_fan_out.board_check.CannotRun):
                review_fan_out.require_agent()
        self.assertEqual(proof.tap_calls(os.path.join(self.work, "tap", "login")), [])
        self.assertEqual(proof.tap_calls(os.path.join(self.work, "no-such-phase")), [])
        self.scenario({"setup": {"answer": "x"}})
        with mock.patch.dict(os.environ, {review_agent_tap.AGENT_ENV: self.program}):
            os.environ.pop(review_agent_tap.LOG_ENV, None)
            self.assertEqual(review_agent_tap.main(["auth", "status"]), 0)


class TheForms(Stubbed):
    def test_the_single_reviewer_runs_with_the_same_four_tools_and_its_figures_and_answer_are_kept(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C8: Run the single-reviewer form and the fanned-out form on one seeded copy of the layout review proof design from the review folder the folder command assembles with the design from the seeded copy's repository and commit kept by the seeding command's opt-in flag, both forms with the same four tools, in sessions with no record of the seeds, the fanned-out form at the full unit count with the reviewers running together. The fanned-out form reports every seeded defect as a finding against the catalogue item that covers it, and every seed the single reviewer reports; the findings that match no seed and the verdicts item by item are compared and a difference explained. Record for the setup and each unit and for each run the wall time, the tokens read, written and generated, the cost, the document retrievals and any that failed, and any call refused for a rate limit, and set the layout caller's bound on reviewers at once from that. The fanned-out run takes no more time and costs no more than the single-reviewer run. A seed not reported is closed where the gap lies, a catalogue amendment, a correction to the review step or to what it gives a reviewer, and the run repeated in a new session. The evidence names the exact model and the commit. Out of scope: the schematic, critical-routing and production-files proofs.
        folder = self.review_folder()
        self.full_scenario(folder)
        single = proof.run_single(folder, self.work, "model-a", 0.0)
        self.assertEqual(single["problems"], [])
        self.assertEqual((single["model"], single["reported"], single["calls"]), ("model-a", True, 1))
        self.assertAlmostEqual(single["cost_usd"], 0.5)
        self.assertEqual(single["tokens"], {"cache_read": 5000, "cache_write": 200, "fresh": 3, "generated": 100})
        self.assertEqual((single["retrieved"], single["failed"], single["rate_limited_calls"]), (0, 0, 0))
        with open(os.path.join(self.work, "single", "answer.md"), encoding="utf-8") as handle:
            self.assertEqual(handle.read(), SINGLE_ANSWER)
        logged = [json.load(open(os.path.join(self.log, name), encoding="utf-8")) for name in os.listdir(self.log)
                  if name.endswith(".json")]
        grant = logged[0]["args"][logged[0]["args"].index("--tools") + 1]
        self.assertEqual(grant, ",".join(review_caller_layout.TOOLS))
        self.assertEqual(os.path.realpath(logged[0]["cwd"]), os.path.realpath(folder))
        self.assertIn("--model", logged[0]["args"])
        self.assertNotIn("UNIT=", logged[0]["prompt"])

    def test_a_single_reviewer_that_starts_with_other_tools_is_a_problem_the_report_names(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C8: Run the single-reviewer form and the fanned-out form on one seeded copy of the layout review proof design from the review folder the folder command assembles with the design from the seeded copy's repository and commit kept by the seeding command's opt-in flag, both forms with the same four tools, in sessions with no record of the seeds, the fanned-out form at the full unit count with the reviewers running together. The fanned-out form reports every seeded defect as a finding against the catalogue item that covers it, and every seed the single reviewer reports; the findings that match no seed and the verdicts item by item are compared and a difference explained. Record for the setup and each unit and for each run the wall time, the tokens read, written and generated, the cost, the document retrievals and any that failed, and any call refused for a rate limit, and set the layout caller's bound on reviewers at once from that. The fanned-out run takes no more time and costs no more than the single-reviewer run. A seed not reported is closed where the gap lies, a catalogue amendment, a correction to the review step or to what it gives a reviewer, and the run repeated in a new session. The evidence names the exact model and the commit. Out of scope: the schematic, critical-routing and production-files proofs.
        folder = self.review_folder()
        self.full_scenario(folder, setup_tools=["Read", "Bash"])
        single = proof.run_single(folder, self.work, None, 0.0)
        self.assertEqual(len(single["problems"]), 1)
        self.assertIn("the single reviewer started with tools ['Bash', 'Read']", single["problems"][0])

    def test_the_fanned_out_form_records_each_units_retrievals_and_the_most_reviewers_that_ran_together(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C8: Run the single-reviewer form and the fanned-out form on one seeded copy of the layout review proof design from the review folder the folder command assembles with the design from the seeded copy's repository and commit kept by the seeding command's opt-in flag, both forms with the same four tools, in sessions with no record of the seeds, the fanned-out form at the full unit count with the reviewers running together. The fanned-out form reports every seeded defect as a finding against the catalogue item that covers it, and every seed the single reviewer reports; the findings that match no seed and the verdicts item by item are compared and a difference explained. Record for the setup and each unit and for each run the wall time, the tokens read, written and generated, the cost, the document retrievals and any that failed, and any call refused for a rate limit, and set the layout caller's bound on reviewers at once from that. The fanned-out run takes no more time and costs no more than the single-reviewer run. A seed not reported is closed where the gap lies, a catalogue amendment, a correction to the review step or to what it gives a reviewer, and the run repeated in a new session. The evidence names the exact model and the commit. Out of scope: the schematic, critical-routing and production-files proofs.
        folder = self.review_folder()
        scenario = self.full_scenario(folder, sleep=0.6)
        scenario["units"] = {"area-FLOOR": [{"uses": [{"name": "WebFetch", "input": {"url": "u1"}, "failed": False},
                                                       {"name": "WebFetch", "input": {"url": "u2"}, "failed": True}]}],
                             "area-CLOCK": [{"uses": [{"name": "WebFetch", "input": {"url": "u3"}, "failed": False}]}]}
        self.scenario(scenario)
        fanned = proof.run_fanned(folder, self.work, "model-a", 4, 0.0)
        self.assertEqual(fanned["status"], 0, fanned["report"].get("refusals"))
        by_unit = {unit["unit"]: unit for unit in fanned["report"]["units"]}
        self.assertEqual((by_unit["area-FLOOR"]["retrieved"], by_unit["area-FLOOR"]["failed"]), (2, 1))
        self.assertEqual((by_unit["area-CLOCK"]["retrieved"], by_unit["area-CLOCK"]["failed"]), (1, 0))
        self.assertEqual((by_unit["area-GROUND"]["retrieved"], by_unit["plan-and-free-pass"]["retrieved"]), (0, 0))
        self.assertEqual((fanned["retrieved"], fanned["failed"]), (3, 1))
        self.assertEqual(fanned["report"]["setup_sessions"][0]["retrieved"], 0)
        self.assertEqual(fanned["peak_reviewers_together"], 4, "all four units ran together at the full unit count")
        self.assertEqual(fanned["bound"], 4)
        self.assertEqual(fanned["calls"], 5, "one setup session and four forks")
        self.assertGreater(fanned["wall_s"], 0.5)
        sessions = proof.unit_sessions(os.path.join(self.work, "fanned"))
        self.assertEqual(sorted(sessions), sorted(by_unit))
        self.assertTrue(all(len(ids) == 1 for ids in sessions.values()))

    def test_a_bound_below_the_unit_count_limits_the_reviewers_that_run_together(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C8: Run the single-reviewer form and the fanned-out form on one seeded copy of the layout review proof design from the review folder the folder command assembles with the design from the seeded copy's repository and commit kept by the seeding command's opt-in flag, both forms with the same four tools, in sessions with no record of the seeds, the fanned-out form at the full unit count with the reviewers running together. The fanned-out form reports every seeded defect as a finding against the catalogue item that covers it, and every seed the single reviewer reports; the findings that match no seed and the verdicts item by item are compared and a difference explained. Record for the setup and each unit and for each run the wall time, the tokens read, written and generated, the cost, the document retrievals and any that failed, and any call refused for a rate limit, and set the layout caller's bound on reviewers at once from that. The fanned-out run takes no more time and costs no more than the single-reviewer run. A seed not reported is closed where the gap lies, a catalogue amendment, a correction to the review step or to what it gives a reviewer, and the run repeated in a new session. The evidence names the exact model and the commit. Out of scope: the schematic, critical-routing and production-files proofs.
        folder = self.review_folder()
        self.full_scenario(folder, sleep=0.4)
        fanned = proof.run_fanned(folder, self.work, None, 2, 0.0)
        self.assertEqual(fanned["peak_reviewers_together"], 2)

    def test_a_fanned_out_run_that_fails_reports_its_refusals_and_compares_nothing_it_did_not_run(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C8: Run the single-reviewer form and the fanned-out form on one seeded copy of the layout review proof design from the review folder the folder command assembles with the design from the seeded copy's repository and commit kept by the seeding command's opt-in flag, both forms with the same four tools, in sessions with no record of the seeds, the fanned-out form at the full unit count with the reviewers running together. The fanned-out form reports every seeded defect as a finding against the catalogue item that covers it, and every seed the single reviewer reports; the findings that match no seed and the verdicts item by item are compared and a difference explained. Record for the setup and each unit and for each run the wall time, the tokens read, written and generated, the cost, the document retrievals and any that failed, and any call refused for a rate limit, and set the layout caller's bound on reviewers at once from that. The fanned-out run takes no more time and costs no more than the single-reviewer run. A seed not reported is closed where the gap lies, a catalogue amendment, a correction to the review step or to what it gives a reviewer, and the run repeated in a new session. The evidence names the exact model and the commit. Out of scope: the schematic, critical-routing and production-files proofs.
        folder = self.review_folder()
        scenario = self.full_scenario(folder)
        scenario["tables"]["area-FLOOR"]["Verdicts"] = scenario["tables"]["area-FLOOR"]["Verdicts"][:1]
        self.scenario(scenario)
        result = proof.prove(folder, self.work, SEEDS, None, None, 0.0)
        self.assertEqual(result["fanned"]["status"], 1)
        self.assertIn("item FLOOR-2 has no verdict row", "; ".join(result["fanned"]["report"]["refusals"]))
        self.assertEqual(result["comparison"]["fanned_misses_a_seed_single_finds"], ["S1"])
        self.assertEqual(result["comparison"]["neither_finds"], ["S2", "S3"])


class TheComparison(unittest.TestCase):
    def test_a_round_written_as_markdown_gives_its_verdicts_and_its_findings_raised_by(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C8: Run the single-reviewer form and the fanned-out form on one seeded copy of the layout review proof design from the review folder the folder command assembles with the design from the seeded copy's repository and commit kept by the seeding command's opt-in flag, both forms with the same four tools, in sessions with no record of the seeds, the fanned-out form at the full unit count with the reviewers running together. The fanned-out form reports every seeded defect as a finding against the catalogue item that covers it, and every seed the single reviewer reports; the findings that match no seed and the verdicts item by item are compared and a difference explained. Record for the setup and each unit and for each run the wall time, the tokens read, written and generated, the cost, the document retrievals and any that failed, and any call refused for a rate limit, and set the layout caller's bound on reviewers at once from that. The fanned-out run takes no more time and costs no more than the single-reviewer run. A seed not reported is closed where the gap lies, a catalogue amendment, a correction to the review step or to what it gives a reviewer, and the run repeated in a new session. The evidence names the exact model and the commit. Out of scope: the schematic, critical-routing and production-files proofs.
        parsed = proof.parsed_round(SINGLE_ANSWER)
        self.assertEqual(parsed["verdicts"], {"FLOOR-1": "fail", "CLOCK-1": "pass"})
        self.assertEqual(parsed["raised_by"], ["FLOOR-1", "free pass"])
        headless = proof.parsed_round(SINGLE_ANSWER.split("\n", 2)[2])
        self.assertEqual(headless, parsed, "a round the reviewer wrote without its heading is read as round 1")
        self.assertEqual(proof.parsed_round("nothing a round holds"), {"verdicts": {}, "raised_by": []})

    def test_each_seed_is_matched_to_the_findings_that_name_its_item_and_what_matches_no_seed_is_listed(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C8: Run the single-reviewer form and the fanned-out form on one seeded copy of the layout review proof design from the review folder the folder command assembles with the design from the seeded copy's repository and commit kept by the seeding command's opt-in flag, both forms with the same four tools, in sessions with no record of the seeds, the fanned-out form at the full unit count with the reviewers running together. The fanned-out form reports every seeded defect as a finding against the catalogue item that covers it, and every seed the single reviewer reports; the findings that match no seed and the verdicts item by item are compared and a difference explained. Record for the setup and each unit and for each run the wall time, the tokens read, written and generated, the cost, the document retrievals and any that failed, and any call refused for a rate limit, and set the layout caller's bound on reviewers at once from that. The fanned-out run takes no more time and costs no more than the single-reviewer run. A seed not reported is closed where the gap lies, a catalogue amendment, a correction to the review step or to what it gives a reviewer, and the run repeated in a new session. The evidence names the exact model and the commit. Out of scope: the schematic, critical-routing and production-files proofs.
        single = {"verdicts": {"FLOOR-1": "fail", "CLOCK-1": "pass", "GROUND-1": "pass"},
                  "raised_by": ["FLOOR-1", "free pass", "plan, row GROUND-1"]}
        fanned = {"verdicts": {"FLOOR-1": "fail", "CLOCK-1": "fail", "GROUND-1": "pass"},
                  "raised_by": ["FLOOR-1", "CLOCK-1", "FLOOR-10", "WORK-1"]}
        result = proof.compare(SEEDS, single, fanned)
        self.assertEqual([(row["id"], row["single"], row["fanned"]) for row in result["seeds"]],
                         [("S1", True, True), ("S2", False, True), ("S3", True, False)])
        self.assertEqual(result["fanned_misses_a_seed_single_finds"], ["S3"])
        self.assertEqual(result["neither_finds"], [])
        self.assertEqual(result["unseeded_findings"], {"single": ["free pass"], "fanned": ["FLOOR-10", "WORK-1"]},
                         "FLOOR-1 is not matched inside FLOOR-10")
        self.assertEqual(result["verdict_differences"], [{"item": "CLOCK-1", "single": "pass", "fanned": "fail"}])
        both_miss = proof.compare(SEEDS, {"verdicts": {}, "raised_by": []}, {"verdicts": {"X": "pass"}, "raised_by": []})
        self.assertEqual(both_miss["neither_finds"], ["S1", "S2", "S3"])
        self.assertEqual(both_miss["verdict_differences"], [{"item": "X", "single": "none", "fanned": "pass"}])


class TheProof(Stubbed):
    DESIGN = review_seed.DESIGN

    def seeded(self, work):
        """What the seeding command leaves, synthetic: the kept work tree with a committed board, the folder it rendered into and
        the seed list; the method and the notes come from this repository, as the seeding command takes them."""
        repo = fx.make_repo(os.path.join(work, "seeded-work"), design=self.DESIGN)
        inputs = fx.make_views(os.path.join(work, "inputs"))
        review = os.path.join(work, proof.SEEDED)
        shutil.copytree(inputs["views"], os.path.join(review, review_seed.VIEWS))
        shutil.copytree(inputs["placement"], os.path.join(review, review_seed.PLACEMENT))
        report = "\n".join([f"DESIGN | {self.DESIGN}/x.kicad_pro | PASS", f"FIGURE | {self.DESIGN}/x.kicad_pro | WORK-2 | 1.3",
                            "RESULT | PASS"]) + "\n"
        fx.write(os.path.join(review, review_seed.REPORT), report)
        fx.write(os.path.join(work, proof.SEEDS), json.dumps({"seeds": SEEDS}))
        return {"repository": repo, "commit": fx.git(repo, "rev-parse", "HEAD")}

    def go(self, *extra, runner=None):
        out, err = io.StringIO(), io.StringIO()
        status = proof.main(["--work", self.work, "--rate-limit-wait", "0", *extra], out=out, err=err,
                            seed_runner=runner or (lambda work, kicad, resvg: self.seeded(work)))
        return status, out.getvalue(), err.getvalue()

    def host_scenario(self):
        """Run the stub for the real method's units: build the folder the proof will, from a throwaway copy of the setup."""
        scratch = os.path.join(self.root, "scratch")
        os.makedirs(scratch)
        seeded = self.seeded(scratch)
        folder = proof.write_folder(scratch, seeded)
        scenario = self.full_scenario(folder, sleep=0.3)
        self.unit_count = len(review_caller_layout.units(folder))
        scenario["single"]["answer"] = SINGLE_ANSWER
        scenario["tables"]["area-GROUND"]["Findings"] = [
            {"Finding": 1, "Item": "GROUND-1", "Raised by": "GROUND-1", "Severity": "function", "What and where": "net-_GND at (1, 1): a gap",
             "Rule": "no", "Added as": "", "Planning shortfall": "—", "Closed by": ""}]
        scenario["tables"]["area-GROUND"]["Verdicts"][0]["Verdict"] = "fail"
        scenario["tables"]["area-GROUND"]["Verdicts"][0]["Why"] = "Finding 1.1."
        self.scenario(scenario)
        return scenario

    def test_the_command_runs_both_forms_on_the_seeded_copy_and_writes_the_comparison_as_text(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C8: Run the single-reviewer form and the fanned-out form on one seeded copy of the layout review proof design from the review folder the folder command assembles with the design from the seeded copy's repository and commit kept by the seeding command's opt-in flag, both forms with the same four tools, in sessions with no record of the seeds, the fanned-out form at the full unit count with the reviewers running together. The fanned-out form reports every seeded defect as a finding against the catalogue item that covers it, and every seed the single reviewer reports; the findings that match no seed and the verdicts item by item are compared and a difference explained. Record for the setup and each unit and for each run the wall time, the tokens read, written and generated, the cost, the document retrievals and any that failed, and any call refused for a rate limit, and set the layout caller's bound on reviewers at once from that. The fanned-out run takes no more time and costs no more than the single-reviewer run. A seed not reported is closed where the gap lies, a catalogue amendment, a correction to the review step or to what it gives a reviewer, and the run repeated in a new session. The evidence names the exact model and the commit. Out of scope: the schematic, critical-routing and production-files proofs.
        self.host_scenario()
        status, text, _ = self.go("--model", "model-a")
        lines = text.splitlines()
        self.assertEqual(status, 0, text)
        self.assertTrue(lines[0].startswith(f"PROOF | {self.work} | tool commit "), lines[0])
        self.assertEqual(sum(line.startswith("UNIT |") for line in lines), self.unit_count, "an area each and the plan unit")
        self.assertGreater(self.unit_count, 2)
        self.assertEqual(sum(line.startswith("SETUP |") for line in lines), 1)
        single = next(line for line in lines if line.startswith("SINGLE |"))
        self.assertIn("model model-a", single)
        self.assertIn("retrievals 0 failed 0 | refused for a rate limit 0", single)
        seeds = [line for line in lines if line.startswith("SEED |")]
        self.assertEqual(seeds, ["SEED | S1 | FLOOR-1 | single reported | fanned not reported",
                                 "SEED | S2 | CLOCK-1 | single not reported | fanned not reported",
                                 "SEED | S3 | GROUND-1 | single not reported | fanned reported"])
        self.assertIn("UNSEEDED | single | 1 findings | free pass", lines)
        compare = next(line for line in lines if line.startswith("COMPARE |"))
        self.assertIn("fanned no more", compare)
        self.assertIn("seeds the single reviewer found and the fanned-out form did not: S1", compare)
        bound = next(line for line in lines if line.startswith("BOUND |"))
        self.assertIn(f"caller's bound now {review_caller_layout.BOUND} | run with {self.unit_count} | most reviewers together {self.unit_count}", bound)
        self.assertTrue(lines[-1].startswith("RESULT | WRITTEN | "), lines[-1])
        with open(os.path.join(self.work, proof.REPORT), encoding="utf-8") as handle:
            written = json.load(handle)
        self.assertEqual(written["seeded_commit"], fx.git(os.path.join(self.work, "seeded-work", "repository"), "rev-parse", "HEAD"))

    def test_the_command_reports_the_same_facts_as_json_and_bounds_the_reviewers_as_asked(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C8: Run the single-reviewer form and the fanned-out form on one seeded copy of the layout review proof design from the review folder the folder command assembles with the design from the seeded copy's repository and commit kept by the seeding command's opt-in flag, both forms with the same four tools, in sessions with no record of the seeds, the fanned-out form at the full unit count with the reviewers running together. The fanned-out form reports every seeded defect as a finding against the catalogue item that covers it, and every seed the single reviewer reports; the findings that match no seed and the verdicts item by item are compared and a difference explained. Record for the setup and each unit and for each run the wall time, the tokens read, written and generated, the cost, the document retrievals and any that failed, and any call refused for a rate limit, and set the layout caller's bound on reviewers at once from that. The fanned-out run takes no more time and costs no more than the single-reviewer run. A seed not reported is closed where the gap lies, a catalogue amendment, a correction to the review step or to what it gives a reviewer, and the run repeated in a new session. The evidence names the exact model and the commit. Out of scope: the schematic, critical-routing and production-files proofs.
        self.host_scenario()
        status, text, _ = self.go("--json", "--bound", "3")
        report = json.loads(text)
        self.assertEqual(status, 0, text)
        self.assertEqual(report["result"], "WRITTEN")
        self.assertEqual(report["for_the_bound"]["bound_run_with"], 3)
        self.assertLessEqual(report["for_the_bound"]["most_reviewers_together"], 3)
        self.assertEqual(len(report["units"]), self.unit_count)
        self.assertEqual({row["id"]: (row["single"], row["fanned"]) for row in report["comparison"]["seeds"]},
                         {"S1": (True, False), "S2": (False, False), "S3": (False, True)})
        self.assertEqual(report["comparison"]["cost"]["single_usd"], 0.5)
        self.assertIs(report["comparison"]["cost"]["fanned_no_more"], False,
                      "thirteen reviewers and a setup session cost more than the one the stub plays")
        self.assertEqual(report["fanned"]["report"]["units"][0]["retrieved"], 0)
        self.assertEqual(set(report["single"]), {"session", "model", "problems", "reported", "wall_s", "cost_usd", "tokens", "turns", "api_ms",
                                                  "retrieved", "failed", "rate_limited_calls", "calls"})

    def test_a_form_that_does_not_run_clean_fails_the_command_and_the_report_is_still_written(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C8: Run the single-reviewer form and the fanned-out form on one seeded copy of the layout review proof design from the review folder the folder command assembles with the design from the seeded copy's repository and commit kept by the seeding command's opt-in flag, both forms with the same four tools, in sessions with no record of the seeds, the fanned-out form at the full unit count with the reviewers running together. The fanned-out form reports every seeded defect as a finding against the catalogue item that covers it, and every seed the single reviewer reports; the findings that match no seed and the verdicts item by item are compared and a difference explained. Record for the setup and each unit and for each run the wall time, the tokens read, written and generated, the cost, the document retrievals and any that failed, and any call refused for a rate limit, and set the layout caller's bound on reviewers at once from that. The fanned-out run takes no more time and costs no more than the single-reviewer run. A seed not reported is closed where the gap lies, a catalogue amendment, a correction to the review step or to what it gives a reviewer, and the run repeated in a new session. The evidence names the exact model and the commit. Out of scope: the schematic, critical-routing and production-files proofs.
        scenario = self.host_scenario()
        scenario["units"] = {"area-GROUND": [{"start_set": {"mcp_servers": [{"name": "x"}]}}]}
        self.scenario(scenario)
        status, text, _ = self.go()
        self.assertEqual(status, 1)
        self.assertIn("FANNED | status 1", text)
        self.assertIn("started with MCP servers", text)
        self.assertTrue(text.splitlines()[-1].startswith("RESULT | FAILED | a form did not run clean"))
        self.assertTrue(os.path.isfile(os.path.join(self.work, proof.REPORT)))

    def test_a_single_answer_with_no_verdicts_table_fails_the_command_instead_of_reporting_no_seed(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C8: Run the single-reviewer form and the fanned-out form on one seeded copy of the layout review proof design from the review folder the folder command assembles with the design from the seeded copy's repository and commit kept by the seeding command's opt-in flag, both forms with the same four tools, in sessions with no record of the seeds, the fanned-out form at the full unit count with the reviewers running together. The fanned-out form reports every seeded defect as a finding against the catalogue item that covers it, and every seed the single reviewer reports; the findings that match no seed and the verdicts item by item are compared and a difference explained. Record for the setup and each unit and for each run the wall time, the tokens read, written and generated, the cost, the document retrievals and any that failed, and any call refused for a rate limit, and set the layout caller's bound on reviewers at once from that. The fanned-out run takes no more time and costs no more than the single-reviewer run. A seed not reported is closed where the gap lies, a catalogue amendment, a correction to the review step or to what it gives a reviewer, and the run repeated in a new session. The evidence names the exact model and the commit. Out of scope: the schematic, critical-routing and production-files proofs.
        scenario = self.host_scenario()
        scenario["single"]["answer"] = "I reviewed the board and found nothing worth a table."
        self.scenario(scenario)
        status, text, _ = self.go()
        self.assertEqual(status, 1)
        self.assertIn("SINGLE PROBLEM | the single reviewer's answer holds no Verdicts table", text)
        self.assertTrue(text.splitlines()[-1].startswith("RESULT | FAILED | a form did not run clean"))
        self.assertTrue(os.path.isfile(os.path.join(self.work, proof.REPORT)))

    def test_the_command_refuses_a_work_folder_that_is_not_new_a_bound_below_one_and_a_seed_it_could_not_write(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C8: Run the single-reviewer form and the fanned-out form on one seeded copy of the layout review proof design from the review folder the folder command assembles with the design from the seeded copy's repository and commit kept by the seeding command's opt-in flag, both forms with the same four tools, in sessions with no record of the seeds, the fanned-out form at the full unit count with the reviewers running together. The fanned-out form reports every seeded defect as a finding against the catalogue item that covers it, and every seed the single reviewer reports; the findings that match no seed and the verdicts item by item are compared and a difference explained. Record for the setup and each unit and for each run the wall time, the tokens read, written and generated, the cost, the document retrievals and any that failed, and any call refused for a rate limit, and set the layout caller's bound on reviewers at once from that. The fanned-out run takes no more time and costs no more than the single-reviewer run. A seed not reported is closed where the gap lies, a catalogue amendment, a correction to the review step or to what it gives a reviewer, and the run repeated in a new session. The evidence names the exact model and the commit. Out of scope: the schematic, critical-routing and production-files proofs.
        fx.write(os.path.join(self.work, "held.txt"), "held")
        status, text, _ = self.go()
        self.assertEqual(status, 1)
        self.assertIn("REFUSED | the work folder", text)
        self.assertIn("already holds files", text)
        os.remove(os.path.join(self.work, "held.txt"))
        status, text, _ = self.go("--bound", "0")
        self.assertEqual((status, "the bound 0 is below one" in text), (1, True))
        status, text, _ = self.go("--json", "--bound", "0")
        self.assertEqual(json.loads(text)["result"], "REFUSED")

        def refusing(work, kicad, resvg):
            raise proof.Refused(["the seeding command did not write the seeded copy: nothing"])

        def missing(work, kicad, resvg):
            raise review_fan_out.board_check.CannotRun("KiCad is not on the search path")
        status, text, _ = self.go(runner=refusing)
        self.assertEqual(status, 1)
        self.assertIn("REFUSED | the seeding command did not write the seeded copy", text)
        status, text, err = self.go(runner=missing)
        self.assertEqual(status, 2)
        self.assertIn("RESULT | CANNOT RUN | KiCad is not on the search path", err)
        inside = io.StringIO()
        status = proof.main(["--work", os.path.join(proof.REPO, "never-written")], out=inside, err=inside)
        self.assertEqual(status, 1)
        self.assertIn("is inside the repository", inside.getvalue())
        self.assertFalse(os.path.exists(os.path.join(proof.REPO, "never-written")))

    def test_the_seeding_command_is_run_with_its_flag_that_keeps_the_work_tree(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C8: Run the single-reviewer form and the fanned-out form on one seeded copy of the layout review proof design from the review folder the folder command assembles with the design from the seeded copy's repository and commit kept by the seeding command's opt-in flag, both forms with the same four tools, in sessions with no record of the seeds, the fanned-out form at the full unit count with the reviewers running together. The fanned-out form reports every seeded defect as a finding against the catalogue item that covers it, and every seed the single reviewer reports; the findings that match no seed and the verdicts item by item are compared and a difference explained. Record for the setup and each unit and for each run the wall time, the tokens read, written and generated, the cost, the document retrievals and any that failed, and any call refused for a rate limit, and set the layout caller's bound on reviewers at once from that. The fanned-out run takes no more time and costs no more than the single-reviewer run. A seed not reported is closed where the gap lies, a catalogue amendment, a correction to the review step or to what it gives a reviewer, and the run repeated in a new session. The evidence names the exact model and the commit. Out of scope: the schematic, critical-routing and production-files proofs.
        done = mock.Mock(returncode=0, stdout="CHECK | x\nSEEDS | 21 seeds | f\nKEPT | /kept/repository | abc123\nRESULT | WRITTEN | out\n", stderr="")
        with mock.patch.object(proof.subprocess, "run", return_value=done) as run:
            kept = proof.run_seed(self.work, "kicad", "resvg")
        self.assertEqual(kept, {"repository": "/kept/repository", "commit": "abc123"})
        command = run.call_args[0][0]
        self.assertEqual(command[command.index("--keep-work-tree") + 1], os.path.join(self.work, proof.KEPT_TREE))
        self.assertEqual(command[command.index("--seeds") + 1], os.path.join(self.work, proof.SEEDS))
        self.assertEqual(command[command.index("--out") + 1], os.path.join(self.work, proof.SEEDED))
        for returncode, error in ((1, proof.Refused), (2, review_fan_out.board_check.CannotRun)):
            with mock.patch.object(proof.subprocess, "run", return_value=mock.Mock(returncode=returncode, stdout="REFUSED | x", stderr="no kicad")):
                with self.assertRaises(error):
                    proof.run_seed(self.work, "kicad", "resvg")
        with mock.patch.object(proof.subprocess, "run", return_value=mock.Mock(returncode=0, stdout="RESULT | WRITTEN", stderr="")):
            with self.assertRaises(proof.Refused):
                proof.run_seed(self.work, "kicad", "resvg")

    def test_the_folder_is_written_from_the_kept_commit_with_the_views_and_the_checks_lines(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C8: Run the single-reviewer form and the fanned-out form on one seeded copy of the layout review proof design from the review folder the folder command assembles with the design from the seeded copy's repository and commit kept by the seeding command's opt-in flag, both forms with the same four tools, in sessions with no record of the seeds, the fanned-out form at the full unit count with the reviewers running together. The fanned-out form reports every seeded defect as a finding against the catalogue item that covers it, and every seed the single reviewer reports; the findings that match no seed and the verdicts item by item are compared and a difference explained. Record for the setup and each unit and for each run the wall time, the tokens read, written and generated, the cost, the document retrievals and any that failed, and any call refused for a rate limit, and set the layout caller's bound on reviewers at once from that. The fanned-out run takes no more time and costs no more than the single-reviewer run. A seed not reported is closed where the gap lies, a catalogue amendment, a correction to the review step or to what it gives a reviewer, and the run repeated in a new session. The evidence names the exact model and the commit. Out of scope: the schematic, critical-routing and production-files proofs.
        seeded = self.seeded(self.work)
        folder = proof.write_folder(self.work, seeded)
        content = fx.round_file(folder)
        self.assertEqual((content["number"], content["kind"], content["commit"]), (1, "full", seeded["commit"]))
        self.assertEqual(content["check"], [f"DESIGN | {self.DESIGN}/x.kicad_pro | PASS", f"FIGURE | {self.DESIGN}/x.kicad_pro | WORK-2 | 1.3"])
        self.assertEqual(content["views"], proof.VIEW_COMMANDS)
        self.assertTrue(os.path.isfile(os.path.join(folder, "views", "index.txt")))
        self.assertTrue(os.path.isfile(os.path.join(folder, self.DESIGN, "board.kicad_pcb")))
        self.assertFalse(os.path.exists(os.path.join(folder, self.DESIGN, "layout-review.md")))
        self.assertFalse(os.path.exists(os.path.join(folder, "seeds.json")))
        os.remove(os.path.join(self.work, proof.SEEDED, review_seed.REPORT))
        shutil.rmtree(folder)
        with self.assertRaises((proof.Refused, OSError)):
            proof.write_folder(self.work, seeded)


if __name__ == "__main__":
    unittest.main()
