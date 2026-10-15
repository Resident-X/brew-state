#!/usr/bin/env python3
"""The daily status reader says what main's latest nightly verification concluded.

The GitHub command-line tool is a shell script that answers with the run history
it is given, or fails the way it is told to, so every verdict is observed
without a network or an account behind it. The declaration of the task and the
nightly workflow's name are read from the repository as text, so these need
nothing beyond the standard library.
"""

from __future__ import annotations

import json
import os
import shlex
import stat
import subprocess
import sys
import tempfile
import unittest

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPOSITORY = os.path.dirname(os.path.dirname(TOOLS))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)

from test_round_gate import task_commands  # noqa: E402
import workflow_declarations  # noqa: E402

READER = os.path.join(TOOLS, "daily_status.py")
WORKFLOW = "Nightly verification"


def run(sha: str, conclusion: str | None, status: str, created: str) -> dict:
    return {"headSha": sha, "conclusion": conclusion, "status": status,
            "createdAt": created, "url": f"https://example.test/runs/{sha}"}


def done(sha: str, conclusion: str, created: str) -> dict:
    return run(sha, conclusion, "completed", created)


class Reader:
    """Runs the reader against a stand-in for gh that prints a history or fails."""

    def __init__(self, directory: str):
        self.directory = directory
        self.argv_log = os.path.join(directory, "argv.log")

    def gh(self, stdout: str = "", status: int = 0, stderr: str = "") -> str:
        path = os.path.join(self.directory, "gh")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(
                "#!/bin/sh\n"
                f'echo "$@" > {shlex.quote(self.argv_log)}\n'
                f"printf '%s' {shlex.quote(stdout)}\n"
                f"printf '%s' {shlex.quote(stderr)} >&2\n"
                f"exit {status}\n"
            )
        os.chmod(path, os.stat(path).st_mode | stat.S_IEXEC)
        return path

    def read(self, gh: str, *flags: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, READER, "--workflow", WORKFLOW, "--branch", "main", "--gh", gh, *flags],
            capture_output=True, text=True, check=False,
        )

    def history(self, runs: list[dict], *flags: str) -> subprocess.CompletedProcess:
        return self.read(self.gh(json.dumps(runs)), *flags)


class TheReaderStatesTheLatestNightlyResult(unittest.TestCase):
    def setUp(self):
        self._directory = tempfile.TemporaryDirectory()
        self.addCleanup(self._directory.cleanup)
        self.reader = Reader(self._directory.name)

    def lines(self, outcome: subprocess.CompletedProcess) -> list[str]:
        return outcome.stdout.splitlines()

    def as_json(self, outcome: subprocess.CompletedProcess) -> dict:
        return json.loads(outcome.stdout)

    def assertUnknown(self, outcome: subprocess.CompletedProcess, mention: str = ""):
        self.assertEqual(self.lines(outcome)[0], "unknown")
        self.assertNotEqual(outcome.returncode, 0)
        self.assertIn(mention, outcome.stdout)
        self.assertNotIn("green", outcome.stdout.replace("unknown", ""))

    def test_a_passing_run_is_green_with_its_commit_and_link(self):
        # SOL-VERIFY-DAILY-STATUS-READ-FIRST.C1: The daily status reader states main's latest nightly result and never reports a result it could not read
        outcome = self.reader.history([done("aaa111", "success", "2026-10-15T02:00:00Z")])
        self.assertEqual(outcome.returncode, 0)
        self.assertEqual(self.lines(outcome), [
            "green", "conclusion: success", "commit: aaa111", "run: https://example.test/runs/aaa111"])
        as_json = self.as_json(self.reader.history([done("aaa111", "success", "2026-10-15T02:00:00Z")], "--json"))
        self.assertEqual(as_json, {"verdict": "green", "conclusion": "success", "commit": "aaa111",
                                   "url": "https://example.test/runs/aaa111"})

    def test_a_failing_run_is_red_and_still_exits_zero(self):
        # SOL-VERIFY-DAILY-STATUS-READ-FIRST.C1: The daily status reader states main's latest nightly result and never reports a result it could not read
        history = [done("bbb222", "failure", "2026-10-15T02:00:00Z")]
        outcome = self.reader.history(history)
        self.assertEqual(outcome.returncode, 0)
        self.assertEqual(self.lines(outcome)[0], "red")
        self.assertIn("conclusion: failure", outcome.stdout)
        self.assertIn("commit: bbb222", outcome.stdout)
        self.assertIn("run: https://example.test/runs/bbb222", outcome.stdout)
        as_json = self.as_json(self.reader.history(history, "--json"))
        self.assertEqual((as_json["verdict"], as_json["conclusion"], as_json["commit"]),
                         ("red", "failure", "bbb222"))

    def test_a_timed_out_or_unstarted_run_is_red_not_an_older_green(self):
        # SOL-VERIFY-DAILY-STATUS-READ-FIRST.C1: The daily status reader states main's latest nightly result and never reports a result it could not read
        for conclusion in ("timed_out", "startup_failure", "action_required"):
            with self.subTest(conclusion=conclusion):
                history = [done("new", conclusion, "2026-10-15T02:00:00Z"),
                           done("old", "success", "2026-10-14T02:00:00Z")]
                outcome = self.reader.history(history)
                self.assertEqual(outcome.returncode, 0)
                self.assertEqual(self.lines(outcome)[0], "red")
                self.assertIn(f"conclusion: {conclusion}", outcome.stdout)
                self.assertEqual(self.as_json(self.reader.history(history, "--json"))["verdict"], "red")

    def test_no_runs_reads_as_none_and_exits_zero(self):
        # SOL-VERIFY-DAILY-STATUS-READ-FIRST.C1: The daily status reader states main's latest nightly result and never reports a result it could not read
        outcome = self.reader.history([])
        self.assertEqual(outcome.returncode, 0)
        self.assertEqual(self.lines(outcome)[0], "none")
        as_json = self.as_json(self.reader.history([], "--json"))
        self.assertEqual(as_json["verdict"], "none")
        self.assertNotIn("commit", as_json)

    def test_only_in_progress_runs_read_as_none(self):
        # SOL-VERIFY-DAILY-STATUS-READ-FIRST.C1: The daily status reader states main's latest nightly result and never reports a result it could not read
        history = [run("p1", None, "in_progress", "2026-10-15T02:00:00Z"),
                   run("p2", None, "queued", "2026-10-14T02:00:00Z")]
        outcome = self.reader.history(history)
        self.assertEqual((outcome.returncode, self.lines(outcome)[0]), (0, "none"))
        self.assertEqual(self.as_json(self.reader.history(history, "--json"))["verdict"], "none")

    def test_only_passed_over_runs_read_as_none(self):
        # SOL-VERIFY-DAILY-STATUS-READ-FIRST.C1: The daily status reader states main's latest nightly result and never reports a result it could not read
        history = [done("c1", "cancelled", "2026-10-15T02:00:00Z"),
                   done("c2", "skipped", "2026-10-14T02:00:00Z"),
                   done("c3", "neutral", "2026-10-13T02:00:00Z")]
        outcome = self.reader.history(history)
        self.assertEqual((outcome.returncode, self.lines(outcome)[0]), (0, "none"))
        self.assertEqual(self.as_json(self.reader.history(history, "--json"))["verdict"], "none")

    def test_a_newer_unfinished_or_passed_over_run_yields_to_an_older_completed_one(self):
        # SOL-VERIFY-DAILY-STATUS-READ-FIRST.C1: The daily status reader states main's latest nightly result and never reports a result it could not read
        for newer in (run("new", None, "in_progress", "2026-10-16T02:00:00Z"),
                      done("new", "cancelled", "2026-10-16T02:00:00Z"),
                      done("new", "skipped", "2026-10-16T02:00:00Z"),
                      done("new", "neutral", "2026-10-16T02:00:00Z")):
            for older, verdict in (("failure", "red"), ("success", "green")):
                with self.subTest(newer=newer["conclusion"] or newer["status"], older=older):
                    # The order the tool lists them in does not decide: createdAt does.
                    history = [done("old", older, "2026-10-15T02:00:00Z"), newer]
                    outcome = self.reader.history(history)
                    self.assertEqual(self.lines(outcome)[0], verdict)
                    self.assertIn("commit: old", outcome.stdout)
                    as_json = self.as_json(self.reader.history(history, "--json"))
                    self.assertEqual((as_json["verdict"], as_json["commit"]), (verdict, "old"))

    def test_the_newest_completed_run_decides_over_an_older_one(self):
        # SOL-VERIFY-DAILY-STATUS-READ-FIRST.C1: The daily status reader states main's latest nightly result and never reports a result it could not read
        history = [done("old", "success", "2026-10-14T02:00:00Z"),
                   done("new", "failure", "2026-10-15T02:00:00Z")]
        outcome = self.reader.history(history)
        self.assertEqual(self.lines(outcome)[0], "red")
        self.assertIn("commit: new", outcome.stdout)

    def test_the_tool_is_asked_for_main_and_the_named_workflow_only(self):
        # SOL-VERIFY-DAILY-STATUS-READ-FIRST.C1: The daily status reader states main's latest nightly result and never reports a result it could not read
        self.reader.history([])
        with open(self.reader.argv_log, encoding="utf-8") as handle:
            asked = handle.read().strip()
        self.assertIn(f"--workflow {WORKFLOW}", asked)
        self.assertIn("--branch main", asked)

    def test_a_failing_call_is_unknown_with_its_reason(self):
        # SOL-VERIFY-DAILY-STATUS-READ-FIRST.C1: The daily status reader states main's latest nightly result and never reports a result it could not read
        gh = self.reader.gh(status=4, stderr="gh: To use GitHub CLI, run: gh auth login")
        outcome = self.reader.read(gh)
        self.assertUnknown(outcome, "gh auth login")
        self.assertEqual(self.as_json(self.reader.read(gh, "--json"))["verdict"], "unknown")
        self.assertIn("gh auth login", self.as_json(self.reader.read(gh, "--json"))["reason"])
        self.assertNotEqual(self.reader.read(gh, "--json").returncode, 0)

    def test_a_missing_workflow_is_unknown_not_none(self):
        # SOL-VERIFY-DAILY-STATUS-READ-FIRST.C1: The daily status reader states main's latest nightly result and never reports a result it could not read
        gh = self.reader.gh(status=1, stderr="could not find any workflows named Nightly verification")
        outcome = self.reader.read(gh)
        self.assertUnknown(outcome, "could not find any workflows")
        self.assertNotEqual(self.lines(outcome)[0], "none")

    def test_malformed_output_is_unknown(self):
        # SOL-VERIFY-DAILY-STATUS-READ-FIRST.C1: The daily status reader states main's latest nightly result and never reports a result it could not read
        for text in ("not json at all", "", '{"conclusion": "success"}', '["success"]',
                     json.dumps([done("x", "", "2026-10-15T02:00:00Z")]),
                     json.dumps([{"status": "completed", "conclusion": "success", "createdAt": "2026-10-15T02:00:00Z"}])):
            with self.subTest(text=text):
                gh = self.reader.gh(stdout=text)
                self.assertUnknown(self.reader.read(gh))
                as_json = self.as_json(self.reader.read(gh, "--json"))
                self.assertEqual(as_json["verdict"], "unknown")
                self.assertTrue(as_json["reason"])

    def test_a_missing_tool_is_unknown_and_named(self):
        # SOL-VERIFY-DAILY-STATUS-READ-FIRST.C1: The daily status reader states main's latest nightly result and never reports a result it could not read
        absent = os.path.join(self._directory.name, "no-such-gh")
        self.assertUnknown(self.reader.read(absent), absent)
        as_json = self.as_json(self.reader.read(absent, "--json"))
        self.assertEqual(as_json["verdict"], "unknown")
        self.assertIn(absent, as_json["reason"])
        self.assertNotEqual(self.reader.read(absent, "--json").returncode, 0)


class TheTaskAsksForTheWorkflowTheNightlyDeclares(unittest.TestCase):
    def test_the_workflow_name_the_task_passes_equals_the_name_the_nightly_declares(self):
        # SOL-VERIFY-DAILY-STATUS-READ-FIRST.C1: A test also holds the workflow name the command asks for equal to the name the nightly workflow declares
        with open(os.path.join(REPOSITORY, "Taskfile.yml"), encoding="utf-8") as handle:
            (command,) = task_commands(handle.read(), "daily:status")
        words = shlex.split(command)
        self.assertIn("daily_status.py", " ".join(words))
        asked = words[words.index("--workflow") + 1]
        self.assertEqual(words[words.index("--branch") + 1], "main")
        with open(os.path.join(REPOSITORY, ".github", "workflows", "nightly-verify.yml"), encoding="utf-8") as handle:
            declared, _ = workflow_declarations.find(handle.read(), "name")
        self.assertEqual(asked, declared)


if __name__ == "__main__":
    unittest.main()
