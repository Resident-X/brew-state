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
import unicodedata
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


def unit_prompt(unit, review_folder):
    return f"Judge UNIT={unit} against the checklist."


def units(folder):
    return sorted(name[:-4] for name in os.listdir(os.path.join(folder, "units")) if name.endswith(".txt"))


def CHECK(folder, units, tables):
    return {CHECK}
'''

FINDINGS = ('{"table": "Findings", "number": "Finding", "item": "Item", "checklist": ["A-1", "B-1", "C-1"], '
            '"citations": [("Verdicts", "Rests on")], "citation": re.compile(r"(?<![\\w-])F(?P<number>\\d+)\\b"), '
            '"key": lambda row: row["What"].split("@")[1] if "@" in row["What"] else None}')


#: A caller whose citations carry the round, as the layout and schematic reviews' `<round>.<n>` do; this is round 2.
ROUNDED = ('{"table": "Findings", "number": "Finding", "item": "Item", "checklist": ["A-1", "B-1", "C-1"], '
           '"citations": [("Verdicts", "Rests on")], '
           '"citation": re.compile(r"(?<![\\w.])(?P<round>\\d+)\\.(?P<number>\\d+)\\b"), '
           '"round": lambda folder: "2", "earlier": lambda folder: {("1", 1), ("1", 2), ("1", 3)}, '
           '"key": lambda row: None}')


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
        # SOL-HW-REVIEW-FAN-OUT-DRIVER.C2: Each session's start report is read and a run whose report shows other tools than were granted, another model, any MCP server, an instruction source the command line was asked to exclude or another working directory fails naming the session. The setup session is started with the read tools only and a prompt that asks for no judgement and no image and for one fixed token as the whole answer and that either tells it which documents and records to read or, when the caller names them as files, holds their text itself, sent on standard input so that the session has no tool use to narrate between; any text the setup session writes, in its answer or between its tool uses, other than that token after trimming, and any content block of its history that is neither text, a tool use nor a thinking block whose text is empty, fails the run, so no forked reviewer inherits a verdict; a thinking block that carries text, and a redacted one, fail it; a setup session that fails only for text written between its tool uses is started again, up to twice, before the run fails, and every attempt's session is reported with its cost, and a read of a file whose type is not text in the setup session's tool uses fails the run naming the file, as does a file the caller names whose type is not text, before any session is started. Out of scope: the content of a caller's prompt for its units.
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

    def rule_of(self, call):
        args = call["args"]
        return args[args.index("--append-system-prompt") + 1] if "--append-system-prompt" in args else None

    def test_only_the_setup_session_is_started_with_the_appended_rule(self):
        # SOL-HW-REVIEW-FAN-OUT-DRIVER.C2: Each session's start report is read and a run whose report shows other tools than were granted, another model, any MCP server, an instruction source the command line was asked to exclude or another working directory fails naming the session. The setup session is started with the read tools only and a prompt that asks for no judgement and no image and for one fixed token as the whole answer and that either tells it which documents and records to read or, when the caller names them as files, holds their text itself, sent on standard input so that the session has no tool use to narrate between; any text the setup session writes, in its answer or between its tool uses, other than that token after trimming, and any content block of its history that is neither text, a tool use nor a thinking block whose text is empty, fails the run, so no forked reviewer inherits a verdict; a thinking block that carries text, and a redacted one, fail it; a setup session that fails only for text written between its tool uses is started again, up to twice, before the run fails, and every attempt's session is reported with its cost, and a read of a file whose type is not text in the setup session's tool uses fails the run naming the file, as does a file the caller names whose type is not text, before any session is started. Out of scope: the content of a caller's prompt for its units.
        status, text, _ = self.run_command()
        self.assertEqual(status, 0, text)
        calls = self.calls()
        setups = [call for call in calls if call["unit"] is None]
        self.assertEqual(len(setups), 1)
        self.assertEqual(self.rule_of(setups[0]), review_fan_out.SETUP_RULE)
        self.assertEqual(len(self.forks()), 3)
        for call in calls:
            if call is not setups[0]:
                self.assertNotIn("--append-system-prompt", call["args"], "a forked reviewer carries no rule")

    def test_a_named_unit_rerun_starts_its_reviewer_without_the_rule_and_its_new_setup_session_with_it(self):
        # SOL-HW-REVIEW-FAN-OUT-DRIVER.C2: Each session's start report is read and a run whose report shows other tools than were granted, another model, any MCP server, an instruction source the command line was asked to exclude or another working directory fails naming the session. The setup session is started with the read tools only and a prompt that asks for no judgement and no image and for one fixed token as the whole answer and that either tells it which documents and records to read or, when the caller names them as files, holds their text itself, sent on standard input so that the session has no tool use to narrate between; any text the setup session writes, in its answer or between its tool uses, other than that token after trimming, and any content block of its history that is neither text, a tool use nor a thinking block whose text is empty, fails the run, so no forked reviewer inherits a verdict; a thinking block that carries text, and a redacted one, fail it; a setup session that fails only for text written between its tool uses is started again, up to twice, before the run fails, and every attempt's session is reported with its cost, and a read of a file whose type is not text in the setup session's tool uses fails the run naming the file, as does a file the caller names whose type is not text, before any session is started. Out of scope: the content of a caller's prompt for its units.
        status, text, _ = self.run_command()
        self.assertEqual(status, 0, text)
        for name in os.listdir(self.log):
            os.remove(os.path.join(self.log, name))
        status, text, _ = self.run_command("--rerun", "bravo")
        self.assertEqual(status, 0, text)
        calls = self.calls()
        self.assertEqual([call["unit"] for call in calls], [None, "bravo"])
        self.assertEqual(self.rule_of(calls[0]), review_fan_out.SETUP_RULE)
        self.assertNotIn("--append-system-prompt", calls[1]["args"])

    def test_the_single_units_second_turn_carries_no_rule(self):
        # SOL-HW-REVIEW-FAN-OUT-DRIVER.C2: Each session's start report is read and a run whose report shows other tools than were granted, another model, any MCP server, an instruction source the command line was asked to exclude or another working directory fails naming the session. The setup session is started with the read tools only and a prompt that asks for no judgement and no image and for one fixed token as the whole answer and that either tells it which documents and records to read or, when the caller names them as files, holds their text itself, sent on standard input so that the session has no tool use to narrate between; any text the setup session writes, in its answer or between its tool uses, other than that token after trimming, and any content block of its history that is neither text, a tool use nor a thinking block whose text is empty, fails the run, so no forked reviewer inherits a verdict; a thinking block that carries text, and a redacted one, fail it; a setup session that fails only for text written between its tool uses is started again, up to twice, before the run fails, and every attempt's session is reported with its cost, and a read of a file whose type is not text in the setup session's tool uses fails the run naming the file, as does a file the caller names whose type is not text, before any session is started. Out of scope: the content of a caller's prompt for its units.
        for unit in ("bravo", "charlie"):
            os.remove(os.path.join(self.review, "units", f"{unit}.txt"))
        status, text, _ = self.run_command()
        self.assertEqual(status, 0, text)
        setup, turn = self.calls()
        self.assertEqual(self.rule_of(setup), review_fan_out.SETUP_RULE)
        self.assertEqual(turn["resume"], setup["session"])
        self.assertNotIn("--append-system-prompt", turn["args"])

    def test_a_restarted_setup_session_carries_the_rule_on_every_attempt(self):
        # SOL-HW-REVIEW-FAN-OUT-DRIVER.C2: Each session's start report is read and a run whose report shows other tools than were granted, another model, any MCP server, an instruction source the command line was asked to exclude or another working directory fails naming the session. The setup session is started with the read tools only and a prompt that asks for no judgement and no image and for one fixed token as the whole answer and that either tells it which documents and records to read or, when the caller names them as files, holds their text itself, sent on standard input so that the session has no tool use to narrate between; any text the setup session writes, in its answer or between its tool uses, other than that token after trimming, and any content block of its history that is neither text, a tool use nor a thinking block whose text is empty, fails the run, so no forked reviewer inherits a verdict; a thinking block that carries text, and a redacted one, fail it; a setup session that fails only for text written between its tool uses is started again, up to twice, before the run fails, and every attempt's session is reported with its cost, and a read of a file whose type is not text in the setup session's tool uses fails the run naming the file, as does a file the caller names whose type is not text, before any session is started. Out of scope: the content of a caller's prompt for its units.
        self.scenario({"setup": {"narration": [{"type": "text", "text": "Still reading the method (about line 1135)."}],
                                 "same_event": False}})
        status, text, _ = self.run_command()
        self.assertEqual(status, 1, text)
        calls = self.calls()
        self.assertEqual(len(calls), review_fan_out.SETUP_ATTEMPTS)
        self.assertEqual([self.rule_of(call) for call in calls], [review_fan_out.SETUP_RULE] * review_fan_out.SETUP_ATTEMPTS)

    def test_the_rule_is_ascii_one_paragraph_and_names_the_token(self):
        # SOL-HW-REVIEW-FAN-OUT-DRIVER.C2: Each session's start report is read and a run whose report shows other tools than were granted, another model, any MCP server, an instruction source the command line was asked to exclude or another working directory fails naming the session. The setup session is started with the read tools only and a prompt that asks for no judgement and no image and for one fixed token as the whole answer and that either tells it which documents and records to read or, when the caller names them as files, holds their text itself, sent on standard input so that the session has no tool use to narrate between; any text the setup session writes, in its answer or between its tool uses, other than that token after trimming, and any content block of its history that is neither text, a tool use nor a thinking block whose text is empty, fails the run, so no forked reviewer inherits a verdict; a thinking block that carries text, and a redacted one, fail it; a setup session that fails only for text written between its tool uses is started again, up to twice, before the run fails, and every attempt's session is reported with its cost, and a read of a file whose type is not text in the setup session's tool uses fails the run naming the file, as does a file the caller names whose type is not text, before any session is started. Out of scope: the content of a caller's prompt for its units.
        rule = review_fan_out.SETUP_RULE
        self.assertTrue(rule.isascii())
        self.assertNotIn("\n", rule)
        self.assertIn(review_fan_out.ACK, rule)
        self.assertIn("Write no text of your own", rule)

    def test_a_start_report_that_shows_more_than_was_granted_fails_naming_the_session(self):
        # SOL-HW-REVIEW-FAN-OUT-DRIVER.C2: Each session's start report is read and a run whose report shows other tools than were granted, another model, any MCP server, an instruction source the command line was asked to exclude or another working directory fails naming the session. The setup session is started with the read tools only and a prompt that asks for no judgement and no image and for one fixed token as the whole answer and that either tells it which documents and records to read or, when the caller names them as files, holds their text itself, sent on standard input so that the session has no tool use to narrate between; any text the setup session writes, in its answer or between its tool uses, other than that token after trimming, and any content block of its history that is neither text, a tool use nor a thinking block whose text is empty, fails the run, so no forked reviewer inherits a verdict; a thinking block that carries text, and a redacted one, fail it; a setup session that fails only for text written between its tool uses is started again, up to twice, before the run fails, and every attempt's session is reported with its cost, and a read of a file whose type is not text in the setup session's tool uses fails the run naming the file, as does a file the caller names whose type is not text, before any session is started. Out of scope: the content of a caller's prompt for its units.
        cases = {"tools": ({"setup_tools": ["Read", "Bash"]}, "tools"),
                 "mcp": ({"mcp_servers": [{"name": "konnect"}]}, "MCP servers"),
                 "skills": ({"skills": ["repo-board-design"]}, "skills"),
                 "plugins": ({"plugins": [{"name": "outside", "path": "/home/someone/plugin"}]}, "plugins"),
                 "cwd": ({"cwd": "/somewhere/else"}, "started in '/somewhere/else'")}
        for name, (scenario, word) in cases.items():
            with self.subTest(case=name):
                shutil.rmtree(self.out, ignore_errors=True)
                for call in os.listdir(self.log):
                    os.remove(os.path.join(self.log, call))
                self.refused(scenario, "the setup session", word)
                self.assertEqual(len(self.calls()), 1, "no unit was started after a setup session that failed its check")

    def test_a_fork_whose_start_report_shows_another_model_or_tools_fails_its_unit(self):
        # SOL-HW-REVIEW-FAN-OUT-DRIVER.C2: Each session's start report is read and a run whose report shows other tools than were granted, another model, any MCP server, an instruction source the command line was asked to exclude or another working directory fails naming the session. The setup session is started with the read tools only and a prompt that asks for no judgement and no image and for one fixed token as the whole answer and that either tells it which documents and records to read or, when the caller names them as files, holds their text itself, sent on standard input so that the session has no tool use to narrate between; any text the setup session writes, in its answer or between its tool uses, other than that token after trimming, and any content block of its history that is neither text, a tool use nor a thinking block whose text is empty, fails the run, so no forked reviewer inherits a verdict; a thinking block that carries text, and a redacted one, fail it; a setup session that fails only for text written between its tool uses is started again, up to twice, before the run fails, and every attempt's session is reported with its cost, and a read of a file whose type is not text in the setup session's tool uses fails the run naming the file, as does a file the caller names whose type is not text, before any session is started. Out of scope: the content of a caller's prompt for its units.
        for scenario, word in (({"fork_model": "model-b"}, "model model-b"), ({"fork_tools": ["Read", "Write"]}, "tools")):
            with self.subTest(word=word):
                shutil.rmtree(self.out, ignore_errors=True)
                self.scenario(scenario)
                status, text, _ = self.run_command()
                self.assertEqual(status, 1, text)
                self.assertRegex(text, r"FAILED \| unit alpha failed: the reviewer of unit alpha started with .*" + word)
                self.assertFalse(os.path.exists(os.path.join(self.out, "record.json")))

    def test_a_setup_session_that_opened_an_image_or_a_binary_file_fails_naming_the_file(self):
        # SOL-HW-REVIEW-FAN-OUT-DRIVER.C2: Each session's start report is read and a run whose report shows other tools than were granted, another model, any MCP server, an instruction source the command line was asked to exclude or another working directory fails naming the session. The setup session is started with the read tools only and a prompt that asks for no judgement and no image and for one fixed token as the whole answer and that either tells it which documents and records to read or, when the caller names them as files, holds their text itself, sent on standard input so that the session has no tool use to narrate between; any text the setup session writes, in its answer or between its tool uses, other than that token after trimming, and any content block of its history that is neither text, a tool use nor a thinking block whose text is empty, fails the run, so no forked reviewer inherits a verdict; a thinking block that carries text, and a redacted one, fail it; a setup session that fails only for text written between its tool uses is started again, up to twice, before the run fails, and every attempt's session is reported with its cost, and a read of a file whose type is not text in the setup session's tool uses fails the run naming the file, as does a file the caller names whose type is not text, before any session is started. Out of scope: the content of a caller's prompt for its units.
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
        # SOL-HW-REVIEW-FAN-OUT-DRIVER.C2: Each session's start report is read and a run whose report shows other tools than were granted, another model, any MCP server, an instruction source the command line was asked to exclude or another working directory fails naming the session. The setup session is started with the read tools only and a prompt that asks for no judgement and no image and for one fixed token as the whole answer and that either tells it which documents and records to read or, when the caller names them as files, holds their text itself, sent on standard input so that the session has no tool use to narrate between; any text the setup session writes, in its answer or between its tool uses, other than that token after trimming, and any content block of its history that is neither text, a tool use nor a thinking block whose text is empty, fails the run, so no forked reviewer inherits a verdict; a thinking block that carries text, and a redacted one, fail it; a setup session that fails only for text written between its tool uses is started again, up to twice, before the run fails, and every attempt's session is reported with its cost, and a read of a file whose type is not text in the setup session's tool uses fails the run naming the file, as does a file the caller names whose type is not text, before any session is started. Out of scope: the content of a caller's prompt for its units.
        self.refused({"setup": {"answer": "I read it. Board 1 looks fine."}}, "the setup session answered", "Board 1 looks fine")
        self.assertEqual(self.forks(), [])
        shutil.rmtree(self.out, ignore_errors=True)
        self.scenario({"setup": {"answer": "  SETUP-READ-COMPLETE \n"}})
        status, text, _ = self.run_command()
        self.assertEqual(status, 0, "trimmed, the token is the whole answer: " + text)

    def test_a_setup_session_that_wrote_text_other_than_the_token_in_any_message_fails_and_starts_no_fork(self):
        # SOL-HW-REVIEW-FAN-OUT-DRIVER.C2: Each session's start report is read and a run whose report shows other tools than were granted, another model, any MCP server, an instruction source the command line was asked to exclude or another working directory fails naming the session. The setup session is started with the read tools only and a prompt that asks for no judgement and no image and for one fixed token as the whole answer and that either tells it which documents and records to read or, when the caller names them as files, holds their text itself, sent on standard input so that the session has no tool use to narrate between; any text the setup session writes, in its answer or between its tool uses, other than that token after trimming, and any content block of its history that is neither text, a tool use nor a thinking block whose text is empty, fails the run, so no forked reviewer inherits a verdict; a thinking block that carries text, and a redacted one, fail it; a setup session that fails only for text written between its tool uses is started again, up to twice, before the run fails, and every attempt's session is reported with its cost, and a read of a file whose type is not text in the setup session's tool uses fails the run naming the file, as does a file the caller names whose type is not text, before any session is started. Out of scope: the content of a caller's prompt for its units.
        text = lambda words: {"type": "text", "text": words}
        cases = {"a verdict in a mid-turn message": ([text("Board 1 fails the clearance item.")], False, "Board 1 fails"),
                 "harmless narration": ([text("I am about to read design.txt.")], False, "about to read"),
                 "a verdict in the message that holds the first read": ([text("Looks wrong to me.")], True, "Looks wrong"),
                 "a thinking block that carries text": ([{"type": "thinking", "thinking": "the board is bad"}], False,
                                                         "thinking block that carries text"),
                 "a redacted thinking block": ([{"type": "redacted_thinking", "data": "x"}], True, "redacted_thinking block"),
                 "a block of a type nobody knows": ([{"type": "image", "source": "x"}], False, "image block")}
        for name, (narration, same_event, word) in cases.items():
            with self.subTest(case=name):
                shutil.rmtree(self.out, ignore_errors=True)
                for call in os.listdir(self.log):
                    os.remove(os.path.join(self.log, call))
                self.refused({"setup": {"narration": narration, "same_event": same_event}}, "the setup session", word)
                self.assertEqual(self.forks(), [])
                text_only = all(block["type"] == "text" for block in narration)
                self.assertEqual(len(self.calls()), 3 if text_only else 1, "no unit was started; only text is started again")

    def test_empty_and_token_text_blocks_between_the_setup_session_s_reads_pass(self):
        # SOL-HW-REVIEW-FAN-OUT-DRIVER.C2: Each session's start report is read and a run whose report shows other tools than were granted, another model, any MCP server, an instruction source the command line was asked to exclude or another working directory fails naming the session. The setup session is started with the read tools only and a prompt that asks for no judgement and no image and for one fixed token as the whole answer and that either tells it which documents and records to read or, when the caller names them as files, holds their text itself, sent on standard input so that the session has no tool use to narrate between; any text the setup session writes, in its answer or between its tool uses, other than that token after trimming, and any content block of its history that is neither text, a tool use nor a thinking block whose text is empty, fails the run, so no forked reviewer inherits a verdict; a thinking block that carries text, and a redacted one, fail it; a setup session that fails only for text written between its tool uses is started again, up to twice, before the run fails, and every attempt's session is reported with its cost, and a read of a file whose type is not text in the setup session's tool uses fails the run naming the file, as does a file the caller names whose type is not text, before any session is started. Out of scope: the content of a caller's prompt for its units.
        for name, narration in {"an empty text block": [{"type": "text", "text": "  "}],
                                "the token before the reads": [{"type": "text", "text": "SETUP-READ-COMPLETE"}]}.items():
            with self.subTest(case=name):
                shutil.rmtree(self.out, ignore_errors=True)
                self.scenario({"setup": {"narration": narration, "reads": ["method.md", "units/alpha.txt"]}})
                status, text, _ = self.run_command()
                self.assertEqual(status, 0, text)

    def test_an_empty_thinking_block_in_the_setup_session_s_history_passes(self):
        # SOL-HW-REVIEW-FAN-OUT-DRIVER.C2: Each session's start report is read and a run whose report shows other tools than were granted, another model, any MCP server, an instruction source the command line was asked to exclude or another working directory fails naming the session. The setup session is started with the read tools only and a prompt that asks for no judgement and no image and for one fixed token as the whole answer and that either tells it which documents and records to read or, when the caller names them as files, holds their text itself, sent on standard input so that the session has no tool use to narrate between; any text the setup session writes, in its answer or between its tool uses, other than that token after trimming, and any content block of its history that is neither text, a tool use nor a thinking block whose text is empty, fails the run, so no forked reviewer inherits a verdict; a thinking block that carries text, and a redacted one, fail it; a setup session that fails only for text written between its tool uses is started again, up to twice, before the run fails, and every attempt's session is reported with its cost, and a read of a file whose type is not text in the setup session's tool uses fails the run naming the file, as does a file the caller names whose type is not text, before any session is started. Out of scope: the content of a caller's prompt for its units.
        for name, text in {"empty": "", "blank": "  \n"}.items():
            with self.subTest(case=name):
                shutil.rmtree(self.out, ignore_errors=True)
                self.scenario({"setup": {"narration": [{"type": "thinking", "thinking": text, "signature": "sig"}],
                                         "reads": ["method.md", "units/alpha.txt"]}})
                status, report, _ = self.run_command(as_json=True)
                self.assertEqual(status, 0, report)
                self.assertEqual(len(json.loads(report)["setup_sessions"]), 1)

    def test_a_thinking_block_with_no_text_field_fails_the_run(self):
        # SOL-HW-REVIEW-FAN-OUT-DRIVER.C2: Each session's start report is read and a run whose report shows other tools than were granted, another model, any MCP server, an instruction source the command line was asked to exclude or another working directory fails naming the session. The setup session is started with the read tools only and a prompt that asks for no judgement and no image and for one fixed token as the whole answer and that either tells it which documents and records to read or, when the caller names them as files, holds their text itself, sent on standard input so that the session has no tool use to narrate between; any text the setup session writes, in its answer or between its tool uses, other than that token after trimming, and any content block of its history that is neither text, a tool use nor a thinking block whose text is empty, fails the run, so no forked reviewer inherits a verdict; a thinking block that carries text, and a redacted one, fail it; a setup session that fails only for text written between its tool uses is started again, up to twice, before the run fails, and every attempt's session is reported with its cost, and a read of a file whose type is not text in the setup session's tool uses fails the run naming the file, as does a file the caller names whose type is not text, before any session is started. Out of scope: the content of a caller's prompt for its units.
        self.refused({"setup": {"narration": [{"type": "thinking", "signature": "sig"}]}}, "thinking block that carries text")
        self.assertEqual(len(self.calls()), 1)

    def test_a_setup_session_that_only_narrated_is_started_again_and_every_attempt_is_reported_with_its_cost(self):
        # SOL-HW-REVIEW-FAN-OUT-DRIVER.C2: Each session's start report is read and a run whose report shows other tools than were granted, another model, any MCP server, an instruction source the command line was asked to exclude or another working directory fails naming the session. The setup session is started with the read tools only and a prompt that asks for no judgement and no image and for one fixed token as the whole answer and that either tells it which documents and records to read or, when the caller names them as files, holds their text itself, sent on standard input so that the session has no tool use to narrate between; any text the setup session writes, in its answer or between its tool uses, other than that token after trimming, and any content block of its history that is neither text, a tool use nor a thinking block whose text is empty, fails the run, so no forked reviewer inherits a verdict; a thinking block that carries text, and a redacted one, fail it; a setup session that fails only for text written between its tool uses is started again, up to twice, before the run fails, and every attempt's session is reported with its cost, and a read of a file whose type is not text in the setup session's tool uses fails the run naming the file, as does a file the caller names whose type is not text, before any session is started. Out of scope: the content of a caller's prompt for its units.
        narrated = {"narration": [{"type": "text", "text": "I will read the method now."}], "cost": 0.07}
        self.scenario({"setup": {"attempts": [narrated, {"cost": 0.04}]}})
        status, text, _ = self.run_command(as_json=True)
        self.assertEqual(status, 0, text)
        setups = [call for call in self.calls() if call["unit"] is None and not call["forked"]]
        self.assertEqual(len(setups), 2, "a fresh session is started, not a resume")
        self.assertTrue(all(call["resume"] is None for call in setups))
        report = json.loads(text)
        sessions = report["setup_sessions"]
        self.assertEqual([entry["id"] for entry in sessions], [call["session"] for call in setups])
        self.assertEqual([entry["cost_usd"] for entry in sessions], [0.07, 0.04])
        self.assertIn("attempt 1 of 2", sessions[0]["kind"])
        self.assertIn("attempt 2 of 2", sessions[1]["kind"])
        self.assertAlmostEqual(report["totals"]["cost_usd"], 0.07 + 0.04 + sum(unit["own"]["cost_usd"] for unit in report["units"]), 6)
        self.assertEqual({unit["setup_session"] for unit in report["units"]}, {sessions[1]["id"]})
        shutil.rmtree(self.out, ignore_errors=True)
        os.remove(os.path.join(self.log, "attempts-setup"))
        status, rendered, _ = self.run_command()
        self.assertEqual(status, 0, rendered)
        self.assertEqual(len([line for line in rendered.splitlines() if line.startswith("SETUP | ")]), 2)

    def test_a_setup_session_that_narrates_on_all_three_attempts_fails_after_exactly_three(self):
        # SOL-HW-REVIEW-FAN-OUT-DRIVER.C2: Each session's start report is read and a run whose report shows other tools than were granted, another model, any MCP server, an instruction source the command line was asked to exclude or another working directory fails naming the session. The setup session is started with the read tools only and a prompt that asks for no judgement and no image and for one fixed token as the whole answer and that either tells it which documents and records to read or, when the caller names them as files, holds their text itself, sent on standard input so that the session has no tool use to narrate between; any text the setup session writes, in its answer or between its tool uses, other than that token after trimming, and any content block of its history that is neither text, a tool use nor a thinking block whose text is empty, fails the run, so no forked reviewer inherits a verdict; a thinking block that carries text, and a redacted one, fail it; a setup session that fails only for text written between its tool uses is started again, up to twice, before the run fails, and every attempt's session is reported with its cost, and a read of a file whose type is not text in the setup session's tool uses fails the run naming the file, as does a file the caller names whose type is not text, before any session is started. Out of scope: the content of a caller's prompt for its units.
        self.scenario({"setup": {"narration": [{"type": "text", "text": "Reading the method."}]}})
        status, text, _ = self.run_command()
        self.assertEqual(status, 1, text)
        self.assertEqual(len(self.calls()), 3)
        self.assertEqual(self.forks(), [])
        line = next(line for line in text.splitlines() if "started 3 times" in line)
        self.assertEqual(line.count("attempt "), 3, line)
        self.assertIn("$0.05", line)

    def test_a_setup_session_with_a_problem_other_than_narration_is_not_started_again(self):
        # SOL-HW-REVIEW-FAN-OUT-DRIVER.C2: Each session's start report is read and a run whose report shows other tools than were granted, another model, any MCP server, an instruction source the command line was asked to exclude or another working directory fails naming the session. The setup session is started with the read tools only and a prompt that asks for no judgement and no image and for one fixed token as the whole answer and that either tells it which documents and records to read or, when the caller names them as files, holds their text itself, sent on standard input so that the session has no tool use to narrate between; any text the setup session writes, in its answer or between its tool uses, other than that token after trimming, and any content block of its history that is neither text, a tool use nor a thinking block whose text is empty, fails the run, so no forked reviewer inherits a verdict; a thinking block that carries text, and a redacted one, fail it; a setup session that fails only for text written between its tool uses is started again, up to twice, before the run fails, and every attempt's session is reported with its cost, and a read of a file whose type is not text in the setup session's tool uses fails the run naming the file, as does a file the caller names whose type is not text, before any session is started. Out of scope: the content of a caller's prompt for its units.
        narrated = [{"type": "text", "text": "I will read."}]
        cases = {"an image read": {"reads": ["method.md", "views/top.png"]},
                 "a wrong final answer": {"answer": "Looks fine."},
                 "a tool outside the grant": {"uses": ["Bash"]},
                 "nothing read": {"reads": []},
                 "narration with a thinking block that carries text": {
                     "narration": narrated + [{"type": "thinking", "thinking": "hmm"}]}}
        for name, outcome in cases.items():
            with self.subTest(case=name):
                shutil.rmtree(self.out, ignore_errors=True)
                for call in os.listdir(self.log):
                    os.remove(os.path.join(self.log, call))
                self.refused({"setup": {"narration": narrated, **outcome}}, "the setup session")
                self.assertEqual(len(self.calls()), 1, "no restart")

    def test_a_setup_session_that_read_nothing_or_used_a_tool_outside_its_grant_fails(self):
        # SOL-HW-REVIEW-FAN-OUT-DRIVER.C2: Each session's start report is read and a run whose report shows other tools than were granted, another model, any MCP server, an instruction source the command line was asked to exclude or another working directory fails naming the session. The setup session is started with the read tools only and a prompt that asks for no judgement and no image and for one fixed token as the whole answer and that either tells it which documents and records to read or, when the caller names them as files, holds their text itself, sent on standard input so that the session has no tool use to narrate between; any text the setup session writes, in its answer or between its tool uses, other than that token after trimming, and any content block of its history that is neither text, a tool use nor a thinking block whose text is empty, fails the run, so no forked reviewer inherits a verdict; a thinking block that carries text, and a redacted one, fail it; a setup session that fails only for text written between its tool uses is started again, up to twice, before the run fails, and every attempt's session is reported with its cost, and a read of a file whose type is not text in the setup session's tool uses fails the run naming the file, as does a file the caller names whose type is not text, before any session is started. Out of scope: the content of a caller's prompt for its units.
        shutil.rmtree(self.out, ignore_errors=True)
        self.refused({"setup": {"reads": []}}, "the setup session read nothing")
        self.assertEqual(self.forks(), [])
        shutil.rmtree(self.out, ignore_errors=True)
        self.refused({"setup": {"uses": ["Bash"]}}, "the setup session used Bash, a tool it was not granted")
        shutil.rmtree(self.out, ignore_errors=True)
        self.scenario({"setup": {"uses": ["Grep", "Glob"]}})
        status, text, _ = self.run_command()
        self.assertEqual(status, 0, "Glob and Grep are in the grant: " + text)

    def test_a_reported_command_or_a_model_alias_the_report_does_not_echo_is_refused(self):
        # SOL-HW-REVIEW-FAN-OUT-DRIVER.C2: Each session's start report is read and a run whose report shows other tools than were granted, another model, any MCP server, an instruction source the command line was asked to exclude or another working directory fails naming the session. The setup session is started with the read tools only and a prompt that asks for no judgement and no image and for one fixed token as the whole answer and that either tells it which documents and records to read or, when the caller names them as files, holds their text itself, sent on standard input so that the session has no tool use to narrate between; any text the setup session writes, in its answer or between its tool uses, other than that token after trimming, and any content block of its history that is neither text, a tool use nor a thinking block whose text is empty, fails the run, so no forked reviewer inherits a verdict; a thinking block that carries text, and a redacted one, fail it; a setup session that fails only for text written between its tool uses is started again, up to twice, before the run fails, and every attempt's session is reported with its cost, and a read of a file whose type is not text in the setup session's tool uses fails the run naming the file, as does a file the caller names whose type is not text, before any session is started. Out of scope: the content of a caller's prompt for its units.
        self.refused({"slash_commands": ["compact"]}, "the setup session", "started with commands ['compact']")
        shutil.rmtree(self.out, ignore_errors=True)
        self.scenario({"model": "claude-real-1"})
        status, text, _ = self.run_command("--model", "sonnet")
        self.assertEqual(status, 1, text)
        self.assertRegex(text, r"REFUSED \| the setup session started with model claude-real-1, not sonnet")

    def test_a_start_report_that_leaves_out_or_mistypes_a_field_the_command_relies_on_is_refused_naming_the_field(self):
        # SOL-HW-REVIEW-FAN-OUT-DRIVER.C2: Each session's start report is read and a run whose report shows other tools than were granted, another model, any MCP server, an instruction source the command line was asked to exclude or another working directory fails naming the session. The setup session is started with the read tools only and a prompt that asks for no judgement and no image and for one fixed token as the whole answer and that either tells it which documents and records to read or, when the caller names them as files, holds their text itself, sent on standard input so that the session has no tool use to narrate between; any text the setup session writes, in its answer or between its tool uses, other than that token after trimming, and any content block of its history that is neither text, a tool use nor a thinking block whose text is empty, fails the run, so no forked reviewer inherits a verdict; a thinking block that carries text, and a redacted one, fail it; a setup session that fails only for text written between its tool uses is started again, up to twice, before the run fails, and every attempt's session is reported with its cost, and a read of a file whose type is not text in the setup session's tool uses fails the run naming the file, as does a file the caller names whose type is not text, before any session is started. Out of scope: the content of a caller's prompt for its units.
        cases = {"model": 5, "cwd": 7, "session_id": ["x"], "tools": "Read", "mcp_servers": "none", "skills": {},
                  "slash_commands": 0, "plugins": "builtin"}
        for extra in ((), ("--model", "model-a")):
            for key, wrong in cases.items():
                for how, scenario in (("omits", {"setup": {"start_omit": [key]}}), ("mistypes", {"setup": {"start_set": {key: wrong}}})):
                    with self.subTest(key=key, how=how, extra=extra):
                        shutil.rmtree(self.out, ignore_errors=True)
                        for call in os.listdir(self.log):
                            os.remove(os.path.join(self.log, call))
                        self.scenario(scenario)
                        status, text, _ = self.run_command(*extra)
                        self.assertEqual(status, 1, text)
                        word = "has no" if how == "omits" else "gives"
                        self.assertRegex(text, rf"REFUSED \| the setup session's start report {word} (a )?`{key}`")
                        self.assertNotIn("None", text)
                        self.assertEqual(self.forks(), [], "no fork is started on a start report that cannot be relied on")
        shutil.rmtree(self.out, ignore_errors=True)
        self.scenario({"setup": {"start_set": {"tools": ["Read", 3, "Glob", "Grep"]}}})
        status, text, _ = self.run_command()
        self.assertEqual(status, 1, text)
        self.assertIn("gives `tools` as ['Read', 3, 'Glob', 'Grep'], which is not a list of names", text)

    def test_a_fork_whose_start_report_leaves_out_or_mistypes_a_field_fails_its_unit_without_a_retry(self):
        # SOL-HW-REVIEW-FAN-OUT-DRIVER.C2: Each session's start report is read and a run whose report shows other tools than were granted, another model, any MCP server, an instruction source the command line was asked to exclude or another working directory fails naming the session. The setup session is started with the read tools only and a prompt that asks for no judgement and no image and for one fixed token as the whole answer and that either tells it which documents and records to read or, when the caller names them as files, holds their text itself, sent on standard input so that the session has no tool use to narrate between; any text the setup session writes, in its answer or between its tool uses, other than that token after trimming, and any content block of its history that is neither text, a tool use nor a thinking block whose text is empty, fails the run, so no forked reviewer inherits a verdict; a thinking block that carries text, and a redacted one, fail it; a setup session that fails only for text written between its tool uses is started again, up to twice, before the run fails, and every attempt's session is reported with its cost, and a read of a file whose type is not text in the setup session's tool uses fails the run naming the file, as does a file the caller names whose type is not text, before any session is started. Out of scope: the content of a caller's prompt for its units.
        for key, wrong in (("model", 5), ("cwd", None), ("session_id", 3), ("tools", "Read"), ("plugins", {})):
            for how, outcome in (("omits", {"start_omit": [key]}), ("mistypes", {"start_set": {key: wrong}})):
                if how == "mistypes" and wrong is None:
                    continue
                with self.subTest(key=key, how=how):
                    shutil.rmtree(self.out, ignore_errors=True)
                    for call in os.listdir(self.log):
                        os.remove(os.path.join(self.log, call))
                    self.scenario({"units": {"alpha": [outcome]}})
                    status, text, _ = self.run_command()
                    self.assertEqual(status, 1, text)
                    self.assertRegex(text, rf"FAILED \| unit alpha failed: the reviewer of unit alpha's start report (has no|gives) (a )?`{key}`")
                    self.assertEqual(len([call for call in self.forks() if call["unit"] == "alpha"]), 1)
                    self.assertFalse(os.path.exists(os.path.join(self.out, "units", "alpha.json")))
                    self.assertTrue(os.path.isfile(os.path.join(self.out, "units", "bravo.json")))

    def test_the_forks_are_started_with_the_model_the_setup_session_reported_when_none_is_asked_for(self):
        # SOL-HW-REVIEW-FAN-OUT-DRIVER.C2: Each session's start report is read and a run whose report shows other tools than were granted, another model, any MCP server, an instruction source the command line was asked to exclude or another working directory fails naming the session. The setup session is started with the read tools only and a prompt that asks for no judgement and no image and for one fixed token as the whole answer and that either tells it which documents and records to read or, when the caller names them as files, holds their text itself, sent on standard input so that the session has no tool use to narrate between; any text the setup session writes, in its answer or between its tool uses, other than that token after trimming, and any content block of its history that is neither text, a tool use nor a thinking block whose text is empty, fails the run, so no forked reviewer inherits a verdict; a thinking block that carries text, and a redacted one, fail it; a setup session that fails only for text written between its tool uses is started again, up to twice, before the run fails, and every attempt's session is reported with its cost, and a read of a file whose type is not text in the setup session's tool uses fails the run naming the file, as does a file the caller names whose type is not text, before any session is started. Out of scope: the content of a caller's prompt for its units.
        self.scenario({"model": "claude-real-1"})
        status, text, _ = self.run_command()
        self.assertEqual(status, 0, text)
        self.assertEqual({self.flag(fork, "--model") for fork in self.forks()}, {"claude-real-1"})
        self.assertNotIn("--model", self.calls()[0]["args"], "the setup session is asked for none")

    def test_a_read_that_cannot_be_shown_to_be_text_fails_the_run_unless_the_stream_shows_it_failed(self):
        # SOL-HW-REVIEW-FAN-OUT-DRIVER.C2: Each session's start report is read and a run whose report shows other tools than were granted, another model, any MCP server, an instruction source the command line was asked to exclude or another working directory fails naming the session. The setup session is started with the read tools only and a prompt that asks for no judgement and no image and for one fixed token as the whole answer and that either tells it which documents and records to read or, when the caller names them as files, holds their text itself, sent on standard input so that the session has no tool use to narrate between; any text the setup session writes, in its answer or between its tool uses, other than that token after trimming, and any content block of its history that is neither text, a tool use nor a thinking block whose text is empty, fails the run, so no forked reviewer inherits a verdict; a thinking block that carries text, and a redacted one, fail it; a setup session that fails only for text written between its tool uses is started again, up to twice, before the run fails, and every attempt's session is reported with its cost, and a read of a file whose type is not text in the setup session's tool uses fails the run naming the file, as does a file the caller names whose type is not text, before any session is started. Out of scope: the content of a caller's prompt for its units.
        method = os.path.join(self.review, "method.md")
        for name, setup in {"no file_path": {"read_inputs": [{"file_path": method}, {}]},
                            "a file_path that is not a string": {"read_inputs": [{"file_path": method}, {"file_path": 5}]},
                            "an empty file_path": {"read_inputs": [{"file_path": method}, {"file_path": ""}]},
                            "an input that is not a mapping": {"read_inputs": [{"file_path": method}, "units"]}}.items():
            with self.subTest(case=name):
                shutil.rmtree(self.out, ignore_errors=True)
                self.refused({"setup": setup}, "the setup session printed a", "Read tool use with no")
                self.assertEqual(self.forks(), [])
        for name, path in {"a file that is absent": "notes/absent", "a folder": "units", "an unknown suffix": "views/absent.dat"}.items():
            with self.subTest(case=name):
                shutil.rmtree(self.out, ignore_errors=True)
                self.refused({"setup": {"reads": [method, path]}}, path, "cannot be shown to be text")
        for path in ("notes/absent", "views/absent.png"):
            with self.subTest(failed=path):
                shutil.rmtree(self.out, ignore_errors=True)
                self.scenario({"setup": {"failed_reads": [path]}})
                status, text, _ = self.run_command()
                self.assertEqual(status, 0, "a read the stream shows failed opened nothing: " + text)

    def test_the_setup_session_is_started_with_read_tools_the_fixed_ask_and_no_loaded_instructions(self):
        # SOL-HW-REVIEW-FAN-OUT-DRIVER.C2: Each session's start report is read and a run whose report shows other tools than were granted, another model, any MCP server, an instruction source the command line was asked to exclude or another working directory fails naming the session. The setup session is started with the read tools only and a prompt that asks for no judgement and no image and for one fixed token as the whole answer and that either tells it which documents and records to read or, when the caller names them as files, holds their text itself, sent on standard input so that the session has no tool use to narrate between; any text the setup session writes, in its answer or between its tool uses, other than that token after trimming, and any content block of its history that is neither text, a tool use nor a thinking block whose text is empty, fails the run, so no forked reviewer inherits a verdict; a thinking block that carries text, and a redacted one, fail it; a setup session that fails only for text written between its tool uses is started again, up to twice, before the run fails, and every attempt's session is reported with its cost, and a read of a file whose type is not text in the setup session's tool uses fails the run naming the file, as does a file the caller names whose type is not text, before any session is started. Out of scope: the content of a caller's prompt for its units.
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
        self.assertIn("Open no image and judge nothing", setup["prompt"])
        self.assertIn("Write no text before, between or after your reads", setup["prompt"])
        self.assertIn("your only text is the single token SETUP-READ-COMPLETE after the last read", setup["prompt"])


class InlineSetup(Fixture):
    """A caller that names its setup documents: their text is the setup prompt, sent on standard input."""

    DOCUMENTS = ["method.md", "notes/extra.txt"]

    def setUp(self):
        super().setUp()
        self.write(os.path.join(self.review, "notes", "extra.txt"), "extra note\n")
        self.write(os.path.join(self.review, "documents.json"), json.dumps(self.DOCUMENTS))
        hook = ("\n\ndef SETUP_DOCUMENTS(folder):\n    import json\n"
                "    with open(os.path.join(folder, 'documents.json'), encoding='utf-8') as handle:\n"
                "        return json.load(handle)\n")
        self.write(os.path.join(self.callers, "review_caller_synth.py"), caller_text() + hook)
        self.scenario({"setup": {"reads": []}})

    def documents(self, listed):
        self.write(os.path.join(self.review, "documents.json"), json.dumps(listed))

    def setups(self):
        return [call for call in self.calls() if call["unit"] is None and not call["forked"]]

    def test_the_documents_text_is_sent_on_standard_input_and_no_prompt_argument_is_given(self):
        # SOL-HW-REVIEW-FAN-OUT-DRIVER.C2: Each session's start report is read and a run whose report shows other tools than were granted, another model, any MCP server, an instruction source the command line was asked to exclude or another working directory fails naming the session. The setup session is started with the read tools only and a prompt that asks for no judgement and no image and for one fixed token as the whole answer and that either tells it which documents and records to read or, when the caller names them as files, holds their text itself, sent on standard input so that the session has no tool use to narrate between; any text the setup session writes, in its answer or between its tool uses, other than that token after trimming, and any content block of its history that is neither text, a tool use nor a thinking block whose text is empty, fails the run, so no forked reviewer inherits a verdict; a thinking block that carries text, and a redacted one, fail it; a setup session that fails only for text written between its tool uses is started again, up to twice, before the run fails, and every attempt's session is reported with its cost, and a read of a file whose type is not text in the setup session's tool uses fails the run naming the file, as does a file the caller names whose type is not text, before any session is started. Out of scope: the content of a caller's prompt for its units.
        status, text, _ = self.run_command()
        self.assertEqual(status, 0, text)
        setup = self.setups()[0]
        args = setup["args"]
        self.assertEqual(args[0], "-p")
        self.assertTrue(args[1].startswith("--"), f"no prompt argument follows -p: {args[:3]}")
        self.assertNotIn("Read every document", " ".join(args))
        stdin = setup["stdin"]
        self.assertTrue(stdin.startswith("Read every document in the review folder."), stdin)
        self.assertIn("=== method.md ===\nthe method\n", stdin)
        self.assertIn("=== notes/extra.txt ===\nextra note\n", stdin)
        self.assertLess(stdin.index("=== method.md ==="), stdin.index("=== notes/extra.txt ==="), "in the caller's order")
        self.assertTrue(stdin.rstrip().endswith(review_fan_out.ACK_INSTRUCTION), "the fixed ask ends the prompt")
        self.assertEqual(self.flag(setup, "--tools"), "Read,Glob,Grep")
        self.assertEqual(setup["args"][setup["args"].index("--append-system-prompt") + 1], review_fan_out.SETUP_RULE)

    def test_a_setup_session_given_its_documents_makes_no_read_and_passes_and_the_forks_start_from_it(self):
        # SOL-HW-REVIEW-FAN-OUT-DRIVER.C2: Each session's start report is read and a run whose report shows other tools than were granted, another model, any MCP server, an instruction source the command line was asked to exclude or another working directory fails naming the session. The setup session is started with the read tools only and a prompt that asks for no judgement and no image and for one fixed token as the whole answer and that either tells it which documents and records to read or, when the caller names them as files, holds their text itself, sent on standard input so that the session has no tool use to narrate between; any text the setup session writes, in its answer or between its tool uses, other than that token after trimming, and any content block of its history that is neither text, a tool use nor a thinking block whose text is empty, fails the run, so no forked reviewer inherits a verdict; a thinking block that carries text, and a redacted one, fail it; a setup session that fails only for text written between its tool uses is started again, up to twice, before the run fails, and every attempt's session is reported with its cost, and a read of a file whose type is not text in the setup session's tool uses fails the run naming the file, as does a file the caller names whose type is not text, before any session is started. Out of scope: the content of a caller's prompt for its units.
        status, text, _ = self.run_command(as_json=True)
        self.assertEqual(status, 0, text)
        setup = self.setups()[0]
        self.assertEqual(len(self.forks()), 3)
        for fork in self.forks():
            self.assertEqual(fork["resume"], setup["session"])
            self.assertIsNone(fork["stdin"], "a reviewer's prompt stays an argument")
        self.assertEqual(json.loads(text)["setup_sessions"][0]["id"], setup["session"])

    def test_the_other_checks_of_the_setup_session_still_apply_when_it_is_given_its_documents(self):
        # SOL-HW-REVIEW-FAN-OUT-DRIVER.C2: Each session's start report is read and a run whose report shows other tools than were granted, another model, any MCP server, an instruction source the command line was asked to exclude or another working directory fails naming the session. The setup session is started with the read tools only and a prompt that asks for no judgement and no image and for one fixed token as the whole answer and that either tells it which documents and records to read or, when the caller names them as files, holds their text itself, sent on standard input so that the session has no tool use to narrate between; any text the setup session writes, in its answer or between its tool uses, other than that token after trimming, and any content block of its history that is neither text, a tool use nor a thinking block whose text is empty, fails the run, so no forked reviewer inherits a verdict; a thinking block that carries text, and a redacted one, fail it; a setup session that fails only for text written between its tool uses is started again, up to twice, before the run fails, and every attempt's session is reported with its cost, and a read of a file whose type is not text in the setup session's tool uses fails the run naming the file, as does a file the caller names whose type is not text, before any session is started. Out of scope: the content of a caller's prompt for its units.
        narrated = [{"type": "text", "text": "I will begin."}]
        cases = {"an image read": ({"reads": ["views/top.png"]}, "the setup session opened views/top.png"),
                 "a wrong final answer": ({"answer": "Looks fine."}, "and not SETUP-READ-COMPLETE"),
                 "a tool outside the grant": ({"uses": ["Bash"]}, "used Bash, a tool it was not granted"),
                 "a thinking block that carries text": ({"narration": [{"type": "thinking", "thinking": "hmm"}]},
                                                        "thinking block that carries text")}
        for name, (outcome, word) in cases.items():
            with self.subTest(case=name):
                shutil.rmtree(self.out, ignore_errors=True)
                for call in os.listdir(self.log):
                    os.remove(os.path.join(self.log, call))
                self.scenario({"setup": {"reads": [], **outcome}})
                status, text, _ = self.run_command()
                self.assertEqual(status, 1, text)
                self.assertIn(word, text)
                self.assertEqual(len(self.calls()), 1, "no restart and no fork")
        shutil.rmtree(self.out, ignore_errors=True)
        for call in os.listdir(self.log):
            os.remove(os.path.join(self.log, call))
        self.scenario({"setup": {"reads": [], "attempts": [{"narration": narrated}, {}]}})
        status, text, _ = self.run_command()
        self.assertEqual(status, 0, text)
        self.assertEqual(len(self.setups()), 2, "narration alone is started again")
        self.assertTrue(all(call["stdin"] for call in self.setups()), "each attempt is sent the documents")

    def test_a_document_that_is_missing_outside_the_folder_repeated_or_not_text_is_refused_before_any_session(self):
        # SOL-HW-REVIEW-FAN-OUT-DRIVER.C2: Each session's start report is read and a run whose report shows other tools than were granted, another model, any MCP server, an instruction source the command line was asked to exclude or another working directory fails naming the session. The setup session is started with the read tools only and a prompt that asks for no judgement and no image and for one fixed token as the whole answer and that either tells it which documents and records to read or, when the caller names them as files, holds their text itself, sent on standard input so that the session has no tool use to narrate between; any text the setup session writes, in its answer or between its tool uses, other than that token after trimming, and any content block of its history that is neither text, a tool use nor a thinking block whose text is empty, fails the run, so no forked reviewer inherits a verdict; a thinking block that carries text, and a redacted one, fail it; a setup session that fails only for text written between its tool uses is started again, up to twice, before the run fails, and every attempt's session is reported with its cost, and a read of a file whose type is not text in the setup session's tool uses fails the run naming the file, as does a file the caller names whose type is not text, before any session is started. Out of scope: the content of a caller's prompt for its units.
        self.write(os.path.join(self.root, "outside.txt"), "secret")
        os.symlink(os.path.join(self.root, "outside.txt"), os.path.join(self.review, "link.txt"))
        with open(os.path.join(self.review, "board.png"), "wb") as handle:
            handle.write(b"\x89PNG\r\n\x1a\n\0")
        with open(os.path.join(self.review, "blob.dat"), "wb") as handle:
            handle.write(b"abc\0def")
        os.makedirs(os.path.join(self.review, "folder"))
        cases = {"a missing file": (["method.md", "gone.md"], "gone.md", "not a file"),
                 "a folder": (["folder"], "folder", "not a file"),
                 "a parent path": (["../outside.txt"], "../outside.txt", "not inside the review folder"),
                 "an absolute path": ([os.path.join(self.root, "outside.txt")], "outside.txt", "not inside the review folder"),
                 "a link out of the folder": (["link.txt"], "link.txt", "not inside the review folder"),
                 "an image": (["board.png"], "board.png", "type is not text"),
                 "a file with a NUL byte": (["blob.dat"], "blob.dat", "type is not text"),
                 "a repeated path": (["method.md", "method.md"], "method.md", "more than once")}
        for name, (listed, path, word) in cases.items():
            with self.subTest(case=name):
                shutil.rmtree(self.out, ignore_errors=True)
                self.documents(listed)
                status, text, _ = self.run_command()
                self.assertEqual(status, 1, text)
                line = next(line for line in text.splitlines() if line.startswith("REFUSED | "))
                self.assertIn(path, line)
                self.assertIn(word, line)
                self.assertEqual(self.calls(), [], "no session was started")

    def test_a_label_and_text_pair_is_given_in_the_setup_prompt_beside_the_files_in_the_callers_order(self):
        # SOL-HW-REVIEW-FAN-OUT-DRIVER.C2: Each session's start report is read and a run whose report shows other tools than were granted, another model, any MCP server, an instruction source the command line was asked to exclude or another working directory fails naming the session. The setup session is started with the read tools only and a prompt that asks for no judgement and no image and for one fixed token as the whole answer and that either tells it which documents and records to read or, when the caller names them as files, holds their text itself, sent on standard input so that the session has no tool use to narrate between; any text the setup session writes, in its answer or between its tool uses, other than that token after trimming, and any content block of its history that is neither text, a tool use nor a thinking block whose text is empty, fails the run, so no forked reviewer inherits a verdict; a thinking block that carries text, and a redacted one, fail it; a setup session that fails only for text written between its tool uses is started again, up to twice, before the run fails, and every attempt's session is reported with its cost, and a read of a file whose type is not text in the setup session's tool uses fails the run naming the file, as does a file the caller names whose type is not text, before any session is started. Out of scope: the content of a caller's prompt for its units.
        self.documents([["method.md (section: Review)", "only the review\n"], "notes/extra.txt"])
        status, text, _ = self.run_command()
        self.assertEqual(status, 0, text)
        stdin = self.setups()[0]["stdin"]
        self.assertIn("=== method.md (section: Review) ===\nonly the review\n", stdin)
        self.assertIn("=== notes/extra.txt ===\nextra note\n", stdin)
        self.assertLess(stdin.index("only the review"), stdin.index("extra note"))
        self.assertNotIn("the method\n", stdin, "the file method.md was not named, only an extract labelled with it")

    def test_a_bad_extract_is_refused_before_any_session(self):
        # SOL-HW-REVIEW-FAN-OUT-DRIVER.C2: Each session's start report is read and a run whose report shows other tools than were granted, another model, any MCP server, an instruction source the command line was asked to exclude or another working directory fails naming the session. The setup session is started with the read tools only and a prompt that asks for no judgement and no image and for one fixed token as the whole answer and that either tells it which documents and records to read or, when the caller names them as files, holds their text itself, sent on standard input so that the session has no tool use to narrate between; any text the setup session writes, in its answer or between its tool uses, other than that token after trimming, and any content block of its history that is neither text, a tool use nor a thinking block whose text is empty, fails the run, so no forked reviewer inherits a verdict; a thinking block that carries text, and a redacted one, fail it; a setup session that fails only for text written between its tool uses is started again, up to twice, before the run fails, and every attempt's session is reported with its cost, and a read of a file whose type is not text in the setup session's tool uses fails the run naming the file, as does a file the caller names whose type is not text, before any session is started. Out of scope: the content of a caller's prompt for its units.
        cases = {"empty text": [["extract", "  \n"]], "a NUL": [["extract", "a\u0000b"]],
                 "a control character": [["extract", "a\u0007b"]], "a label that repeats a path": [["method.md", "x"], "method.md"],
                 "a label twice": [["extract", "a"], ["extract", "b"]], "an empty label": [["", "text"]],
                 "a triple": [["a", "b", "c"]], "a non-text body": [["extract", 5]]}
        for name, listed in cases.items():
            with self.subTest(case=name):
                shutil.rmtree(self.out, ignore_errors=True)
                self.documents(listed)
                status, text, _ = self.run_command()
                self.assertEqual(status, 1, text)
                self.assertIn("REFUSED", text)
                self.assertEqual(self.calls(), [], "no session was started")

    def test_a_pair_with_tabs_and_line_breaks_is_given_as_it_is(self):
        # SOL-HW-REVIEW-FAN-OUT-DRIVER.C2: Each session's start report is read and a run whose report shows other tools than were granted, another model, any MCP server, an instruction source the command line was asked to exclude or another working directory fails naming the session. The setup session is started with the read tools only and a prompt that asks for no judgement and no image and for one fixed token as the whole answer and that either tells it which documents and records to read or, when the caller names them as files, holds their text itself, sent on standard input so that the session has no tool use to narrate between; any text the setup session writes, in its answer or between its tool uses, other than that token after trimming, and any content block of its history that is neither text, a tool use nor a thinking block whose text is empty, fails the run, so no forked reviewer inherits a verdict; a thinking block that carries text, and a redacted one, fail it; a setup session that fails only for text written between its tool uses is started again, up to twice, before the run fails, and every attempt's session is reported with its cost, and a read of a file whose type is not text in the setup session's tool uses fails the run naming the file, as does a file the caller names whose type is not text, before any session is started. Out of scope: the content of a caller's prompt for its units.
        self.documents([["extract", "a\tb\r\nc\n"]])
        status, text, _ = self.run_command()
        self.assertEqual(status, 0, text)
        self.assertIn("=== extract ===", self.setups()[0]["stdin"])

    def test_a_setup_documents_hook_that_raises_or_returns_the_wrong_kind_is_refused_before_any_session(self):
        # SOL-HW-REVIEW-FAN-OUT-DRIVER.C2: Each session's start report is read and a run whose report shows other tools than were granted, another model, any MCP server, an instruction source the command line was asked to exclude or another working directory fails naming the session. The setup session is started with the read tools only and a prompt that asks for no judgement and no image and for one fixed token as the whole answer and that either tells it which documents and records to read or, when the caller names them as files, holds their text itself, sent on standard input so that the session has no tool use to narrate between; any text the setup session writes, in its answer or between its tool uses, other than that token after trimming, and any content block of its history that is neither text, a tool use nor a thinking block whose text is empty, fails the run, so no forked reviewer inherits a verdict; a thinking block that carries text, and a redacted one, fail it; a setup session that fails only for text written between its tool uses is started again, up to twice, before the run fails, and every attempt's session is reported with its cost, and a read of a file whose type is not text in the setup session's tool uses fails the run naming the file, as does a file the caller names whose type is not text, before any session is started. Out of scope: the content of a caller's prompt for its units.
        for name, body in {"a string": "return 'method.md'", "a list of numbers": "return [1]",
                           "a raise": "raise ValueError('no')"}.items():
            with self.subTest(case=name):
                shutil.rmtree(self.out, ignore_errors=True)
                self.write(os.path.join(self.callers, "review_caller_synth.py"),
                           caller_text() + f"\n\ndef SETUP_DOCUMENTS(folder):\n    {body}\n")
                status, text, _ = self.run_command()
                self.assertEqual(status, 1, text)
                self.assertIn("REFUSED | the caller's SETUP_DOCUMENTS", text)
                self.assertEqual(self.calls(), [])
        shutil.rmtree(self.out, ignore_errors=True)
        self.write(os.path.join(self.callers, "review_caller_synth.py"), caller_text() + "\nSETUP_DOCUMENTS = ['method.md']\n")
        status, text, _ = self.run_command()
        self.assertEqual(status, 1, text)
        self.assertIn("SETUP_DOCUMENTS", text)
        self.assertEqual(self.calls(), [])

    def test_a_caller_without_setup_documents_still_sends_its_prompt_as_an_argument_and_must_read(self):
        # SOL-HW-REVIEW-FAN-OUT-DRIVER.C2: Each session's start report is read and a run whose report shows other tools than were granted, another model, any MCP server, an instruction source the command line was asked to exclude or another working directory fails naming the session. The setup session is started with the read tools only and a prompt that asks for no judgement and no image and for one fixed token as the whole answer and that either tells it which documents and records to read or, when the caller names them as files, holds their text itself, sent on standard input so that the session has no tool use to narrate between; any text the setup session writes, in its answer or between its tool uses, other than that token after trimming, and any content block of its history that is neither text, a tool use nor a thinking block whose text is empty, fails the run, so no forked reviewer inherits a verdict; a thinking block that carries text, and a redacted one, fail it; a setup session that fails only for text written between its tool uses is started again, up to twice, before the run fails, and every attempt's session is reported with its cost, and a read of a file whose type is not text in the setup session's tool uses fails the run naming the file, as does a file the caller names whose type is not text, before any session is started. Out of scope: the content of a caller's prompt for its units.
        self.write(os.path.join(self.callers, "review_caller_synth.py"), caller_text())
        self.scenario({})
        status, text, _ = self.run_command()
        self.assertEqual(status, 0, text)
        setup = self.setups()[0]
        self.assertEqual(setup["args"][1], setup["prompt"])
        self.assertTrue(setup["prompt"].startswith("Read every document in the review folder."))
        self.assertIsNone(setup["stdin"])
        self.assertNotIn("===", setup["prompt"])
        shutil.rmtree(self.out, ignore_errors=True)
        self.scenario({"setup": {"reads": []}})
        status, text, _ = self.run_command()
        self.assertEqual(status, 1, text)
        self.assertIn("the setup session read nothing", text)


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


    def test_a_unit_that_fails_twice_has_the_cost_of_its_attempts_in_its_figures_and_the_run_s_total(self):
        # SOL-HW-REVIEW-FAN-OUT-DRIVER.C5: Against a stub that reports a fork's cost, API time and turn count cumulatively including its setup session, as the agent command line does, the record gives each fork its own cost, time and turns, the setup session its own, and the run their sum; token usage is taken as each session reports it, split into tokens read from the cache, written to it, fresh and generated, and a fork that reads no cache is flagged. The record is in the text and the JSON report. Out of scope: judging whether a run was worth its cost.
        self.scenario({"units": {"alpha": [{"text": "not json", "cost": 0.07, "api_ms": 700, "turns": 2}]}})
        status, text, _ = self.run_command("--bound", "3", as_json=True)
        self.assertEqual(status, 1, text)
        report = json.loads(text)
        alpha = [unit for unit in report["units"] if unit["unit"] == "alpha"][0]
        self.assertEqual(alpha["status"], "failed")
        self.assertEqual(alpha["attempts"], 2)
        self.assertAlmostEqual(alpha["own"]["cost_usd"], 0.14)
        self.assertEqual((alpha["own"]["api_ms"], alpha["own"]["turns"]), (1400, 4))
        self.assertTrue(alpha["session"])
        self.assertAlmostEqual(report["totals"]["cost_usd"], 0.05 + 0.14 + 0.05 + 0.05)

    def test_a_failed_attempt_s_cost_stays_in_the_totals_when_the_unit_is_later_run_again_and_judged(self):
        # SOL-HW-REVIEW-FAN-OUT-DRIVER.C5: Against a stub that reports a fork's cost, API time and turn count cumulatively including its setup session, as the agent command line does, the record gives each fork its own cost, time and turns, the setup session its own, and the run their sum; token usage is taken as each session reports it, split into tokens read from the cache, written to it, fresh and generated, and a fork that reads no cache is flagged. The record is in the text and the JSON report. Out of scope: judging whether a run was worth its cost.
        self.scenario({"units": {"charlie": [{"text": "not json", "cost": 0.07}]}})
        status, text, _ = self.run_command()
        self.assertEqual(status, 1, text)
        self.scenario({})
        status, text, _ = self.run_command("--rerun", "charlie", as_json=True)
        self.assertEqual(status, 0, text)
        report = json.loads(text)
        charlie = [unit for unit in report["units"] if unit["unit"] == "charlie"][0]
        self.assertAlmostEqual(charlie["own"]["cost_usd"], 0.05 + 0.14, msg="the judged sessions and the two failed ones")
        self.assertAlmostEqual(report["totals"]["cost_usd"], 0.05 + 0.05 + 0.05 + 0.19 + 0.05,
                               msg="two setup sessions, alpha, bravo and charlie's every session")
        self.assertFalse(os.path.exists(os.path.join(self.out, "failed", "charlie.json")), "folded into the kept result")

    def test_a_unit_run_again_keeps_the_cost_of_the_result_it_replaced_in_its_figures_and_the_total(self):
        # SOL-HW-REVIEW-FAN-OUT-DRIVER.C5: Against a stub that reports a fork's cost, API time and turn count cumulatively including its setup session, as the agent command line does, the record gives each fork its own cost, time and turns, the setup session its own, and the run their sum; token usage is taken as each session reports it, split into tokens read from the cache, written to it, fresh and generated, and a fork that reads no cache is flagged. The record is in the text and the JSON report. Out of scope: judging whether a run was worth its cost.
        status, text, _ = self.run_command()
        self.assertEqual(status, 0, text)
        status, text, _ = self.run_command("--rerun", "bravo", as_json=True)
        self.assertEqual(status, 0, text)
        report = json.loads(text)
        bravo = [unit for unit in report["units"] if unit["unit"] == "bravo"][0]
        self.assertAlmostEqual(bravo["own"]["cost_usd"], 0.10, msg="the new session and the one replaced")
        self.assertAlmostEqual(report["totals"]["cost_usd"], 0.05 + 0.05 + 0.05 + 0.05 + 0.10)
        self.assertEqual(len(self.kept("bravo")["superseded"]), 1)

    def test_a_reviewer_that_loses_its_login_mid_run_is_that_unit_s_failure_and_the_others_are_kept(self):
        # SOL-HW-REVIEW-FAN-OUT-DRIVER.C3: A unit whose reviewer exits with an error or returns nothing is run once more; a call refused for a rate limit is retried after a wait that grows, a bounded number of times; a unit that still fails fails the run, naming the unit and what the reviewer returned, and the other units' results are kept in the output. Out of scope: what a caller counts as a malformed result, which the caller defines.
        self.scenario({"units": {"alpha": [{"login": True}]}})
        status, text, err = self.run_command("--bound", "1")
        self.assertEqual(status, 2, text)
        self.assertIn("is not logged in; log it in, then run again", err)
        self.assertNotIn("unit alpha failed", err, "the cause alone is reported, as the command line gave it")
        self.assertEqual(review_fan_out.LoginLost("alpha", "the cause").cause, "the cause")
        self.assertRegex(text, r"FAILED \| unit alpha failed: .*is not logged in")
        self.assertRegex(text, r"RESULT \| CANNOT RUN \| 1 of 3 units failed: alpha; the others' results are kept in")
        for unit in ("bravo", "charlie"):
            self.assertTrue(os.path.isfile(os.path.join(self.out, "units", f"{unit}.json")))
        self.assertFalse(os.path.exists(os.path.join(self.out, "record.json")))
        self.assertFalse(os.path.exists(os.path.join(self.out, review_fan_out.LOCK)), "the lock is released")
        self.assertEqual(len([call for call in self.forks() if call["unit"] == "alpha"]), 1, "a lost login is not run once more")

    def test_an_exception_in_one_unit_s_worker_is_that_unit_s_failure_and_not_a_traceback(self):
        # SOL-HW-REVIEW-FAN-OUT-DRIVER.C3: A unit whose reviewer exits with an error or returns nothing is run once more; a call refused for a rate limit is retried after a wait that grows, a bounded number of times; a unit that still fails fails the run, naming the unit and what the reviewer returned, and the other units' results are kept in the output. Out of scope: what a caller counts as a malformed result, which the caller defines.
        real = review_fan_out.call_agent

        def vanishing(program, prompt, *rest, **named):
            if "UNIT=alpha" in prompt:
                raise FileNotFoundError("the agent binary vanished")
            return real(program, prompt, *rest, **named)
        with mock.patch.object(review_fan_out, "call_agent", vanishing):
            status, text, _ = self.run_command("--bound", "3")
        self.assertEqual(status, 1, text)
        self.assertIn("FAILED | unit alpha failed: FileNotFoundError: the agent binary vanished", text)
        self.assertTrue(os.path.isfile(os.path.join(self.out, "units", "bravo.json")))
        self.assertFalse(os.path.exists(os.path.join(self.out, review_fan_out.LOCK)))

    def test_a_reviewer_s_words_about_a_rate_limit_or_a_login_are_not_the_command_line_saying_so(self):
        # SOL-HW-REVIEW-FAN-OUT-DRIVER.C3: A unit whose reviewer exits with an error or returns nothing is run once more; a call refused for a rate limit is retried after a wait that grows, a bounded number of times; a unit that still fails fails the run, naming the unit and what the reviewer returned, and the other units' results are kept in the output. Out of scope: what a caller counts as a malformed result, which the caller defines.
        prose = "R429 is overloaded and the user is not logged in"
        self.scenario({"units": {"alpha": [{"prose": prose}]}})
        status, text, _ = self.run_command("--bound", "3")
        self.assertEqual(status, 1, text)
        self.assertRegex(text, r"FAILED \| unit alpha failed after 2 attempts; the reviewer returned: R429 is overloaded")
        self.assertEqual(len([call for call in self.forks() if call["unit"] == "alpha"]), 2, "run once more, not retried")

    def test_a_setup_session_refused_for_a_rate_limit_after_the_retries_refuses_the_run_and_starts_no_fork(self):
        # SOL-HW-REVIEW-FAN-OUT-DRIVER.C3: A unit whose reviewer exits with an error or returns nothing is run once more; a call refused for a rate limit is retried after a wait that grows, a bounded number of times; a unit that still fails fails the run, naming the unit and what the reviewer returned, and the other units' results are kept in the output. Out of scope: what a caller counts as a malformed result, which the caller defines.
        self.scenario({"setup": {"rate_limit": True}})
        status, text, _ = self.run_command()
        self.assertEqual(status, 1, text)
        self.assertRegex(text, r"REFUSED \| the setup session still refused for a rate limit after 5 retries")
        self.assertEqual(len(self.calls()), review_fan_out.RATE_RETRIES + 1)
        self.assertEqual(self.forks(), [])
        self.assertIn("RESULT | REFUSED | no unit was started", text)

    def test_a_setup_session_that_loses_its_login_exits_two_and_keeps_nothing(self):
        # SOL-HW-REVIEW-FAN-OUT-DRIVER.C4: The exit status is 0 when the merged record is written, 1 when the command refuses or a unit fails, and 2 when the agent command line is missing or not logged in, each with a line beginning REFUSED or CANNOT RUN as the other board commands print; a review folder inside the repository, a folder that does not exist, an output folder inside the review folder or containing it or inside the repository, a caller name with no module or whose module lacks a required attribute, an output folder that already holds a record when no unit is named to run again, an output folder in use by another run, and a bound below one are refused. Each REFUSED and CANNOT RUN line names its cause and what to do about it. The report is available as text and as JSON and the two hold the same facts. Out of scope: the merge's own refusals, which each caller names.
        self.scenario({"setup": {"login": True}})
        status, text, err = self.run_command()
        self.assertEqual(status, 2, text)
        self.assertIn("is not logged in; log it in, then run again", err)
        self.assertIn("RESULT | CANNOT RUN | nothing was kept", text)


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
        busy = os.path.join(self.root, "busy")
        self.write(os.path.join(busy, review_fan_out.LOCK), "123")
        self.write(os.path.join(busy, "units", "x.json"), "{}")
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
            ("in use with units written", dict(out=busy), (), "is in use by another run", "wait for that run"),
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
        self.assertIn("is not logged in: `auth status` exited 1", err)
        self.assertIn("log it in, then run again", err)
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
        self.assertEqual(text.splitlines()[-1], f"RESULT | WRITTEN | {report['detail']}")
        lines = review_fan_out.render_text(report)
        self.assertEqual(len(lines), len(text.splitlines()), "the command prints these lines for a run of the same shape")
        clean = review_fan_out.board_check.clean

        def scalars(value):
            """Every string and number in the JSON, as the text prints it; flags and empty cells carry no token."""
            if isinstance(value, dict):
                for inner in value.values():
                    yield from scalars(inner)
            elif isinstance(value, (list, tuple)):
                for inner in value:
                    yield from scalars(inner)
            elif value is not None and not isinstance(value, bool) and clean(value):
                yield clean(value)

        def line_of(prefix):
            return [line for line in lines if line.startswith(prefix)]

        def holds(line, value, what):
            for token in scalars(value):
                self.assertIn(token, line, f"{what}: {token!r} of the JSON is in the text")
        holds(line_of("RUN | ")[0], [report["caller"], report["review"], report["out"]], "the run")
        holds(line_of("RESULT | ")[0], [report["result"], report["detail"]], "the result")
        self.assertEqual(len(line_of("SETUP | ")), len(report["setup_sessions"]))
        for setup, line in zip(report["setup_sessions"], line_of("SETUP | ")):
            holds(line, setup, "a setup session")
        self.assertEqual(len(line_of("UNIT | ")), len(report["units"]))
        for unit, line in zip(report["units"], line_of("UNIT | ")):
            holds(line, unit, "a unit")
            self.assertEqual("run again" in line, unit["run_again"])
        holds(line_of("TOTAL | ")[0], report["totals"], "the total")
        self.assertEqual(len(line_of("SAME PLACE | ")), len(report["same_place"]))
        for place, line in zip(report["same_place"], line_of("SAME PLACE | ")):
            holds(line, place, "a place")
        self.assertEqual(report["same_place"][0]["findings"], [1, 2])
        self.assertEqual(len(line_of("TABLE | ")), len(report["tables"]))
        for (name, table), line in zip(report["tables"].items(), line_of("TABLE | ")):
            holds(line, [name, table["columns"], len(table["rows"])], "a table")
        rows = [(name, row) for name, table in report["tables"].items() for row in table["rows"]]
        self.assertEqual(len(line_of("ROW | ")), len(rows))
        for (name, row), line in zip(rows, line_of("ROW | ")):
            holds(line, [name, row], "a table row")
        for line in lines:
            self.assertRegex(line, r"^(RUN|SETUP|UNIT|SAME PLACE|TABLE|ROW|TOTAL|RESULT|RERUN|FAILED|REFUSED|CANNOT RUN) \| ")

        self.scenario({"units": {"bravo": [{"exit": 1}]}})
        shutil.rmtree(self.out)
        status, as_json, _ = self.run_command(as_json=True)
        self.assertEqual(status, 1)
        report = json.loads(as_json)
        shown = review_fan_out.render_text(report)
        failed = [unit for unit in report["units"] if unit["status"] == "failed"][0]
        self.assertIn(f"FAILED | {clean(failed['detail'])}", shown)
        holds([line for line in shown if line.startswith("UNIT | bravo")][0], {k: v for k, v in failed.items() if k != "detail"}, "a failed unit")
        holds([line for line in shown if line.startswith("RESULT | ")][0], [report["result"], report["detail"]], "the failed result")

        shutil.rmtree(self.out)
        os.makedirs(os.path.join(self.out, "units"))
        self.write(os.path.join(self.out, "units", "x.json"), "{}")
        status, text, _ = self.run_command()
        status_json, as_json, _ = self.run_command(as_json=True)
        self.assertEqual((status, status_json), (1, 1))
        self.assertEqual([line[len("REFUSED | "):] for line in self.refusal_lines(text)],
                         [review_fan_out.board_check.clean(why) for why in json.loads(as_json)["refusals"]])

    def test_a_folder_a_run_that_kept_nothing_but_its_setup_session_list_is_one_a_fresh_run_refuses(self):
        # SOL-HW-REVIEW-FAN-OUT-DRIVER.C4: The exit status is 0 when the merged record is written, 1 when the command refuses or a unit fails, and 2 when the agent command line is missing or not logged in, each with a line beginning REFUSED or CANNOT RUN as the other board commands print; a review folder inside the repository, a folder that does not exist, an output folder inside the review folder or containing it or inside the repository, a caller name with no module or whose module lacks a required attribute, an output folder that already holds a record when no unit is named to run again, an output folder in use by another run, and a bound below one are refused. Each REFUSED and CANNOT RUN line names its cause and what to do about it. The report is available as text and as JSON and the two hold the same facts. Out of scope: the merge's own refusals, which each caller names.
        self.scenario({"units": {name: [{"exit": 1}] for name in Fixture.UNITS}})
        status, text, _ = self.run_command("--bound", "3")
        self.assertEqual(status, 1, text)
        self.assertFalse(os.path.exists(os.path.join(self.out, "units", "alpha.json")))
        self.assertTrue(os.path.isfile(os.path.join(self.out, "setups.json")))
        for name in os.listdir(self.log):
            os.remove(os.path.join(self.log, name))
        self.scenario({})
        status, text, _ = self.run_command()
        self.assertEqual(status, 1, text)
        self.assertIn("already holds a record", text)
        self.assertEqual(self.calls(), [], "nothing was started")
        status, text, _ = self.run_command("--rerun", "alpha")
        self.assertIn("holds no result for bravo, charlie; name each of them with --rerun too", text)

    def test_a_refusal_after_the_lock_leaves_no_lock_and_no_folder_it_created(self):
        # SOL-HW-REVIEW-FAN-OUT-DRIVER.C4: The exit status is 0 when the merged record is written, 1 when the command refuses or a unit fails, and 2 when the agent command line is missing or not logged in, each with a line beginning REFUSED or CANNOT RUN as the other board commands print; a review folder inside the repository, a folder that does not exist, an output folder inside the review folder or containing it or inside the repository, a caller name with no module or whose module lacks a required attribute, an output folder that already holds a record when no unit is named to run again, an output folder in use by another run, and a bound below one are refused. Each REFUSED and CANNOT RUN line names its cause and what to do about it. The report is available as text and as JSON and the two hold the same facts. Out of scope: the merge's own refusals, which each caller names.
        folder = os.path.join(self.root, "fresh")
        status, text, _ = self.run_command("--rerun", "alpha", out=folder)
        self.assertEqual(status, 1, text)
        self.assertIn("holds no earlier result to run alpha again against", text)
        self.assertFalse(os.path.exists(folder))

    def test_a_merge_the_caller_s_check_refuses_exits_one_with_a_refused_line_and_keeps_the_results(self):
        # SOL-HW-REVIEW-FAN-OUT-DRIVER.C4: The exit status is 0 when the merged record is written, 1 when the command refuses or a unit fails, and 2 when the agent command line is missing or not logged in, each with a line beginning REFUSED or CANNOT RUN as the other board commands print; a review folder inside the repository, a folder that does not exist, an output folder inside the review folder or containing it or inside the repository, a caller name with no module or whose module lacks a required attribute, an output folder that already holds a record when no unit is named to run again, an output folder in use by another run, and a bound below one are refused. Each REFUSED and CANNOT RUN line names its cause and what to do about it. The report is available as text and as JSON and the two hold the same facts. Out of scope: the merge's own refusals, which each caller names.
        self.write(os.path.join(self.callers, "review_caller_strict.py"),
                   caller_text(check='["item C-1 has no verdict; ask for it with --rerun charlie"]'))
        status, text, _ = self.run_command(caller="strict")
        self.assertEqual(status, 1, text)
        self.assertIn("REFUSED | item C-1 has no verdict; ask for it with --rerun charlie", text)
        self.assertTrue(os.path.isfile(os.path.join(self.out, "units", "charlie.json")))
        self.assertFalse(os.path.exists(os.path.join(self.out, "record.json")))

    def raising_hook(self, findings=FINDINGS, check="[]", units=False):
        text = caller_text(findings, check)
        if units:
            text = text.replace("    return sorted(name[:-4]", '    raise KeyError("no such unit")\n    return sorted(name[:-4]')
        self.write(os.path.join(self.callers, "review_caller_broken.py"), text)

    def assert_hook_refused(self, hook, kept=True):
        for as_json in (False, True):
            shutil.rmtree(self.out, True)
            status, text, _ = self.run_command(caller="broken", as_json=as_json)
            self.assertEqual(status, 1, text)
            if as_json:
                report = json.loads(text)
                self.assertEqual(report["result"], "REFUSED")
                self.assertTrue(any(f"the caller's {hook} raised KeyError" in cause and "fix the caller" in cause
                                    for cause in report["refusals"]), report["refusals"])
            else:
                self.assertRegex(text, rf"REFUSED \| the caller's {hook} raised KeyError: .*fix the caller")
            self.assertNotIn("Traceback", text)
            if kept:
                self.assertTrue(os.path.isfile(os.path.join(self.out, "units", "charlie.json")))
                self.assertFalse(os.path.exists(os.path.join(self.out, "record.json")))
                self.assertFalse(os.path.exists(os.path.join(self.out, review_fan_out.LOCK)))
            else:
                self.assertFalse(os.path.exists(self.out))

    def test_a_caller_s_key_that_raises_in_the_merge_exits_one_with_a_refused_line_naming_it_and_keeps_the_results(self):
        # SOL-HW-REVIEW-FAN-OUT-DRIVER.C4: The exit status is 0 when the merged record is written, 1 when the command refuses or a unit fails, and 2 when the agent command line is missing or not logged in, each with a line beginning REFUSED or CANNOT RUN as the other board commands print; a review folder inside the repository, a folder that does not exist, an output folder inside the review folder or containing it or inside the repository, a caller name with no module or whose module lacks a required attribute, an output folder that already holds a record when no unit is named to run again, an output folder in use by another run, and a bound below one are refused. Each REFUSED and CANNOT RUN line names its cause and what to do about it. The report is available as text and as JSON and the two hold the same facts. Out of scope: the merge's own refusals, which each caller names.
        self.scenario({"tables": {"alpha": {"Verdicts": [{"Item": "A-1", "Verdict": "pass", "Rests on": "read"}],
                                              "Findings": [finding(1, "A-1", "stub")]}}})
        self.raising_hook(findings=FINDINGS.replace('"key": lambda row: row["What"].split("@")[1] if "@" in row["What"] else None',
                                                    '"key": lambda row: row["Missing"]'))
        self.assert_hook_refused("key")

    def test_a_caller_s_check_that_raises_exits_one_with_a_refused_line_naming_it_and_keeps_the_results(self):
        # SOL-HW-REVIEW-FAN-OUT-DRIVER.C4: The exit status is 0 when the merged record is written, 1 when the command refuses or a unit fails, and 2 when the agent command line is missing or not logged in, each with a line beginning REFUSED or CANNOT RUN as the other board commands print; a review folder inside the repository, a folder that does not exist, an output folder inside the review folder or containing it or inside the repository, a caller name with no module or whose module lacks a required attribute, an output folder that already holds a record when no unit is named to run again, an output folder in use by another run, and a bound below one are refused. Each REFUSED and CANNOT RUN line names its cause and what to do about it. The report is available as text and as JSON and the two hold the same facts. Out of scope: the merge's own refusals, which each caller names.
        self.raising_hook(check='{"a": 1}["b"]')
        self.assert_hook_refused("CHECK")

    def test_a_caller_s_units_that_raises_exits_one_with_a_refused_line_naming_it_and_leaves_no_folder(self):
        # SOL-HW-REVIEW-FAN-OUT-DRIVER.C4: The exit status is 0 when the merged record is written, 1 when the command refuses or a unit fails, and 2 when the agent command line is missing or not logged in, each with a line beginning REFUSED or CANNOT RUN as the other board commands print; a review folder inside the repository, a folder that does not exist, an output folder inside the review folder or containing it or inside the repository, a caller name with no module or whose module lacks a required attribute, an output folder that already holds a record when no unit is named to run again, an output folder in use by another run, and a bound below one are refused. Each REFUSED and CANNOT RUN line names its cause and what to do about it. The report is available as text and as JSON and the two hold the same facts. Out of scope: the merge's own refusals, which each caller names.
        self.raising_hook(units=True)
        self.assert_hook_refused("units", kept=False)

    def test_a_caller_s_first_hook_that_raises_exits_one_with_a_refused_line_naming_it_and_keeps_the_results(self):
        # SOL-HW-REVIEW-FAN-OUT-DRIVER.C4: The exit status is 0 when the merged record is written, 1 when the command refuses or a unit fails, and 2 when the agent command line is missing or not logged in, each with a line beginning REFUSED or CANNOT RUN as the other board commands print; a review folder inside the repository, a folder that does not exist, an output folder inside the review folder or containing it or inside the repository, a caller name with no module or whose module lacks a required attribute, an output folder that already holds a record when no unit is named to run again, an output folder in use by another run, and a bound below one are refused. Each REFUSED and CANNOT RUN line names its cause and what to do about it. The report is available as text and as JSON and the two hold the same facts. Out of scope: the merge's own refusals, which each caller names.
        self.scenario({"tables": {"alpha": {"Verdicts": [{"Item": "A-1", "Verdict": "pass", "Rests on": "read"}],
                                              "Findings": [finding(1, "A-1", "stub")]}}})
        self.raising_hook(findings=FINDINGS.replace('"key"', '"first": lambda folder: {}["x"], "key"'))
        self.assert_hook_refused("first")

    def test_a_rerun_whose_setup_session_loses_its_login_says_this_run_kept_nothing_and_names_the_earlier_results(self):
        # SOL-HW-REVIEW-FAN-OUT-DRIVER.C4: The exit status is 0 when the merged record is written, 1 when the command refuses or a unit fails, and 2 when the agent command line is missing or not logged in, each with a line beginning REFUSED or CANNOT RUN as the other board commands print; a review folder inside the repository, a folder that does not exist, an output folder inside the review folder or containing it or inside the repository, a caller name with no module or whose module lacks a required attribute, an output folder that already holds a record when no unit is named to run again, an output folder in use by another run, and a bound below one are refused. Each REFUSED and CANNOT RUN line names its cause and what to do about it. The report is available as text and as JSON and the two hold the same facts. Out of scope: the merge's own refusals, which each caller names.
        self.run_command()
        self.scenario({"setup": {"login": True}})
        status, text, _ = self.run_command("--rerun", "alpha")
        self.assertEqual(status, 2, text)
        self.assertIn(f"RESULT | CANNOT RUN | this run kept nothing; the earlier results stay in {self.out}", text)
        self.assertNotIn("nothing was kept", text)
        status, text, _ = self.run_command("--rerun", "alpha", as_json=True)
        self.assertEqual(json.loads(text)["detail"], f"this run kept nothing; the earlier results stay in {self.out}")
        self.assertTrue(os.path.isfile(os.path.join(self.out, "units", "alpha.json")))


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
        self.assertRegex(text, r"SETUP \| \S+ \| initial \| model-a \| \S+ \| units alpha, bravo, charlie \| 4000 ms API \| [\d.]+ s \| 3 turns \| \$0\.4 \| read 5000")
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


    def test_an_attempt_with_no_result_report_records_zero_figures_marked_so_and_never_negative_ones(self):
        # SOL-HW-REVIEW-FAN-OUT-DRIVER.C5: Against a stub that reports a fork's cost, API time and turn count cumulatively including its setup session, as the agent command line does, the record gives each fork its own cost, time and turns, the setup session its own, and the run their sum; token usage is taken as each session reports it, split into tokens read from the cache, written to it, fresh and generated, and a fork that reads no cache is flagged. The record is in the text and the JSON report. Out of scope: judging whether a run was worth its cost.
        self.scenario({"units": {"bravo": [{"exit": 3}, {}]}})
        status, text, _ = self.run_command("--bound", "3", as_json=True)
        self.assertEqual(status, 0, text)
        report = json.loads(text)
        first, second = self.kept("bravo")["sessions"]
        self.assertEqual((first["cost_usd"], first["api_ms"], first["turns"]), (0.0, 0, 0))
        self.assertEqual(first["tokens"], {"cache_read": 0, "cache_write": 0, "fresh": 0, "generated": 0})
        self.assertEqual(first["flags"], ["no report"])
        self.assertEqual((second["cost_usd"], second["api_ms"], second["turns"]), (0.05, 500, 1), "the retry takes the setup session off")
        self.assertEqual(second["flags"], [])
        bravo = [unit for unit in report["units"] if unit["unit"] == "bravo"][0]
        self.assertAlmostEqual(bravo["own"]["cost_usd"], 0.05)
        self.assertIn("no report", bravo["flags"])
        self.assertAlmostEqual(report["totals"]["cost_usd"], 0.20, msg="the setup session and three units, each once")
        self.assertEqual((report["totals"]["api_ms"], report["totals"]["turns"]), (2000, 4))
        for unit in report["units"]:
            self.assertGreaterEqual(unit["own"]["cost_usd"], 0)
            self.assertGreaterEqual(unit["own"]["turns"], 0)

    def test_a_unit_whose_every_attempt_has_no_result_report_costs_nothing_in_the_totals(self):
        # SOL-HW-REVIEW-FAN-OUT-DRIVER.C5: Against a stub that reports a fork's cost, API time and turn count cumulatively including its setup session, as the agent command line does, the record gives each fork its own cost, time and turns, the setup session its own, and the run their sum; token usage is taken as each session reports it, split into tokens read from the cache, written to it, fresh and generated, and a fork that reads no cache is flagged. The record is in the text and the JSON report. Out of scope: judging whether a run was worth its cost.
        self.scenario({"units": {"alpha": [{"exit": 3}]}})
        status, text, _ = self.run_command("--bound", "3", as_json=True)
        self.assertEqual(status, 1, text)
        report = json.loads(text)
        alpha = [unit for unit in report["units"] if unit["unit"] == "alpha"][0]
        self.assertEqual((alpha["own"]["cost_usd"], alpha["own"]["api_ms"], alpha["own"]["turns"]), (0.0, 0, 0))
        self.assertEqual(alpha["flags"], ["no report"])
        self.assertAlmostEqual(report["totals"]["cost_usd"], 0.15)

    def test_a_setup_session_or_a_fork_whose_successful_result_report_lacks_or_mistypes_a_figure_is_named(self):
        # SOL-HW-REVIEW-FAN-OUT-DRIVER.C5: Against a stub that reports a fork's cost, API time and turn count cumulatively including its setup session, as the agent command line does, the record gives each fork its own cost, time and turns, the setup session its own, and the run their sum; token usage is taken as each session reports it, split into tokens read from the cache, written to it, fresh and generated, and a fork that reads no cache is flagged. The record is in the text and the JSON report. Out of scope: judging whether a run was worth its cost.
        cases = {"cost": ({"result_omit": ["total_cost_usd"]}, "without total_cost_usd"),
                 "api time": ({"result_omit": ["duration_api_ms"]}, "without duration_api_ms"),
                 "turns mistyped": ({"result_set": {"num_turns": "3"}}, "gives `num_turns` as '3'"),
                 "usage": ({"result_omit": ["usage"]}, "without usage"),
                 "a token count": ({"result_set": {"usage": {"input_tokens": 1}}}, "usage.output_tokens"),
                 "is_error": ({"result_omit": ["is_error"]}, "no `is_error`"),
                 "the text": ({"result_omit": ["result"]}, "without result")}
        for name, (outcome, word) in cases.items():
            with self.subTest(case=name, session="setup"):
                shutil.rmtree(self.out, ignore_errors=True)
                for call in os.listdir(self.log):
                    os.remove(os.path.join(self.log, call))
                self.scenario({"setup": outcome})
                status, text, _ = self.run_command()
                self.assertEqual(status, 1, text)
                self.assertRegex(text, r"REFUSED \| the setup session printed a result report")
                self.assertIn(word, text)
                self.assertEqual(self.forks(), [])
            with self.subTest(case=name, session="fork"):
                shutil.rmtree(self.out, ignore_errors=True)
                for call in os.listdir(self.log):
                    os.remove(os.path.join(self.log, call))
                self.scenario({"units": {"alpha": [outcome]}})
                status, text, _ = self.run_command("--bound", "3", as_json=True)
                self.assertEqual(status, 1, text)
                alpha = [unit for unit in json.loads(text)["units"] if unit["unit"] == "alpha"][0]
                self.assertEqual(alpha["status"], "failed")
                self.assertIn(word, alpha["detail"])
                self.assertEqual(len([call for call in self.forks() if call["unit"] == "alpha"]), 1, "not retried")
                self.assertGreaterEqual(alpha["own"]["cost_usd"], 0)


class MergeBase(unittest.TestCase):
    """A synthetic caller loaded from a temporary folder, for the merge's tests."""

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


class Merge(MergeBase):
    """The merge, over synthetic unit results and a synthetic caller."""

    def results(self):
        return {
            "alpha": {"Verdicts": verdicts(("A-1", "fail", "F2 and R1-F2"), ("B-1", "fail", "F1")),
                      "Findings": [finding(1, "B-1", "gap at the 3V3 pad @U4"), finding(2, "C-1", "silk over a pad")]},
            "bravo": {"Verdicts": verdicts(("A-1", "fail", "F1 beside F2")),
                      "Findings": [finding(1, "A-1", "stub on the clock @U4"), finding(2, "A-1", "stub elsewhere")]},
            "charlie": {"Verdicts": verdicts(("C-1", "pass", "R2-F1 was put right")), "Findings": []},
        }

    def test_the_merge_renumbers_this_round_s_findings_in_the_checklist_s_order_and_rewrites_their_citations(self):
        # SOL-HW-REVIEW-FAN-OUT-DRIVER.C6: Over synthetic unit results and a synthetic caller, the merge rejects a table with a column the caller's table does not have and a verdict outside the caller's set, replaces every finding number a reviewer wrote with the number the checklist's order gives and rewrites the citations of them in the verdict rows, leaves a citation of an earlier round's finding as written, tells the two by the round each citation carries against the round the caller names as this one, and refuses a citation of an earlier round's finding that the review folder's earlier rounds do not hold, reports two findings that the caller's key assigns to the same item or place and keeps both, and gives the same record for every order the units arrive in. For a caller that declares no findings table nothing is renumbered. It reads no model and no file outside the unit results and the review folder. Out of scope: what a caller's tables must cover and whether a verdict is right.
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
        # SOL-HW-REVIEW-FAN-OUT-DRIVER.C6: Over synthetic unit results and a synthetic caller, the merge rejects a table with a column the caller's table does not have and a verdict outside the caller's set, replaces every finding number a reviewer wrote with the number the checklist's order gives and rewrites the citations of them in the verdict rows, leaves a citation of an earlier round's finding as written, tells the two by the round each citation carries against the round the caller names as this one, and refuses a citation of an earlier round's finding that the review folder's earlier rounds do not hold, reports two findings that the caller's key assigns to the same item or place and keeps both, and gives the same record for every order the units arrive in. For a caller that declares no findings table nothing is renumbered. It reads no model and no file outside the unit results and the review folder. Out of scope: what a caller's tables must cover and whether a verdict is right.
        caller = self.caller(FINDINGS.replace('"checklist"', '"first": lambda folder: 8, "checklist"'))
        merged = review_fan_out.merge(caller, self.folder, self.ORDER, self.results())
        self.assertEqual([row["Finding"] for row in merged["tables"]["Findings"]["rows"]], [8, 9, 10, 11])
        self.assertEqual(merged["tables"]["Verdicts"]["rows"][1]["Rests on"], "F10")

    def test_two_findings_the_caller_s_key_puts_at_one_place_are_reported_and_both_kept(self):
        # SOL-HW-REVIEW-FAN-OUT-DRIVER.C6: Over synthetic unit results and a synthetic caller, the merge rejects a table with a column the caller's table does not have and a verdict outside the caller's set, replaces every finding number a reviewer wrote with the number the checklist's order gives and rewrites the citations of them in the verdict rows, leaves a citation of an earlier round's finding as written, tells the two by the round each citation carries against the round the caller names as this one, and refuses a citation of an earlier round's finding that the review folder's earlier rounds do not hold, reports two findings that the caller's key assigns to the same item or place and keeps both, and gives the same record for every order the units arrive in. For a caller that declares no findings table nothing is renumbered. It reads no model and no file outside the unit results and the review folder. Out of scope: what a caller's tables must cover and whether a verdict is right.
        merged = review_fan_out.merge(self.caller(), self.folder, self.ORDER, self.results())
        self.assertEqual(merged["same_place"], [{"key": "U4", "findings": [1, 3], "units": ["alpha", "bravo"]}])
        self.assertEqual(len(merged["tables"]["Findings"]["rows"]), 4, "neither is dropped")
        alone = self.results()
        alone["bravo"]["Findings"][0]["What"] = "stub on the clock"
        self.assertEqual(review_fan_out.merge(self.caller(), self.folder, self.ORDER, alone)["same_place"], [])

    def test_the_merge_gives_one_record_for_every_order_the_units_arrive_in(self):
        # SOL-HW-REVIEW-FAN-OUT-DRIVER.C6: Over synthetic unit results and a synthetic caller, the merge rejects a table with a column the caller's table does not have and a verdict outside the caller's set, replaces every finding number a reviewer wrote with the number the checklist's order gives and rewrites the citations of them in the verdict rows, leaves a citation of an earlier round's finding as written, tells the two by the round each citation carries against the round the caller names as this one, and refuses a citation of an earlier round's finding that the review folder's earlier rounds do not hold, reports two findings that the caller's key assigns to the same item or place and keeps both, and gives the same record for every order the units arrive in. For a caller that declares no findings table nothing is renumbered. It reads no model and no file outside the unit results and the review folder. Out of scope: what a caller's tables must cover and whether a verdict is right.
        caller, results = self.caller(), self.results()
        reference = review_fan_out.merge(caller, self.folder, self.ORDER, results)
        for arrival in itertools.permutations(results):
            arrived = {unit: results[unit] for unit in arrival}
            self.assertEqual(review_fan_out.merge(caller, self.folder, self.ORDER, arrived), reference, arrival)

    def test_the_merge_rejects_a_column_a_verdict_a_table_and_a_citation_the_caller_does_not_have(self):
        # SOL-HW-REVIEW-FAN-OUT-DRIVER.C6: Over synthetic unit results and a synthetic caller, the merge rejects a table with a column the caller's table does not have and a verdict outside the caller's set, replaces every finding number a reviewer wrote with the number the checklist's order gives and rewrites the citations of them in the verdict rows, leaves a citation of an earlier round's finding as written, tells the two by the round each citation carries against the round the caller names as this one, and refuses a citation of an earlier round's finding that the review folder's earlier rounds do not hold, reports two findings that the caller's key assigns to the same item or place and keeps both, and gives the same record for every order the units arrive in. For a caller that declares no findings table nothing is renumbered. It reads no model and no file outside the unit results and the review folder. Out of scope: what a caller's tables must cover and whether a verdict is right.
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

    def test_a_verdict_that_is_not_a_string_is_refused_whatever_collection_the_caller_declares_its_verdicts_in(self):
        # SOL-HW-REVIEW-FAN-OUT-DRIVER.C6: Over synthetic unit results and a synthetic caller, the merge rejects a table with a column the caller's table does not have and a verdict outside the caller's set, replaces every finding number a reviewer wrote with the number the checklist's order gives and rewrites the citations of them in the verdict rows, leaves a citation of an earlier round's finding as written, tells the two by the round each citation carries against the round the caller names as this one, and refuses a citation of an earlier round's finding that the review folder's earlier rounds do not hold, reports two findings that the caller's key assigns to the same item or place and keeps both, and gives the same record for every order the units arrive in. For a caller that declares no findings table nothing is renumbered. It reads no model and no file outside the unit results and the review folder. Out of scope: what a caller's tables must cover and whether a verdict is right.
        for verdicts_in in ('("pass", "fail")', '{"pass", "fail"}', '["pass", "fail"]'):
            caller = self.caller()
            caller.TABLES["Verdicts"]["verdicts"] = eval(verdicts_in)
            for wrong in (["pass"], {"v": 1}, 3, None):
                with self.subTest(verdicts=verdicts_in, wrong=wrong):
                    results = self.results()
                    results["alpha"]["Verdicts"][0]["Verdict"] = wrong
                    with self.assertRaises(review_fan_out.Refused) as caught:
                        review_fan_out.merge(caller, self.folder, self.ORDER, results)
                    self.assertIn(f"has the verdict {wrong!r}", " ".join(caught.exception.causes))

    def test_a_caller_with_no_findings_table_has_nothing_renumbered(self):
        # SOL-HW-REVIEW-FAN-OUT-DRIVER.C6: Over synthetic unit results and a synthetic caller, the merge rejects a table with a column the caller's table does not have and a verdict outside the caller's set, replaces every finding number a reviewer wrote with the number the checklist's order gives and rewrites the citations of them in the verdict rows, leaves a citation of an earlier round's finding as written, tells the two by the round each citation carries against the round the caller names as this one, and refuses a citation of an earlier round's finding that the review folder's earlier rounds do not hold, reports two findings that the caller's key assigns to the same item or place and keeps both, and gives the same record for every order the units arrive in. For a caller that declares no findings table nothing is renumbered. It reads no model and no file outside the unit results and the review folder. Out of scope: what a caller's tables must cover and whether a verdict is right.
        merged = review_fan_out.merge(self.caller(findings="None"), self.folder, self.ORDER, self.results())
        self.assertEqual([row["Finding"] for row in merged["tables"]["Findings"]["rows"]], [1, 2, 1, 2])
        self.assertEqual(merged["tables"]["Verdicts"]["rows"][0]["Rests on"], "F2 and R1-F2", "citations left as written")
        self.assertEqual(merged["same_place"], [])

    def test_the_merge_reads_no_model_and_hands_the_caller_s_check_only_the_folder_the_order_and_the_tables(self):
        # SOL-HW-REVIEW-FAN-OUT-DRIVER.C6: Over synthetic unit results and a synthetic caller, the merge rejects a table with a column the caller's table does not have and a verdict outside the caller's set, replaces every finding number a reviewer wrote with the number the checklist's order gives and rewrites the citations of them in the verdict rows, leaves a citation of an earlier round's finding as written, tells the two by the round each citation carries against the round the caller names as this one, and refuses a citation of an earlier round's finding that the review folder's earlier rounds do not hold, reports two findings that the caller's key assigns to the same item or place and keeps both, and gives the same record for every order the units arrive in. For a caller that declares no findings table nothing is renumbered. It reads no model and no file outside the unit results and the review folder. Out of scope: what a caller's tables must cover and whether a verdict is right.
        caller = self.caller(check='[f"saw {len(tables)} tables of {len(units)} units in " + os.path.basename(folder)]')
        with mock.patch("subprocess.run", side_effect=AssertionError("the merge started a program")), \
                mock.patch("builtins.open", side_effect=AssertionError("the merge opened a file")):
            with self.assertRaises(review_fan_out.Refused) as caught:
                review_fan_out.merge(caller, self.folder, self.ORDER, self.results())
        self.assertEqual(caught.exception.causes, [f"saw 2 tables of 3 units in {os.path.basename(self.folder)}"])


class RoundedMerge(MergeBase):
    """The merge for a caller whose citations carry the round, over the same units."""

    def results(self):
        return {
            "alpha": {"Verdicts": verdicts(("A-1", "fail", "2.1 and 1.3"), ("B-1", "fail", "1.1 stays; 2.2 is raised")),
                      "Findings": [finding(1, "B-1", "gap at the 3V3 pad"), finding(2, "C-1", "silk over a pad")]},
            "bravo": {"Verdicts": verdicts(("A-1", "fail", "2.1")),
                      "Findings": [finding(1, "A-1", "stub on the clock"), finding(2, "A-1", "stub elsewhere")]},
            "charlie": {"Verdicts": verdicts(("C-1", "pass", "1.2 was put right")), "Findings": []},
        }

    def merged(self, results=None):
        return review_fan_out.merge(self.caller(ROUNDED), self.folder, self.ORDER, results or self.results())

    def refused(self, edit, *words):
        results = self.results()
        edit(results)
        with self.assertRaises(review_fan_out.Refused) as caught:
            self.merged(results)
        for word in words:
            self.assertIn(word, " ".join(caught.exception.causes))

    def test_a_cell_citing_this_round_s_finding_and_an_earlier_round_s_renumbers_only_this_round_s(self):
        # SOL-HW-REVIEW-FAN-OUT-DRIVER.C6: Over synthetic unit results and a synthetic caller, the merge rejects a table with a column the caller's table does not have and a verdict outside the caller's set, replaces every finding number a reviewer wrote with the number the checklist's order gives and rewrites the citations of them in the verdict rows, leaves a citation of an earlier round's finding as written, tells the two by the round each citation carries against the round the caller names as this one, and refuses a citation of an earlier round's finding that the review folder's earlier rounds do not hold, reports two findings that the caller's key assigns to the same item or place and keeps both, and gives the same record for every order the units arrive in. For a caller that declares no findings table nothing is renumbered. It reads no model and no file outside the unit results and the review folder. Out of scope: what a caller's tables must cover and whether a verdict is right.
        rows = self.merged()["tables"]["Verdicts"]["rows"]
        self.assertEqual(rows[0]["Rests on"], "2.3 and 1.3", "alpha's 2.1 is its B-1 finding, now 3; round 1's 1.3 is left")
        self.assertEqual(rows[2]["Rests on"], "2.1", "bravo's own 1 stays 1")

    def test_an_earlier_round_s_citation_is_left_while_the_unit_owns_a_finding_of_the_same_number(self):
        # SOL-HW-REVIEW-FAN-OUT-DRIVER.C6: Over synthetic unit results and a synthetic caller, the merge rejects a table with a column the caller's table does not have and a verdict outside the caller's set, replaces every finding number a reviewer wrote with the number the checklist's order gives and rewrites the citations of them in the verdict rows, leaves a citation of an earlier round's finding as written, tells the two by the round each citation carries against the round the caller names as this one, and refuses a citation of an earlier round's finding that the review folder's earlier rounds do not hold, reports two findings that the caller's key assigns to the same item or place and keeps both, and gives the same record for every order the units arrive in. For a caller that declares no findings table nothing is renumbered. It reads no model and no file outside the unit results and the review folder. Out of scope: what a caller's tables must cover and whether a verdict is right.
        rows = self.merged()["tables"]["Verdicts"]["rows"]
        self.assertEqual(rows[1]["Rests on"], "1.1 stays; 2.4 is raised", "round 1's 1.1 is not alpha's finding 1")
        self.assertEqual(rows[3]["Rests on"], "1.2 was put right")

    def test_a_citation_of_an_earlier_round_the_review_folder_does_not_hold_is_refused_naming_the_cell(self):
        # SOL-HW-REVIEW-FAN-OUT-DRIVER.C6: Over synthetic unit results and a synthetic caller, the merge rejects a table with a column the caller's table does not have and a verdict outside the caller's set, replaces every finding number a reviewer wrote with the number the checklist's order gives and rewrites the citations of them in the verdict rows, leaves a citation of an earlier round's finding as written, tells the two by the round each citation carries against the round the caller names as this one, and refuses a citation of an earlier round's finding that the review folder's earlier rounds do not hold, reports two findings that the caller's key assigns to the same item or place and keeps both, and gives the same record for every order the units arrive in. For a caller that declares no findings table nothing is renumbered. It reads no model and no file outside the unit results and the review folder. Out of scope: what a caller's tables must cover and whether a verdict is right.
        self.refused(lambda r: r["alpha"]["Verdicts"][0].update(**{"Rests on": "see 1.9"}),
                     "unit alpha", "'Rests on'", "'see 1.9'", "'1.9'", "round 1", "earlier rounds do not hold")
        self.refused(lambda r: r["charlie"]["Verdicts"][0].update(**{"Rests on": "3.1"}), "'3.1'", "round 3")

    def test_a_citation_of_this_round_s_finding_the_unit_did_not_raise_is_refused(self):
        # SOL-HW-REVIEW-FAN-OUT-DRIVER.C6: Over synthetic unit results and a synthetic caller, the merge rejects a table with a column the caller's table does not have and a verdict outside the caller's set, replaces every finding number a reviewer wrote with the number the checklist's order gives and rewrites the citations of them in the verdict rows, leaves a citation of an earlier round's finding as written, tells the two by the round each citation carries against the round the caller names as this one, and refuses a citation of an earlier round's finding that the review folder's earlier rounds do not hold, reports two findings that the caller's key assigns to the same item or place and keeps both, and gives the same record for every order the units arrive in. For a caller that declares no findings table nothing is renumbered. It reads no model and no file outside the unit results and the review folder. Out of scope: what a caller's tables must cover and whether a verdict is right.
        self.refused(lambda r: r["charlie"]["Verdicts"][0].update(**{"Rests on": "2.7"}), "cites a finding 7 the unit did not raise")

    def test_a_caller_with_a_round_group_gives_one_record_for_every_order_the_units_arrive_in(self):
        # SOL-HW-REVIEW-FAN-OUT-DRIVER.C6: Over synthetic unit results and a synthetic caller, the merge rejects a table with a column the caller's table does not have and a verdict outside the caller's set, replaces every finding number a reviewer wrote with the number the checklist's order gives and rewrites the citations of them in the verdict rows, leaves a citation of an earlier round's finding as written, tells the two by the round each citation carries against the round the caller names as this one, and refuses a citation of an earlier round's finding that the review folder's earlier rounds do not hold, reports two findings that the caller's key assigns to the same item or place and keeps both, and gives the same record for every order the units arrive in. For a caller that declares no findings table nothing is renumbered. It reads no model and no file outside the unit results and the review folder. Out of scope: what a caller's tables must cover and whether a verdict is right.
        caller, results = self.caller(ROUNDED), self.results()
        reference = review_fan_out.merge(caller, self.folder, self.ORDER, results)
        for arrival in itertools.permutations(results):
            arrived = {unit: results[unit] for unit in arrival}
            self.assertEqual(review_fan_out.merge(caller, self.folder, self.ORDER, arrived), reference, arrival)

    def test_a_caller_with_a_round_group_and_no_round_or_no_earlier_set_is_refused(self):
        # SOL-HW-REVIEW-FAN-OUT-DRIVER.C6: Over synthetic unit results and a synthetic caller, the merge rejects a table with a column the caller's table does not have and a verdict outside the caller's set, replaces every finding number a reviewer wrote with the number the checklist's order gives and rewrites the citations of them in the verdict rows, leaves a citation of an earlier round's finding as written, tells the two by the round each citation carries against the round the caller names as this one, and refuses a citation of an earlier round's finding that the review folder's earlier rounds do not hold, reports two findings that the caller's key assigns to the same item or place and keeps both, and gives the same record for every order the units arrive in. For a caller that declares no findings table nothing is renumbered. It reads no model and no file outside the unit results and the review folder. Out of scope: what a caller's tables must cover and whether a verdict is right.
        for dropped, word in (('"round": lambda folder: "2", ', "FINDINGS['round']"),
                              (', "earlier": lambda folder: {("1", 1), ("1", 2), ("1", 3)}', "FINDINGS['earlier']")):
            with self.subTest(dropped=word):
                self.assertIn(dropped, ROUNDED)
                with self.assertRaises(review_fan_out.Refused) as caught:
                    self.caller(ROUNDED.replace(dropped, ""))
                self.assertIn(word, " ".join(caught.exception.causes))

    def test_a_caller_s_round_or_earlier_hook_that_raises_is_refused_naming_the_hook(self):
        # SOL-HW-REVIEW-FAN-OUT-DRIVER.C6: Over synthetic unit results and a synthetic caller, the merge rejects a table with a column the caller's table does not have and a verdict outside the caller's set, replaces every finding number a reviewer wrote with the number the checklist's order gives and rewrites the citations of them in the verdict rows, leaves a citation of an earlier round's finding as written, tells the two by the round each citation carries against the round the caller names as this one, and refuses a citation of an earlier round's finding that the review folder's earlier rounds do not hold, reports two findings that the caller's key assigns to the same item or place and keeps both, and gives the same record for every order the units arrive in. For a caller that declares no findings table nothing is renumbered. It reads no model and no file outside the unit results and the review folder. Out of scope: what a caller's tables must cover and whether a verdict is right.
        for hook in ("round", "earlier"):
            findings = ROUNDED.replace(f'"{hook}": lambda folder: ' + ('"2"' if hook == "round" else '{("1", 1), ("1", 2), ("1", 3)}'),
                                       f'"{hook}": lambda folder: {{}}["x"]')
            with self.assertRaises(review_fan_out.Refused) as caught:
                review_fan_out.merge(self.caller(findings), self.folder, self.ORDER, self.results())
            self.assertIn(f"the caller's {hook} raised KeyError", " ".join(caught.exception.causes))
            self.assertIn("fix the caller", " ".join(caught.exception.causes))

    def test_a_pattern_with_no_round_group_still_matches_this_round_s_citations_only(self):
        # SOL-HW-REVIEW-FAN-OUT-DRIVER.C6: Over synthetic unit results and a synthetic caller, the merge rejects a table with a column the caller's table does not have and a verdict outside the caller's set, replaces every finding number a reviewer wrote with the number the checklist's order gives and rewrites the citations of them in the verdict rows, leaves a citation of an earlier round's finding as written, tells the two by the round each citation carries against the round the caller names as this one, and refuses a citation of an earlier round's finding that the review folder's earlier rounds do not hold, reports two findings that the caller's key assigns to the same item or place and keeps both, and gives the same record for every order the units arrive in. For a caller that declares no findings table nothing is renumbered. It reads no model and no file outside the unit results and the review folder. Out of scope: what a caller's tables must cover and whether a verdict is right.
        merged = review_fan_out.merge(self.caller(), self.folder, self.ORDER, Merge.results(self))
        self.assertEqual(merged["tables"]["Verdicts"]["rows"][0]["Rests on"], "F4 and R1-F2")


class Rerun(Fixture):
    def test_named_units_are_run_again_in_a_new_setup_session_and_merged_with_the_kept_results(self):
        # SOL-HW-REVIEW-FAN-OUT-DRIVER.C8: The command keeps each unit's result in its output folder. Given the names of units to run again, it runs only those, replaces their results, and merges again; it refuses a name that is not a unit of the review and refuses a run that leaves out a unit whose last run again failed, naming that unit, and the record shows which units were run again and when, and that a new setup session was started for them. A unit that failed, or that needs a view the round's starter has since rendered, is therefore run without repeating the others. Out of scope: deciding which units to run again.
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
        # SOL-HW-REVIEW-FAN-OUT-DRIVER.C8: The command keeps each unit's result in its output folder. Given the names of units to run again, it runs only those, replaces their results, and merges again; it refuses a name that is not a unit of the review and refuses a run that leaves out a unit whose last run again failed, naming that unit, and the record shows which units were run again and when, and that a new setup session was started for them. A unit that failed, or that needs a view the round's starter has since rendered, is therefore run without repeating the others. Out of scope: deciding which units to run again.
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
        # SOL-HW-REVIEW-FAN-OUT-DRIVER.C8: The command keeps each unit's result in its output folder. Given the names of units to run again, it runs only those, replaces their results, and merges again; it refuses a name that is not a unit of the review and refuses a run that leaves out a unit whose last run again failed, naming that unit, and the record shows which units were run again and when, and that a new setup session was started for them. A unit that failed, or that needs a view the round's starter has since rendered, is therefore run without repeating the others. Out of scope: deciding which units to run again.
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
        # SOL-HW-REVIEW-FAN-OUT-DRIVER.C8: The command keeps each unit's result in its output folder. Given the names of units to run again, it runs only those, replaces their results, and merges again; it refuses a name that is not a unit of the review and refuses a run that leaves out a unit whose last run again failed, naming that unit, and the record shows which units were run again and when, and that a new setup session was started for them. A unit that failed, or that needs a view the round's starter has since rendered, is therefore run without repeating the others. Out of scope: deciding which units to run again.
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


    def failed_rerun_of_alpha(self):
        self.run_command()
        self.scenario({"units": {"alpha": [{"exit": 1}]}})
        status, text, _ = self.run_command("--rerun", "alpha")
        self.assertEqual(status, 1, text)
        self.assertTrue(os.path.isfile(os.path.join(self.out, "failed", "alpha.json")))
        for name in os.listdir(self.log):
            os.remove(os.path.join(self.log, name))
        self.scenario({})

    def test_a_run_that_leaves_out_a_unit_whose_last_run_again_failed_is_refused_naming_it(self):
        # SOL-HW-REVIEW-FAN-OUT-DRIVER.C8: The command keeps each unit's result in its output folder. Given the names of units to run again, it runs only those, replaces their results, and merges again; it refuses a name that is not a unit of the review and refuses a run that leaves out a unit whose last run again failed, naming that unit, and the record shows which units were run again and when, and that a new setup session was started for them. A unit that failed, or that needs a view the round's starter has since rendered, is therefore run without repeating the others. Out of scope: deciding which units to run again.
        self.failed_rerun_of_alpha()
        record = os.path.join(self.out, "record.json")
        with open(record, encoding="utf-8") as handle:
            before = handle.read()
        for as_json in (False, True):
            status, text, _ = self.run_command("--rerun", "bravo", as_json=as_json)
            self.assertEqual(status, 1, text)
            if as_json:
                self.assertTrue(any("unit alpha's last run again failed" in why and "name alpha with --rerun too" in why
                                    for why in json.loads(text)["refusals"]))
            else:
                self.assertIn("REFUSED | unit alpha's last run again failed, so its kept result is not settled; name alpha with --rerun too", text)
        self.assertEqual(self.calls(), [], "nothing was started")
        with open(record, encoding="utf-8") as handle:
            self.assertEqual(handle.read(), before, "the earlier record stands")
        self.assertFalse(os.path.exists(os.path.join(self.out, review_fan_out.LOCK)))
        status, text, _ = self.run_command("--rerun", "bravo", "--rerun", "alpha")
        self.assertEqual(status, 0, "named too, it is run again with the other: " + text)
        self.assertFalse(os.path.exists(os.path.join(self.out, "failed", "alpha.json")), "a successful run again clears it")

    def test_a_successful_run_again_of_the_unit_clears_what_made_a_later_run_refuse(self):
        # SOL-HW-REVIEW-FAN-OUT-DRIVER.C8: The command keeps each unit's result in its output folder. Given the names of units to run again, it runs only those, replaces their results, and merges again; it refuses a name that is not a unit of the review and refuses a run that leaves out a unit whose last run again failed, naming that unit, and the record shows which units were run again and when, and that a new setup session was started for them. A unit that failed, or that needs a view the round's starter has since rendered, is therefore run without repeating the others. Out of scope: deciding which units to run again.
        self.failed_rerun_of_alpha()
        status, text, _ = self.run_command("--rerun", "alpha")
        self.assertEqual(status, 0, text)
        self.assertFalse(os.path.exists(os.path.join(self.out, "failed", "alpha.json")))
        status, text, _ = self.run_command("--rerun", "bravo")
        self.assertEqual(status, 0, "alpha is settled, so bravo alone may be run again: " + text)

    def test_a_failed_record_that_cannot_be_read_is_a_named_refusal_and_not_a_traceback(self):
        # SOL-HW-REVIEW-FAN-OUT-DRIVER.C8: The command keeps each unit's result in its output folder. Given the names of units to run again, it runs only those, replaces their results, and merges again; it refuses a name that is not a unit of the review and refuses a run that leaves out a unit whose last run again failed, naming that unit, and the record shows which units were run again and when, and that a new setup session was started for them. A unit that failed, or that needs a view the round's starter has since rendered, is therefore run without repeating the others. Out of scope: deciding which units to run again.
        self.run_command()
        for content in ("{not json", "{}"):
            with self.subTest(content=content):
                self.write(os.path.join(self.out, "failed", "charlie.json"), content)
                status, text, _ = self.run_command("--rerun", "alpha")
                self.assertEqual(status, 1, text)
                self.assertRegex(text, r"REFUSED \| the record of unit charlie's failed attempts .*charlie\.json cannot be read")
                self.assertIn("delete it", text)
                self.assertNotIn("Traceback", text)
        self.assertFalse(os.path.exists(os.path.join(self.out, review_fan_out.LOCK)))

    def test_a_failed_record_that_turns_unreadable_mid_run_is_that_unit_s_failure_and_not_a_traceback(self):
        # SOL-HW-REVIEW-FAN-OUT-DRIVER.C8: The command keeps each unit's result in its output folder. Given the names of units to run again, it runs only those, replaces their results, and merges again; it refuses a name that is not a unit of the review and refuses a run that leaves out a unit whose last run again failed, naming that unit, and the record shows which units were run again and when, and that a new setup session was started for them. A unit that failed, or that needs a view the round's starter has since rendered, is therefore run without repeating the others. Out of scope: deciding which units to run again.
        self.scenario({"units": {"alpha": [{"exit": 1}]}})
        real = review_fan_out.Run.failed_sessions

        def unreadable(run, unit):
            if unit == "alpha":
                raise review_fan_out.Refused(["bad json"])
            return real(run, unit)
        with mock.patch.object(review_fan_out.Run, "failed_sessions", unreadable):
            status, text, _ = self.run_command("--bound", "3")
        self.assertEqual(status, 1, text)
        self.assertRegex(text, r"FAILED \| unit alpha failed after 2 attempts; .*its cost could not be kept \(bad json\)")
        self.assertNotIn("Traceback", text)


#: A field the hostile value leaves out, rather than a value it gives.
ABSENT = "<absent>"
#: The hostile values every field the command reads is driven with: absent, null, the wrong type, an empty string, a
#: non-finite number, a negative number, a number too large to be a float, and nested garbage.
HOSTILE = {"absent": ABSENT, "null": None, "wrong type": True, "empty string": "", "not finite": float("inf"),
           "not a number": float("nan"), "negative": -1, "too large": 10 ** 400, "nested garbage": {"a": [None, {"b": []}]}}


def hostile(*names, **instead):
    """The hostile values named (all when none), with any given `instead` for a field the default does not mistype."""
    return {**{name: HOSTILE[name] for name in (names or HOSTILE)}, **{name.replace("_", " "): value for name, value in instead.items()}}


def tool_line(use_id, path="notes/absent.md"):
    return json.dumps({"type": "assistant", "message": {"content": [
        {"type": "tool_use", "id": use_id, "name": "Read", "input": {"file_path": path}}]}})


def failed_result_line(use_id, flag=True):
    return json.dumps({"type": "user", "message": {"content": [
        {"type": "tool_result", "tool_use_id": use_id, "is_error": flag, "content": "File does not exist."}]}})


def assistant_line(*blocks):
    return json.dumps({"type": "assistant", "message": {"content": list(blocks)}})


#: Every input the command reads from outside itself, by class: the field, the hostile values it is driven with and the
#: words the named outcome must hold. The tests below drive each through `main` against the stub, or, for a site the stub
#: cannot reach, through the function that reads it.
INVENTORY = {
    # The start report (`system` event, subtype `init`) of the setup session and of every fork.
    "start report": {field: hostile() for field in ("model", "cwd", "session_id", "tools", "mcp_servers", "skills",
                                                    "slash_commands", "plugins")},
    # The result report (`result` event) of the setup session and of every fork, each figure and token count.
    "result report": {"is_error": hostile(wrong_type="false", a_number=0),
                      **{field: hostile() for field in ("result", "total_cost_usd", "duration_api_ms", "num_turns", "usage")},
                      **{f"usage.{field}": hostile() for field in ("input_tokens", "output_tokens",
                                                                    "cache_read_input_tokens", "cache_creation_input_tokens")},
                      # Not relied on, so absent or null is accepted; typed when present.
                      "session_id": hostile("wrong type", "not finite", "negative", "nested garbage")},
    # The stream's framing, its assistant events and blocks, and the tool results of its user events.
    "stream": {
        "a line": {"not JSON": ["not json"], "a JSON array": ["[1]"], "a JSON null": ["null"], "a JSON string": ['"x"'],
                   "deeply nested": ["[" * 100000 + "]" * 100000]},
        "an event's type": {"absent": ["{}"], "null": ['{"type": null}'], "wrong type": ['{"type": 5}'],
                            "nested garbage": ['{"type": {"a": []}}']},
        "a second report": {"start": [json.dumps({"type": "system", "subtype": "init"})],
                            "result": [json.dumps({"type": "result", "is_error": False, "result": "x"})]},
        "an assistant event's message.content": {
            "absent": ['{"type": "assistant"}'], "null": ['{"type": "assistant", "message": null}'],
            "wrong type": ['{"type": "assistant", "message": {"content": "x"}}'],
            "nested garbage": ['{"type": "assistant", "message": {"content": {"a": [null]}}}']},
        "a content block": {"null": [assistant_line(None)], "wrong type": [assistant_line(5)], "no type": [assistant_line({})],
                            "empty type": [assistant_line({"type": ""})], "nested type": [assistant_line({"type": ["text"]})]},
        "a text block's text": {name: [assistant_line({"type": "text"} if value is ABSENT else {"type": "text", "text": value})]
                                for name, value in hostile("absent", "null", "wrong type", "not finite", "nested garbage").items()},
        "a tool use's name": {name: [assistant_line({"type": "tool_use", "input": {}} if value is ABSENT else
                                                    {"type": "tool_use", "name": value, "input": {}})]
                              for name, value in hostile("absent", "null", "wrong type", "empty string", "nested garbage").items()},
        "a tool use's input": {name: [assistant_line({"type": "tool_use", "name": "Grep"} if value is ABSENT else
                                                     {"type": "tool_use", "name": "Grep", "input": value})]
                               for name, value in hostile("absent", "null", "wrong type", "empty string",
                                                          a_list=[{"a": None}]).items()},
        "a Read's input.file_path": {name: [tool_line("toolu_x", value)] for name, value in
                                     {**hostile("null", "wrong type", "empty string", "nested garbage"),
                                      "a NUL byte": "notes/\u0000x.md"}.items()},
        # A read that opened nothing is excused only by a tool result naming its id as a string and marked failed with true.
        "a tool use's id": {name: [tool_line(value), failed_result_line(value)] for name, value in
                            hostile("null", "wrong type", "empty string", "negative", "nested garbage").items()},
        "a tool result's is_error": {name: [tool_line("toolu_x"), failed_result_line("toolu_x", value)] for name, value in
                                     {**hostile("null", "empty string", "negative", "nested garbage"), "the text true": "true"}.items()},
        "a user event": {"null message": [tool_line("toolu_x"), '{"type": "user", "message": null}'],
                         "text content": [tool_line("toolu_x"), '{"type": "user", "message": {"content": "x"}}'],
                         "garbage items": [tool_line("toolu_x"), '{"type": "user", "message": {"content": [null, 5, [], {"type": 5}]}}']},
        "the output's bytes": {"not UTF-8": "garbled"},
    },
    # The exit status and error stream of a session, and a program that cannot be started.
    "exit": {"an error exit with no result report": {"exit": 255}, "a clean exit with no result report": {"no_result": True},
             "an error stream that is not UTF-8": {"exit": 1, "garbled": True}},
    # What `auth status` prints and its exit status.
    "auth status": {"empty": ("", 0), "not JSON": ("logged in", 0), "an empty object": ("{}", 0), "null": ("null", 0),
                    "loggedIn null": ('{"loggedIn": null}', 0), "loggedIn the text false": ('{"loggedIn": "false"}', 0),
                    "loggedIn the text true": ('{"loggedIn": "true"}', 0), "loggedIn one": ('{"loggedIn": 1}', 0),
                    "an array": ("[true]", 0), "loggedIn false": ('{"loggedIn": false}', 0),
                    "loggedIn true with an error exit": ('{"loggedIn": true}', 1), "not UTF-8": (None, 0)},
    # The records the output folder keeps, read back on a run again.
    "folder records": {
        record: {"not JSON": "{not json", "empty": "", "null": "null", "wrong type": "5", "empty string": '""',
                 "nested garbage": '{"a": [null, {"b": []}]}', "a folder": None}
        for record in ("setups.json", "reruns.json", "units/bravo.json", "units/alpha.json", "failed/bravo.json")},
    # A field of a kept record, edited in place: (record, how to edit it, the words).
    "folder record fields": {
        "a setup session's cost not finite": ("setups.json", lambda r: r[0].update(cost_usd=float("nan")), "cost_usd"),
        "a setup session's turns negative": ("setups.json", lambda r: r[0].update(turns=-1), "turns"),
        "a setup session's tokens absent": ("setups.json", lambda r: r[0].pop("tokens"), "tokens"),
        "a kept session's cost infinite": ("units/bravo.json", lambda r: r["sessions"][0].update(cost_usd=float("inf")), "cost_usd"),
        "a kept session's tokens garbage": ("units/bravo.json", lambda r: r["sessions"][0].update(tokens={"a": []}), "tokens"),
        "a kept result's sessions empty": ("units/bravo.json", lambda r: r.update(sessions=[]), "no attempt"),
        "a kept result naming another unit": ("units/bravo.json", lambda r: r.update(unit="alpha"), "holds unit 'alpha'"),
        "a kept result citing no kept setup": ("units/bravo.json", lambda r: r.update(setup=7), "cites setup session 7"),
        "a kept result's setup negative": ("units/bravo.json", lambda r: r.update(setup=-1), "setup"),
        "a failed attempt's figure too large": ("failed/bravo.json", lambda r: r[0].update(api_ms=10 ** 400), "api_ms"),
        "a run again's units garbage": ("reruns.json", lambda r: r[0].update(units=[None]), "units"),
    },
    # The caller module's attributes, as its source gives them: (what is replaced, by what).
    "caller attributes": {
        **{f"SETUP_PROMPT {name}": ('SETUP_PROMPT = "Read every document in the review folder."', f"SETUP_PROMPT = {value}")
           for name, value in {"null": "None", "a number": "5", "empty": '""', "blank": '"  "', "a list": '["x"]'}.items()},
        **{f"{attribute} not callable": (f"def {attribute}(", f"{attribute} = 5\ndef _{attribute}(")
           for attribute in ("unit_prompt", "units", "CHECK")},
        **{f"TABLES {name}": ("TABLES = {", f"TABLES = {value}\n_TABLES = {{") for name, value in {
            "null": "None", "empty": "{}", "a list": "[]", "a table that is null": '{"Verdicts": None}',
            "columns as text": '{"Verdicts": {"columns": "Item"}}', "no columns": '{"Verdicts": {"columns": []}}',
            "a column twice": '{"Verdicts": {"columns": ["Item", "Item"]}}',
            "a verdict column it does not have": '{"Verdicts": {"columns": ["Item"], "verdict_column": "V", "verdicts": ["p"]}}',
            "verdicts null": '{"Verdicts": {"columns": ["Item", "V"], "verdict_column": "V", "verdicts": None}}',
            "columns as a set": '{"Verdicts": {"columns": {"Item", "Verdict"}}}',
            "columns as a frozenset": '{"Verdicts": {"columns": frozenset({"Item", "Verdict"})}}',
            "a verdict column that is a list": '{"Verdicts": {"columns": ["Item", "V"], "verdict_column": [], "verdicts": ["p"]}}',
            "a verdict column that is a mapping": '{"Verdicts": {"columns": ["Item", "V"], "verdict_column": {}, "verdicts": ["p"]}}'}.items()},
        **{f"FINDINGS {name}": ("FINDINGS = {", f"FINDINGS = {value}\n_FINDINGS = {{") for name, value in {
            "a number": "5", "an empty mapping": "{}", "a list": "[]"}.items()},
        "FINDINGS table it does not have": ('"table": "Findings"', '"table": "Nope"'),
        **{f"FINDINGS table as {name}": ('"table": "Findings"', f'"table": {value}')
           for name, value in {"a list": "[]", "a mapping": "{}", "a set": '{"Findings"}', "a number": "5", "null": "None"}.items()},
        **{f"FINDINGS number column as {name}": ('"number": "Finding"', f'"number": {value}')
           for name, value in {"a list": "[]", "a mapping": "{}"}.items()},
        **{f"FINDINGS citations table as {name}": ('"citations": [("Verdicts", "Rests on")]', f'"citations": [({value}, "Rests on")]')
           for name, value in {"a list": "[]", "a mapping": "{}", "a set": '{"Verdicts"}', "a number": "5"}.items()},
        **{f"FINDINGS citations column as {name}": ('"citations": [("Verdicts", "Rests on")]', f'"citations": [("Verdicts", {value})]')
           for name, value in {"a list": "[]", "a mapping": "{}", "a set": '{"Rests on"}'}.items()},
        "FINDINGS citations as a mapping": ('"citations": [("Verdicts", "Rests on")]', '"citations": {"Verdicts": "Rests on"}'),
        "FINDINGS number column it does not have": ('"number": "Finding"', '"number": "Nope"'),
        "FINDINGS checklist as a set": ('"checklist": ["A-1", "B-1", "C-1"]', '"checklist": {"A-1", "B-1"}'),
        "FINDINGS checklist garbage": ('"checklist": ["A-1", "B-1", "C-1"]', '"checklist": [None, 5]'),
        "FINDINGS citations garbage": ('"citations": [("Verdicts", "Rests on")]', '"citations": [("Verdicts",)]'),
        "FINDINGS citation as text": ('"citation": re.compile(r"(?<![\\w-])F(?P<number>\\d+)\\b")', '"citation": "F1"'),
        "FINDINGS citation with no number group": ('"citation": re.compile(r"(?<![\\w-])F(?P<number>\\d+)\\b")',
                                                   '"citation": re.compile(r"F\\d+")'),
        "FINDINGS key not callable": ('"key": lambda row', '"key": 5, "_key": lambda row'),
        "FINDINGS first not callable": ('"key": lambda row', '"first": 3, "key": lambda row'),
    },
    # What each of the caller's hooks returns: (hook, the source of the return).
    "caller hooks": {
        **{f"units returns {name}": ("units", value) for name, value in
           {"text": '"abc"', "null": "None", "a number": "5", "a mapping": '{"alpha": 1}'}.items()},
        **{f"unit_prompt returns {name}": ("unit_prompt", value) for name, value in
           {"null": "None", "a number": "5", "empty": '""', "nested garbage": '{"a": []}'}.items()},
        **{f"CHECK returns {name}": ("CHECK", value) for name, value in
           {"text": '"refused"', "null": "None", "a list of numbers": "[5]", "a mapping": '{"a": 1}'}.items()},
        **{f"round returns {name}": ("round", value) for name, value in {"a number": "2", "null": "None", "empty": '""'}.items()},
        **{f"earlier returns {name}": ("earlier", value) for name, value in
           {"numbers as text": '{("1", "1")}', "rounds as numbers": "{(1, 1)}", "null": "None", "a zero": '{("1", 0)}',
            "text": '"1.1"', "a triple": '{("1", 1, 2)}'}.items()},
        **{f"first returns {name}": ("first", value) for name, value in
           {"text": '"8"', "zero": "0", "negative": "-1", "true": "True", "a fraction": "1.5", "infinite": 'float("inf")'}.items()},
        **{f"key returns {name}": ("key", value) for name, value in
           {"a number": "5", "a list": "[]", "empty": '""'}.items()},
    },
    # The tables a reviewer returns as its answer.
    "reviewer tables": {
        "not JSON": "not json", "null": "null", "a list": "[]", "deeply nested": "[" * 100000 + "]" * 100000,
        "tables null": '{"tables": null}', "tables a list": '{"tables": []}', "a table as text": '{"tables": {"Verdicts": "x"}}',
        "a row null": '{"tables": {"Verdicts": [null]}}',
        **{f"a cell {name}": json.dumps({"tables": {"Verdicts": [{"Item": "A-1", "Verdict": "pass", "Rests on": value}]}})
           for name, value in {"null": None, "true": True, "not finite": float("inf"), "not a number": float("nan"),
                               "nested garbage": {"a": [None]}}.items()},
        "a cell too large": '{"tables": {"Verdicts": [{"Item": "A-1", "Verdict": "pass", "Rests on": 1' + "0" * 400 + '}]}}',
        **{f"a verdict {name}": json.dumps({"tables": {"Verdicts": [{"Item": "A-1", "Verdict": value, "Rests on": "x"}]}})
           for name, value in {"null": None, "a number": 5, "empty": "", "nested garbage": ["pass"]}.items()},
        **{f"a finding number {name}": json.dumps({"tables": {"Verdicts": verdicts(("A-1", "fail", "F1")),
                                                               "Findings": [finding(value, "A-1", "x")]}})
           for name, value in {"negative": -1, "text": "1", "a fraction": 1.5, "true": True, "not finite": float("inf")}.items()},
        "a finding item nested": json.dumps({"tables": {"Verdicts": verdicts(("A-1", "fail", "F1")),
                                                         "Findings": [finding(1, {"a": "A-1"}, "x")]}}),
    },
    # The command line's own arguments: (the arguments, the words).
    "arguments": {
        **{f"--rate-limit-wait {value}": (("--rate-limit-wait", value), "rate limit wait") for value in ("nan", "inf", "-1", "x", "")},
        **{f"--model {value!r}": (("--model", value), "the model") for value in ("", "  ")},
        **{f"--bound {value}": (("--bound", value), "the bound") for value in ("0", "-1", "x", "1.5")},
    },
}


class HostileInputs(Fixture):
    """Every input of the inventory, driven with hostile values through the command as shipped.

    Each outcome is a named REFUSED, CANNOT RUN or unit FAILED line: never a traceback, never a pass and never a value
    coerced into shape.
    """

    def setUp(self):
        super().setUp()
        # Each case writes a caller module of its own in one second; a cached compile of an earlier one must not stand in.
        patcher = mock.patch.object(sys, "dont_write_bytecode", True)
        patcher.start()
        self.addCleanup(patcher.stop)

    def fresh(self):
        shutil.rmtree(self.out, ignore_errors=True)
        for name in os.listdir(self.log):
            os.remove(os.path.join(self.log, name))

    def outcome(self, *extra, caller="synth", as_json=False):
        try:
            return self.run_command(*extra, caller=caller, as_json=as_json)
        except BaseException as error:  # a traceback out of the command is the failure this class looks for
            self.fail(f"the command raised {type(error).__name__}: {error}")

    def assert_refused(self, words, *extra, caller="synth", started=None):
        status, text, err = self.outcome(*extra, caller=caller)
        self.assertEqual(status, 1, text + err)
        lines = [line for line in text.splitlines() if line.startswith("REFUSED | ")]
        self.assertTrue(any(all(word in line for word in words) for line in lines), f"{words} in {lines}")
        self.assertRegex(text.splitlines()[-1], r"^RESULT \| REFUSED \| ")
        if started is not None:
            self.assertEqual(len(self.calls()), started, "the sessions started before the refusal")
        return text

    def assert_unit_failed(self, unit, words, *extra, caller="synth", status=1):
        got, text, err = self.outcome(*extra, caller=caller, as_json=True)
        self.assertEqual(got, status, text + err)
        report = json.loads(text)
        failed = [entry for entry in report["units"] if entry["unit"] == unit]
        self.assertEqual([entry["status"] for entry in failed], ["failed"], text)
        for word in words:
            self.assertIn(word, failed[0]["detail"])
        self.assertIn(report["result"], ("FAILED", "CANNOT RUN"))
        self.assertFalse(os.path.exists(os.path.join(self.out, "record.json")), "no record is written")
        for part in [report["totals"]] + [entry["own"] for entry in report["units"]]:
            for key in ("cost_usd", "api_ms", "turns"):
                self.assertTrue(review_fan_out.named(part[key], (int, float)), (key, part[key]))
        return report

    def test_every_field_of_a_start_report_that_is_absent_or_hostile_is_refused_or_fails_its_unit_naming_it(self):
        # SOL-HW-REVIEW-FAN-OUT-DRIVER.C2: Each session's start report is read and a run whose report shows other tools than were granted, another model, any MCP server, an instruction source the command line was asked to exclude or another working directory fails naming the session. The setup session is started with the read tools only and a prompt that asks for no judgement and no image and for one fixed token as the whole answer and that either tells it which documents and records to read or, when the caller names them as files, holds their text itself, sent on standard input so that the session has no tool use to narrate between; any text the setup session writes, in its answer or between its tool uses, other than that token after trimming, and any content block of its history that is neither text, a tool use nor a thinking block whose text is empty, fails the run, so no forked reviewer inherits a verdict; a thinking block that carries text, and a redacted one, fail it; a setup session that fails only for text written between its tool uses is started again, up to twice, before the run fails, and every attempt's session is reported with its cost, and a read of a file whose type is not text in the setup session's tool uses fails the run naming the file, as does a file the caller names whose type is not text, before any session is started. Out of scope: the content of a caller's prompt for its units.
        for field, values in INVENTORY["start report"].items():
            for name, value in values.items():
                change = {"start_omit": [field]} if value is ABSENT else {"start_set": {field: value}}
                with self.subTest(field=field, value=name, session="setup"):
                    self.fresh()
                    self.scenario({"setup": change})
                    self.assert_refused(["the setup session", f"`{field}`"], started=1)
                with self.subTest(field=field, value=name, session="fork"):
                    self.fresh()
                    self.scenario({"units": {"alpha": [change]}})
                    self.assert_unit_failed("alpha", ["the reviewer of unit alpha", f"`{field}`"], "--bound", "3")
        for name, (change, word) in {"a tool that is not a name": ({"tools": [3, "Read"]}, "not a list of names"),
                                     "an MCP server that is garbage": ({"mcp_servers": [[None]]}, "MCP servers"),
                                     "a plugin that is not a mapping": ({"plugins": ["builtin"]}, "plugins"),
                                     "a plugin with no path": ({"plugins": [{"name": "p", "path": None}]}, "plugins"),
                                     "a working folder with a NUL byte": ({"cwd": "/review\u0000"}, "started in")}.items():
            with self.subTest(element=name):
                self.fresh()
                self.scenario({"setup": {"start_set": change}})
                self.assert_refused(["the setup session", word], started=1)

    def test_every_field_of_a_result_report_that_is_absent_or_hostile_is_refused_or_fails_its_unit_naming_it(self):
        # SOL-HW-REVIEW-FAN-OUT-DRIVER.C5: Against a stub that reports a fork's cost, API time and turn count cumulatively including its setup session, as the agent command line does, the record gives each fork its own cost, time and turns, the setup session its own, and the run their sum; token usage is taken as each session reports it, split into tokens read from the cache, written to it, fresh and generated, and a fork that reads no cache is flagged. The record is in the text and the JSON report. Out of scope: judging whether a run was worth its cost.
        full = {"input_tokens": 3, "output_tokens": 100, "cache_read_input_tokens": 5000, "cache_creation_input_tokens": 200}
        for field, values in INVENTORY["result report"].items():
            for name, value in values.items():
                if field.startswith("usage."):
                    key = field.split(".", 1)[1]
                    usage = {k: v for k, v in full.items() if k != key or value is not ABSENT}
                    if value is not ABSENT:
                        usage[key] = value
                    change = {"result_set": {"usage": usage}}
                else:
                    change = {"result_omit": [field]} if value is ABSENT else {"result_set": {field: value}}
                label = field.split(".")[-1]
                setup_word = "answered ''" if (field, name) == ("result", "empty string") else label
                fork_words = (["failed after 2 attempts"] if (field, name) == ("result", "empty string") else [label])
                with self.subTest(field=field, value=name, session="setup"):
                    self.fresh()
                    self.scenario({"setup": change})
                    self.assert_refused(["the setup session", setup_word], started=1)
                with self.subTest(field=field, value=name, session="fork"):
                    self.fresh()
                    self.scenario({"units": {"alpha": [change]}})
                    self.assert_unit_failed("alpha", fork_words, "--bound", "3")
        for field in ("total_cost_usd", "duration_api_ms", "num_turns"):
            with self.subTest(below=field):
                self.fresh()
                self.scenario({"units": {"alpha": [{"result_set": {field: 0}}]}})
                report = self.assert_unit_failed("alpha", ["below that of the session it was resumed from"], "--bound", "3")
                alpha = [entry for entry in report["units"] if entry["unit"] == "alpha"][0]
                self.assertEqual(alpha["flags"], ["figures below those it includes"])
                self.assertEqual(alpha["own"]["cost_usd"], 0.0, "its own cost cannot be told, so none is made up")

    def test_every_hostile_line_event_and_block_of_a_session_s_stream_is_refused_or_fails_its_unit_naming_it(self):
        # SOL-HW-REVIEW-FAN-OUT-DRIVER.C2: Each session's start report is read and a run whose report shows other tools than were granted, another model, any MCP server, an instruction source the command line was asked to exclude or another working directory fails naming the session. The setup session is started with the read tools only and a prompt that asks for no judgement and no image and for one fixed token as the whole answer and that either tells it which documents and records to read or, when the caller names them as files, holds their text itself, sent on standard input so that the session has no tool use to narrate between; any text the setup session writes, in its answer or between its tool uses, other than that token after trimming, and any content block of its history that is neither text, a tool use nor a thinking block whose text is empty, fails the run, so no forked reviewer inherits a verdict; a thinking block that carries text, and a redacted one, fail it; a setup session that fails only for text written between its tool uses is started again, up to twice, before the run fails, and every attempt's session is reported with its cost, and a read of a file whose type is not text in the setup session's tool uses fails the run naming the file, as does a file the caller names whose type is not text, before any session is started. Out of scope: the content of a caller's prompt for its units.
        words = {"a line": "not a JSON event", "an event's type": "no string `type`",
                 "a second report": "second", "an assistant event's message.content": "no `message.content` list",
                 "a content block": "the setup session", "a text block's text": "text block with no string `text`",
                 "a tool use's name": "tool use with no string `name`", "a tool use's input": "no `input` mapping",
                 "a Read's input.file_path": "the setup session", "a tool use's id": "notes/absent.md",
                 "a tool result's is_error": "notes/absent.md", "a user event": "notes/absent.md",
                 "the output's bytes": "not a JSON event"}
        for site, values in INVENTORY["stream"].items():
            for name, lines in values.items():
                change = {"garbled": True} if lines == "garbled" else {"lines": lines}
                with self.subTest(site=site, value=name, session="setup"):
                    self.fresh()
                    self.scenario({"setup": change})
                    self.assert_refused(["the setup session", words[site]], started=1)
        for name, (lines, word) in {"a line that is not JSON": (["not json"], "not a JSON event"),
                                    "an event with no type": (["{}"], "no string `type`"),
                                    "a second start report": ([json.dumps({"type": "system", "subtype": "init"})], "second start report"),
                                    "bytes that are not UTF-8": ("garbled", "not a JSON event")}.items():
            with self.subTest(fork=name):
                self.fresh()
                self.scenario({"units": {"alpha": [{"garbled": True} if lines == "garbled" else {"lines": lines}]}})
                self.assert_unit_failed("alpha", ["the reviewer of unit alpha", word], "--bound", "3")
        for name, raw in {"a line separator": "\u2028", "a paragraph separator": "\u2029", "a next line": "\u0085"}.items():
            with self.subTest(control=f"{name} written raw inside an event"):
                self.fresh()
                separators = "a\u2028b\u2029c\u0085d"
                event = json.dumps({"type": "rate_limit_event", "note": f"x{raw}y {separators}"}, ensure_ascii=False)
                tables = {"Verdicts": verdicts(("A-1", "pass", separators))}
                self.scenario({"setup": {"lines": [event], "raw_unicode": True},
                               "units": {"alpha": [{"raw_unicode": True, "lines": [event],
                                                    "text": json.dumps({"tables": tables}, ensure_ascii=False)}]}})
                status, text, _ = self.outcome()
                self.assertEqual(status, 0, "a correct session is not refused for a character that only looks like a line end: " + text)
        with self.subTest(control="an event of a type the command does not read"):
            self.fresh()
            self.scenario({"setup": {"lines": [json.dumps({"type": "rate_limit_event", "rate_limit_info": {"status": "allowed"}})]}})
            status, text, _ = self.outcome()
            self.assertEqual(status, 0, "the real command line prints it, and it carries nothing the command relies on: " + text)

    def test_a_session_that_exits_without_a_report_or_writes_bytes_that_are_not_text_is_named_and_never_a_traceback(self):
        # SOL-HW-REVIEW-FAN-OUT-DRIVER.C4: The exit status is 0 when the merged record is written, 1 when the command refuses or a unit fails, and 2 when the agent command line is missing or not logged in, each with a line beginning REFUSED or CANNOT RUN as the other board commands print; a review folder inside the repository, a folder that does not exist, an output folder inside the review folder or containing it or inside the repository, a caller name with no module or whose module lacks a required attribute, an output folder that already holds a record when no unit is named to run again, an output folder in use by another run, and a bound below one are refused. Each REFUSED and CANNOT RUN line names its cause and what to do about it. The report is available as text and as JSON and the two hold the same facts. Out of scope: the merge's own refusals, which each caller names.
        for name, change in INVENTORY["exit"].items():
            with self.subTest(case=name, session="setup"):
                self.fresh()
                self.scenario({"setup": change})
                self.assert_refused(["the setup session"], started=1)
            with self.subTest(case=name, session="fork"):
                self.fresh()
                self.scenario({"units": {"alpha": [change]}})
                self.assert_unit_failed("alpha", ["unit alpha failed"], "--bound", "3")
        real = review_fan_out.subprocess.run

        def unstartable(command, *rest, **named):
            if command[1:3] != ["auth", "status"] and "UNIT=alpha" in " ".join(command):
                raise PermissionError("permission denied")
            return real(command, *rest, **named)
        with self.subTest(case="a reviewer program that cannot be started"):
            self.fresh()
            self.scenario({})
            with mock.patch.object(review_fan_out.subprocess, "run", unstartable):
                report = self.assert_unit_failed("alpha", ["could not be started", "permission denied"], "--bound", "3", status=2)
            self.assertEqual(report["result"], "CANNOT RUN")

        def unchecked(*_):
            raise ZeroDivisionError("a check that broke")
        with self.subTest(case="a setup check that breaks"):
            self.fresh()
            with mock.patch.object(review_fan_out, "setup_findings", unchecked):
                self.assert_refused(["the setup session could not be checked", "ZeroDivisionError"], started=1)

    def test_an_auth_status_that_is_not_an_object_whose_logged_in_is_true_after_a_clean_exit_cannot_run(self):
        # SOL-HW-REVIEW-FAN-OUT-DRIVER.C4: The exit status is 0 when the merged record is written, 1 when the command refuses or a unit fails, and 2 when the agent command line is missing or not logged in, each with a line beginning REFUSED or CANNOT RUN as the other board commands print; a review folder inside the repository, a folder that does not exist, an output folder inside the review folder or containing it or inside the repository, a caller name with no module or whose module lacks a required attribute, an output folder that already holds a record when no unit is named to run again, an output folder in use by another run, and a bound below one are refused. Each REFUSED and CANNOT RUN line names its cause and what to do about it. The report is available as text and as JSON and the two hold the same facts. Out of scope: the merge's own refusals, which each caller names.
        for name, (printed, code) in INVENTORY["auth status"].items():
            with self.subTest(auth=name):
                self.fresh()
                self.scenario({"auth_garbled": True} if printed is None else {"auth_stdout": printed, "auth": code})
                for as_json in (False, True):
                    status, text, err = self.outcome(as_json=as_json)
                    self.assertEqual(status, 2, text + err)
                    cause = json.loads(text)["cannot_run"] if as_json else err
                    self.assertIn(f"is not logged in: `auth status` exited {code} and printed", cause)
                    if printed and printed.strip():
                        self.assertIn(review_fan_out.board_check.clean(printed)[:40], cause, "what the command line printed")
                    self.assertIn("log it in, then run again", cause)
                self.assertEqual(self.calls(), [], "no session was started")
        with self.subTest(control="logged in"):
            self.fresh()
            self.scenario({"auth_stdout": '{"loggedIn": true, "authMethod": "x"}'})
            self.assertEqual(self.outcome()[0], 0)

    def test_a_kept_record_that_is_unreadable_or_hostile_refuses_a_run_again_naming_its_file(self):
        # SOL-HW-REVIEW-FAN-OUT-DRIVER.C8: The command keeps each unit's result in its output folder. Given the names of units to run again, it runs only those, replaces their results, and merges again; it refuses a name that is not a unit of the review and refuses a run that leaves out a unit whose last run again failed, naming that unit, and the record shows which units were run again and when, and that a new setup session was started for them. A unit that failed, or that needs a view the round's starter has since rendered, is therefore run without repeating the others. Out of scope: deciding which units to run again.
        def prepared():
            self.fresh()
            self.scenario({"units": {"bravo": [{"exit": 1}, {}]}})
            self.assertEqual(self.outcome()[0], 0)
            self.assertEqual(self.outcome("--rerun", "charlie")[0], 0)
            review_fan_out.write_json(os.path.join(self.out, "failed", "bravo.json"), self.kept("bravo")["sessions"][:1])
            for name in os.listdir(self.log):
                os.remove(os.path.join(self.log, name))
            self.scenario({})
        for record, values in INVENTORY["folder records"].items():
            for name, content in values.items():
                with self.subTest(record=record, value=name):
                    prepared()
                    path = os.path.join(self.out, record)
                    os.remove(path)
                    if content is None:
                        os.makedirs(path)
                    else:
                        self.write(path, content)
                    self.assert_refused([os.path.basename(record), "cannot be read"], "--rerun", "alpha", started=0)
        for name, (record, edit, word) in INVENTORY["folder record fields"].items():
            with self.subTest(field=name):
                prepared()
                path = os.path.join(self.out, record)
                content = review_fan_out.read_json(path)
                edit(content)
                review_fan_out.write_json(path, content)
                self.assert_refused([os.path.basename(record), "cannot be read", word], "--rerun", "alpha", started=0)
        with self.subTest(control="the prepared folder"):
            prepared()
            self.assertEqual(self.outcome("--rerun", "alpha")[0], 0)

    def test_a_caller_module_whose_attributes_are_hostile_is_refused_naming_the_attribute(self):
        # SOL-HW-REVIEW-FAN-OUT-DRIVER.C4: The exit status is 0 when the merged record is written, 1 when the command refuses or a unit fails, and 2 when the agent command line is missing or not logged in, each with a line beginning REFUSED or CANNOT RUN as the other board commands print; a review folder inside the repository, a folder that does not exist, an output folder inside the review folder or containing it or inside the repository, a caller name with no module or whose module lacks a required attribute, an output folder that already holds a record when no unit is named to run again, an output folder in use by another run, and a bound below one are refused. Each REFUSED and CANNOT RUN line names its cause and what to do about it. The report is available as text and as JSON and the two hold the same facts. Out of scope: the merge's own refusals, which each caller names.
        for name, (old, new) in INVENTORY["caller attributes"].items():
            with self.subTest(attribute=name):
                self.fresh()
                text = caller_text()
                self.assertIn(old, text)
                self.write(os.path.join(self.callers, "review_caller_hostile.py"), text.replace(old, new, 1))
                attribute = name.split(" ")[0]
                self.assert_refused(["review_caller_hostile.py", attribute], caller="hostile", started=0)
                self.assertFalse(os.path.exists(self.out))

    def test_a_caller_value_that_raises_when_checked_is_refused_naming_the_module_and_never_a_traceback(self):
        # SOL-HW-REVIEW-FAN-OUT-DRIVER.C4: The exit status is 0 when the merged record is written, 1 when the command refuses or a unit fails, and 2 when the agent command line is missing or not logged in, each with a line beginning REFUSED or CANNOT RUN as the other board commands print; a review folder inside the repository, a folder that does not exist, an output folder inside the review folder or containing it or inside the repository, a caller name with no module or whose module lacks a required attribute, an output folder that already holds a record when no unit is named to run again, an output folder in use by another run, and a bound below one are refused. Each REFUSED and CANNOT RUN line names its cause and what to do about it. The report is available as text and as JSON and the two hold the same facts. Out of scope: the merge's own refusals, which each caller names.
        self.fresh()
        text = caller_text().replace('TOOLS = ("Read", "Glob")', 'class Odd:\n    def __eq__(self, other):\n        raise RuntimeError("no")\n'
                                     '    __hash__ = None\n\n\nTOOLS = (Odd(),)')
        self.write(os.path.join(self.callers, "review_caller_odd.py"), text)
        self.assert_refused(["review_caller_odd.py", "cannot be checked", "RuntimeError"], caller="odd", started=0)
        self.assertFalse(os.path.exists(self.out))

    def test_a_caller_hook_that_returns_a_hostile_value_is_refused_or_fails_its_unit_naming_the_hook(self):
        # SOL-HW-REVIEW-FAN-OUT-DRIVER.C4: The exit status is 0 when the merged record is written, 1 when the command refuses or a unit fails, and 2 when the agent command line is missing or not logged in, each with a line beginning REFUSED or CANNOT RUN as the other board commands print; a review folder inside the repository, a folder that does not exist, an output folder inside the review folder or containing it or inside the repository, a caller name with no module or whose module lacks a required attribute, an output folder that already holds a record when no unit is named to run again, an output folder in use by another run, and a bound below one are refused. Each REFUSED and CANNOT RUN line names its cause and what to do about it. The report is available as text and as JSON and the two hold the same facts. Out of scope: the merge's own refusals, which each caller names.
        tables = {"alpha": {"Verdicts": verdicts(("A-1", "fail", "F1")), "Findings": [finding(1, "A-1", "x @U1")]}}
        rounded = {"alpha": {"Verdicts": verdicts(("A-1", "fail", "2.1")), "Findings": [finding(1, "A-1", "x")]}}
        for name, (hook, value) in INVENTORY["caller hooks"].items():
            with self.subTest(hook=name):
                self.fresh()
                text = caller_text(ROUNDED if hook in ("round", "earlier") else FINDINGS)
                if hook == "units":
                    text = text.replace("def units(folder):\n", f"def units(folder):\n    return {value}\n")
                elif hook == "unit_prompt":
                    text = text.replace("def unit_prompt(unit, review_folder):\n", f"def unit_prompt(unit, review_folder):\n    if unit == 'alpha':\n        return {value}\n")
                elif hook == "CHECK":
                    text = text.replace("def CHECK(folder, units, tables):\n", f"def CHECK(folder, units, tables):\n    return {value}\n")
                elif hook in ("round", "earlier"):
                    given = {"round": '"round": lambda folder: "2"',
                             "earlier": '"earlier": lambda folder: {("1", 1), ("1", 2), ("1", 3)}'}[hook]
                    self.assertIn(given, text)
                    text = text.replace(given, f'"{hook}": lambda folder: {value}')
                else:
                    text = text.replace('"key": lambda row', f'"{hook}": lambda _: {value}, "_key": lambda row', 1)
                    if hook == "first":
                        text = text.replace('"_key": lambda row', '"key": lambda row')
                self.write(os.path.join(self.callers, "review_caller_hostile.py"), text)
                self.scenario({"tables": rounded if hook in ("round", "earlier") else tables})
                if hook in ("unit_prompt", "round", "earlier"):
                    # Each unit's own tables are checked against this round's citations as it is judged.
                    self.assert_unit_failed("alpha", [f"the caller's {hook} returned", "fix the caller"], caller="hostile")
                else:
                    self.assert_refused([f"the caller's {hook} returned", "fix the caller"], caller="hostile")

    def test_a_reviewer_answer_whose_tables_are_hostile_is_run_once_more_and_then_fails_its_unit_naming_it(self):
        # SOL-HW-REVIEW-FAN-OUT-DRIVER.C3: A unit whose reviewer exits with an error or returns nothing is run once more; a call refused for a rate limit is retried after a wait that grows, a bounded number of times; a unit that still fails fails the run, naming the unit and what the reviewer returned, and the other units' results are kept in the output. Out of scope: what a caller counts as a malformed result, which the caller defines.
        for name, answer in INVENTORY["reviewer tables"].items():
            with self.subTest(answer=name):
                self.fresh()
                self.scenario({"units": {"alpha": [{"text": answer}]}})
                self.assert_unit_failed("alpha", ["unit alpha failed after 2 attempts"], "--bound", "3")
                self.assertEqual(len([call for call in self.forks() if call["unit"] == "alpha"]), 2)

    def test_a_command_line_argument_that_is_hostile_is_refused_naming_it(self):
        # SOL-HW-REVIEW-FAN-OUT-DRIVER.C4: The exit status is 0 when the merged record is written, 1 when the command refuses or a unit fails, and 2 when the agent command line is missing or not logged in, each with a line beginning REFUSED or CANNOT RUN as the other board commands print; a review folder inside the repository, a folder that does not exist, an output folder inside the review folder or containing it or inside the repository, a caller name with no module or whose module lacks a required attribute, an output folder that already holds a record when no unit is named to run again, an output folder in use by another run, and a bound below one are refused. Each REFUSED and CANNOT RUN line names its cause and what to do about it. The report is available as text and as JSON and the two hold the same facts. Out of scope: the merge's own refusals, which each caller names.
        for name, (extra, word) in INVENTORY["arguments"].items():
            with self.subTest(argument=name):
                self.fresh()
                self.assert_refused([word], *extra, started=0)

    def test_every_failure_of_a_unit_run_again_leaves_it_unsettled_so_a_run_again_of_another_unit_is_refused(self):
        # SOL-HW-REVIEW-FAN-OUT-DRIVER.C8: The command keeps each unit's result in its output folder. Given the names of units to run again, it runs only those, replaces their results, and merges again; it refuses a name that is not a unit of the review and refuses a run that leaves out a unit whose last run again failed, naming that unit, and the record shows which units were run again and when, and that a new setup session was started for them. A unit that failed, or that needs a view the round's starter has since rendered, is therefore run without repeating the others. Out of scope: deciding which units to run again.
        self.write(os.path.join(self.callers, "review_caller_flaky.py"), caller_text().replace(
            "def unit_prompt(unit, review_folder):\n", "def unit_prompt(unit, review_folder):\n    if os.environ.get('FLAKY_UNIT') == unit:\n        raise KeyError(unit)\n"))
        real = review_fan_out.call_agent

        def vanishing(program, prompt, *rest, **named):
            if "UNIT=alpha" in prompt:
                raise FileNotFoundError("the agent binary vanished")
            return real(program, prompt, *rest, **named)
        shapes = {"a rate limit that outlasts the retries": ({"units": {"alpha": [{"rate_limit": True}]}}, {}, None),
                  "the unit prompt raising": ({}, {"FLAKY_UNIT": "alpha"}, None),
                  "a lost login on the first call": ({"units": {"alpha": [{"login": True}]}}, {}, None),
                  "a call that raises before any session": ({}, {}, vanishing),
                  "an attempt that cost a session": ({"units": {"alpha": [{"exit": 1}]}}, {}, None)}
        for name, (scenario, environment, call) in shapes.items():
            with self.subTest(shape=name):
                self.fresh()
                self.scenario({})
                self.assertEqual(self.outcome(caller="flaky")[0], 0)
                self.scenario(scenario)
                with mock.patch.dict(os.environ, environment), \
                        mock.patch.object(review_fan_out, "call_agent", call or real):
                    status, text, err = self.outcome("--rerun", "alpha", caller="flaky")
                self.assertIn(status, (1, 2), text + err)
                self.assertTrue(os.path.exists(os.path.join(self.out, "unsettled", "alpha.json")), name)
                for name_ in os.listdir(self.log):
                    os.remove(os.path.join(self.log, name_))
                self.scenario({})
                self.assert_refused(["unit alpha's last run again failed", "name alpha with --rerun too"],
                                    "--rerun", "bravo", caller="flaky", started=0)
                status, text, _ = self.outcome("--rerun", "alpha", "--rerun", "bravo", caller="flaky")
                self.assertEqual(status, 0, text)
                self.assertFalse(os.path.exists(os.path.join(self.out, "unsettled", "alpha.json")), "a kept result settles it")
        with self.subTest(shape="a mark that is a folder or holds garbage"):
            for name in os.listdir(self.log):
                os.remove(os.path.join(self.log, name))
            for content in (None, "{not json"):
                path = os.path.join(self.out, "unsettled", "charlie.json")
                if content is None:
                    os.makedirs(path)
                else:
                    shutil.rmtree(path, ignore_errors=True)
                    self.write(path, content)
                self.assert_refused(["unit charlie's last run again failed"], "--rerun", "bravo", caller="flaky", started=0)


RENDERING = """

def RENDER(folder, tables):
    mode = os.environ.get("RENDER_MODE", "ok")
    if mode == "raise":
        raise KeyError("render")
    if mode == "string":
        return "not a mapping"
    if mode == "other":
        return {"other.md": "other"}
    if mode == "named":
        return {os.environ["RENDER_NAME"]: "x"}
    if mode == "table":
        import json
        return json.loads(os.environ["RENDER_FILES"])
    if mode == "casepair":
        return {"Summary.md": "x", "summary.MD": "y"}
    if mode == "dotpair":
        return {"Summary.md": "x", "summary.md.": "y"}
    if mode == "fewer":
        return {"summary.md": "only"}
    if mode == "dropped":
        return {"second.md": "again"}
    names = {"path": {"sub/x.md": "x"}, "back": {"a\\\\b.md": "x"}, "dots": {"..": "x"}, "record": {"record.json": "x"},
             "units": {"units": "x"}, "lock": {".review-fan-out.lock": "x"}, "setups": {"setups.json": "x"},
             "clash": {"notes.md": "mine"}}
    if mode in names:
        return names[mode]
    rows = len(tables["Verdicts"]["rows"])
    return {"summary.md": f"{folder}|{rows}|{os.environ.get('RENDER_TAG', 'a')}", "second.md": "second"}
"""

CHECKLISTING = """

def CHECKLIST(folder):
    with open(os.environ["CHECKLIST_LOG"], "a", encoding="utf-8") as handle:
        handle.write("x\\n")
    mode = os.environ.get("CHECKLIST_MODE", "ok")
    if mode == "raise":
        raise KeyError("checklist")
    if mode == "string":
        return "A-1"
    if mode == "dupe":
        return ["A-1", "A-1"]
    with open(os.path.join(folder, "checklist.txt"), encoding="utf-8") as handle:
        return handle.read().split()
"""

FUNCTION_FINDINGS = FINDINGS.replace('"checklist": ["A-1", "B-1", "C-1"]', '"checklist": lambda folder: CHECKLIST(folder)')


class CallerSeam(Fixture):
    """The attributes a caller may define beyond the driver's required ones, over synthetic callers and review folders."""

    def setUp(self):
        super().setUp()
        self.checklist_log = os.path.join(self.root, "checklist.log")
        patcher = mock.patch.dict(os.environ, {"CHECKLIST_LOG": self.checklist_log})
        patcher.start()
        self.addCleanup(patcher.stop)
        # a caller rewritten within a second at the same size must not be loaded from its stale compiled copy
        bytecode = mock.patch.object(sys, "dont_write_bytecode", True)
        bytecode.start()
        self.addCleanup(bytecode.stop)

    def caller_module(self, text, name="synth"):
        self.write(os.path.join(self.callers, f"review_caller_{name}.py"), text)

    def environment(self, **values):
        patcher = mock.patch.dict(os.environ, values)
        patcher.start()
        self.addCleanup(patcher.stop)

    def single(self):
        os.remove(os.path.join(self.review, "units", "bravo.txt"))
        os.remove(os.path.join(self.review, "units", "charlie.txt"))

    def checklist_calls(self):
        if not os.path.exists(self.checklist_log):
            return 0
        with open(self.checklist_log, encoding="utf-8") as handle:
            return len(handle.read().split())

    def refused(self, *words, **options):
        status, text, _ = self.run_command(as_json=True, **options)
        self.assertEqual(status, 1, text)
        causes = json.loads(text)["refusals"]
        for word in words:
            self.assertTrue(any(word in cause for cause in causes), f"{word!r} in {causes}")
        return causes

    # --- C1: the retrieval grant

    def test_a_caller_may_grant_the_read_tools_and_the_one_retrieval_tool_and_the_setup_session_keeps_the_read_tools_alone(self):
        # SOL-HW-REVIEW-FAN-OUT-CALLER-SEAM.C1: A caller's tool set may be the read tools, or the read tools and the one retrieval tool the driver names, which fetches a published document at an address and writes nothing, and the driver starts each reviewer with the caller's set. Any tool outside those is refused at load as before. The setup turn that reads the review's documents is started with the read tools alone whatever the caller grants, and the turn that judges a single unit in the setup session is started with the caller's set. The start report of a session that reports a tool outside the set granted to it fails the run, as now. Out of scope: whether a fork can retrieve, and what a retrieved document holds.
        self.caller_module(caller_text().replace('TOOLS = ("Read", "Glob")', 'TOOLS = ("Read", "Glob", "WebFetch")'))
        status, text, _ = self.run_command(as_json=True)
        self.assertEqual(status, 0, text)
        setup = [call for call in self.calls() if call["unit"] is None]
        self.assertEqual([self.flag(call, "--tools") for call in setup], ["Read,Glob,Grep"], "the setup turn: the read tools alone")
        self.assertEqual([self.flag(call, "--allowedTools") for call in setup], ["Read,Glob,Grep"])
        self.assertEqual(len(self.forks()), 3)
        for fork in self.forks():
            self.assertEqual(self.flag(fork, "--tools"), "Read,Glob,WebFetch", "each reviewer starts with the caller's set")
            self.assertEqual(self.flag(fork, "--allowedTools"), "Read,Glob,WebFetch")

        shutil.rmtree(self.out)
        for name in os.listdir(self.log):
            os.remove(os.path.join(self.log, name))
        self.single()
        status, text, _ = self.run_command(as_json=True)
        self.assertEqual(status, 0, text)
        calls = self.calls()
        self.assertEqual([self.flag(call, "--tools") for call in calls], ["Read,Glob,Grep", "Read,Glob,WebFetch"],
                         "the single unit's turn in the setup session is started with the caller's set")
        self.assertFalse(calls[1]["forked"])

    def test_a_tool_outside_the_read_tools_and_the_retrieval_tool_is_refused_at_load(self):
        # SOL-HW-REVIEW-FAN-OUT-CALLER-SEAM.C1: A caller's tool set may be the read tools, or the read tools and the one retrieval tool the driver names, which fetches a published document at an address and writes nothing, and the driver starts each reviewer with the caller's set. Any tool outside those is refused at load as before. The setup turn that reads the review's documents is started with the read tools alone whatever the caller grants, and the turn that judges a single unit in the setup session is started with the caller's set. The start report of a session that reports a tool outside the set granted to it fails the run, as now. Out of scope: whether a fork can retrieve, and what a retrieved document holds.
        for tools in ('("Read", "WebSearch")', '("WebFetch", "Write")', '("Read", "Bash", "WebFetch")', '("webfetch",)', '()'):
            self.caller_module(caller_text().replace('TOOLS = ("Read", "Glob")', f"TOOLS = {tools}"))
            causes = self.refused("a reviewer is read-only", "WebFetch", "no others")
            self.assertTrue(any(f"grants tools {eval(tools)!r}" in cause for cause in causes), f"{tools}: {causes}")
            self.assertEqual(self.calls(), [], "refused before any session")

    def test_a_session_reporting_a_tool_outside_its_grant_fails_the_run_and_the_setup_session_may_not_use_the_retrieval_tool(self):
        # SOL-HW-REVIEW-FAN-OUT-CALLER-SEAM.C1: A caller's tool set may be the read tools, or the read tools and the one retrieval tool the driver names, which fetches a published document at an address and writes nothing, and the driver starts each reviewer with the caller's set. Any tool outside those is refused at load as before. The setup turn that reads the review's documents is started with the read tools alone whatever the caller grants, and the turn that judges a single unit in the setup session is started with the caller's set. The start report of a session that reports a tool outside the set granted to it fails the run, as now. Out of scope: whether a fork can retrieve, and what a retrieved document holds.
        self.caller_module(caller_text())  # grants Read and Glob alone
        self.scenario({"fork_tools": ["Read", "Glob", "WebFetch"]})
        status, text, _ = self.run_command(as_json=True)
        self.assertEqual(status, 1, text)
        failed = [unit for unit in json.loads(text)["units"] if unit["status"] == "failed"]
        self.assertEqual(len(failed), 3)
        self.assertIn("not the ['Glob', 'Read'] it was granted", failed[0]["detail"])

        shutil.rmtree(self.out, ignore_errors=True)
        self.caller_module(caller_text().replace('TOOLS = ("Read", "Glob")', 'TOOLS = ("Read", "Glob", "WebFetch")'))
        self.scenario({"setup_tools": ["Read", "Glob", "Grep", "WebFetch"]})
        causes = self.refused("the setup session started with tools")
        self.assertTrue(any("not the ['Glob', 'Grep', 'Read'] it was granted" in cause for cause in causes), causes)

        shutil.rmtree(self.out, ignore_errors=True)
        self.scenario({"setup": {"uses": ["WebFetch"]}})
        self.refused("the setup session used WebFetch, a tool it was not granted")

    # --- C2: the review folder in the prompt

    def test_the_prompt_function_is_given_the_unit_and_the_review_folder_for_a_fork_and_for_the_single_unit(self):
        # SOL-HW-REVIEW-FAN-OUT-CALLER-SEAM.C2: The driver passes the review folder to the caller's prompt function as well as the unit, for a forked reviewer and for the one unit judged in the setup session, and requires the function to accept both. A caller whose prompt function does not accept the unit and the review folder is refused at load naming the attribute and the caller, and a prompt function that raises fails the run naming the caller and the unit. Out of scope: any file the folder holds.
        self.caller_module(caller_text().replace('return f"Judge UNIT={unit} against the checklist."',
                                                 'return f"Judge UNIT={unit} reading {review_folder}/round.md"'))
        status, text, _ = self.run_command(as_json=True)
        self.assertEqual(status, 0, text)
        self.assertEqual(len(self.forks()), 3)
        for fork in self.forks():
            self.assertIn(f"UNIT={fork['unit']} reading {self.review}/round.md", fork["prompt"])

        shutil.rmtree(self.out)
        for name in os.listdir(self.log):
            os.remove(os.path.join(self.log, name))
        self.single()
        status, text, _ = self.run_command(as_json=True)
        self.assertEqual(status, 0, text)
        judged = [call for call in self.calls() if call["unit"] == "alpha"]
        self.assertEqual(len(judged), 1)
        self.assertFalse(judged[0]["forked"])
        self.assertIn(f"reading {self.review}/round.md", judged[0]["prompt"])

    def test_a_prompt_function_that_does_not_accept_the_unit_and_the_review_folder_is_refused_naming_the_attribute_and_the_caller(self):
        # SOL-HW-REVIEW-FAN-OUT-CALLER-SEAM.C2: The driver passes the review folder to the caller's prompt function as well as the unit, for a forked reviewer and for the one unit judged in the setup session, and requires the function to accept both. A caller whose prompt function does not accept the unit and the review folder is refused at load naming the attribute and the caller, and a prompt function that raises fails the run naming the caller and the unit. Out of scope: any file the folder holds.
        for signature in ("unit", "", "unit, review_folder, extra", "*, unit, review_folder"):
            self.caller_module(caller_text().replace("def unit_prompt(unit, review_folder):", f"def unit_prompt({signature}):"),
                               name="narrow")
            causes = self.refused("unit_prompt", "narrow", "the unit and the review folder", caller="narrow")
            self.assertTrue(all("narrow" in cause for cause in causes), causes)
            self.assertEqual(self.calls(), [], "refused before any session")
        # a function that takes them under any names, or with defaults after, is accepted
        self.caller_module(caller_text().replace("def unit_prompt(unit, review_folder):", "def unit_prompt(unit, folder, extra=None):"),
                           name="wide")
        status, text, _ = self.run_command(as_json=True, caller="wide")
        self.assertEqual(status, 0, text)

    def test_a_prompt_function_that_raises_fails_its_unit_naming_the_caller_and_the_unit(self):
        # SOL-HW-REVIEW-FAN-OUT-CALLER-SEAM.C2: The driver passes the review folder to the caller's prompt function as well as the unit, for a forked reviewer and for the one unit judged in the setup session, and requires the function to accept both. A caller whose prompt function does not accept the unit and the review folder is refused at load naming the attribute and the caller, and a prompt function that raises fails the run naming the caller and the unit. Out of scope: any file the folder holds.
        self.caller_module(caller_text().replace("def unit_prompt(unit, review_folder):\n",
                                                 "def unit_prompt(unit, review_folder):\n    open(os.path.join(review_folder, 'absent.md'))\n"),
                           name="raising")
        status, text, _ = self.run_command(as_json=True, caller="raising")
        self.assertEqual(status, 1, text)
        report = json.loads(text)
        self.assertEqual(sorted(unit["unit"] for unit in report["units"] if unit["status"] == "failed"), list(self.UNITS))
        for unit in report["units"]:
            self.assertIn(f"unit {unit['unit']} failed", unit["detail"])
            self.assertIn("the caller's unit_prompt raised FileNotFoundError", unit["detail"])
            self.assertIn("fix the caller raising", unit["detail"])
        status, text, _ = self.run_command("--rerun", "alpha", out=os.path.join(self.root, "out2"), caller="raising")
        self.assertEqual(status, 1)

    # --- C3: the checklist as a function

    def function_checklist(self, text=None):
        self.write(os.path.join(self.review, "checklist.txt"), "P-1 A-1 B-1 C-1")
        self.caller_module((text or caller_text(FUNCTION_FINDINGS)) + CHECKLISTING)

    def test_a_checklist_function_is_resolved_once_per_run_and_the_merge_numbers_findings_by_the_resolved_list(self):
        # SOL-HW-REVIEW-FAN-OUT-CALLER-SEAM.C3: A checklist given as a function is resolved once per run from the review folder, after load and before the setup session starts, so a function that raises costs no session; the per-unit checks and the merge use that same resolved list, and a rerun of named units resolves it again. A function that raises or returns anything but a list of distinct names fails the run naming the caller. The merge refuses a finding whose item is outside the resolved list and orders findings by it, as it does for a list; which items must have a verdict stays the caller's check. A caller whose checklist is a list behaves as before. Out of scope: what the items of any caller's checklist are.
        self.function_checklist()
        self.scenario({"tables": {
            "alpha": {"Verdicts": verdicts(("A-1", "fail", "F1")), "Findings": [finding(1, "A-1", "x")]},
            "bravo": {"Verdicts": verdicts(("P-1", "fail", "F1")), "Findings": [finding(1, "P-1", "plan row")]},
            "charlie": {"Verdicts": [], "Findings": []}}})
        status, text, _ = self.run_command(as_json=True)
        self.assertEqual(status, 0, text)
        self.assertEqual(self.checklist_calls(), 1, "resolved once for the setup session, three units and the merge")
        tables = json.loads(text)["tables"]
        self.assertEqual([(row["Finding"], row["Item"]) for row in tables["Findings"]["rows"]], [(1, "P-1"), (2, "A-1")],
                         "ordered by the resolved list, which places P-1 before A-1")
        rests = {row["Item"]: row["Rests on"] for row in tables["Verdicts"]["rows"] if row["Item"] in ("A-1", "P-1")}
        self.assertEqual(rests, {"A-1": "F2", "P-1": "F1"}, "the citations follow the new numbers")

    def test_the_checklist_function_is_resolved_before_the_setup_session_and_a_failing_one_costs_no_session(self):
        # SOL-HW-REVIEW-FAN-OUT-CALLER-SEAM.C3: A checklist given as a function is resolved once per run from the review folder, after load and before the setup session starts, so a function that raises costs no session; the per-unit checks and the merge use that same resolved list, and a rerun of named units resolves it again. A function that raises or returns anything but a list of distinct names fails the run naming the caller. The merge refuses a finding whose item is outside the resolved list and orders findings by it, as it does for a list; which items must have a verdict stays the caller's check. A caller whose checklist is a list behaves as before. Out of scope: what the items of any caller's checklist are.
        self.function_checklist()
        for mode, words in (("raise", "raised KeyError"), ("string", "which is not a list of distinct item names"),
                            ("dupe", "which is not a list of distinct item names")):
            with mock.patch.dict(os.environ, {"CHECKLIST_MODE": mode}):
                causes = self.refused("the caller's checklist", words, "fix the caller synth")
            self.assertEqual(self.calls(), [], f"{mode}: no session was started")
            self.assertFalse(os.path.exists(os.path.join(self.out, "record.json")))
        text_status, text, _ = self.run_command()
        self.assertEqual(text_status, 0, text)

        # a missing file is the function's raise, named the same way
        os.remove(os.path.join(self.review, "checklist.txt"))
        shutil.rmtree(self.out)
        for name in os.listdir(self.log):
            os.remove(os.path.join(self.log, name))
        self.refused("the caller's checklist", "FileNotFoundError")
        self.assertEqual(self.calls(), [])

    def test_a_finding_outside_the_resolved_checklist_is_refused_by_the_unit_check_and_a_rerun_resolves_the_list_again(self):
        # SOL-HW-REVIEW-FAN-OUT-CALLER-SEAM.C3: A checklist given as a function is resolved once per run from the review folder, after load and before the setup session starts, so a function that raises costs no session; the per-unit checks and the merge use that same resolved list, and a rerun of named units resolves it again. A function that raises or returns anything but a list of distinct names fails the run naming the caller. The merge refuses a finding whose item is outside the resolved list and orders findings by it, as it does for a list; which items must have a verdict stays the caller's check. A caller whose checklist is a list behaves as before. Out of scope: what the items of any caller's checklist are.
        self.function_checklist()
        self.scenario({"tables": {"alpha": {"Verdicts": verdicts(("Z-1", "fail", "F1")), "Findings": [finding(1, "Z-1", "x")]}}})
        status, text, _ = self.run_command(as_json=True)
        self.assertEqual(status, 1, text)
        report = json.loads(text)
        alpha = [unit for unit in report["units"] if unit["unit"] == "alpha"][0]
        self.assertEqual(alpha["status"], "failed")
        self.assertIn("raised a finding on 'Z-1', which is no item of the checklist", alpha["detail"])
        self.assertEqual(alpha["attempts"], 2, "run once more, against the same list")
        self.assertEqual(self.checklist_calls(), 1)

        self.write(os.path.join(self.review, "checklist.txt"), "P-1 A-1 B-1 C-1 Z-1")
        status, text, _ = self.run_command("--rerun", "alpha", as_json=True)
        self.assertEqual(status, 0, text)
        self.assertEqual(self.checklist_calls(), 2, "the rerun resolved the list again from the folder")
        self.assertEqual([row["Item"] for row in json.loads(text)["tables"]["Findings"]["rows"]], ["Z-1"])

    def test_the_merge_refuses_a_finding_outside_a_resolved_checklist_it_is_given(self):
        # SOL-HW-REVIEW-FAN-OUT-CALLER-SEAM.C3: A checklist given as a function is resolved once per run from the review folder, after load and before the setup session starts, so a function that raises costs no session; the per-unit checks and the merge use that same resolved list, and a rerun of named units resolves it again. A function that raises or returns anything but a list of distinct names fails the run naming the caller. The merge refuses a finding whose item is outside the resolved list and orders findings by it, as it does for a list; which items must have a verdict stays the caller's check. A caller whose checklist is a list behaves as before. Out of scope: what the items of any caller's checklist are.
        self.function_checklist()
        with mock.patch.object(sys, "dont_write_bytecode", True):
            caller = review_fan_out.load_caller("synth", self.callers)
        run = review_fan_out.Run(caller, self.review, self.out, "unused", 2, None, 0)
        run.resolve_checklist()
        self.assertEqual(caller.FINDINGS["checklist"], ["P-1", "A-1", "B-1", "C-1"])
        results = {unit: {"Verdicts": [], "Findings": []} for unit in self.UNITS}
        results["bravo"]["Findings"] = [finding(1, "Q-9", "outside")]
        with self.assertRaises(review_fan_out.Refused) as caught:
            review_fan_out.merge(caller, self.review, list(self.UNITS), results)
        self.assertIn("'Q-9', which is no item of the checklist", caught.exception.causes[0])

    # --- C4: the rendered record

    def rendering_caller(self):
        self.caller_module(caller_text() + RENDERING)

    def read_out(self, name):
        with open(os.path.join(self.out, name), encoding="utf-8") as handle:
            return handle.read()

    def test_a_rendered_record_is_written_after_the_merge_and_named_in_the_record_and_the_report_in_text_and_json(self):
        # SOL-HW-REVIEW-FAN-OUT-CALLER-SEAM.C4: A caller may supply a function of the review folder and the merged tables that returns file names with their text. The driver calls it before writing anything, then writes each file into the output folder after the merge and lists the names it wrote in the record it writes and in its report, in text and in JSON with the same content. It refuses a name that carries a path, a name the driver itself uses in the output folder, and a name that the output folder already holds unless an earlier merge wrote it, which the driver knows from the list of rendered names in the record that merge wrote, so a merge after running named units again replaces the files the earlier merge wrote and never a file put there by anyone else. A function that raises fails the run naming the caller, after the record in table form is written and with the report naming the earlier merge's rendered files as not of this merge. A caller that supplies none writes no file beyond the record in table form. Out of scope: the content of any rendered record.
        self.rendering_caller()
        status, text, _ = self.run_command(as_json=True)
        self.assertEqual(status, 0, text)
        report = json.loads(text)
        self.assertEqual(report["rendered"], ["summary.md", "second.md"])
        self.assertEqual(self.read_out("summary.md"), f"{self.review}|3|a", "given the review folder and the merged tables")
        self.assertEqual(self.read_out("second.md"), "second")
        with open(os.path.join(self.out, "record.json"), encoding="utf-8") as handle:
            self.assertEqual(json.load(handle)["rendered"], ["summary.md", "second.md"], "the record lists the names")
        self.assertEqual(report["tables"]["Verdicts"]["columns"], ["Item", "Verdict", "Rests on"], "the table form is still written")

        shutil.rmtree(self.out)
        status, text, _ = self.run_command()
        self.assertEqual(status, 0, text)
        self.assertIn("RENDERED | summary.md", text.splitlines())
        self.assertIn("RENDERED | second.md", text.splitlines())
        self.assertLess(text.index("RENDERED | summary.md"), text.index("RESULT | WRITTEN"))

    def test_a_rendered_name_with_a_path_or_the_drivers_own_name_or_a_file_it_does_not_own_is_refused_and_nothing_is_written(self):
        # SOL-HW-REVIEW-FAN-OUT-CALLER-SEAM.C4: A caller may supply a function of the review folder and the merged tables that returns file names with their text. The driver calls it before writing anything, then writes each file into the output folder after the merge and lists the names it wrote in the record it writes and in its report, in text and in JSON with the same content. It refuses a name that carries a path, a name the driver itself uses in the output folder, and a name that the output folder already holds unless an earlier merge wrote it, which the driver knows from the list of rendered names in the record that merge wrote, so a merge after running named units again replaces the files the earlier merge wrote and never a file put there by anyone else. A function that raises fails the run naming the caller, after the record in table form is written and with the report naming the earlier merge's rendered files as not of this merge. A caller that supplies none writes no file beyond the record in table form. Out of scope: the content of any rendered record.
        self.rendering_caller()
        for mode, words in (("path", "with a path in it"), ("back", "with a path in it"), ("dots", "with a path in it"),
                            ("record", "which the command uses"), ("units", "which the command uses"),
                            ("lock", "which the command uses"), ("setups", "which the command uses")):
            shutil.rmtree(self.out, ignore_errors=True)
            with mock.patch.dict(os.environ, {"RENDER_MODE": mode}):
                causes = self.refused("caller synth", words)
            self.assertFalse(os.path.exists(os.path.join(self.out, "record.json")), f"{mode}: no record")
            for name in ("summary.md", "second.md"):
                self.assertFalse(os.path.exists(os.path.join(self.out, name)), f"{mode}: nothing written")
        # a file someone else put there is never replaced
        shutil.rmtree(self.out, ignore_errors=True)
        self.write(os.path.join(self.out, "notes.md"), "someone else's")
        with mock.patch.dict(os.environ, {"RENDER_MODE": "clash"}):
            self.refused("'notes.md'", "no earlier merge wrote")
        self.assertEqual(self.read_out("notes.md"), "someone else's")
        self.assertFalse(os.path.exists(os.path.join(self.out, "record.json")))
        # a return that is not a mapping of names to text fails the run as a function that raises does
        shutil.rmtree(self.out, ignore_errors=True)
        with mock.patch.dict(os.environ, {"RENDER_MODE": "string"}):
            self.refused("the caller's RENDER returned 'not a mapping'", "a mapping of file name to text", "fix the caller synth")
        self.assertEqual(json.loads(self.read_out("record.json"))["rendered"], [])
        self.assertFalse(os.path.exists(os.path.join(self.out, "summary.md")))

    def test_a_merge_after_running_named_units_again_replaces_the_files_the_earlier_merge_wrote_and_never_another_file(self):
        # SOL-HW-REVIEW-FAN-OUT-CALLER-SEAM.C4: A caller may supply a function of the review folder and the merged tables that returns file names with their text. The driver calls it before writing anything, then writes each file into the output folder after the merge and lists the names it wrote in the record it writes and in its report, in text and in JSON with the same content. It refuses a name that carries a path, a name the driver itself uses in the output folder, and a name that the output folder already holds unless an earlier merge wrote it, which the driver knows from the list of rendered names in the record that merge wrote, so a merge after running named units again replaces the files the earlier merge wrote and never a file put there by anyone else. A function that raises fails the run naming the caller, after the record in table form is written and with the report naming the earlier merge's rendered files as not of this merge. A caller that supplies none writes no file beyond the record in table form. Out of scope: the content of any rendered record.
        self.rendering_caller()
        status, text, _ = self.run_command(as_json=True)
        self.assertEqual(status, 0, text)
        self.write(os.path.join(self.out, "other.md"), "someone else's")
        with mock.patch.dict(os.environ, {"RENDER_TAG": "b"}):
            status, text, _ = self.run_command("--rerun", "alpha", as_json=True)
        self.assertEqual(status, 0, text)
        self.assertEqual(self.read_out("summary.md"), f"{self.review}|3|b", "the earlier merge's file is replaced")
        self.assertEqual(json.loads(text)["rendered"], ["summary.md", "second.md"])
        with mock.patch.dict(os.environ, {"RENDER_MODE": "other"}):
            status, text, _ = self.run_command("--rerun", "alpha", as_json=True)
        self.assertEqual(status, 1, text)
        self.assertTrue(any("'other.md'" in cause for cause in json.loads(text)["refusals"]))
        self.assertEqual(self.read_out("other.md"), "someone else's", "a file no merge wrote is never replaced")
        self.assertEqual(self.read_out("summary.md"), f"{self.review}|3|b", "and nothing else was written by that merge")

    def test_a_rendered_name_that_differs_only_in_case_from_the_drivers_own_name_or_from_another_rendered_name_is_refused(self):
        # SOL-HW-REVIEW-FAN-OUT-CALLER-SEAM.C4: A caller may supply a function of the review folder and the merged tables that returns file names with their text. The driver calls it before writing anything, then writes each file into the output folder after the merge and lists the names it wrote in the record it writes and in its report, in text and in JSON with the same content. It refuses a name that carries a path, a name the driver itself uses in the output folder, and a name that the output folder already holds unless an earlier merge wrote it, which the driver knows from the list of rendered names in the record that merge wrote, so a merge after running named units again replaces the files the earlier merge wrote and never a file put there by anyone else. A function that raises fails the run naming the caller, after the record in table form is written and with the report naming the earlier merge's rendered files as not of this merge. A caller that supplies none writes no file beyond the record in table form. Out of scope: the content of any rendered record.
        self.rendering_caller()
        for reserved in ("Record.json", "RECORD.JSON", "Units", ".Review-Fan-Out.Lock", "SETUPS.json", "Reruns.JSON",
                         "Failed", "UNSETTLED"):
            for as_json in (True, False):
                shutil.rmtree(self.out, ignore_errors=True)
                with mock.patch.dict(os.environ, {"RENDER_MODE": "named", "RENDER_NAME": reserved}):
                    status, text, _ = self.run_command(as_json=as_json)
                self.assertEqual(status, 1, f"{reserved}: {text}")
                self.assertIn("which the command uses", text, reserved)
                self.assertFalse(os.path.exists(os.path.join(self.out, "record.json")), f"{reserved}: no record")
        shutil.rmtree(self.out, ignore_errors=True)
        with mock.patch.dict(os.environ, {"RENDER_MODE": "casepair"}):
            causes = self.refused("differ only in case", "'Summary.md'", "'summary.MD'")
            shutil.rmtree(self.out, ignore_errors=True)
            status, text, _ = self.run_command()
        self.assertEqual(status, 1, text)
        self.assertTrue(any(line.startswith("REFUSED | ") and "differ only in case" in line for line in text.splitlines()), text)
        self.assertEqual(len(causes), 1)
        self.assertFalse(os.path.exists(os.path.join(self.out, "record.json")))
        # a case variant of a file someone else put there is not the driver's to replace either
        shutil.rmtree(self.out, ignore_errors=True)
        self.write(os.path.join(self.out, "Notes.md"), "someone else's")
        with mock.patch.dict(os.environ, {"RENDER_MODE": "named", "RENDER_NAME": "NOTES.md"}):
            self.refused("'NOTES.md'", "no earlier merge wrote")
        self.assertEqual(self.read_out("Notes.md"), "someone else's")

    def test_a_rendered_name_that_differs_from_the_drivers_own_name_or_another_rendered_name_only_in_trailing_dots_or_spaces_is_refused(self):
        # SOL-HW-REVIEW-FAN-OUT-CALLER-SEAM.C4: A caller may supply a function of the review folder and the merged tables that returns file names with their text. The driver calls it before writing anything, then writes each file into the output folder after the merge and lists the names it wrote in the record it writes and in its report, in text and in JSON with the same content. It accepts a name only if it is one plain component of ASCII letters, digits, full stops, underscores and hyphens that begins with a letter or digit and ends in neither a full stop nor the suffix the driver gives its own scratch files, and refuses any other name. It also refuses a name that, compared without regard to case, equals a name the driver itself uses in the output folder or another name rendered in the same merge, and a name that the output folder already holds unless an earlier merge wrote it and it is still a regular file, which the driver knows from the list of rendered names in the record that merge wrote, so a merge after running named units again replaces the files the earlier merge wrote and never a file put there by anyone else, nor one that has since become a link or a folder. A function that raises fails the run naming the caller, after the record in table form is written and with the report naming the earlier merge's rendered files as not of this merge. A caller that supplies none writes no file beyond the record in table form. Out of scope: the content of any rendered record.
        self.rendering_caller()
        for reserved in ("Record.json.", "record.json ", "UNITS.", ".review-fan-out.lock ", "setups.json. .", "Failed ", "summary.md."):
            for as_json in (True, False):
                shutil.rmtree(self.out, ignore_errors=True)
                with mock.patch.dict(os.environ, {"RENDER_MODE": "named", "RENDER_NAME": reserved}):
                    status, text, _ = self.run_command(as_json=as_json)
                self.assertEqual(status, 1, f"{reserved!r}: {text}")
                self.assertIn("ends in neither a full stop", text, reserved)
                self.assertFalse(os.path.exists(os.path.join(self.out, "record.json")), f"{reserved!r}: no record")
        for as_json in (True, False):
            shutil.rmtree(self.out, ignore_errors=True)
            with mock.patch.dict(os.environ, {"RENDER_MODE": "dotpair"}):
                status, text, _ = self.run_command(as_json=as_json)
            self.assertEqual(status, 1, text)
            self.assertIn("'summary.md.'", text)
            self.assertFalse(os.path.exists(os.path.join(self.out, "record.json")))

    def test_a_rendered_name_that_is_not_one_plain_ascii_component_or_ends_in_the_scratch_suffix_is_refused_and_nothing_is_written(self):
        # SOL-HW-REVIEW-FAN-OUT-CALLER-SEAM.C4: A caller may supply a function of the review folder and the merged tables that returns file names with their text. The driver calls it before writing anything, then writes each file into the output folder after the merge and lists the names it wrote in the record it writes and in its report, in text and in JSON with the same content. It accepts a name only if it is one plain component of ASCII letters, digits, full stops, underscores and hyphens that begins with a letter or digit and ends in neither a full stop nor the suffix the driver gives its own scratch files, and refuses any other name. It also refuses a name that, compared without regard to case, equals a name the driver itself uses in the output folder or another name rendered in the same merge, and a name that the output folder already holds unless an earlier merge wrote it and it is still a regular file, which the driver knows from the list of rendered names in the record that merge wrote, so a merge after running named units again replaces the files the earlier merge wrote and never a file put there by anyone else, nor one that has since become a link or a folder. A function that raises fails the run naming the caller, after the record in table form is written and with the report naming the earlier merge's rendered files as not of this merge. A caller that supplies none writes no file beyond the record in table form. Out of scope: the content of any rendered record.
        self.rendering_caller()
        refused = ("record.json.part", "setups.json.part", "reruns.json.part", "RECORD.JSON.PART", "notes.md.part",
                   "caf\u00e9.md", "cafe\u0301.md", "\u30ce\u30fc\u30c8.md", "-notes.md", ".notes.md", "_notes.md", "-",
                   "notes.", "notes.md.", "has space.md", "tab\t.md", "line\n.md", "notes.md\n")
        for name in refused:
            for as_json in (True, False):
                shutil.rmtree(self.out, ignore_errors=True)
                with mock.patch.dict(os.environ, {"RENDER_MODE": "named", "RENDER_NAME": name}):
                    status, text, _ = self.run_command(as_json=as_json)
                self.assertEqual(status, 1, f"{name!r}: {text}")
                self.assertIn("one plain component of ASCII letters, digits, full stops, underscores and hyphens", text, repr(name))
                self.assertFalse(os.path.exists(os.path.join(self.out, "record.json")), f"{name!r}: no record")
                self.assertEqual(set(os.listdir(self.out)) - {"units", "setups.json", "failed", "unsettled"}, set(), repr(name))

    def test_a_rendered_name_is_at_most_sixty_four_characters_long(self):
        # SOL-HW-REVIEW-FAN-OUT-CALLER-SEAM.C4: A caller may supply a function of the review folder and the merged tables that returns file names with their text. The driver calls it before writing anything, then writes each file into the output folder after the merge and lists the names it wrote in the record it writes and in its report, in text and in JSON with the same content. It refuses a name that carries a path, a name the driver itself uses in the output folder, and a name that the output folder already holds unless an earlier merge wrote it, which the driver knows from the list of rendered names in the record that merge wrote, so a merge after running named units again replaces the files the earlier merge wrote and never a file put there by anyone else. A function that raises fails the run naming the caller, after the record in table form is written and with the report naming the earlier merge's rendered files as not of this merge. A caller that supplies none writes no file beyond the record in table form. Out of scope: the content of any rendered record.
        self.rendering_caller()
        for name in ("a" * 61 + ".md", "b" * 64):
            self.assertEqual(len(name), 64)
            for as_json in (True, False):
                shutil.rmtree(self.out, ignore_errors=True)
                with mock.patch.dict(os.environ, {"RENDER_MODE": "named", "RENDER_NAME": name}):
                    status, text, _ = self.run_command(as_json=as_json)
                self.assertEqual(status, 0, f"{name!r}: {text}")
                self.assertEqual(self.read_out(name), "x")
                self.assertIn(name, json.loads(self.read_out("record.json"))["rendered"])
        for name in ("a" * 62 + ".md", "c" * 65, "d" * 300):
            self.assertGreater(len(name), 64)
            for as_json in (True, False):
                shutil.rmtree(self.out, ignore_errors=True)
                with mock.patch.dict(os.environ, {"RENDER_MODE": "named", "RENDER_NAME": name}):
                    status, text, _ = self.run_command(as_json=as_json)
                self.assertEqual(status, 1, f"{len(name)}: {text}")
                self.assertIn("is at most 64 characters long", text)
                self.assertFalse(os.path.exists(os.path.join(self.out, "record.json")), "no record")
                self.assertEqual(set(os.listdir(self.out)) - {"units", "setups.json", "failed", "unsettled"}, set())

    def test_a_rendered_name_the_windows_file_system_reserves_for_a_device_is_refused_with_or_without_an_extension_in_any_case(self):
        # SOL-HW-REVIEW-FAN-OUT-CALLER-SEAM.C4: A caller may supply a function of the review folder and the merged tables that returns file names with their text. The driver calls it before writing anything, then writes each file into the output folder after the merge and lists the names it wrote in the record it writes and in its report, in text and in JSON with the same content. It refuses a name that carries a path, a name the driver itself uses in the output folder, and a name that the output folder already holds unless an earlier merge wrote it, which the driver knows from the list of rendered names in the record that merge wrote, so a merge after running named units again replaces the files the earlier merge wrote and never a file put there by anyone else. A function that raises fails the run naming the caller, after the record in table form is written and with the report naming the earlier merge's rendered files as not of this merge. A caller that supplies none writes no file beyond the record in table form. Out of scope: the content of any rendered record.
        self.rendering_caller()
        for name in ("con", "CON", "Nul.txt", "COM1.md", "lpt9", "aux.tar.gz", "Prn", "com9", "LPT1.md"):
            for as_json in (True, False):
                shutil.rmtree(self.out, ignore_errors=True)
                with mock.patch.dict(os.environ, {"RENDER_MODE": "named", "RENDER_NAME": name}):
                    status, text, _ = self.run_command(as_json=as_json)
                self.assertEqual(status, 1, f"{name!r}: {text}")
                self.assertIn("is not a name Windows reserves for a device", text, name)
                self.assertFalse(os.path.exists(os.path.join(self.out, "record.json")), f"{name!r}: no record")
                self.assertEqual(set(os.listdir(self.out)) - {"units", "setups.json", "failed", "unsettled"}, set(), repr(name))
        for name in ("console.md", "com10.md", "a.con", "com0", "lpt", "nullable", "aux1.md"):
            shutil.rmtree(self.out, ignore_errors=True)
            with mock.patch.dict(os.environ, {"RENDER_MODE": "named", "RENDER_NAME": name}):
                status, text, _ = self.run_command(as_json=True)
            self.assertEqual(status, 0, f"{name!r}: {text}")
            self.assertEqual(self.read_out(name), "x")

    def test_a_name_the_drivers_own_record_lists_as_rendered_is_not_reported_as_not_of_this_merge(self):
        # SOL-HW-REVIEW-FAN-OUT-CALLER-SEAM.C4: A caller may supply a function of the review folder and the merged tables that returns file names with their text. The driver calls it before writing anything, then writes each file into the output folder after the merge and lists the names it wrote in the record it writes and in its report, in text and in JSON with the same content. It refuses a name that carries a path, a name the driver itself uses in the output folder, and a name that the output folder already holds unless an earlier merge wrote it, which the driver knows from the list of rendered names in the record that merge wrote, so a merge after running named units again replaces the files the earlier merge wrote and never a file put there by anyone else. A function that raises fails the run naming the caller, after the record in table form is written and with the report naming the earlier merge's rendered files as not of this merge. A caller that supplies none writes no file beyond the record in table form. Out of scope: the content of any rendered record.
        self.rendering_caller()
        status, text, _ = self.run_command(as_json=True)
        self.assertEqual(status, 0, text)
        record = json.loads(self.read_out("record.json"))
        record["rendered"] = record["rendered"] + ["record.json", "UNITS", "Setups.json", "x" * 65, "con"]
        self.write(os.path.join(self.out, "record.json"), json.dumps(record))
        with mock.patch.dict(os.environ, {"RENDER_MODE": "fewer"}):
            status, text, _ = self.run_command("--rerun", "alpha", as_json=True)
        self.assertEqual(status, 0, text)
        report = json.loads(text)
        self.assertEqual(report["not_this_merge"], ["second.md"])
        self.assertEqual(json.loads(self.read_out("record.json"))["not_this_merge"], ["second.md"])
        self.assertEqual(review_fan_out.rendered_earlier(self.out), ["summary.md", "second.md"])

    def test_a_rendered_name_of_plain_ascii_is_accepted_and_the_same_name_in_nfc_and_nfd_form_is_never_written_twice(self):
        # SOL-HW-REVIEW-FAN-OUT-CALLER-SEAM.C4: A caller may supply a function of the review folder and the merged tables that returns file names with their text. The driver calls it before writing anything, then writes each file into the output folder after the merge and lists the names it wrote in the record it writes and in its report, in text and in JSON with the same content. It accepts a name only if it is one plain component of ASCII letters, digits, full stops, underscores and hyphens that begins with a letter or digit and ends in neither a full stop nor the suffix the driver gives its own scratch files, and refuses any other name. It also refuses a name that, compared without regard to case, equals a name the driver itself uses in the output folder or another name rendered in the same merge, and a name that the output folder already holds unless an earlier merge wrote it and it is still a regular file, which the driver knows from the list of rendered names in the record that merge wrote, so a merge after running named units again replaces the files the earlier merge wrote and never a file put there by anyone else, nor one that has since become a link or a folder. A function that raises fails the run naming the caller, after the record in table form is written and with the report naming the earlier merge's rendered files as not of this merge. A caller that supplies none writes no file beyond the record in table form. Out of scope: the content of any rendered record.
        self.rendering_caller()
        for name in ("layout-review-2.md", "a", "Notes_1.v2.txt", "7.md"):
            for as_json in (True, False):
                shutil.rmtree(self.out, ignore_errors=True)
                with mock.patch.dict(os.environ, {"RENDER_MODE": "named", "RENDER_NAME": name}):
                    status, text, _ = self.run_command(as_json=as_json)
                self.assertEqual(status, 0, f"{name!r}: {text}")
                self.assertEqual(self.read_out(name), "x")
                self.assertIn(name, json.loads(self.read_out("record.json"))["rendered"])
        nfc, nfd = unicodedata.normalize("NFC", "caf\u00e9.md"), unicodedata.normalize("NFD", "caf\u00e9.md")
        self.assertNotEqual(nfc, nfd)
        for name in (nfc, nfd):
            shutil.rmtree(self.out, ignore_errors=True)
            with mock.patch.dict(os.environ, {"RENDER_MODE": "named", "RENDER_NAME": name}):
                status, text, _ = self.run_command(as_json=True)
            self.assertEqual(status, 1, text)
            self.assertEqual(set(os.listdir(self.out)) - {"units", "setups.json", "failed", "unsettled"}, set())
            self.assertFalse(os.path.exists(os.path.join(self.out, "record.json")))

    def test_an_earlier_written_name_that_has_become_a_link_or_a_folder_is_refused_and_nothing_outside_the_output_folder_is_written(self):
        # SOL-HW-REVIEW-FAN-OUT-CALLER-SEAM.C4: A caller may supply a function of the review folder and the merged tables that returns file names with their text. The driver calls it before writing anything, then writes each file into the output folder after the merge and lists the names it wrote in the record it writes and in its report, in text and in JSON with the same content. It accepts a name only if it is one plain component of ASCII letters, digits, full stops, underscores and hyphens that begins with a letter or digit and ends in neither a full stop nor the suffix the driver gives its own scratch files, and refuses any other name. It also refuses a name that, compared without regard to case, equals a name the driver itself uses in the output folder or another name rendered in the same merge, and a name that the output folder already holds unless an earlier merge wrote it and it is still a regular file, which the driver knows from the list of rendered names in the record that merge wrote, so a merge after running named units again replaces the files the earlier merge wrote and never a file put there by anyone else, nor one that has since become a link or a folder. A function that raises fails the run naming the caller, after the record in table form is written and with the report naming the earlier merge's rendered files as not of this merge. A caller that supplies none writes no file beyond the record in table form. Out of scope: the content of any rendered record.
        self.rendering_caller()
        status, text, _ = self.run_command(as_json=True)
        self.assertEqual(status, 0, text)
        outside = os.path.join(self.root, "outside-target.txt")
        self.write(outside, "untouched")
        for kind in ("link", "dangling", "folder"):
            for as_json in (True, False):
                path = os.path.join(self.out, "summary.md")
                if os.path.islink(path) or os.path.isfile(path):
                    os.remove(path)
                elif os.path.isdir(path):
                    shutil.rmtree(path)
                if kind == "link":
                    os.symlink(outside, path)
                elif kind == "dangling":
                    os.symlink(os.path.join(self.root, "never-made.txt"), path)
                else:
                    os.mkdir(path)
                before = self.read_out("record.json")
                status, text, _ = self.run_command("--rerun", "alpha", as_json=as_json)
                self.assertEqual(status, 1, f"{kind}: {text}")
                self.assertIn("'summary.md'", text)
                self.assertIn("as a link or a folder", text, kind)
                with open(outside, encoding="utf-8") as handle:
                    self.assertEqual(handle.read(), "untouched", kind)
                self.assertFalse(os.path.exists(os.path.join(self.root, "never-made.txt")), kind)
                self.assertEqual(self.read_out("record.json"), before, f"{kind}: the record is not rewritten")
        # a link or a folder is not listed as the driver's own file left over either
        path = os.path.join(self.out, "summary.md")
        shutil.rmtree(path)
        os.symlink(outside, path)
        os.remove(os.path.join(self.out, "second.md"))
        os.mkdir(os.path.join(self.out, "second.md"))
        self.assertEqual(review_fan_out.left_over(self.out, ["second.md", "summary.md"], []), [])

    def test_a_file_an_earlier_merge_wrote_that_this_merge_does_not_render_again_is_named_as_not_of_this_merge_and_stays_the_drivers(self):
        # SOL-HW-REVIEW-FAN-OUT-CALLER-SEAM.C4: A caller may supply a function of the review folder and the merged tables that returns file names with their text. The driver calls it before writing anything, then writes each file into the output folder after the merge and lists the names it wrote in the record it writes and in its report, in text and in JSON with the same content. It refuses a name that carries a path, a name the driver itself uses in the output folder, and a name that the output folder already holds unless an earlier merge wrote it, which the driver knows from the list of rendered names in the record that merge wrote, so a merge after running named units again replaces the files the earlier merge wrote and never a file put there by anyone else. A function that raises fails the run naming the caller, after the record in table form is written and with the report naming the earlier merge's rendered files as not of this merge. A caller that supplies none writes no file beyond the record in table form. Out of scope: the content of any rendered record.
        self.rendering_caller()
        status, text, _ = self.run_command(as_json=True)
        self.assertEqual(status, 0, text)
        with mock.patch.dict(os.environ, {"RENDER_MODE": "fewer"}):
            status, text, _ = self.run_command("--rerun", "alpha", as_json=True)
        self.assertEqual(status, 0, text)
        report = json.loads(text)
        self.assertEqual(report["rendered"], ["summary.md"])
        self.assertEqual(report["not_this_merge"], ["second.md"])
        self.assertEqual(json.loads(self.read_out("record.json"))["not_this_merge"], ["second.md"], "the record names it too")
        self.assertEqual(self.read_out("second.md"), "second", "the dropped file stays on disk")

        with mock.patch.dict(os.environ, {"RENDER_MODE": "fewer"}):
            status, text, _ = self.run_command("--rerun", "alpha")
        self.assertEqual(status, 0, text)
        self.assertIn("NOT THIS MERGE | second.md | written by an earlier merge, not by this one", text.splitlines())

        # a later merge naming the dropped file replaces it, as the driver's own
        with mock.patch.dict(os.environ, {"RENDER_MODE": "dropped"}):
            status, text, _ = self.run_command("--rerun", "alpha", as_json=True)
        self.assertEqual(status, 0, text)
        report = json.loads(text)
        self.assertEqual(report["rendered"], ["second.md"])
        self.assertEqual(report["not_this_merge"], ["summary.md"])
        self.assertEqual(self.read_out("second.md"), "again")

        # a dropped file that has been removed is no longer named
        os.remove(os.path.join(self.out, "summary.md"))
        with mock.patch.dict(os.environ, {"RENDER_MODE": "dropped"}):
            status, text, _ = self.run_command("--rerun", "alpha", as_json=True)
        self.assertEqual(status, 0, text)
        self.assertEqual(json.loads(text)["not_this_merge"], [])

    def test_a_rendering_function_that_raises_fails_the_run_after_the_record_is_written_and_names_the_earlier_files(self):
        # SOL-HW-REVIEW-FAN-OUT-CALLER-SEAM.C4: A caller may supply a function of the review folder and the merged tables that returns file names with their text. The driver calls it before writing anything, then writes each file into the output folder after the merge and lists the names it wrote in the record it writes and in its report, in text and in JSON with the same content. It refuses a name that carries a path, a name the driver itself uses in the output folder, and a name that the output folder already holds unless an earlier merge wrote it, which the driver knows from the list of rendered names in the record that merge wrote, so a merge after running named units again replaces the files the earlier merge wrote and never a file put there by anyone else. A function that raises fails the run naming the caller, after the record in table form is written and with the report naming the earlier merge's rendered files as not of this merge. A caller that supplies none writes no file beyond the record in table form. Out of scope: the content of any rendered record.
        self.rendering_caller()
        status, text, _ = self.run_command(as_json=True)
        self.assertEqual(status, 0, text)
        with mock.patch.dict(os.environ, {"RENDER_MODE": "raise", "RENDER_TAG": "c"}):
            status, text, _ = self.run_command("--rerun", "alpha", as_json=True)
        self.assertEqual(status, 1, text)
        report = json.loads(text)
        self.assertEqual(report["result"], "FAILED")
        self.assertTrue(any("the caller's RENDER raised KeyError" in cause and "fix the caller synth" in cause
                            for cause in report["refusals"]), report["refusals"])
        self.assertEqual(report["not_this_merge"], ["summary.md", "second.md"])
        self.assertEqual(report["rendered"], [])
        with open(os.path.join(self.out, "record.json"), encoding="utf-8") as handle:
            record = json.load(handle)
        self.assertEqual(record["not_this_merge"], ["summary.md", "second.md"], "the record in table form is written")
        self.assertEqual(record["tables"]["Verdicts"]["columns"], ["Item", "Verdict", "Rests on"])
        self.assertEqual(self.read_out("summary.md"), f"{self.review}|3|a", "the earlier merge's file stands, unchanged")

        with mock.patch.dict(os.environ, {"RENDER_MODE": "raise"}):
            status, text, _ = self.run_command("--rerun", "alpha")
        self.assertEqual(status, 1)
        self.assertIn("NOT THIS MERGE | summary.md | written by an earlier merge, not by this one", text.splitlines())
        self.assertIn("NOT THIS MERGE | second.md | written by an earlier merge, not by this one", text.splitlines())
        self.assertTrue(any(line.startswith("REFUSED | the caller's RENDER raised KeyError") for line in text.splitlines()))
        self.assertTrue(any(line.startswith("RESULT | FAILED") for line in text.splitlines()))

        # the files stay the driver's to replace once the function works again
        with mock.patch.dict(os.environ, {"RENDER_TAG": "d"}):
            status, text, _ = self.run_command("--rerun", "alpha", as_json=True)
        self.assertEqual(status, 0, text)
        self.assertEqual(self.read_out("summary.md"), f"{self.review}|3|d")

    def folds_case(self):
        probe = os.path.join(self.root, "CaseProbe")
        self.write(probe, "x")
        self.addCleanup(os.remove, probe)
        return os.path.exists(probe.lower())

    def test_an_earlier_merges_file_whose_name_differs_only_in_case_from_a_later_name_stays_disclosed_and_a_foreign_file_is_never_overwritten(self):
        # SOL-HW-REVIEW-FAN-OUT-CALLER-SEAM.C4: A caller may supply a function of the review folder and the merged tables that returns file names with their text. The driver calls it before writing anything, then writes each file into the output folder after the merge and lists the names it wrote in the record it writes and in its report, in text and in JSON with the same content. It accepts a name only if it is one plain component of ASCII letters, digits, full stops, underscores and hyphens that begins with a letter or digit and ends in neither a full stop nor the suffix the driver gives its own scratch files, is at most sixty-four characters long and is not a name the Windows file system reserves for a device (such as CON, PRN, AUX, NUL, COM1 to COM9 and LPT1 to LPT9, with or without an extension), and refuses any other name. It also refuses a name that, compared without regard to case, equals a name the driver itself uses in the output folder or another name rendered in the same merge, and a name that the output folder already holds unless an earlier merge wrote it and it is still a regular file, which the driver knows from the list of rendered names in the record that merge wrote, so a merge after running named units again replaces the files the earlier merge wrote and never a file put there by anyone else, nor one that has since become a link or a folder. A function that raises fails the run naming the caller, after the record in table form is written and with the report naming the earlier merge's rendered files as not of this merge. A caller that supplies none writes no file beyond the record in table form. Out of scope: the content of any rendered record.
        if self.folds_case():
            self.skipTest("the temporary folder's file system folds case, so Report.md and report.md are one file here")
        self.rendering_caller()
        with mock.patch.dict(os.environ, {"RENDER_MODE": "named", "RENDER_NAME": "Report.md"}):
            status, text, _ = self.run_command(as_json=True)
        self.assertEqual(status, 0, text)
        self.assertEqual(json.loads(self.read_out("record.json"))["rendered"], ["Report.md"])

        # no foreign file: the later name is written and the earlier file is named as not of this merge, in the report and the record
        with mock.patch.dict(os.environ, {"RENDER_MODE": "named", "RENDER_NAME": "report.md"}):
            status, text, _ = self.run_command("--rerun", "alpha", as_json=True)
            self.assertEqual(status, 0, text)
            report = json.loads(text)
            self.assertEqual((report["rendered"], report["not_this_merge"]), (["report.md"], ["Report.md"]))
            self.assertEqual(json.loads(self.read_out("record.json"))["not_this_merge"], ["Report.md"])
            self.assertEqual((self.read_out("Report.md"), self.read_out("report.md")), ("x", "x"))
            status, text, _ = self.run_command("--rerun", "alpha")
        self.assertEqual(status, 0, text)
        self.assertIn("NOT THIS MERGE | Report.md | written by an earlier merge, not by this one", text.splitlines())

        # a foreign file under the later name: refused, never overwritten, and the earlier file stands and stays disclosed
        shutil.rmtree(self.out)
        with mock.patch.dict(os.environ, {"RENDER_MODE": "named", "RENDER_NAME": "Report.md"}):
            status, text, _ = self.run_command(as_json=True)
        self.assertEqual(status, 0, text)
        self.write(os.path.join(self.out, "report.md"), "someone else's")
        before = self.read_out("record.json")
        with mock.patch.dict(os.environ, {"RENDER_MODE": "named", "RENDER_NAME": "report.md"}):
            status, text, _ = self.run_command("--rerun", "alpha", as_json=True)
        self.assertEqual(status, 1, text)
        self.assertTrue(any("'report.md'" in cause and "no earlier merge wrote" in cause for cause in json.loads(text)["refusals"]))
        self.assertEqual(self.read_out("report.md"), "someone else's")
        self.assertEqual(self.read_out("Report.md"), "x")
        self.assertEqual(self.read_out("record.json"), before, "a refusal leaves the record, which still names Report.md")
        self.assertEqual(json.loads(before)["rendered"], ["Report.md"])

    def test_a_rerun_with_a_caller_that_defines_no_render_carries_the_earlier_files_into_not_this_merge_and_a_caller_that_never_rendered_adds_no_keys(self):
        # SOL-HW-REVIEW-FAN-OUT-CALLER-SEAM.C4: A caller may supply a function of the review folder and the merged tables that returns file names with their text. The driver calls it before writing anything, then writes each file into the output folder after the merge and lists the names it wrote in the record it writes and in its report, in text and in JSON with the same content. It accepts a name only if it is one plain component of ASCII letters, digits, full stops, underscores and hyphens that begins with a letter or digit and ends in neither a full stop nor the suffix the driver gives its own scratch files, is at most sixty-four characters long and is not a name the Windows file system reserves for a device (such as CON, PRN, AUX, NUL, COM1 to COM9 and LPT1 to LPT9, with or without an extension), and refuses any other name. It also refuses a name that, compared without regard to case, equals a name the driver itself uses in the output folder or another name rendered in the same merge, and a name that the output folder already holds unless an earlier merge wrote it and it is still a regular file, which the driver knows from the list of rendered names in the record that merge wrote, so a merge after running named units again replaces the files the earlier merge wrote and never a file put there by anyone else, nor one that has since become a link or a folder. A function that raises fails the run naming the caller, after the record in table form is written and with the report naming the earlier merge's rendered files as not of this merge. A caller that supplies none writes no file beyond the record in table form. Out of scope: the content of any rendered record.
        self.rendering_caller()
        status, text, _ = self.run_command(as_json=True)
        self.assertEqual(status, 0, text)
        self.caller_module(caller_text())
        status, text, _ = self.run_command("--rerun", "alpha", as_json=True)
        self.assertEqual(status, 0, text)
        report = json.loads(text)
        self.assertEqual((report["rendered"], report["not_this_merge"]), ([], ["summary.md", "second.md"]))
        self.assertEqual(json.loads(self.read_out("record.json"))["not_this_merge"], ["summary.md", "second.md"])
        self.assertEqual((self.read_out("second.md"), self.read_out("summary.md")), ("second", f"{self.review}|3|a"))
        status, text, _ = self.run_command("--rerun", "alpha")
        self.assertEqual(status, 0, text)
        self.assertIn("NOT THIS MERGE | summary.md | written by an earlier merge, not by this one", text.splitlines())
        self.assertIn("NOT THIS MERGE | second.md | written by an earlier merge, not by this one", text.splitlines())
        # the carried names are not lost on the next rerun either
        status, text, _ = self.run_command("--rerun", "alpha", as_json=True)
        self.assertEqual(json.loads(text)["not_this_merge"], ["summary.md", "second.md"])

        # a caller that never rendered anything adds no keys
        shutil.rmtree(self.out)
        status, text, _ = self.run_command(as_json=True)
        self.assertEqual(status, 0, text)
        for document in (json.loads(text), json.loads(self.read_out("record.json"))):
            self.assertNotIn("rendered", document)
            self.assertNotIn("not_this_merge", document)
        status, text, _ = self.run_command("--rerun", "alpha", as_json=True)
        self.assertEqual(status, 0, text)
        self.assertNotIn("rendered", json.loads(text))
        self.assertNotIn("not_this_merge", json.loads(text))

    def test_whatever_the_earlier_merge_wrote_and_the_folder_holds_and_this_merge_renders_a_foreign_file_is_never_touched_every_earlier_file_is_disclosed_and_a_refusal_writes_nothing(self):
        # SOL-HW-REVIEW-FAN-OUT-CALLER-SEAM.C4: A caller may supply a function of the review folder and the merged tables that returns file names with their text. The driver calls it before writing anything, then writes each file into the output folder after the merge and lists the names it wrote in the record it writes and in its report, in text and in JSON with the same content. It accepts a name only if it is one plain component of ASCII letters, digits, full stops, underscores and hyphens that begins with a letter or digit and ends in neither a full stop nor the suffix the driver gives its own scratch files, is at most sixty-four characters long and is not a name the Windows file system reserves for a device (such as CON, PRN, AUX, NUL, COM1 to COM9 and LPT1 to LPT9, with or without an extension), and refuses any other name. It also refuses a name that, compared without regard to case, equals a name the driver itself uses in the output folder or another name rendered in the same merge, and a name that the output folder already holds unless an earlier merge wrote it and it is still a regular file, which the driver knows from the list of rendered names in the record that merge wrote, so a merge after running named units again replaces the files the earlier merge wrote and never a file put there by anyone else, nor one that has since become a link or a folder. A function that raises fails the run naming the caller, after the record in table form is written and with the report naming the earlier merge's rendered files as not of this merge. A caller that supplies none writes no file beyond the record in table form. Out of scope: the content of any rendered record.
        folds = self.folds_case()
        self.rendering_caller()
        status, text, _ = self.run_command(as_json=True)
        self.assertEqual(status, 0, text)
        base = os.path.join(self.root, "base")
        shutil.copytree(self.out, base, symlinks=True)
        bookkeeping = set(review_fan_out.RESERVED_NAMES)
        outside = os.path.join(self.root, "outside.txt")
        pairs = [] if folds else [["Report.md", "report.md"]]
        earliers = [[], ["a.md"], ["a.md", "b.md"]] + pairs
        extras = ("nothing extra", "a foreign file of the same name", "a foreign file of a case-variant name", "a link", "a folder")
        shapes = ("the same", "fewer", "none", "a case variant", "new")
        checked = 0
        for earlier in earliers:
            for extra in extras:
                if folds and extra == "a foreign file of a case-variant name":
                    continue
                for shape in shapes + ("no RENDER",):
                    if folds and shape == "a case variant":
                        continue
                    state = f"earlier {earlier}, folder with {extra}, this merge renders {shape}"
                    renders = {"the same": list(earlier) or ["a.md"], "fewer": earlier[:1], "none": [],
                               "a case variant": [name.swapcase() for name in earlier] or ["A.md"],
                               "new": ["new.md"], "no RENDER": []}[shape]
                    shutil.rmtree(self.out)
                    shutil.copytree(base, self.out, symlinks=True)
                    for name in ("summary.md", "second.md"):
                        os.remove(os.path.join(self.out, name))
                    record = json.loads(self.read_out("record.json"))
                    record["rendered"] = list(earlier)
                    record.pop("not_this_merge", None)
                    self.write(os.path.join(self.out, "record.json"), json.dumps(record))
                    for name in earlier:
                        self.write(os.path.join(self.out, name), f"driver {name}")
                    self.write(outside, "outside")
                    target = (earlier or renders or ["a.md"])[0]
                    foreign = target if target not in earlier else "foreign.md"
                    foreign = foreign.swapcase() if extra == "a foreign file of a case-variant name" else foreign
                    if foreign in earlier:
                        foreign = "other-foreign.md"
                    guarded = {}
                    if extra.startswith("a foreign file"):
                        self.write(os.path.join(self.out, foreign), "foreign")
                        guarded[foreign] = "foreign"
                    elif extra == "a link":
                        os.remove(os.path.join(self.out, target)) if os.path.lexists(os.path.join(self.out, target)) else None
                        os.symlink(outside, os.path.join(self.out, target))
                        guarded[target] = ("link", outside)
                    elif extra == "a folder":
                        if os.path.lexists(os.path.join(self.out, target)):
                            os.remove(os.path.join(self.out, target))
                        os.mkdir(os.path.join(self.out, target))
                        guarded[target] = ("folder",)
                    top = lambda: {name: (os.path.islink(os.path.join(self.out, name)), os.path.isdir(os.path.join(self.out, name)))
                                   for name in os.listdir(self.out) if name not in bookkeeping - {review_fan_out.RECORD}}
                    contents = lambda: {name: self.read_out(name) for name in os.listdir(self.out)
                                        if os.path.isfile(os.path.join(self.out, name)) and name not in bookkeeping - {review_fan_out.RECORD}}
                    before_top, before_contents = top(), contents()
                    on_disk = [name for name in earlier if review_fan_out.is_regular_file(os.path.join(self.out, name))]
                    if shape == "no RENDER":
                        self.caller_module(caller_text())
                        environment = {}
                    else:
                        self.rendering_caller()
                        environment = {"RENDER_MODE": "table", "RENDER_FILES": json.dumps({name: "this merge" for name in renders})}
                    with mock.patch.dict(os.environ, environment):
                        status, text, _ = self.run_command("--rerun", "alpha", as_json=True)
                    document = json.loads(text)
                    for name, kept in guarded.items():
                        path = os.path.join(self.out, name)
                        if kept == "foreign":
                            self.assertEqual(self.read_out(name), "foreign", f"{state}: a foreign file was replaced")
                        elif kept[0] == "link":
                            self.assertTrue(os.path.islink(path) and os.readlink(path) == outside, f"{state}: a link was replaced")
                            with open(outside, encoding="utf-8") as handle:
                                self.assertEqual(handle.read(), "outside", f"{state}: the file behind a link was written")
                        else:
                            self.assertTrue(os.path.isdir(path) and not os.path.islink(path), f"{state}: a folder was replaced")
                    record = json.loads(self.read_out("record.json"))
                    listed = set(record.get("rendered", [])) | set(record.get("not_this_merge", []))
                    for name in on_disk:
                        if name in guarded:
                            continue
                        self.assertIn(name, listed, f"{state}: the earlier file {name} is named in neither rendered nor not_this_merge of the record")
                        if status == 0:
                            self.assertIn(name, set(document.get("rendered", [])) | set(document.get("not_this_merge", [])),
                                          f"{state}: the earlier file {name} is named in neither list of the report")
                    if status != 0:
                        self.assertTrue(document["refusals"], f"{state}: the run failed with no refusal")
                        self.assertEqual((top(), contents()), (before_top, before_contents), f"{state}: a refused run wrote something")
                        self.assertEqual(record["rendered"], list(earlier), f"{state}: a refused run changed the record")
                    else:
                        for name in renders:
                            self.assertEqual(self.read_out(name), "this merge", f"{state}: {name} was not written")
                    checked += 1
        self.assertGreaterEqual(checked, 60)

    def test_a_record_that_cannot_be_read_back_for_the_rendered_names_is_refused_not_defaulted(self):
        # SOL-HW-REVIEW-FAN-OUT-CALLER-SEAM.C4: A caller may supply a function of the review folder and the merged tables that returns file names with their text. The driver calls it before writing anything, then writes each file into the output folder after the merge and lists the names it wrote in the record it writes and in its report, in text and in JSON with the same content. It refuses a name that carries a path, a name the driver itself uses in the output folder, and a name that the output folder already holds unless an earlier merge wrote it, which the driver knows from the list of rendered names in the record that merge wrote, so a merge after running named units again replaces the files the earlier merge wrote and never a file put there by anyone else. A function that raises fails the run naming the caller, after the record in table form is written and with the report naming the earlier merge's rendered files as not of this merge. A caller that supplies none writes no file beyond the record in table form. Out of scope: the content of any rendered record.
        self.rendering_caller()
        status, text, _ = self.run_command(as_json=True)
        self.assertEqual(status, 0, text)
        for damage in ("not json", '{"rendered": "summary.md"}', '{"rendered": [1]}', '[]'):
            self.write(os.path.join(self.out, "record.json"), damage)
            status, text, _ = self.run_command("--rerun", "alpha", as_json=True)
            self.assertEqual(status, 1, damage)
            self.assertTrue(any("record.json" in cause for cause in json.loads(text)["refusals"]), damage)
            self.assertEqual(self.read_out("summary.md"), f"{self.review}|3|a")

    def test_a_rendering_function_that_does_not_accept_the_review_folder_and_the_tables_is_refused_at_load(self):
        # SOL-HW-REVIEW-FAN-OUT-CALLER-SEAM.C4: A caller may supply a function of the review folder and the merged tables that returns file names with their text. The driver calls it before writing anything, then writes each file into the output folder after the merge and lists the names it wrote in the record it writes and in its report, in text and in JSON with the same content. It refuses a name that carries a path, a name the driver itself uses in the output folder, and a name that the output folder already holds unless an earlier merge wrote it, which the driver knows from the list of rendered names in the record that merge wrote, so a merge after running named units again replaces the files the earlier merge wrote and never a file put there by anyone else. A function that raises fails the run naming the caller, after the record in table form is written and with the report naming the earlier merge's rendered files as not of this merge. A caller that supplies none writes no file beyond the record in table form. Out of scope: the content of any rendered record.
        self.caller_module(caller_text() + "\nRENDER = 5\n")
        self.refused("RENDER", "make it a function")
        self.caller_module(caller_text() + "\ndef RENDER(folder):\n    return {}\n")
        self.refused("RENDER", "synth", "RENDER(review_folder, tables)")
        self.assertEqual(self.calls(), [])

    # --- C5: a caller defining none of the attributes

    def test_a_caller_defining_none_of_the_optional_attributes_writes_and_reports_nothing_more(self):
        # SOL-HW-REVIEW-FAN-OUT-CALLER-SEAM.C5: A synthetic caller that defines none of the retrieval grant, the checklist function and the rendered record gives the results it gave before this change, in text and in JSON, and the driver's existing tests pass with the one change that each synthetic caller's prompt function accepts the review folder. Out of scope: the new attributes' own behaviour, which the criteria above cover.
        status, text, _ = self.run_command(as_json=True)
        self.assertEqual(status, 0, text)
        report = json.loads(text)
        self.assertNotIn("rendered", report)
        self.assertNotIn("not_this_merge", report)
        self.assertEqual(set(os.listdir(self.out)) - {"failed", "unsettled"}, {"record.json", "setups.json", "units"})
        self.assertEqual(sorted(os.listdir(os.path.join(self.out, "units"))), [f"{unit}.json" for unit in self.UNITS])
        for fork in self.forks():
            self.assertEqual(self.flag(fork, "--tools"), "Read,Glob")
        self.assertEqual(self.checklist_calls(), 0)
        shutil.rmtree(self.out)
        status, text, _ = self.run_command()
        self.assertEqual(status, 0, text)
        self.assertFalse([line for line in text.splitlines() if line.startswith(("RENDERED", "NOT THIS MERGE"))])


class Parsing(unittest.TestCase):
    """The agent command line's events as the command reads them, over synthetic streams."""

    def stream(self, *events):
        return "\n".join(json.dumps(event) for event in events)

    def test_an_event_or_block_the_command_relies_on_that_is_ill_formed_is_named_and_never_defaulted(self):
        # SOL-HW-REVIEW-FAN-OUT-DRIVER.C2: Each session's start report is read and a run whose report shows other tools than were granted, another model, any MCP server, an instruction source the command line was asked to exclude or another working directory fails naming the session. The setup session is started with the read tools only and a prompt that asks for no judgement and no image and for one fixed token as the whole answer and that either tells it which documents and records to read or, when the caller names them as files, holds their text itself, sent on standard input so that the session has no tool use to narrate between; any text the setup session writes, in its answer or between its tool uses, other than that token after trimming, and any content block of its history that is neither text, a tool use nor a thinking block whose text is empty, fails the run, so no forked reviewer inherits a verdict; a thinking block that carries text, and a redacted one, fail it; a setup session that fails only for text written between its tool uses is started again, up to twice, before the run fails, and every attempt's session is reported with its cost, and a read of a file whose type is not text in the setup session's tool uses fails the run naming the file, as does a file the caller names whose type is not text, before any session is started. Out of scope: the content of a caller's prompt for its units.
        use = lambda **given: {"type": "assistant", "message": {"content": [{"type": "tool_use", **given}]}}
        cases = {"a tool use with no name": (use(input={}), "tool use with no string `name`"),
                 "a tool use with a name that is not text": (use(name=7, input={}), "tool use with no string `name`"),
                 "a tool use with no input": (use(name="Grep"), "Grep tool use with no `input` mapping"),
                 "an assistant event with no content": ({"type": "assistant", "message": "x"}, "no `message.content` list"),
                 "a content list that is text": ({"type": "assistant", "message": {"content": "hello"}}, "no `message.content` list"),
                 "a block with no type": ({"type": "assistant", "message": {"content": [{"text": "x"}]}}, "content block with no string `type`"),
                 "a block that is not a mapping": ({"type": "assistant", "message": {"content": ["x"]}}, "content block with no string `type`"),
                 "a text block with no text": ({"type": "assistant", "message": {"content": [{"type": "text"}]}}, "text block with no string `text`")}
        for name, (event, word) in cases.items():
            with self.subTest(case=name):
                session = review_fan_out.parse_stream(self.stream(event))
                self.assertTrue(any(word in why for why in session.malformed), session.malformed)
                self.assertFalse(any(name == "None" for name, _, _ in session.tool_uses))
                problems = review_fan_out.start_problems(session, "the session", ["Read"], None, "/review")
                self.assertTrue(any(word in why for why in problems), problems)
        session = review_fan_out.parse_stream(self.stream({"type": "assistant", "message": {"content": [{"type": "text"}]}}))
        self.assertEqual(session.blocks, [("text", "")])

    def test_a_result_report_that_succeeded_without_a_figure_or_with_a_mistyped_one_is_named(self):
        # SOL-HW-REVIEW-FAN-OUT-DRIVER.C5: Against a stub that reports a fork's cost, API time and turn count cumulatively including its setup session, as the agent command line does, the record gives each fork its own cost, time and turns, the setup session its own, and the run their sum; token usage is taken as each session reports it, split into tokens read from the cache, written to it, fresh and generated, and a fork that reads no cache is flagged. The record is in the text and the JSON report. Out of scope: judging whether a run was worth its cost.
        full = {"type": "result", "is_error": False, "result": "ok", "total_cost_usd": 0.1, "duration_api_ms": 5, "num_turns": 1,
                "usage": {"input_tokens": 1, "output_tokens": 2, "cache_read_input_tokens": 3, "cache_creation_input_tokens": 4}}
        good = review_fan_out.parse_stream(self.stream(full))
        self.assertTrue(good.reported)
        self.assertEqual((good.malformed, good.absent), ([], []))
        for key in ("total_cost_usd", "duration_api_ms", "num_turns", "usage", "result"):
            gone = review_fan_out.parse_stream(self.stream({k: v for k, v in full.items() if k != key}))
            self.assertEqual(gone.absent, [key])
            if key != "result":
                self.assertEqual(review_fan_out.figures(gone)["cost_usd"], 0.0, "no figure is made up")
        for key in ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"):
            gone = review_fan_out.parse_stream(self.stream({**full, "usage": {k: v for k, v in full["usage"].items() if k != key}}))
            self.assertEqual(gone.absent, [f"usage.{key}"])
            self.assertFalse(gone.reported)
        for key, wrong in (("total_cost_usd", "0.1"), ("duration_api_ms", True), ("num_turns", 1.5), ("usage", []), ("result", 5),
                           ("is_error", "no"), ("session_id", 4)):
            bad = review_fan_out.parse_stream(self.stream({**full, key: wrong}))
            self.assertTrue(any(f"`{key}`" in why for why in bad.malformed), (key, bad.malformed))
        bad = review_fan_out.parse_stream(self.stream({**full, "usage": {**full["usage"], "input_tokens": "1"}}))
        self.assertTrue(any("`usage.input_tokens`" in why for why in bad.malformed))
        silent = review_fan_out.parse_stream(self.stream({k: v for k, v in full.items() if k != "is_error"}))
        self.assertTrue(any("no `is_error`" in why for why in silent.malformed))
        self.assertFalse(silent.succeeded)

    def test_the_one_typing_layer_takes_no_figure_that_is_not_finite_or_is_negative_and_no_cell_that_is_not_finite(self):
        # SOL-HW-REVIEW-FAN-OUT-DRIVER.C5: Against a stub that reports a fork's cost, API time and turn count cumulatively including its setup session, as the agent command line does, the record gives each fork its own cost, time and turns, the setup session its own, and the run their sum; token usage is taken as each session reports it, split into tokens read from the cache, written to it, fresh and generated, and a fork that reads no cache is flagged. The record is in the text and the JSON report. Out of scope: judging whether a run was worth its cost.
        for kind in (int, (int, float)):
            for value in (float("inf"), float("-inf"), float("nan"), -1, -0.5, 10 ** 400, True, False, "1", None, [], {}):
                with self.subTest(kind=kind, value=value):
                    self.assertFalse(review_fan_out.named(value, kind))
            self.assertTrue(review_fan_out.named(0, kind))
        self.assertTrue(review_fan_out.named(0.0, (int, float)))
        self.assertFalse(review_fan_out.named(0.5, int))
        for value in (float("inf"), float("nan"), 10 ** 400, True, None, [], {}):
            self.assertFalse(review_fan_out.cell(value), value)
        for value in ("", "text", -3, 2.5):
            self.assertTrue(review_fan_out.cell(value), value)
        shape = {"a": int, "b": [review_fan_out.SESSION_SHAPE["tokens"]], "c": review_fan_out.ANY_TEXT}
        self.assertIsNone(review_fan_out.shape_problem({"a": 1, "b": [], "c": ""}, shape, "r"))
        for value, word in (({"a": -1, "b": [], "c": ""}, "r.a is -1"), ({"a": 1, "b": [None], "c": ""}, "r.b[0] is not a mapping"),
                            ({"a": 1, "b": [], "c": None}, "r.c is None, not text"), ({"b": [], "c": ""}, "r has no `a`"),
                            ([], "r is not a mapping")):
            self.assertIn(word, review_fan_out.shape_problem(value, shape, "r"))


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
        for words in ("version 2.1.304", "slash commands", "`--model` takes a full model id", "the built-in plugins and agents",
                      "the account email", "the branch, the status and the recent commit subjects", "outside any work tree",
                      "the hooks and memory exclusions", "any text it writes other than the fixed token",
                      "is never defaulted or counted as cooperative", "unless the stream itself shows that read failed",
                      "unit whose last run again failed is unsettled", "flagged `no report`",
                      "a thinking block whose text is empty", "is started again as a fresh session, up to twice", "A pattern with no `round` group matches this round's citations only",
                      'FINDINGS["round"](review_folder)', 'FINDINGS["earlier"](review_folder)', "leaves any other match as written",
                      "naming the cell and the citation", "the caller's unit prompt must forbid it",
                      "each cell text or a finite number and never `null`, `true` or `false`",
                      "a caller's unit prompt must tell its reviewers to write text"):
            self.assertIn(words, section, f"the section says {words!r}")
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
        for words in ("A pattern with no `round` group matches this round's citations only", 'FINDINGS["round"]',
                      'FINDINGS["earlier"]', "leaves any other match as written", 'refuses one that "earlier" does not hold',
                      "the unit prompt must forbid it"):
            self.assertIn(words, doc)
        self.assertIn("Write no text before, between or after your reads", review_fan_out.ACK_INSTRUCTION)

    def test_the_four_attributes_a_caller_defines_are_named_where_the_command_describes_itself(self):
        # SOL-HW-REVIEW-FAN-OUT-CALLER-SEAM.C6: The task-runner description of the command, the driver's module description and the hardware notes' account of what a caller defines name the retrieval grant, the review folder in the prompt, the checklist as a function and the rendered record, and the hardware notes say the setup session keeps the read tools alone and state the retrieval grant's risk and why it is bounded (reviewers write nothing, the setup session fetches nothing and every verdict is checked structurally at the merge). Out of scope: the callers' own sections.
        taskfile = self.read("Taskfile.yml")
        task = self.flat(taskfile[taskfile.index("  hw:review-fan-out:"):].splitlines()[1])
        notes = self.read("hardware", "README.md")
        section = self.flat(notes[notes.index("## The review fan-out command"):].split("\n## ")[0])
        doc = self.flat(review_fan_out.__doc__)
        places = {
            "the task's description": (task, ("WebFetch", "retrieval grant", "unit and the review folder", "checklist (a list, or a function",
                                              "rendered record", "setup session keeps the read tools alone")),
            "the module description": (doc, ("WebFetch", "unit_prompt(unit, review_folder)", "checklist as a function",
                                             "RENDER(review_folder, tables)", "the setup session keeps the read tools alone",
                                             "at most 64 characters", "not a Windows device name")),
            "the hardware notes": (section, ("WebFetch", "unit_prompt(unit, review_folder)", "`FINDINGS[\"checklist\"]` may be a function",
                                             "`RENDER(review_folder, tables)`", "The retrieval grant", "read tools alone",
                                             "a fetched page is text the reviewer did not write", "reviewers write nothing",
                                             "the setup session fetches nothing",
                                             "every verdict is checked structurally at the merge",
                                             "one plain component of ASCII letters, digits, full stops, underscores and hyphens",
                                             "ends in neither a full stop nor `.part`",
                                             "is at most 64 characters long and is not a name Windows reserves for a device")),
        }
        for place, (text, clauses) in places.items():
            for words in clauses:
                self.assertIn(words, text, f"{place} says {words!r}")


if __name__ == "__main__":
    unittest.main()
