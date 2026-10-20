#!/usr/bin/env python3
"""The review fan-out command, run against a stub in place of the agent command line.

The command is run as shipped, over synthetic review folders and a synthetic
caller written to a temporary folder. A stub program named by the command's
environment variable plays the agent command line: it records how it was
started, plays a session's start report and result report, including the
cumulative figures a fork reports, and sleeps to show concurrency. No model and
no KiCad are used.
"""

from __future__ import annotations

import contextlib
import io
import itertools
import json
import os
import re
import shutil
import stat
import sys
import tempfile
import textwrap
import unittest
from unittest import mock

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)

import review_fan_out  # noqa: E402

REPO = os.path.dirname(os.path.dirname(TOOLS))
STUB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "review_fan_out_stub.py")

CALLER = '''
import os
import re

SETUP_PROMPT = "Read every document in the review folder."
TOOLS = ("Read", "Glob")
BOUND = 2
TABLES = {"Verdicts": {"columns": ["Item", "Verdict", "Rests on"], "verdict_column": "Verdict",
                       "verdicts": ("pass", "fail")},
          "Findings": {"columns": ["Finding", "Item", "What"]}}
FINDINGS = {FINDINGS}


def unit_prompt(unit):
    return f"Judge UNIT={unit} against the checklist."


def units(folder):
    return sorted(name[:-4] for name in os.listdir(os.path.join(folder, "units")) if name.endswith(".txt"))


def CHECK(folder, units, tables):
    return {CHECK}
'''

FINDINGS = ('{"table": "Findings", "number": "Finding", "item": "Item", "checklist": ["A-1", "B-1", "C-1"], '
            '"citations": [("Verdicts", "Rests on")], "citation": re.compile(r"(?<![\\w-])F(?P<number>\\d+)\\b"), '
            '"key": lambda row: row["What"].split("@")[1] if "@" in row["What"] else None}')


def caller_text(findings=FINDINGS, check="[]"):
    return CALLER.replace("{FINDINGS}", findings).replace("{CHECK}", check)


def verdicts(*rows):
    return [{"Item": item, "Verdict": verdict, "Rests on": rests} for item, verdict, rests in rows]


def finding(number, item, what):
    return {"Finding": number, "Item": item, "What": what}


class Fixture(unittest.TestCase):
    """A review folder, an output folder, a caller folder and the stub, in a temporary folder."""

    UNITS = ("alpha", "bravo", "charlie")

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="fan-out-test-")
        self.addCleanup(shutil.rmtree, self.root, True)
        self.review = os.path.join(self.root, "review")
        self.out = os.path.join(self.root, "out")
        self.callers = os.path.join(self.root, "callers")
        self.log = os.path.join(self.root, "log")
        for folder in (self.callers, self.log, os.path.join(self.review, "units")):
            os.makedirs(folder)
        for unit in self.UNITS:
            self.write(os.path.join(self.review, "units", f"{unit}.txt"), unit)
        self.write(os.path.join(self.review, "method.md"), "the method")
        self.write(os.path.join(self.callers, "review_caller_synth.py"), caller_text())
        self.scenario_path = os.path.join(self.root, "scenario.json")
        self.scenario({})
        self.program = os.path.join(self.root, "agent")
        self.write(self.program, f'#!/bin/sh\nexec "{sys.executable}" "{STUB}" "$@"\n')
        os.chmod(self.program, os.stat(self.program).st_mode | stat.S_IXUSR)
        patcher = mock.patch.dict(os.environ, {review_fan_out.AGENT_ENV: self.program, "STUB_SCENARIO": self.scenario_path,
                                               "STUB_LOG": self.log})
        patcher.start()
        self.addCleanup(patcher.stop)

    def write(self, path, text):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)

    def scenario(self, content):
        self.write(self.scenario_path, json.dumps(content))

    def run_command(self, *extra, as_json=False, caller="synth", wait="0", review=None, out=None):
        args = ["--caller", caller, "--callers", self.callers, "--review", review or self.review,
                "--out", out or self.out, "--rate-limit-wait", wait] + list(extra) + (["--json"] if as_json else [])
        stdout, stderr = io.StringIO(), io.StringIO()
        status = review_fan_out.main(args, out=stdout, err=stderr)
        return status, stdout.getvalue(), stderr.getvalue()

    def calls(self):
        found = []
        for name in sorted(os.listdir(self.log)):
            if name.endswith(".json"):
                with open(os.path.join(self.log, name), encoding="utf-8") as handle:
                    found.append(json.load(handle))
        return sorted(found, key=lambda call: call["began"])

    def forks(self):
        return [call for call in self.calls() if call["forked"]]

    def kept(self, unit):
        with open(os.path.join(self.out, "units", f"{unit}.json"), encoding="utf-8") as handle:
            return json.load(handle)

    @staticmethod
    def flag(call, name):
        return call["args"][call["args"].index(name) + 1]


class Judging(Fixture):
    def overlap(self, calls):
        points = sorted([(call["began"], 1) for call in calls] + [(call["ended"], -1) for call in calls])
        running = most = 0
        for _, step in points:
            running += step
            most = max(most, running)
        return most

    def test_units_are_judged_in_forks_of_one_setup_session_and_no_more_run_at_once_than_the_bound(self):
        # SOL-HW-REVIEW-FAN-OUT-DRIVER.C1: Against a stub in place of the agent command line, the setup session is started once and before any unit; with two or more units each unit's reviewer is started by resuming the setup session's id as a fork, the count of forks equals the count of units, and no more than the stated number are running at once however many units there are; with one unit no fork is started and the unit is judged in the setup session. The model and tool set of every fork equal the setup session's and the caller's. The result of each unit is returned with the unit's name, and the order the stub finishes them in does not change the merged output. Out of scope: the checks of a session's report, failure handling and any merge.
        units = [f"u{n}" for n in range(6)]
        for name in os.listdir(os.path.join(self.review, "units")):
            os.remove(os.path.join(self.review, "units", name))
        for unit in units:
            self.write(os.path.join(self.review, "units", f"{unit}.txt"), unit)
        self.scenario({"sleep": 0.3})
        status, text, _ = self.run_command(as_json=True)
        self.assertEqual(status, 0, text)
        report = json.loads(text)
        calls = self.calls()
        setups = [call for call in calls if call["unit"] is None]
        self.assertEqual(len(setups), 1, "one setup session")
        self.assertIs(calls[0], setups[0], "started before any unit")
        self.assertFalse(setups[0]["forked"])
        self.assertEqual(len(self.forks()), len(units), "one fork for each unit")
        for fork in self.forks():
            self.assertEqual(fork["resume"], setups[0]["session"], "forked from the setup session's id")
            self.assertEqual(self.flag(fork, "--tools"), "Read,Glob", "the caller's tools")
            self.assertEqual(self.flag(fork, "--model"), "model-a", "the setup session's model")
        self.assertEqual(sorted(fork["unit"] for fork in self.forks()), units)
        self.assertEqual(self.overlap(self.forks()), 2, "the caller's bound of two, reached and not passed")
        self.assertEqual([unit["unit"] for unit in report["units"]], units, "each result with its unit's name")

        shutil.rmtree(self.out)
        for name in os.listdir(self.log):
            os.remove(os.path.join(self.log, name))
        status, text, _ = self.run_command("--bound", "3", as_json=True)
        self.assertEqual(status, 0, text)
        self.assertEqual(self.overlap(self.forks()), 3, "--bound replaces the caller's value")

    def test_the_merged_output_does_not_depend_on_the_order_the_units_finish_in(self):
        # SOL-HW-REVIEW-FAN-OUT-DRIVER.C1: Against a stub in place of the agent command line, the setup session is started once and before any unit; with two or more units each unit's reviewer is started by resuming the setup session's id as a fork, the count of forks equals the count of units, and no more than the stated number are running at once however many units there are; with one unit no fork is started and the unit is judged in the setup session. The model and tool set of every fork equal the setup session's and the caller's. The result of each unit is returned with the unit's name, and the order the stub finishes them in does not change the merged output. Out of scope: the checks of a session's report, failure handling and any merge.
        tables = {"alpha": {"Verdicts": verdicts(("A-1", "fail", "F1")), "Findings": [finding(1, "A-1", "x")]},
                  "bravo": {"Verdicts": verdicts(("B-1", "fail", "F1")), "Findings": [finding(1, "B-1", "y")]},
                  "charlie": {"Verdicts": verdicts(("C-1", "pass", "ok")), "Findings": []}}
        merged = []
        for sleeps in ({"alpha": 0.6, "bravo": 0.3, "charlie": 0}, {"alpha": 0, "bravo": 0.3, "charlie": 0.6}):
            self.scenario({"tables": tables, "units": {unit: [{"sleep": sleep}] for unit, sleep in sleeps.items()}})
            shutil.rmtree(self.out, ignore_errors=True)
            status, text, _ = self.run_command("--bound", "3", as_json=True)
            self.assertEqual(status, 0, text)
            merged.append(json.loads(text)["tables"])
        self.assertEqual(merged[0], merged[1])
        self.assertEqual([row["Finding"] for row in merged[0]["Findings"]["rows"]], [1, 2])

    def test_a_single_unit_is_judged_in_a_second_turn_of_the_setup_session_without_a_fork(self):
        # SOL-HW-REVIEW-FAN-OUT-DRIVER.C1: Against a stub in place of the agent command line, the setup session is started once and before any unit; with two or more units each unit's reviewer is started by resuming the setup session's id as a fork, the count of forks equals the count of units, and no more than the stated number are running at once however many units there are; with one unit no fork is started and the unit is judged in the setup session. The model and tool set of every fork equal the setup session's and the caller's. The result of each unit is returned with the unit's name, and the order the stub finishes them in does not change the merged output. Out of scope: the checks of a session's report, failure handling and any merge.
        for unit in ("bravo", "charlie"):
            os.remove(os.path.join(self.review, "units", f"{unit}.txt"))
        status, text, _ = self.run_command(as_json=True)
        self.assertEqual(status, 0, text)
        calls = self.calls()
        self.assertEqual(len(calls), 2)
        self.assertFalse(any(call["forked"] for call in calls), "no fork is started")
        setup, turn = calls
        self.assertIsNone(setup["unit"])
        self.assertEqual(self.flag(setup, "--tools"), "Read,Glob,Grep", "the setup turn has the read tools")
        self.assertEqual(turn["resume"], setup["session"], "the unit is judged in the setup session")
        self.assertEqual(self.flag(turn, "--tools"), "Read,Glob", "with the caller's tools")
        report = json.loads(text)
        self.assertEqual([(unit["unit"], unit["mode"]) for unit in report["units"]], [("alpha", "setup session")])

    def test_a_setup_answer_is_not_checked_a_second_time_on_the_single_units_turn(self):
        # SOL-HW-REVIEW-FAN-OUT-DRIVER.C2: Each session's start report is read and a run whose report shows other tools than were granted, another model, any MCP server, an instruction source the command line was asked to exclude or another working directory fails naming the session. The setup session is started with the read tools only and a prompt that reads documents and records and asks for no judgement and no image and for one fixed token as the whole answer; a setup answer other than that token after trimming fails the run, so no forked reviewer inherits a verdict, and a read of a file whose type is not text in the setup session's tool uses fails the run naming the file. Out of scope: the content of a caller's prompt for its units.
        for unit in ("bravo", "charlie"):
            os.remove(os.path.join(self.review, "units", f"{unit}.txt"))
        status, text, _ = self.run_command(as_json=True)
        self.assertEqual(status, 0, text)
        self.assertNotEqual(json.loads(text)["units"][0]["status"], "failed",
                            "the unit's answer is a table and not the fixed token")


class StartReports(Fixture):
    def refused(self, scenario, *words):
        self.scenario(scenario)
        status, text, _ = self.run_command()
        self.assertEqual(status, 1, text)
        lines = [line for line in text.splitlines() if line.startswith("REFUSED | ")]
        self.assertTrue(lines, text)
        for word in words:
            self.assertTrue(any(word in line for line in lines), f"{word!r} in {lines}")
        return text

    def test_a_start_report_that_shows_more_than_was_granted_fails_naming_the_session(self):
        # SOL-HW-REVIEW-FAN-OUT-DRIVER.C2: Each session's start report is read and a run whose report shows other tools than were granted, another model, any MCP server, an instruction source the command line was asked to exclude or another working directory fails naming the session. The setup session is started with the read tools only and a prompt that reads documents and records and asks for no judgement and no image and for one fixed token as the whole answer; a setup answer other than that token after trimming fails the run, so no forked reviewer inherits a verdict, and a read of a file whose type is not text in the setup session's tool uses fails the run naming the file. Out of scope: the content of a caller's prompt for its units.
        cases = {"tools": ({"setup_tools": ["Read", "Bash"]}, "tools"),
                 "mcp": ({"mcp_servers": [{"name": "konnect"}]}, "MCP servers"),
                 "skills": ({"skills": ["repo-board-design"]}, "skills"),
                 "plugins": ({"plugins": [{"name": "outside", "path": "/home/someone/plugin"}]}, "plugins"),
                 "cwd": ({"cwd": "/somewhere/else"}, "started in /somewhere/else")}
        for name, (scenario, word) in cases.items():
            with self.subTest(case=name):
                shutil.rmtree(self.out, ignore_errors=True)
                for call in os.listdir(self.log):
                    os.remove(os.path.join(self.log, call))
                self.refused(scenario, "the setup session", word)
                self.assertEqual(len(self.calls()), 1, "no unit was started after a setup session that failed its check")

    def test_a_fork_whose_start_report_shows_another_model_or_tools_fails_its_unit(self):
        # SOL-HW-REVIEW-FAN-OUT-DRIVER.C2: Each session's start report is read and a run whose report shows other tools than were granted, another model, any MCP server, an instruction source the command line was asked to exclude or another working directory fails naming the session. The setup session is started with the read tools only and a prompt that reads documents and records and asks for no judgement and no image and for one fixed token as the whole answer; a setup answer other than that token after trimming fails the run, so no forked reviewer inherits a verdict, and a read of a file whose type is not text in the setup session's tool uses fails the run naming the file. Out of scope: the content of a caller's prompt for its units.
        for scenario, word in (({"fork_model": "model-b"}, "model model-b"), ({"fork_tools": ["Read", "Write"]}, "tools")):
            with self.subTest(word=word):
                shutil.rmtree(self.out, ignore_errors=True)
                self.scenario(scenario)
                status, text, _ = self.run_command()
                self.assertEqual(status, 1, text)
                self.assertRegex(text, r"FAILED \| unit alpha failed: the reviewer of unit alpha started with .*" + word)
                self.assertFalse(os.path.exists(os.path.join(self.out, "record.json")))

    def test_a_setup_session_that_opened_an_image_or_a_binary_file_fails_naming_the_file(self):
        # SOL-HW-REVIEW-FAN-OUT-DRIVER.C2: Each session's start report is read and a run whose report shows other tools than were granted, another model, any MCP server, an instruction source the command line was asked to exclude or another working directory fails naming the session. The setup session is started with the read tools only and a prompt that reads documents and records and asks for no judgement and no image and for one fixed token as the whole answer; a setup answer other than that token after trimming fails the run, so no forked reviewer inherits a verdict, and a read of a file whose type is not text in the setup session's tool uses fails the run naming the file. Out of scope: the content of a caller's prompt for its units.
        with open(os.path.join(self.review, "blob"), "wb") as handle:
            handle.write(b"\x89PNG\0\0data")
        for path in (os.path.join(self.review, "views", "top.png"), os.path.join(self.review, "blob"), "views/side.PDF"):
            with self.subTest(path=path):
                shutil.rmtree(self.out, ignore_errors=True)
                self.refused({"setup": {"reads": [os.path.join(self.review, "method.md"), path]}}, path, "not text")
        shutil.rmtree(self.out, ignore_errors=True)
        self.scenario({"setup": {"reads": [os.path.join(self.review, "method.md"), "units/alpha.txt"]}})
        status, text, _ = self.run_command()
        self.assertEqual(status, 0, "text files are read freely: " + text)

    def test_a_setup_answer_other_than_the_fixed_token_fails_the_run_and_starts_no_fork(self):
        # SOL-HW-REVIEW-FAN-OUT-DRIVER.C2: Each session's start report is read and a run whose report shows other tools than were granted, another model, any MCP server, an instruction source the command line was asked to exclude or another working directory fails naming the session. The setup session is started with the read tools only and a prompt that reads documents and records and asks for no judgement and no image and for one fixed token as the whole answer; a setup answer other than that token after trimming fails the run, so no forked reviewer inherits a verdict, and a read of a file whose type is not text in the setup session's tool uses fails the run naming the file. Out of scope: the content of a caller's prompt for its units.
        self.refused({"setup": {"answer": "I read it. Board 1 looks fine."}}, "the setup session answered", "Board 1 looks fine")
        self.assertEqual(self.forks(), [])
        shutil.rmtree(self.out, ignore_errors=True)
        self.scenario({"setup": {"answer": "  SETUP-READ-COMPLETE \n"}})
        status, text, _ = self.run_command()
        self.assertEqual(status, 0, "trimmed, the token is the whole answer: " + text)

    def test_the_setup_session_is_started_with_read_tools_the_fixed_ask_and_no_loaded_instructions(self):
        # SOL-HW-REVIEW-FAN-OUT-DRIVER.C2: Each session's start report is read and a run whose report shows other tools than were granted, another model, any MCP server, an instruction source the command line was asked to exclude or another working directory fails naming the session. The setup session is started with the read tools only and a prompt that reads documents and records and asks for no judgement and no image and for one fixed token as the whole answer; a setup answer other than that token after trimming fails the run, so no forked reviewer inherits a verdict, and a read of a file whose type is not text in the setup session's tool uses fails the run naming the file. Out of scope: the content of a caller's prompt for its units.
        status, text, _ = self.run_command()
        self.assertEqual(status, 0, text)
        for call in self.calls():
            self.assertIn("--strict-mcp-config", call["args"])
            self.assertIn("--disable-slash-commands", call["args"])
            self.assertEqual(self.flag(call, "--setting-sources"), "")
            self.assertEqual(self.flag(call, "--permission-mode"), "dontAsk")
            self.assertIn("disableAllHooks", self.flag(call, "--settings"))
            self.assertEqual(self.flag(call, "--output-format"), "stream-json")
            self.assertEqual(os.path.realpath(call["cwd"]), os.path.realpath(self.review))
            self.assertIn("CLAUDE_CODE_DISABLE_CLAUDE_MDS", call["env"])
        setup = self.calls()[0]
        self.assertEqual(self.flag(setup, "--tools"), "Read,Glob,Grep")
        self.assertTrue(setup["prompt"].startswith("Read every document in the review folder."))
        self.assertIn("answer with exactly SETUP-READ-COMPLETE and nothing else", setup["prompt"])
        self.assertIn("Open no image and judge nothing", setup["prompt"])


class Failures(Fixture):
    def test_a_unit_whose_reviewer_errors_or_returns_nothing_or_malformed_tables_is_run_once_more(self):
        # SOL-HW-REVIEW-FAN-OUT-DRIVER.C3: A unit whose reviewer exits with an error or returns nothing is run once more; a call refused for a rate limit is retried after a wait that grows, a bounded number of times; a unit that still fails fails the run, naming the unit and what the reviewer returned, and the other units' results are kept in the output. Out of scope: what a caller counts as a malformed result, which the caller defines.
        bad_verdict = json.dumps({"tables": {"Verdicts": verdicts(("A-1", "maybe", "x"))}})
        extra_column = json.dumps({"tables": {"Verdicts": [{"Item": "A-1", "Verdict": "pass", "Rests on": "x", "Mood": "ok"}]}})
        for first in ({"exit": 1}, {"text": ""}, {"text": "not json"}, {"text": bad_verdict}, {"text": extra_column},
                      {"text": json.dumps({"verdicts": []})}):
            with self.subTest(first=first):
                shutil.rmtree(self.out, ignore_errors=True)
                for call in os.listdir(self.log):
                    os.remove(os.path.join(self.log, call))
                self.scenario({"units": {"bravo": [first, {}]}})
                status, text, _ = self.run_command(as_json=True)
                self.assertEqual(status, 0, text)
                bravo = [unit for unit in json.loads(text)["units"] if unit["unit"] == "bravo"][0]
                self.assertEqual(bravo["attempts"], 2)
                self.assertEqual(len([call for call in self.forks() if call["unit"] == "bravo"]), 2)
                self.assertEqual(len([call for call in self.forks() if call["unit"] == "alpha"]), 1, "the others run once")

    def test_a_unit_that_still_fails_fails_the_run_naming_it_and_what_it_returned_and_keeps_the_others(self):
        # SOL-HW-REVIEW-FAN-OUT-DRIVER.C3: A unit whose reviewer exits with an error or returns nothing is run once more; a call refused for a rate limit is retried after a wait that grows, a bounded number of times; a unit that still fails fails the run, naming the unit and what the reviewer returned, and the other units' results are kept in the output. Out of scope: what a caller counts as a malformed result, which the caller defines.
        self.scenario({"units": {"bravo": [{"exit": 3, "stderr": "segfault in the reviewer"}]}})
        status, text, _ = self.run_command()
        self.assertEqual(status, 1, text)
        self.assertRegex(text, r"FAILED \| unit bravo failed after 2 attempts; the reviewer returned: segfault in the reviewer")
        self.assertIn("RESULT | FAILED | 1 of 3 units failed: bravo", text)
        self.assertTrue(os.path.isfile(os.path.join(self.out, "units", "alpha.json")))
        self.assertTrue(os.path.isfile(os.path.join(self.out, "units", "charlie.json")))
        self.assertFalse(os.path.exists(os.path.join(self.out, "units", "bravo.json")))
        self.assertFalse(os.path.exists(os.path.join(self.out, "record.json")), "no merged record is written")
        self.assertFalse(os.path.exists(os.path.join(self.out, review_fan_out.LOCK)), "the lock is released")
        status, text, _ = self.run_command(as_json=True, out=self.out)
        self.assertEqual(status, 1, "the kept results make the folder one a fresh run refuses")

    def test_a_malformed_result_names_what_the_reviewer_returned(self):
        # SOL-HW-REVIEW-FAN-OUT-DRIVER.C3: A unit whose reviewer exits with an error or returns nothing is run once more; a call refused for a rate limit is retried after a wait that grows, a bounded number of times; a unit that still fails fails the run, naming the unit and what the reviewer returned, and the other units' results are kept in the output. Out of scope: what a caller counts as a malformed result, which the caller defines.
        self.scenario({"units": {"charlie": [{"text": "I could not decide."}]}})
        status, text, _ = self.run_command(as_json=True)
        self.assertEqual(status, 1, text)
        failed = [unit for unit in json.loads(text)["units"] if unit["status"] == "failed"]
        self.assertEqual([unit["unit"] for unit in failed], ["charlie"])
        self.assertIn("I could not decide.", failed[0]["detail"])

    def test_a_call_refused_for_a_rate_limit_is_retried_after_a_wait_that_grows_a_bounded_number_of_times(self):
        # SOL-HW-REVIEW-FAN-OUT-DRIVER.C3: A unit whose reviewer exits with an error or returns nothing is run once more; a call refused for a rate limit is retried after a wait that grows, a bounded number of times; a unit that still fails fails the run, naming the unit and what the reviewer returned, and the other units' results are kept in the output. Out of scope: what a caller counts as a malformed result, which the caller defines.
        waits = []
        refused = mock.Mock(side_effect=review_fan_out.RateLimited("429"))
        with self.assertRaises(review_fan_out.UnitFailed) as caught:
            review_fan_out.with_rate_retry(refused, 2.0, waits.append)
        self.assertEqual(waits, [2.0, 4.0, 8.0, 16.0, 32.0], "doubling")
        self.assertEqual(refused.call_count, review_fan_out.RATE_RETRIES + 1, "bounded")
        self.assertIn("429", str(caught.exception))
        calls = iter([review_fan_out.RateLimited("429"), review_fan_out.RateLimited("429"), "ok"])

        def call():
            item = next(calls)
            if isinstance(item, Exception):
                raise item
            return item
        waits.clear()
        self.assertEqual(review_fan_out.with_rate_retry(call, 1.0, waits.append), "ok")
        self.assertEqual(waits, [1.0, 2.0])

    def test_a_rate_limited_reviewer_call_is_retried_without_using_the_unit_s_one_more_run(self):
        # SOL-HW-REVIEW-FAN-OUT-DRIVER.C3: A unit whose reviewer exits with an error or returns nothing is run once more; a call refused for a rate limit is retried after a wait that grows, a bounded number of times; a unit that still fails fails the run, naming the unit and what the reviewer returned, and the other units' results are kept in the output. Out of scope: what a caller counts as a malformed result, which the caller defines.
        self.scenario({"units": {"alpha": [{"rate_limit": True}, {"rate_limit": True}, {"exit": 1}, {}]}})
        status, text, _ = self.run_command(as_json=True)
        self.assertEqual(status, 0, text)
        alpha = [call for call in self.forks() if call["unit"] == "alpha"]
        self.assertEqual(len(alpha), 4, "two refusals retried, one error run once more")
        self.assertEqual([unit["attempts"] for unit in json.loads(text)["units"] if unit["unit"] == "alpha"], [2])

    def test_a_reviewer_still_refused_for_a_rate_limit_after_the_retries_fails_its_unit(self):
        # SOL-HW-REVIEW-FAN-OUT-DRIVER.C3: A unit whose reviewer exits with an error or returns nothing is run once more; a call refused for a rate limit is retried after a wait that grows, a bounded number of times; a unit that still fails fails the run, naming the unit and what the reviewer returned, and the other units' results are kept in the output. Out of scope: what a caller counts as a malformed result, which the caller defines.
        self.scenario({"units": {"alpha": [{"rate_limit": True}]}})
        status, text, _ = self.run_command()
        self.assertEqual(status, 1, text)
        self.assertRegex(text, r"FAILED \| unit alpha failed: still refused for a rate limit after 5 retries")
        self.assertEqual(len([call for call in self.forks() if call["unit"] == "alpha"]), review_fan_out.RATE_RETRIES + 1)
        self.assertTrue(os.path.isfile(os.path.join(self.out, "units", "bravo.json")))


class Interface(Fixture):
    def refusal_lines(self, text):
        return [line for line in text.splitlines() if line.startswith("REFUSED | ")]

    def test_every_refusal_exits_one_with_a_refused_line_naming_its_cause_and_what_to_do(self):
        # SOL-HW-REVIEW-FAN-OUT-DRIVER.C4: The exit status is 0 when the merged record is written, 1 when the command refuses or a unit fails, and 2 when the agent command line is missing or not logged in, each with a line beginning REFUSED or CANNOT RUN as the other board commands print; a review folder inside the repository, a folder that does not exist, an output folder inside the review folder or containing it or inside the repository, a caller name with no module or whose module lacks a required attribute, an output folder that already holds a record when no unit is named to run again, an output folder in use by another run, and a bound below one are refused. Each REFUSED and CANNOT RUN line names its cause and what to do about it. The report is available as text and as JSON and the two hold the same facts. Out of scope: the merge's own refusals, which each caller names.
        self.write(os.path.join(self.callers, "review_caller_bare.py"), "SETUP_PROMPT = 'x'\n")
        self.write(os.path.join(self.callers, "review_caller_wild.py"), caller_text().replace('TOOLS = ("Read", "Glob")', 'TOOLS = ("Read", "Bash")'))
        self.write(os.path.join(self.callers, "review_caller_broken.py"), "this is not python (\n")
        os.makedirs(os.path.join(self.out, "units"))
        self.write(os.path.join(self.out, "units", "alpha.json"), "{}")
        held = os.path.join(self.root, "held")
        self.write(os.path.join(held, review_fan_out.LOCK), "123")
        inner = os.path.join(self.review, "kept-here")
        elsewhere = os.path.join(self.root, "elsewhere")
        cases = [
            ("missing review", dict(review=os.path.join(self.root, "nowhere"), out=elsewhere), (), "does not exist", "give"),
            ("output in review", dict(out=inner), (), "inside the review folder", "give a folder apart"),
            ("output containing review", dict(out=self.root), (), "contains the review folder", "give a folder apart"),
            ("no module", dict(caller="absent", out=elsewhere), (), "there is no caller module", "give the name"),
            ("missing attribute", dict(caller="bare", out=elsewhere), (), "lacks unit_prompt, units, TOOLS", "add each"),
            ("write tool", dict(caller="wild", out=elsewhere), (), "a reviewer is read-only", "grant"),
            ("unloadable", dict(caller="broken", out=elsewhere), (), "cannot be loaded", "fix the module"),
            ("record held", dict(), (), "already holds a record", "--rerun"),
            ("in use", dict(out=held), (), "is in use by another run", "wait for that run"),
            ("bound below one", dict(out=elsewhere), ("--bound", "0"), "below one", "give one or more"),
            ("bound not a number", dict(out=elsewhere), ("--bound", "many"), "not a whole number", "give one or more"),
            ("bad name", dict(caller="Bad-Name", out=elsewhere), (), "not a lower-case name", "give the <name>"),
        ]
        for name, options, extra, cause, advice in cases:
            with self.subTest(case=name):
                options.setdefault("out", self.out)
                status, text, _ = self.run_command(*extra, **options)
                self.assertEqual(status, 1, text)
                lines = self.refusal_lines(text)
                self.assertTrue(any(cause in line and advice in line for line in lines), f"{cause!r} and {advice!r} in {lines}")
                self.assertIn("RESULT | REFUSED | nothing was run", text)
                self.assertEqual(self.calls(), [], "nothing was started")

    def test_the_output_folder_inside_the_repository_and_a_review_folder_inside_it_are_refused(self):
        # SOL-HW-REVIEW-FAN-OUT-DRIVER.C4: The exit status is 0 when the merged record is written, 1 when the command refuses or a unit fails, and 2 when the agent command line is missing or not logged in, each with a line beginning REFUSED or CANNOT RUN as the other board commands print; a review folder inside the repository, a folder that does not exist, an output folder inside the review folder or containing it or inside the repository, a caller name with no module or whose module lacks a required attribute, an output folder that already holds a record when no unit is named to run again, an output folder in use by another run, and a bound below one are refused. Each REFUSED and CANNOT RUN line names its cause and what to do about it. The report is available as text and as JSON and the two hold the same facts. Out of scope: the merge's own refusals, which each caller names.
        with mock.patch.object(review_fan_out, "REPO", self.root):
            status, text, _ = self.run_command(out=os.path.join(self.root, "elsewhere"))
            self.assertEqual(status, 1)
            self.assertTrue(any("the review folder" in line and "is inside the repository" in line and "outside it" in line
                                for line in self.refusal_lines(text)), text)
            self.assertTrue(any("the output folder" in line and "is inside the repository" in line
                                for line in self.refusal_lines(text)), text)
        self.assertEqual(self.calls(), [])

    def test_a_missing_agent_command_line_or_one_not_logged_in_exits_two_with_a_cannot_run_line(self):
        # SOL-HW-REVIEW-FAN-OUT-DRIVER.C4: The exit status is 0 when the merged record is written, 1 when the command refuses or a unit fails, and 2 when the agent command line is missing or not logged in, each with a line beginning REFUSED or CANNOT RUN as the other board commands print; a review folder inside the repository, a folder that does not exist, an output folder inside the review folder or containing it or inside the repository, a caller name with no module or whose module lacks a required attribute, an output folder that already holds a record when no unit is named to run again, an output folder in use by another run, and a bound below one are refused. Each REFUSED and CANNOT RUN line names its cause and what to do about it. The report is available as text and as JSON and the two hold the same facts. Out of scope: the merge's own refusals, which each caller names.
        os.environ[review_fan_out.AGENT_ENV] = os.path.join(self.root, "no-such-agent")
        status, text, err = self.run_command()
        self.assertEqual(status, 2)
        self.assertRegex(err, r"^CANNOT RUN \| the agent command line .*no-such-agent is not on the search path; install it, or name the program in the environment variable REVIEW_FAN_OUT_AGENT")
        status, text, _ = self.run_command(as_json=True)
        self.assertEqual(status, 2)
        self.assertIn("is not on the search path", json.loads(text)["cannot_run"])
        os.environ[review_fan_out.AGENT_ENV] = self.program
        self.scenario({"auth": 1})
        status, text, err = self.run_command()
        self.assertEqual(status, 2)
        self.assertIn("CANNOT RUN | the agent command line", err)
        self.assertIn("is not logged in; log it in, then run again", err)
        self.assertEqual(self.calls(), [], "no session was started")
        self.assertFalse(os.path.exists(self.out), "nothing was created")

    def test_the_text_and_the_json_report_hold_the_same_facts(self):
        # SOL-HW-REVIEW-FAN-OUT-DRIVER.C4: The exit status is 0 when the merged record is written, 1 when the command refuses or a unit fails, and 2 when the agent command line is missing or not logged in, each with a line beginning REFUSED or CANNOT RUN as the other board commands print; a review folder inside the repository, a folder that does not exist, an output folder inside the review folder or containing it or inside the repository, a caller name with no module or whose module lacks a required attribute, an output folder that already holds a record when no unit is named to run again, an output folder in use by another run, and a bound below one are refused. Each REFUSED and CANNOT RUN line names its cause and what to do about it. The report is available as text and as JSON and the two hold the same facts. Out of scope: the merge's own refusals, which each caller names.
        tables = {"alpha": {"Verdicts": verdicts(("A-1", "fail", "F1")), "Findings": [finding(1, "A-1", "pad @U1")]},
                  "bravo": {"Verdicts": verdicts(("B-1", "fail", "F1")), "Findings": [finding(1, "B-1", "pad @U1")]}}
        self.scenario({"tables": tables, "setup": {"cost": 0.2}, "units": {"charlie": [{"cache_read": 0}]}})
        status, text, _ = self.run_command()
        self.assertEqual(status, 0, text)
        shutil.rmtree(self.out)
        self.scenario({"tables": tables, "setup": {"cost": 0.2}, "units": {"charlie": [{"cache_read": 0}]}})
        status, as_json, _ = self.run_command(as_json=True)
        self.assertEqual(status, 0)
        report = json.loads(as_json)
        self.assertEqual(report["result"], "WRITTEN")
        self.assertTrue(os.path.isfile(os.path.join(self.out, "record.json")))
        with open(os.path.join(self.out, "record.json"), encoding="utf-8") as handle:
            self.assertEqual(json.load(handle), report, "the record on disk is the JSON report")
        lines = text.splitlines()
        self.assertEqual(lines[-1], f"RESULT | WRITTEN | {report['detail']}")
        for unit in report["units"]:
            line = [line for line in lines if line.startswith(f"UNIT | {unit['unit']} |")][0]
            for fact in (unit["status"], unit["mode"], f"{unit['attempts']} attempts",
                         f"{unit['own']['api_ms']} ms API", f"{unit['own']['turns']} turns", f"${unit['own']['cost_usd']}",
                         f"read {unit['own']['tokens']['cache_read']}"):
                self.assertIn(fact, line)
            for flag in unit["flags"]:
                self.assertIn(flag, line)
        self.assertEqual(len([line for line in lines if line.startswith("SETUP | ")]), len(report["setup_sessions"]))
        self.assertIn(f"TOTAL | {report['totals']['api_ms']} ms API", text)
        self.assertEqual(len([line for line in lines if line.startswith("SAME PLACE | ")]), len(report["same_place"]))
        self.assertEqual(report["same_place"][0]["findings"], [1, 2])
        for line in lines:
            self.assertRegex(line, r"^(SETUP|UNIT|SAME PLACE|TOTAL|RESULT|RERUN|FAILED|REFUSED) \| ")

        shutil.rmtree(self.out)
        os.makedirs(os.path.join(self.out, "units"))
        self.write(os.path.join(self.out, "units", "x.json"), "{}")
        status, text, _ = self.run_command()
        status_json, as_json, _ = self.run_command(as_json=True)
        self.assertEqual((status, status_json), (1, 1))
        self.assertEqual([line[len("REFUSED | "):] for line in self.refusal_lines(text)],
                         [review_fan_out.board_check.clean(why) for why in json.loads(as_json)["refusals"]])

    def test_a_merge_the_caller_s_check_refuses_exits_one_with_a_refused_line_and_keeps_the_results(self):
        # SOL-HW-REVIEW-FAN-OUT-DRIVER.C4: The exit status is 0 when the merged record is written, 1 when the command refuses or a unit fails, and 2 when the agent command line is missing or not logged in, each with a line beginning REFUSED or CANNOT RUN as the other board commands print; a review folder inside the repository, a folder that does not exist, an output folder inside the review folder or containing it or inside the repository, a caller name with no module or whose module lacks a required attribute, an output folder that already holds a record when no unit is named to run again, an output folder in use by another run, and a bound below one are refused. Each REFUSED and CANNOT RUN line names its cause and what to do about it. The report is available as text and as JSON and the two hold the same facts. Out of scope: the merge's own refusals, which each caller names.
        self.write(os.path.join(self.callers, "review_caller_strict.py"),
                   caller_text(check='["item C-1 has no verdict; ask for it with --rerun charlie"]'))
        status, text, _ = self.run_command(caller="strict")
        self.assertEqual(status, 1, text)
        self.assertIn("REFUSED | item C-1 has no verdict; ask for it with --rerun charlie", text)
        self.assertTrue(os.path.isfile(os.path.join(self.out, "units", "charlie.json")))
        self.assertFalse(os.path.exists(os.path.join(self.out, "record.json")))


class Cost(Fixture):
    def test_each_session_s_own_figures_are_taken_off_the_cumulative_ones_a_fork_reports(self):
        # SOL-HW-REVIEW-FAN-OUT-DRIVER.C5: Against a stub that reports a fork's cost, API time and turn count cumulatively including its setup session, as the agent command line does, the record gives each fork its own cost, time and turns, the setup session its own, and the run their sum; token usage is taken as each session reports it, split into tokens read from the cache, written to it, fresh and generated, and a fork that reads no cache is flagged. The record is in the text and the JSON report. Out of scope: judging whether a run was worth its cost.
        self.scenario({"setup": {"cost": 0.4, "api_ms": 4000, "turns": 3, "cache_read": 0, "cache_write": 9000, "fresh": 11, "generated": 7},
                       "units": {"alpha": [{"cost": 0.1, "api_ms": 1000, "turns": 2, "cache_read": 9000, "cache_write": 5, "fresh": 1, "generated": 50}],
                                 "bravo": [{"cost": 0.2, "api_ms": 2000, "turns": 4, "cache_read": 0}],
                                 "charlie": [{"cost": 0.3, "api_ms": 500, "turns": 1, "cache_read": 8000}]}})
        status, text, _ = self.run_command("--bound", "3", as_json=True)
        self.assertEqual(status, 0, text)
        report = json.loads(text)
        units = {unit["unit"]: unit for unit in report["units"]}
        self.assertEqual((units["alpha"]["own"]["cost_usd"], units["alpha"]["own"]["api_ms"], units["alpha"]["own"]["turns"]), (0.1, 1000, 2))
        self.assertEqual((units["bravo"]["own"]["cost_usd"], units["bravo"]["own"]["api_ms"], units["bravo"]["own"]["turns"]), (0.2, 2000, 4))
        self.assertEqual(units["alpha"]["own"]["tokens"], {"cache_read": 9000, "cache_write": 5, "fresh": 1, "generated": 50},
                         "tokens as the session reports them")
        setup = report["setup_sessions"][0]
        self.assertEqual((setup["cost_usd"], setup["api_ms"], setup["turns"]), (0.4, 4000, 3))
        self.assertEqual(setup["tokens"], {"cache_read": 0, "cache_write": 9000, "fresh": 11, "generated": 7})
        self.assertEqual((report["totals"]["cost_usd"], report["totals"]["api_ms"], report["totals"]["turns"]), (1.0, 7500, 10))
        self.assertEqual(report["totals"]["tokens"]["cache_read"], 17000)
        self.assertEqual(units["bravo"]["flags"], ["no cache read"])
        self.assertEqual(units["alpha"]["flags"], [])
        self.assertEqual(units["charlie"]["flags"], [])

    def test_the_text_report_carries_the_figures_and_the_flag(self):
        # SOL-HW-REVIEW-FAN-OUT-DRIVER.C5: Against a stub that reports a fork's cost, API time and turn count cumulatively including its setup session, as the agent command line does, the record gives each fork its own cost, time and turns, the setup session its own, and the run their sum; token usage is taken as each session reports it, split into tokens read from the cache, written to it, fresh and generated, and a fork that reads no cache is flagged. The record is in the text and the JSON report. Out of scope: judging whether a run was worth its cost.
        self.scenario({"setup": {"cost": 0.4, "api_ms": 4000, "turns": 3},
                       "units": {"bravo": [{"cost": 0.2, "api_ms": 2000, "turns": 4, "cache_read": 0, "cache_write": 77}]}})
        status, text, _ = self.run_command()
        self.assertEqual(status, 0, text)
        self.assertRegex(text, r"SETUP \| \S+ \| initial \| model-a \| 4000 ms API \| [\d.]+ s \| 3 turns \| \$0\.4 \| read 5000")
        self.assertRegex(text, r"UNIT \| bravo \| judged \| fork \| \S+ \| 1 attempts \| 2000 ms API \| [\d.]+ s \| 4 turns \| \$0\.2 "
                               r"\| read 0 wrote 77 fresh 3 generated 100 \| no cache read")
        self.assertRegex(text, r"UNIT \| alpha .* \| no flag")
        self.assertRegex(text, r"TOTAL \| 7000 ms API \| [\d.]+ s \| 9 turns")

    def test_a_single_unit_turn_has_the_setup_session_s_figures_taken_off_and_is_not_flagged(self):
        # SOL-HW-REVIEW-FAN-OUT-DRIVER.C5: Against a stub that reports a fork's cost, API time and turn count cumulatively including its setup session, as the agent command line does, the record gives each fork its own cost, time and turns, the setup session its own, and the run their sum; token usage is taken as each session reports it, split into tokens read from the cache, written to it, fresh and generated, and a fork that reads no cache is flagged. The record is in the text and the JSON report. Out of scope: judging whether a run was worth its cost.
        for unit in ("bravo", "charlie"):
            os.remove(os.path.join(self.review, "units", f"{unit}.txt"))
        self.scenario({"setup": {"cost": 0.4, "api_ms": 4000, "turns": 3}, "units": {"alpha": [{"cost": 0.1, "cache_read": 0}]}})
        status, text, _ = self.run_command(as_json=True)
        self.assertEqual(status, 0, text)
        report = json.loads(text)
        self.assertEqual(report["units"][0]["own"]["cost_usd"], 0.1)
        self.assertEqual(report["units"][0]["flags"], [], "only a fork is flagged for reading no cache")
        self.assertEqual(report["totals"]["cost_usd"], 0.5)


class Merge(unittest.TestCase):
    """The merge, over synthetic unit results and a synthetic caller."""

    @classmethod
    def setUpClass(cls):
        cls.folder = tempfile.mkdtemp(prefix="fan-out-merge-")
        cls.addClassCleanup(shutil.rmtree, cls.folder, True)

    def caller(self, findings=FINDINGS, check="[]"):
        path = os.path.join(self.folder, "review_caller_m.py")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(caller_text(findings, check))
        with mock.patch.object(sys, "dont_write_bytecode", True):
            return review_fan_out.load_caller("m", self.folder)

    ORDER = ("alpha", "bravo", "charlie")

    def results(self):
        return {
            "alpha": {"Verdicts": verdicts(("A-1", "fail", "F2 and R1-F2"), ("B-1", "fail", "F1")),
                      "Findings": [finding(1, "B-1", "gap at the 3V3 pad @U4"), finding(2, "C-1", "silk over a pad")]},
            "bravo": {"Verdicts": verdicts(("A-1", "fail", "F1 beside F2")),
                      "Findings": [finding(1, "A-1", "stub on the clock @U4"), finding(2, "A-1", "stub elsewhere")]},
            "charlie": {"Verdicts": verdicts(("C-1", "pass", "R2-F1 was put right")), "Findings": []},
        }

    def test_the_merge_renumbers_this_round_s_findings_in_the_checklist_s_order_and_rewrites_their_citations(self):
        # SOL-HW-REVIEW-FAN-OUT-DRIVER.C6: Over synthetic unit results and a synthetic caller, the merge rejects a table with a column the caller's table does not have and a verdict outside the caller's set, replaces every finding number a reviewer wrote with the number the checklist's order gives and rewrites the citations of them in the verdict rows, leaves a citation of an earlier round's finding as written, reports two findings that the caller's key assigns to the same item or place and keeps both, and gives the same record for every order the units arrive in. For a caller that declares no findings table nothing is renumbered. It reads no model and no file outside the unit results and the review folder. Out of scope: what a caller's tables must cover and whether a verdict is right.
        merged = review_fan_out.merge(self.caller(), self.folder, self.ORDER, self.results())
        findings = merged["tables"]["Findings"]["rows"]
        # The checklist runs A-1, B-1, C-1: bravo's two A-1 findings come first, then alpha's B-1, then alpha's C-1.
        self.assertEqual([(row["Finding"], row["What"]) for row in findings],
                         [(1, "stub on the clock @U4"), (2, "stub elsewhere"), (3, "gap at the 3V3 pad @U4"), (4, "silk over a pad")])
        cited = [row["Rests on"] for row in merged["tables"]["Verdicts"]["rows"]]
        self.assertEqual(cited, ["F4 and R1-F2", "F3", "F1 beside F2", "R2-F1 was put right"],
                         "each unit's own numbers rewritten by that unit's map, an earlier round's left as written")
        self.assertEqual(merged["tables"]["Findings"]["columns"], ["Finding", "Item", "What"])
        self.assertEqual(merged["tables"]["Verdicts"]["columns"], ["Item", "Verdict", "Rests on"])

    def test_the_first_number_of_a_round_is_the_caller_s(self):
        # SOL-HW-REVIEW-FAN-OUT-DRIVER.C6: Over synthetic unit results and a synthetic caller, the merge rejects a table with a column the caller's table does not have and a verdict outside the caller's set, replaces every finding number a reviewer wrote with the number the checklist's order gives and rewrites the citations of them in the verdict rows, leaves a citation of an earlier round's finding as written, reports two findings that the caller's key assigns to the same item or place and keeps both, and gives the same record for every order the units arrive in. For a caller that declares no findings table nothing is renumbered. It reads no model and no file outside the unit results and the review folder. Out of scope: what a caller's tables must cover and whether a verdict is right.
        caller = self.caller(FINDINGS.replace('"checklist"', '"first": lambda folder: 8, "checklist"'))
        merged = review_fan_out.merge(caller, self.folder, self.ORDER, self.results())
        self.assertEqual([row["Finding"] for row in merged["tables"]["Findings"]["rows"]], [8, 9, 10, 11])
        self.assertEqual(merged["tables"]["Verdicts"]["rows"][1]["Rests on"], "F10")

    def test_two_findings_the_caller_s_key_puts_at_one_place_are_reported_and_both_kept(self):
        # SOL-HW-REVIEW-FAN-OUT-DRIVER.C6: Over synthetic unit results and a synthetic caller, the merge rejects a table with a column the caller's table does not have and a verdict outside the caller's set, replaces every finding number a reviewer wrote with the number the checklist's order gives and rewrites the citations of them in the verdict rows, leaves a citation of an earlier round's finding as written, reports two findings that the caller's key assigns to the same item or place and keeps both, and gives the same record for every order the units arrive in. For a caller that declares no findings table nothing is renumbered. It reads no model and no file outside the unit results and the review folder. Out of scope: what a caller's tables must cover and whether a verdict is right.
        merged = review_fan_out.merge(self.caller(), self.folder, self.ORDER, self.results())
        self.assertEqual(merged["same_place"], [{"key": "U4", "findings": [1, 3], "units": ["alpha", "bravo"]}])
        self.assertEqual(len(merged["tables"]["Findings"]["rows"]), 4, "neither is dropped")
        alone = self.results()
        alone["bravo"]["Findings"][0]["What"] = "stub on the clock"
        self.assertEqual(review_fan_out.merge(self.caller(), self.folder, self.ORDER, alone)["same_place"], [])

    def test_the_merge_gives_one_record_for_every_order_the_units_arrive_in(self):
        # SOL-HW-REVIEW-FAN-OUT-DRIVER.C6: Over synthetic unit results and a synthetic caller, the merge rejects a table with a column the caller's table does not have and a verdict outside the caller's set, replaces every finding number a reviewer wrote with the number the checklist's order gives and rewrites the citations of them in the verdict rows, leaves a citation of an earlier round's finding as written, reports two findings that the caller's key assigns to the same item or place and keeps both, and gives the same record for every order the units arrive in. For a caller that declares no findings table nothing is renumbered. It reads no model and no file outside the unit results and the review folder. Out of scope: what a caller's tables must cover and whether a verdict is right.
        caller, results = self.caller(), self.results()
        reference = review_fan_out.merge(caller, self.folder, self.ORDER, results)
        for arrival in itertools.permutations(results):
            arrived = {unit: results[unit] for unit in arrival}
            self.assertEqual(review_fan_out.merge(caller, self.folder, self.ORDER, arrived), reference, arrival)

    def test_the_merge_rejects_a_column_a_verdict_a_table_and_a_citation_the_caller_does_not_have(self):
        # SOL-HW-REVIEW-FAN-OUT-DRIVER.C6: Over synthetic unit results and a synthetic caller, the merge rejects a table with a column the caller's table does not have and a verdict outside the caller's set, replaces every finding number a reviewer wrote with the number the checklist's order gives and rewrites the citations of them in the verdict rows, leaves a citation of an earlier round's finding as written, reports two findings that the caller's key assigns to the same item or place and keeps both, and gives the same record for every order the units arrive in. For a caller that declares no findings table nothing is renumbered. It reads no model and no file outside the unit results and the review folder. Out of scope: what a caller's tables must cover and whether a verdict is right.
        caller = self.caller()

        def rejected(edit, *words):
            results = self.results()
            edit(results)
            with self.assertRaises(review_fan_out.Refused) as caught:
                review_fan_out.merge(caller, self.folder, self.ORDER, results)
            for word in words:
                self.assertIn(word, " ".join(caught.exception.causes))
        rejected(lambda r: r["alpha"]["Verdicts"][0].update(Mood="calm"), "unit alpha", "a column ['Mood']")
        rejected(lambda r: r["alpha"]["Verdicts"][0].pop("Rests on"), "lacks the column ['Rests on']")
        rejected(lambda r: r["alpha"]["Verdicts"][0].update(Verdict="maybe"), "the verdict 'maybe'")
        rejected(lambda r: r["bravo"].update(Extras=[]), "a table 'Extras'")
        rejected(lambda r: r["bravo"]["Findings"][0].update(Finding=0), "numbered a finding 0")
        rejected(lambda r: r["bravo"]["Findings"][1].update(Finding=1), "numbered two findings 1")
        rejected(lambda r: r["bravo"]["Findings"][0].update(Item="Z-9"), "no item of the checklist")
        rejected(lambda r: r["charlie"]["Verdicts"][0].update(**{"Rests on": "F7"}), "cites a finding 7 the unit did not raise")
        rejected(lambda r: r["charlie"].update(Verdicts="pass"), "not a list of rows")

    def test_a_caller_with_no_findings_table_has_nothing_renumbered(self):
        # SOL-HW-REVIEW-FAN-OUT-DRIVER.C6: Over synthetic unit results and a synthetic caller, the merge rejects a table with a column the caller's table does not have and a verdict outside the caller's set, replaces every finding number a reviewer wrote with the number the checklist's order gives and rewrites the citations of them in the verdict rows, leaves a citation of an earlier round's finding as written, reports two findings that the caller's key assigns to the same item or place and keeps both, and gives the same record for every order the units arrive in. For a caller that declares no findings table nothing is renumbered. It reads no model and no file outside the unit results and the review folder. Out of scope: what a caller's tables must cover and whether a verdict is right.
        merged = review_fan_out.merge(self.caller(findings="None"), self.folder, self.ORDER, self.results())
        self.assertEqual([row["Finding"] for row in merged["tables"]["Findings"]["rows"]], [1, 2, 1, 2])
        self.assertEqual(merged["tables"]["Verdicts"]["rows"][0]["Rests on"], "F2 and R1-F2", "citations left as written")
        self.assertEqual(merged["same_place"], [])

    def test_the_merge_reads_no_model_and_hands_the_caller_s_check_only_the_folder_the_order_and_the_tables(self):
        # SOL-HW-REVIEW-FAN-OUT-DRIVER.C6: Over synthetic unit results and a synthetic caller, the merge rejects a table with a column the caller's table does not have and a verdict outside the caller's set, replaces every finding number a reviewer wrote with the number the checklist's order gives and rewrites the citations of them in the verdict rows, leaves a citation of an earlier round's finding as written, reports two findings that the caller's key assigns to the same item or place and keeps both, and gives the same record for every order the units arrive in. For a caller that declares no findings table nothing is renumbered. It reads no model and no file outside the unit results and the review folder. Out of scope: what a caller's tables must cover and whether a verdict is right.
        caller = self.caller(check='[f"saw {len(tables)} tables of {len(units)} units in " + os.path.basename(folder)]')
        with mock.patch("subprocess.run", side_effect=AssertionError("the merge started a program")), \
                mock.patch("builtins.open", side_effect=AssertionError("the merge opened a file")):
            with self.assertRaises(review_fan_out.Refused) as caught:
                review_fan_out.merge(caller, self.folder, self.ORDER, self.results())
        self.assertEqual(caught.exception.causes, [f"saw 2 tables of 3 units in {os.path.basename(self.folder)}"])


class Rerun(Fixture):
    def test_named_units_are_run_again_in_a_new_setup_session_and_merged_with_the_kept_results(self):
        # SOL-HW-REVIEW-FAN-OUT-DRIVER.C8: The command keeps each unit's result in its output folder. Given the names of units to run again, it runs only those, replaces their results, and merges again; it refuses a name that is not a unit of the review, and the record shows which units were run again and when, and that a new setup session was started for them. A unit that failed, or that needs a view the round's starter has since rendered, is therefore run without repeating the others. Out of scope: deciding which units to run again.
        self.scenario({})
        status, text, _ = self.run_command(as_json=True)
        self.assertEqual(status, 0, text)
        first = json.loads(text)
        before = {unit: self.kept(unit) for unit in Fixture.UNITS}
        for name in os.listdir(self.log):
            os.remove(os.path.join(self.log, name))
        tables = {"bravo": {"Verdicts": verdicts(("B-1", "fail", "F1")), "Findings": [finding(1, "B-1", "now found")]}}
        self.scenario({"tables": tables})
        status, text, _ = self.run_command("--rerun", "bravo", as_json=True)
        self.assertEqual(status, 0, text)
        report = json.loads(text)
        calls = self.calls()
        self.assertEqual([call["unit"] for call in calls], [None, "bravo"], "a new setup session and only the named unit")
        self.assertNotEqual(calls[0]["session"], first["setup_sessions"][0]["id"])
        self.assertEqual(calls[1]["resume"], calls[0]["session"])
        self.assertEqual(self.kept("alpha"), before["alpha"], "the others' results stay as they were")
        self.assertEqual(self.kept("charlie"), before["charlie"])
        self.assertNotEqual(self.kept("bravo")["tables"], before["bravo"]["tables"])
        self.assertEqual([row["What"] for row in report["tables"]["Findings"]["rows"]], ["now found"])
        self.assertEqual(len(report["reruns"]), 1)
        self.assertEqual(report["reruns"][0]["units"], ["bravo"])
        self.assertTrue(report["reruns"][0]["new_setup_session"])
        self.assertRegex(report["reruns"][0]["at"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")
        self.assertEqual([setup["kind"] for setup in report["setup_sessions"]], ["initial", "rerun"])
        self.assertEqual({unit["unit"]: unit["run_again"] for unit in report["units"]},
                         {"alpha": False, "bravo": True, "charlie": False})
        status, text, _ = self.run_command("--rerun", "bravo")
        self.assertRegex(text, r"RERUN \| bravo \| \S+ \| new setup session \S+")
        self.assertIn("| run again", text)

    def test_a_unit_that_failed_is_run_again_alone_and_the_record_is_then_written(self):
        # SOL-HW-REVIEW-FAN-OUT-DRIVER.C8: The command keeps each unit's result in its output folder. Given the names of units to run again, it runs only those, replaces their results, and merges again; it refuses a name that is not a unit of the review, and the record shows which units were run again and when, and that a new setup session was started for them. A unit that failed, or that needs a view the round's starter has since rendered, is therefore run without repeating the others. Out of scope: deciding which units to run again.
        self.scenario({"units": {"charlie": [{"exit": 1}]}})
        status, text, _ = self.run_command()
        self.assertEqual(status, 1, text)
        kept = {unit: self.kept(unit) for unit in ("alpha", "bravo")}
        for name in os.listdir(self.log):
            os.remove(os.path.join(self.log, name))
        self.scenario({})
        status, text, _ = self.run_command("--rerun", "charlie", as_json=True)
        self.assertEqual(status, 0, text)
        self.assertEqual([call["unit"] for call in self.calls()], [None, "charlie"])
        self.assertEqual({unit: self.kept(unit) for unit in ("alpha", "bravo")}, kept)
        report = json.loads(text)
        self.assertEqual([unit["unit"] for unit in report["units"]], ["alpha", "bravo", "charlie"])
        self.assertEqual(len(report["setup_sessions"]), 2)

    def test_a_rerun_that_fails_again_keeps_the_earlier_results_and_the_earlier_record(self):
        # SOL-HW-REVIEW-FAN-OUT-DRIVER.C8: The command keeps each unit's result in its output folder. Given the names of units to run again, it runs only those, replaces their results, and merges again; it refuses a name that is not a unit of the review, and the record shows which units were run again and when, and that a new setup session was started for them. A unit that failed, or that needs a view the round's starter has since rendered, is therefore run without repeating the others. Out of scope: deciding which units to run again.
        self.run_command()
        record = os.path.join(self.out, "record.json")
        with open(record, encoding="utf-8") as handle:
            before = handle.read()
        old = self.kept("alpha")
        self.scenario({"units": {"alpha": [{"exit": 1}]}})
        status, text, _ = self.run_command("--rerun", "alpha")
        self.assertEqual(status, 1, text)
        self.assertEqual(self.kept("alpha"), old)
        with open(record, encoding="utf-8") as handle:
            self.assertEqual(handle.read(), before)

    def test_a_rerun_refuses_a_name_that_is_no_unit_and_an_output_folder_with_nothing_to_merge_with(self):
        # SOL-HW-REVIEW-FAN-OUT-DRIVER.C8: The command keeps each unit's result in its output folder. Given the names of units to run again, it runs only those, replaces their results, and merges again; it refuses a name that is not a unit of the review, and the record shows which units were run again and when, and that a new setup session was started for them. A unit that failed, or that needs a view the round's starter has since rendered, is therefore run without repeating the others. Out of scope: deciding which units to run again.
        status, text, _ = self.run_command("--rerun", "alpha")
        self.assertEqual(status, 1)
        self.assertIn("holds no earlier result to run alpha again against; run without --rerun into a new folder first", text)
        self.run_command()
        for name in os.listdir(self.log):
            os.remove(os.path.join(self.log, name))
        status, text, _ = self.run_command("--rerun", "delta", "--rerun", "echo")
        self.assertEqual(status, 1)
        self.assertIn("REFUSED | delta, echo is not a unit of the review; the units are alpha, bravo, charlie", text)
        os.remove(os.path.join(self.out, "units", "bravo.json"))
        status, text, _ = self.run_command("--rerun", "alpha")
        self.assertEqual(status, 1)
        self.assertIn("holds no result for bravo; name each of them with --rerun too", text)
        self.assertEqual(self.calls(), [], "nothing was started")


class Documentation(unittest.TestCase):
    def read(self, *path):
        with open(os.path.join(REPO, *path), encoding="utf-8") as handle:
            return handle.read()

    @staticmethod
    def flat(text):
        return " ".join(text.split())

    def test_the_task_and_the_hardware_notes_describe_the_command(self):
        # SOL-HW-REVIEW-FAN-OUT-DRIVER.C7: The task runner's description of the command and the hardware notes' section on it say that it runs a judged review as a setup session and forked reviewers, that it is on demand and in neither the build round nor the nightly, that it needs the agent command line on the path and logged in, that the command line's name is read from one environment variable, and what the report records, and the task runner's description of the board tooling's tests and the hardware notes' list of tested tools name the command's tests. Checked by reading each place against these clauses. Out of scope: the callers' own descriptions.
        taskfile = self.read("Taskfile.yml")
        task = taskfile[taskfile.index("  hw:review-fan-out:"):]
        task = self.flat(task.splitlines()[1])
        notes = self.read("hardware", "README.md")
        section = self.flat(notes[notes.index("## The review fan-out command"):].split("\n## ")[0])
        clauses = ("review_fan_out.py", "setup session", "forked", "on demand", "neither the build round nor the nightly",
                   "on the search path and logged in", review_fan_out.AGENT_ENV, "cost", "tokens", "cache")
        for place, text in (("the task's description", task), ("the hardware notes' section", section)):
            for words in clauses:
                self.assertIn(words, text, f"{place} says {words!r}")
        for words in ("REFUSED", "CANNOT RUN", "--rerun", "--json", "outside the repository", "plugins"):
            self.assertIn(words, section)
        self.assertIn("task hw:review-fan-out", section)
        for text in (taskfile[taskfile.index("  hw:test:\n"):].splitlines()[1],
                     taskfile[taskfile.index("  hw:test:round:"):].splitlines()[1]):
            self.assertIn("the review fan-out command", text, "the board tooling tests' descriptions name the command's tests")
        listed = self.flat(notes[notes.index("- `task hw:test` runs"):].splitlines()[0])
        self.assertIn("review fan-out command", listed)
        self.assertIn("runs a judged review as a setup session and forked reviewers", self.flat(notes.splitlines()[5]),
                      "the tools folder's list names the command")
        self.assertIn("task hw:review-fan-out", notes[notes.index("## The commands"):notes.index("## The schematic sheets")])

    def test_the_command_s_own_description_states_what_it_needs(self):
        # SOL-HW-REVIEW-FAN-OUT-DRIVER.C7: The task runner's description of the command and the hardware notes' section on it say that it runs a judged review as a setup session and forked reviewers, that it is on demand and in neither the build round nor the nightly, that it needs the agent command line on the path and logged in, that the command line's name is read from one environment variable, and what the report records, and the task runner's description of the board tooling's tests and the hardware notes' list of tested tools name the command's tests. Checked by reading each place against these clauses. Out of scope: the callers' own descriptions.
        doc = self.flat(review_fan_out.__doc__)
        for words in (review_fan_out.AGENT_ENV, "setup session", "forked", "REFUSED", "CANNOT RUN", "--json"):
            self.assertIn(words, doc)


if __name__ == "__main__":
    unittest.main()
