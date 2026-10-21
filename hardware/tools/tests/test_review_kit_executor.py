#!/usr/bin/env python3
"""The review kit's executors: the stub, the replay and the real command line, run as shipped.

The real executor is started against a stand-in program named by its environment variable, never the agent command
line; the clock is injected, so no test sleeps. No model, no network and no KiCad are used.
"""

from __future__ import annotations

import json
import os
import stat
import sys
import tempfile
import unittest
from dataclasses import replace

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)

from review_kit import executor as ex  # noqa: E402
from review_kit import session as sess  # noqa: E402
from review_kit import transcripts  # noqa: E402

SPEC = sess.SessionSpec(("Read", "Glob"), "/work/review", model="claude-sonnet-5-5", system="You are a reviewer.",
                        json_schema='{"type": "object"}')


def call(message="m", **kwargs):
    return sess.Call(SPEC, sess.user_message([sess.text_block(message)]), **kwargs)


class FakeClock:
    """A clock that moves only when slept on, and keeps the waits it was asked for."""

    def __init__(self):
        self.t = 1000.0
        self.slept = []

    def now(self):
        return self.t

    def sleep(self, seconds):
        self.slept.append(seconds)
        self.t += seconds


RATE = ex.Reply(is_error=True, api_error_status=429, text="Rate limit reached", exit_code=1)


class InterfaceTests(unittest.TestCase):
    # SOL-HW-REVIEW-KIT.C2: the stub, the replay and the real-command-line executors satisfy one interface
    def test_the_three_executors_share_one_interface(self):
        for kind in (ex.StubExecutor, ex.ReplayExecutor, ex.ClaudeCliExecutor):
            self.assertTrue(issubclass(kind, ex.Executor))
            self.assertIs(kind.run, ex.Executor.run, "the guard, the retry and the start check are not overridden")
        outcome = ex.StubExecutor().run(call(label="root"))
        self.assertIsInstance(outcome, ex.Outcome)
        self.assertEqual(outcome.kind, ex.OK)

    def test_a_fork_reads_its_parents_prefix_and_reports_cumulative_figures(self):
        stub = ex.StubExecutor([ex.Reply(cost=0.5, api_ms=1000, turns=2, write=400), ex.Reply(cost=0.25, api_ms=300, turns=3)])
        root = stub.run(call("root", label="root"))
        fork = stub.run(call("fork", parent=root.session.id, fork=True, label="fork"))
        self.assertEqual(root.session.first_read, 0)
        self.assertEqual(fork.session.first_read, 400)
        report = fork.session.result
        self.assertAlmostEqual(report["total_cost_usd"], 0.75)
        self.assertEqual((report["duration_api_ms"], report["num_turns"]), (1300, 5))

    def test_a_structured_answer_is_the_answer_and_an_empty_text_with_it_is_not_empty(self):
        outcome = ex.StubExecutor([ex.Reply(text="", structured={"tables": {}})]).run(call(label="u"))
        self.assertEqual(outcome.kind, ex.OK)
        self.assertEqual(json.loads(outcome.answer), {"tables": {}})


class RateLimitTests(unittest.TestCase):
    # SOL-HW-REVIEW-KIT.C2: against the stub with an injected clock, a call refused for a rate limit is retried after
    # waits that grow, a bounded number of times, without the test sleeping
    def test_a_rate_limited_call_is_retried_after_growing_waits_without_sleeping(self):
        clock = FakeClock()
        stub = ex.StubExecutor(lambda c, n: [RATE, RATE, RATE, ex.Reply(text="answer")], clock=clock)
        outcome = stub.run(call(label="u"))
        self.assertEqual(outcome.kind, ex.OK)
        self.assertEqual(outcome.answer, "answer")
        self.assertEqual(stub.executions, 4)
        self.assertEqual(outcome.attempts, 4)
        self.assertEqual(clock.slept, [30.0, 60.0, 120.0])
        self.assertEqual(outcome.waits, clock.slept)

    # SOL-HW-REVIEW-KIT.C2: a call that still fails comes back as a typed rate-limit result
    def test_a_call_that_stays_refused_is_a_typed_rate_limit_after_a_bounded_number_of_retries(self):
        clock = FakeClock()
        policy = ex.RetryPolicy(retries=4, first_s=2.0, factor=3.0, longest_s=40.0)
        stub = ex.StubExecutor(lambda c, n: RATE, clock=clock, policy=policy)
        outcome = stub.run(call(label="u"))
        self.assertEqual(outcome.kind, ex.RATE_LIMIT)
        self.assertEqual(stub.executions, 5, "the first call and four retries, no more")
        self.assertEqual(clock.slept, [2.0, 6.0, 18.0, 40.0], "waits grow and are capped at the longest")
        self.assertIn("Rate limit", outcome.said())
        self.assertEqual(outcome.exit_code, 1)

    def test_a_refusal_is_known_by_its_status_or_by_what_the_command_line_printed(self):
        for reply in (ex.Reply(is_error=True, api_error_status=429, exit_code=1),
                      ex.Reply(is_error=True, text="", stderr="Error: Too Many Requests", exit_code=1),
                      ex.Reply(is_error=True, text="API is overloaded", exit_code=1),
                      ex.Reply(text="", stderr="rate_limit exceeded", exit_code=1)):
            with self.subTest(reply=reply):
                clock = FakeClock()
                outcome = ex.StubExecutor(lambda c, n: reply, clock=clock, policy=ex.RetryPolicy(retries=1)).run(call(label="u"))
                self.assertEqual(outcome.kind, ex.RATE_LIMIT)
                self.assertEqual(len(clock.slept), 1)

    # SOL-HW-REVIEW-KIT.C2: an error exit and an empty answer each come back as a typed result carrying what the command
    # line returned, and nothing else is retried by the executor
    def test_an_error_exit_is_a_typed_result_carrying_what_was_returned_and_is_not_retried(self):
        clock = FakeClock()
        stub = ex.StubExecutor(lambda c, n: ex.Reply(text="Something broke", stderr="trace line", is_error=True, exit_code=1),
                               clock=clock)
        outcome = stub.run(call(label="u"))
        self.assertEqual(outcome.kind, ex.ERROR)
        self.assertEqual((outcome.exit_code, outcome.stderr), (1, "trace line"))
        self.assertEqual(outcome.session.text, "Something broke")
        self.assertIn('"is_error": true', outcome.stream)
        self.assertEqual((stub.executions, clock.slept), (1, []))

    def test_an_error_exit_with_no_result_report_is_an_error_too(self):
        raw = json.dumps({"type": "system", "subtype": "init", "session_id": "s"}) + "\n"
        stub = ex.StubExecutor([ex.Reply(raw=raw, exit_code=2, stderr="killed")], check_start=False)
        outcome = stub.run(call(label="u"))
        self.assertEqual((outcome.kind, outcome.exit_code, outcome.stderr), (ex.ERROR, 2, "killed"))
        self.assertIsNone(outcome.session.result)

    def test_an_exit_zero_whose_report_says_error_is_an_error(self):
        outcome = ex.StubExecutor([ex.Reply(is_error=True, text="refused: policy", exit_code=0)]).run(call(label="u"))
        self.assertEqual(outcome.kind, ex.ERROR)

    def test_an_empty_answer_is_a_typed_result_and_is_not_retried(self):
        clock = FakeClock()
        for text in ("", "  \n"):
            stub = ex.StubExecutor([ex.Reply(text=text)], clock=clock)
            outcome = stub.run(call(label="u"))
            self.assertEqual(outcome.kind, ex.EMPTY)
            self.assertEqual(outcome.answer.strip(), "")
            self.assertEqual((stub.executions, clock.slept), (1, []))

    def test_an_error_after_a_rate_limit_is_returned_and_retries_stop(self):
        clock = FakeClock()
        stub = ex.StubExecutor(lambda c, n: [RATE, ex.Reply(is_error=True, text="boom", exit_code=1)], clock=clock)
        outcome = stub.run(call(label="u"))
        self.assertEqual(outcome.kind, ex.ERROR)
        self.assertEqual((stub.executions, len(clock.slept)), (2, 1))

    def test_a_command_line_that_is_not_logged_in_stops_the_run_and_is_not_retried(self):
        stub = ex.StubExecutor([ex.Reply(is_error=True, api_error_status=401, text="Invalid API key", exit_code=1)])
        with self.assertRaises(ex.CannotRun) as caught:
            stub.run(call(label="u"))
        self.assertIn("not logged in", str(caught.exception))
        self.assertEqual(stub.executions, 1)

    def test_the_retry_wait_grows_and_is_bounded_by_the_policy(self):
        policy = ex.RetryPolicy()
        waits = [policy.wait(n) for n in range(policy.retries)]
        self.assertEqual(waits, sorted(waits))
        self.assertEqual(len(set(waits)), len(waits))
        self.assertLessEqual(max(waits), policy.longest_s)
        self.assertGreater(policy.retries, 0)


class ReplayTests(unittest.TestCase):
    def record(self, out):
        stub = ex.StubExecutor([ex.Reply(text="root answer", write=300), ex.Reply(text="fork answer")], out=out)
        root = stub.run(call("root", label="root"))
        fork = stub.run(call("fork", parent=root.session.id, fork=True, label="fork"))
        return root, fork

    # SOL-HW-REVIEW-KIT.C2: the replay returns the recorded stream for the hash of a specification, a parent and a message
    def test_the_replay_returns_the_recorded_stream_for_the_hash(self):
        with tempfile.TemporaryDirectory() as out:
            root, fork = self.record(out)
            replay = ex.ReplayExecutor.from_folder(out)
            again_fork = replay.run(call("fork", parent=root.session.id, fork=True, label="fork"))
            again_root = replay.run(call("root", label="root"))
            self.assertEqual(again_root.stream, root.stream)
            self.assertEqual(again_fork.stream, fork.stream)
            self.assertEqual(again_fork.answer, "fork answer")
            self.assertEqual(again_fork.session.id, fork.session.id)

    # SOL-HW-REVIEW-KIT.C2: and fails naming the hash when none is recorded
    def test_the_replay_fails_naming_the_hash_when_none_is_recorded(self):
        with tempfile.TemporaryDirectory() as out:
            root, _ = self.record(out)
            others = {"a different message": call("other", label="x"),
                      "a different parent": call("fork", parent="not-the-parent", fork=True, label="x"),
                      "no parent": call("fork", label="x"),
                      "a different specification": sess.Call(replace(SPEC, model="claude-haiku-5-5"), call("root").message,
                                                             label="x")}
            for why, other in others.items():
                with self.subTest(why):
                    replay = ex.ReplayExecutor.from_folder(out)
                    with self.assertRaises(ex.NotRecorded) as caught:
                        replay.run(other)
                    self.assertIn(other.key, str(caught.exception))

    def test_a_key_recorded_more_than_once_replays_in_order_and_a_rate_limit_is_retried_on_the_clock(self):
        clock = FakeClock()
        stream_rate = ex.StubExecutor([RATE], clock=FakeClock(), policy=ex.RetryPolicy(retries=0)).run(call("m", label="u")).stream
        stream_ok = ex.StubExecutor([ex.Reply(text="finally")]).run(call("m", label="u")).stream
        replay = ex.ReplayExecutor({call("m").key: [{"stream": stream_rate, "exit_code": 1, "stderr": ""},
                                                   {"stream": stream_ok, "exit_code": 0, "stderr": ""}]}, clock=clock)
        outcome = replay.run(call("m", label="u"))
        self.assertEqual((outcome.kind, outcome.answer, clock.slept), (ex.OK, "finally", [30.0]))
        self.assertEqual(replay.run(call("m", label="u")).answer, "finally", "the last recording repeats")

    def test_the_replay_holds_the_specification_like_every_executor(self):
        with tempfile.TemporaryDirectory() as out:
            self.record(out)
            replay = ex.ReplayExecutor.from_folder(out)
            replay.run(call("root", label="root"))
            with self.assertRaises(sess.SpecChanged):
                replay.run(sess.Call(replace(SPEC, system="other"), call("root").message, label="x"))


AGENT_SCRIPT = '''#!{python}
import json, os, sys
args = sys.argv[1:]
log = os.environ["AGENT_LOG"]
if args[:2] == ["auth", "status"]:
    print(os.environ.get("AGENT_AUTH", '{{"loggedIn": true}}'))
    sys.exit(int(os.environ.get("AGENT_AUTH_EXIT", "0")))
stdin = sys.stdin.read()
with open(log, "a", encoding="utf-8") as handle:
    handle.write(json.dumps({{"args": args, "stdin": stdin, "cwd": os.getcwd(),
                            "env": {{k: os.environ.get(k) for k in ("CLAUDE_CODE_DISABLE_CLAUDE_MDS",
                                                                   "CLAUDE_CODE_DISABLE_AUTO_MEMORY")}}}}) + "\\n")
sys.stdout.buffer.write(open(os.environ["AGENT_STREAM"], "rb").read())
sys.stderr.write(os.environ.get("AGENT_STDERR", ""))
sys.exit(int(os.environ.get("AGENT_EXIT", "0")))
'''


class RealCommandLineTests(unittest.TestCase):
    """The real executor, started against a stand-in program: no agent command line is ever run."""

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="kit-executor-")
        self.addCleanup(__import__("shutil").rmtree, self.root, True)
        self.program = os.path.join(self.root, "agent")
        with open(self.program, "w", encoding="utf-8") as handle:
            handle.write(AGENT_SCRIPT.format(python=sys.executable))
        os.chmod(self.program, os.stat(self.program).st_mode | stat.S_IXUSR)
        self.log = os.path.join(self.root, "log.jsonl")
        self.work = os.path.join(self.root, "work")
        os.makedirs(self.work)
        self.spec = replace(SPEC, cwd=self.work)
        self.environ = {AGENT_VAR: self.program}

    def stream(self, text, **kwargs):
        path = os.path.join(self.root, "stream.jsonl")
        with open(path, "w", encoding="utf-8", newline="") as handle:
            handle.write(ex.stream_text("real-1", text=text, tools=self.spec.expected_tools, model=self.spec.model,
                                        cwd=self.work, **kwargs))
        return path

    def environment(self, **extra):
        from unittest import mock
        values = {"AGENT_LOG": self.log, "AGENT_STREAM": self.stream("an answer"), **extra}
        patcher = mock.patch.dict(os.environ, values)
        patcher.start()
        self.addCleanup(patcher.stop)

    # SOL-HW-REVIEW-KIT.C2: the real executor reads the command line's name from one environment variable
    def test_the_program_is_named_by_one_environment_variable(self):
        self.assertEqual(ex.AGENT_ENV, AGENT_VAR)
        self.assertEqual(ex.agent_program({ex.AGENT_ENV: "/some/program"}), "/some/program")
        self.assertEqual(ex.agent_program({}), ex.DEFAULT_AGENT)
        self.assertEqual(ex.agent_program({ex.AGENT_ENV: ""}), ex.DEFAULT_AGENT)
        self.environment()
        outcome = ex.ClaudeCliExecutor(environ=self.environ).run(sess.Call(self.spec, "the message", label="u"))
        self.assertEqual(outcome.kind, ex.OK)
        self.assertEqual(outcome.answer, "an answer")

    # SOL-HW-REVIEW-KIT.C2: the command line is started with the arguments built from the specification, the message on
    # standard input, in the specification's folder, with the memory and instruction files of the machine switched off
    def test_the_command_line_is_started_from_the_specification(self):
        self.environment()
        message = sess.user_message([sess.text_block("hold this")])
        c = sess.Call(self.spec, message, parent="parent-id", fork=True, label="u")
        ex.ClaudeCliExecutor(self.program).run(c)
        with open(self.log, encoding="utf-8") as handle:
            started = [json.loads(line) for line in handle]
        self.assertEqual(len(started), 1)
        self.assertEqual(started[0]["args"], c.arguments)
        self.assertEqual(started[0]["stdin"].strip(), message)
        self.assertEqual(os.path.realpath(started[0]["cwd"]), os.path.realpath(self.work))
        self.assertEqual(started[0]["env"], {"CLAUDE_CODE_DISABLE_CLAUDE_MDS": "1", "CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1"})

    # SOL-HW-REVIEW-KIT.C2: it writes each stream, with the specification and message hashes, into the output folder as the
    # command line printed it
    def test_each_stream_is_saved_verbatim_with_the_hashes_that_key_it(self):
        out = os.path.join(self.root, "out")
        self.environment(AGENT_STREAM=self.stream("café   line\u0085 end"))
        with open(os.environ["AGENT_STREAM"], encoding="utf-8", newline="") as handle:
            printed = handle.read()
        executor = ex.ClaudeCliExecutor(self.program, out=out)
        first = executor.run(sess.Call(self.spec, "one", label="a"))
        executor.run(sess.Call(self.spec, "two", parent="real-1", fork=True, label="b"))
        names = sorted(os.listdir(out))
        self.assertEqual([n[:4] for n in names], ["0001", "0001", "0002", "0002"])
        streams = [n for n in names if n.endswith(".jsonl")]
        with open(os.path.join(out, streams[0]), encoding="utf-8", newline="") as handle:
            self.assertEqual(handle.read(), printed, "byte for byte as the command line printed it")
        self.assertEqual(first.stream, printed)
        with open(os.path.join(out, streams[1][:-6] + ".json"), encoding="utf-8") as handle:
            meta = json.load(handle)
        c = sess.Call(self.spec, "two", parent="real-1", fork=True)
        self.assertEqual(meta["spec_digest"], self.spec.digest)
        self.assertEqual(meta["message_digest"], c.message_digest)
        self.assertEqual(meta["key"], c.key)
        self.assertEqual((meta["parent"], meta["fork"], meta["label"]), ("real-1", True, "b"))
        self.assertEqual(meta["spec"]["cwd"], self.work)
        # the saved streams replay: the folder is a recording of the review
        replay = ex.ReplayExecutor.from_folder(out)
        self.assertEqual(replay.run(c).stream, printed)

    def test_streams_saved_by_a_later_run_continue_the_numbering(self):
        out = os.path.join(self.root, "out")
        self.environment()
        ex.ClaudeCliExecutor(self.program, out=out).run(sess.Call(self.spec, "one", label="a"))
        ex.ClaudeCliExecutor(self.program, out=out).run(sess.Call(self.spec, "two", label="b"))
        self.assertEqual(sorted(n[:4] for n in os.listdir(out) if n.endswith(".jsonl")), ["0001", "0002"])

    def test_an_error_exit_of_the_real_command_line_is_typed_with_what_it_printed(self):
        self.environment(AGENT_EXIT="1", AGENT_STDERR="fatal: boom")
        outcome = ex.ClaudeCliExecutor(self.program).run(sess.Call(self.spec, "one", label="a"))
        self.assertEqual((outcome.kind, outcome.exit_code, outcome.stderr), (ex.ERROR, 1, "fatal: boom"))

    def test_a_program_that_cannot_be_started_is_cannot_run(self):
        missing = os.path.join(self.root, "no-such-program")
        with self.assertRaises(ex.CannotRun) as caught:
            ex.ClaudeCliExecutor(missing).run(sess.Call(self.spec, "one", label="a"))
        self.assertIn(missing, str(caught.exception))

    # SOL-HW-REVIEW-KIT.C2: the command line is on the path and logged in, or the run cannot be made
    def test_require_agent_names_the_cause_and_what_to_do(self):
        with self.assertRaises(ex.CannotRun) as caught:
            ex.require_agent({ex.AGENT_ENV: "definitely-not-an-installed-program"})
        self.assertIn("not on the search path", str(caught.exception))
        self.assertIn(ex.AGENT_ENV, str(caught.exception))
        self.environment(AGENT_AUTH='{"loggedIn": false}')
        with self.assertRaises(ex.CannotRun) as caught:
            ex.require_agent(self.environ)
        self.assertIn("not logged in", str(caught.exception))
        self.assertIn("log it in", str(caught.exception))
        self.environment(AGENT_AUTH="not json")
        with self.assertRaises(ex.CannotRun):
            ex.require_agent(self.environ)
        self.environment(AGENT_AUTH='{"loggedIn": true}', AGENT_AUTH_EXIT="1")
        with self.assertRaises(ex.CannotRun):
            ex.require_agent(self.environ)
        self.environment(AGENT_AUTH='{"loggedIn": true}', AGENT_AUTH_EXIT="0")
        self.assertEqual(ex.require_agent(self.environ), self.program)


AGENT_VAR = "REVIEW_KIT_AGENT"


def shape_record(session_id, *texts, kind="api-request-shape"):
    return {"type": kind, "sessionId": session_id, "shapeHash": "h",
            "shape": {"system": [{"type": "text", "text": text} for text in texts], "tools": []}}


class TranscriptTests(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="kit-transcripts-")
        self.addCleanup(__import__("shutil").rmtree, self.root, True)
        self.cwd = os.path.join(self.root, "my review.d")
        os.makedirs(self.cwd)

    def write(self, session_id, records, folder=None, raw_lines=()):
        folder = os.path.join(self.root, "projects", folder or transcripts.folder_name(self.cwd))
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, session_id + ".jsonl")
        with open(path, "w", encoding="utf-8") as handle:
            for line in raw_lines:
                handle.write(line + "\n")
            for record in records:
                handle.write(json.dumps(record) + "\n")
        return path

    def projects(self):
        return os.path.join(self.root, "projects")

    # SOL-HW-REVIEW-KIT.C4: the system prompt a session used is read from the transcript Claude Code writes for that
    # session, found by the session's identifier, because the start report carries none
    def test_the_system_prompt_is_read_from_the_sessions_transcript(self):
        self.write("sess-1", [{"type": "user", "sessionId": "sess-1"}, shape_record("sess-1", "You are an agent.", "Rules.")])
        self.assertEqual(transcripts.session_system_prompt("sess-1", self.cwd, self.projects()), "You are an agent.\nRules.")

    def test_the_folder_name_follows_the_working_directory(self):
        self.assertTrue(transcripts.folder_name(self.cwd).endswith("my-review-d"))
        self.assertNotIn("/", transcripts.folder_name(self.cwd))
        self.assertNotIn(" ", transcripts.folder_name(self.cwd))

    def test_a_transcript_in_another_folder_is_found_by_the_identifier(self):
        path = self.write("sess-2", [shape_record("sess-2", "Elsewhere.")], folder="-some-other-folder")
        self.assertEqual(transcripts.find_transcript("sess-2", self.cwd, self.projects()), path)
        self.assertEqual(transcripts.session_system_prompt("sess-2", self.cwd, self.projects()), "Elsewhere.")

    def test_a_fork_is_compared_with_its_parent_by_their_own_transcripts(self):
        self.write("parent", [shape_record("parent", "Reviewer rule.")])
        self.write("fork-same", [shape_record("fork-same", "Reviewer rule.")])
        self.write("fork-other", [shape_record("fork-other", "A setup rule: write nothing.")])
        read = lambda sid: transcripts.session_system_prompt(sid, self.cwd, self.projects())  # noqa: E731
        self.assertEqual(read("parent"), read("fork-same"))
        self.assertNotEqual(read("parent"), read("fork-other"))

    def test_records_of_other_sessions_other_types_and_bad_lines_are_ignored(self):
        self.write("sess-3", [shape_record("someone-else", "Not mine."), shape_record("sess-3", "Mine.", kind="other-record"),
                              shape_record("sess-3", "Mine."), shape_record("sess-3", "Mine.")],
                   raw_lines=["not json {api-request-shape", ""])
        self.assertEqual(transcripts.session_system_prompt("sess-3", self.cwd, self.projects()), "Mine.")

    def test_a_missing_transcript_names_where_it_looked(self):
        os.makedirs(self.projects())
        with self.assertRaises(transcripts.TranscriptMissing) as caught:
            transcripts.session_system_prompt("absent", self.cwd, self.projects())
        self.assertIn("absent.jsonl", str(caught.exception))
        self.assertIn(self.projects(), str(caught.exception))
        with self.assertRaises(transcripts.TranscriptMissing):
            transcripts.session_system_prompt("absent", self.cwd, os.path.join(self.root, "no-such-folder"))

    def test_an_identifier_that_is_a_path_is_refused(self):
        for bad in ("../x", "a/b", "", "a b"):
            with self.assertRaises(transcripts.TranscriptMissing):
                transcripts.find_transcript(bad, self.cwd, self.projects())

    def test_a_transcript_with_no_request_shape_or_a_changed_format_or_two_prompts_is_named(self):
        self.write("none", [{"type": "user", "sessionId": "none"}])
        with self.assertRaises(transcripts.TranscriptMissing) as caught:
            transcripts.session_system_prompt("none", self.cwd, self.projects())
        self.assertIn("api-request-shape", str(caught.exception))
        self.write("changed", [{"type": "api-request-shape", "sessionId": "changed", "shape": {"tools": []}}])
        with self.assertRaises(transcripts.TranscriptMissing) as caught:
            transcripts.session_system_prompt("changed", self.cwd, self.projects())
        self.assertIn("format has changed", str(caught.exception))
        self.write("two", [shape_record("two", "First."), shape_record("two", "Second.")])
        with self.assertRaises(transcripts.TranscriptMissing) as caught:
            transcripts.session_system_prompt("two", self.cwd, self.projects())
        self.assertIn("2 different system prompts", str(caught.exception))

    def test_the_projects_folder_follows_the_configuration_variable(self):
        self.assertEqual(transcripts.projects_root({transcripts.PROJECTS_ENV: "/cfg"}), os.path.join("/cfg", "projects"))
        self.assertTrue(transcripts.projects_root({}).endswith(os.path.join(".claude", "projects")))


if __name__ == "__main__":
    unittest.main()
