#!/usr/bin/env python3
"""The review kit's contract smoke: its assertions over recorded probe streams, its probe plan, and its missing-command path.

The live run is the operator's. The assertions are driven over streams of the shape the probes recorded (synthetic, built
with the figures the recorded probes gave), over the recorded probe files when the fixtures folder holds them, and the
probe plan over the stub. No model is used and the agent command line is never run.
"""

from __future__ import annotations

import io
import json
import os
import stat
import struct
import sys
import tempfile
import unittest
import zlib

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)

from review_kit import executor as ex  # noqa: E402
from review_kit import session as sess  # noqa: E402
from review_kit import smoke  # noqa: E402

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "review_streams")


def session(read, write, session_id="s", **kwargs):
    return ex.parse_stream(ex.stream_text(session_id, read=read, write=write, **kwargs))


# The figures the recorded probes gave: p1 a root without a result schema that wrote 3261 tokens after reading 3223; p2 its
# fork started with a result-schema flag, which read nothing and wrote 7042; p4 a root with the schema (6644 written) and
# p5, p6 and p7 forks that read the prefix of their parents.
P1 = (3223, 3261)
P2 = (0, 7042)
P4, P5, P6, P7 = (0, 6644), (6644, 451), (6644, 1532), (8176, 458)


class AssertionTests(unittest.TestCase):
    # SOL-HW-REVIEW-KIT.C2: a fork's system prompt equal to its root's passes and a differing one fails
    def test_equal_system_prompts_pass_and_a_differing_one_fails(self):
        self.assertIsNone(smoke.same_system("Reviewer rule.", "Reviewer rule."))
        smoke.assert_same_system("Reviewer rule.", "Reviewer rule.", "p5")
        for fork in ("Reviewer rule. ", "A setup rule: write nothing.", ""):
            with self.subTest(fork=fork):
                self.assertIn("not its parent's", smoke.same_system("Reviewer rule.", fork))
                with self.assertRaises(smoke.SmokeFailure) as caught:
                    smoke.assert_same_system("Reviewer rule.", fork, "p5")
                self.assertIn("p5", str(caught.exception))

    # SOL-HW-REVIEW-KIT.C2: a fork whose first call reads at least its parent's prefix from the cache passes
    def test_a_fork_that_reads_the_prefix_passes(self):
        parent, fork = session(*P4, "p4"), session(*P5, "p5")
        self.assertEqual(parent.prefix_tokens, 6644)
        self.assertIsNone(smoke.cache_miss(parent, fork))
        smoke.assert_prefix_read(parent, fork, "p5")
        smoke.assert_prefix_read(parent, session(9999, 1), "more than the prefix")
        grandchild = session(*P7, "p7")
        smoke.assert_prefix_read(session(*P6, "p6"), grandchild, "p7")
        self.assertEqual(session(*P6).prefix_tokens, 8176)

    # SOL-HW-REVIEW-KIT.C2: the recorded probe in which the result-schema flag differed between a root and its fork, so that
    # the fork read nothing from the cache, is flagged as a cache miss
    def test_the_schema_flag_probe_is_flagged_with_both_figures(self):
        parent, fork = session(*P1, "p1"), session(*P2, "p2")
        why = smoke.cache_miss(parent, fork)
        self.assertIn("read 0 tokens", why)
        self.assertIn("6484", why)
        smoke.assert_cache_miss_flagged(parent, fork, "p2")
        with self.assertRaises(smoke.SmokeFailure) as caught:
            smoke.assert_prefix_read(parent, fork, "p2")
        self.assertIn("p2", str(caught.exception))

    # SOL-HW-REVIEW-KIT.C2: the check must see the break: a fork that read the prefix is not a flagged miss, and the
    # smoke fails if the schema-flag fork is not flagged
    def test_the_smoke_fails_when_the_schema_flag_fork_is_not_flagged(self):
        parent = session(*P1, "p1")
        with self.assertRaises(smoke.SmokeFailure) as caught:
            smoke.assert_cache_miss_flagged(parent, session(6484, 10, "p2"), "p2")
        self.assertIn("cannot see the cache break", str(caught.exception))
        self.assertEqual(smoke.cache_miss(parent, session(6483, 10)) is not None, True, "one token short is a miss")
        self.assertIsNone(smoke.cache_miss(parent, session(6484, 0)))

    def test_a_session_with_no_model_call_cannot_be_judged_and_is_flagged(self):
        none = ex.parse_stream(json.dumps({"type": "system", "subtype": "init", "session_id": "x"}) + "\n")
        self.assertIn("cannot be told", smoke.cache_miss(session(*P1), none))
        self.assertIn("cannot be told", smoke.cache_miss(none, session(*P2)))

    @unittest.skipUnless(os.path.exists(os.path.join(FIXTURES, "p1.jsonl")) and os.path.exists(os.path.join(FIXTURES, "p2.jsonl")),
                         "the recorded probe fixtures are not in the fixtures folder")
    def test_the_recorded_probe_streams_give_the_same_verdicts(self):
        def recorded(name):
            with open(os.path.join(FIXTURES, name + ".jsonl"), encoding="utf-8", newline="") as handle:
                return ex.parse_stream(handle.read())
        smoke.assert_cache_miss_flagged(recorded("p1"), recorded("p2"), "p2")


def whole_set(p2=P2, systems=None):
    """The seven probes' sessions, with the figures the recorded probes gave unless changed."""
    figures = {"p1": P1, "p2": p2, "p3": (5809, 1511), "p4": P4, "p5": P5, "p6": P6, "p7": P7}
    sessions = {name: session(*figure, name) for name, figure in figures.items()}
    systems = {name: "One reviewer rule." for name in figures} if systems is None else systems
    return sessions, systems


class ChecksTests(unittest.TestCase):
    def outcome(self, **kwargs):
        sessions, systems = whole_set(**kwargs)
        return {name: (held, detail) for name, held, detail in smoke.checks(sessions, systems)}

    # SOL-HW-REVIEW-KIT.C2: the smoke asserts that a fork's system prompt equals its root's, that a fork reads its parent's
    # prefix, and that a fork whose schema flag differs shows as a cache miss
    def test_all_three_assertions_hold_over_the_recorded_shapes(self):
        found = self.outcome()
        self.assertEqual(sorted(found), sorted([
            "system prompt p2 = p1", "system prompt p3 = p1", "system prompt p5 = p4", "system prompt p6 = p4",
            "system prompt p7 = p6", "cache read p5", "cache read p6", "cache read p7", "cache miss flagged p2"]))
        self.assertTrue(all(held for held, _ in found.values()), found)

    def test_a_fork_with_another_system_prompt_fails_naming_the_probe(self):
        sessions, systems = whole_set()
        systems["p5"] = "A setup rule: write nothing, judge nothing."
        found = {name: held for name, held, _ in smoke.checks(sessions, systems)}
        self.assertFalse(found["system prompt p5 = p4"])
        self.assertTrue(found["system prompt p6 = p4"])

    def test_a_cache_break_in_a_same_specification_fork_fails(self):
        found = self.outcome()
        sessions, systems = whole_set()
        sessions["p7"] = session(0, 8634, "p7")
        broken = {name: (held, detail) for name, held, detail in smoke.checks(sessions, systems)}
        self.assertFalse(broken["cache read p7"][0])
        self.assertIn("read 0 tokens", broken["cache read p7"][1])
        self.assertTrue(found["cache read p7"][0])

    def test_a_schema_flag_fork_that_reads_the_cache_fails_the_smoke(self):
        found = self.outcome(p2=(6484, 500))
        held, detail = found["cache miss flagged p2"]
        self.assertFalse(held)
        self.assertIn("p2", detail)

    def test_the_added_tool_probe_is_not_asserted_to_miss(self):
        self.assertNotIn("cache miss flagged p3", self.outcome())
        self.assertNotIn("cache read p3", self.outcome())

    def test_report_lines_name_each_check_and_the_version_and_the_result(self):
        sessions, systems = whole_set()
        lines = smoke.report_lines(smoke.checks(sessions, systems), "2.1.304")
        self.assertTrue(all(line.startswith("CHECK | ") for line in lines[:-1]))
        self.assertTrue(all(line.endswith("| holds") for line in lines[:-1]))
        self.assertEqual(lines[-1], "RESULT | PASS | agent command line version 2.1.304: 9 of 9 assertions hold")
        sessions["p2"] = session(6484, 1, "p2")
        failing = smoke.report_lines(smoke.checks(sessions, systems), "2.1.304")
        self.assertTrue(failing[-1].startswith("RESULT | FAIL"))
        self.assertTrue(any("| FAIL |" in line for line in failing))


class ProbePlanTests(unittest.TestCase):
    def stub_run(self):
        shared = {}
        made = []

        def make():
            def replies(call, number):
                # the schema-flag fork reads nothing, as the recorded p2 did
                return ex.Reply(read=0, write=7042) if call.label == "p2" else ex.Reply(write=500)
            executor = ex.StubExecutor(replies)
            executor.sessions = shared
            made.append(executor)
            return executor
        sessions = smoke.run_probes(make, "/work/smoke", "claude-sonnet-5-5")
        return sessions, made

    def test_seven_probes_run_in_order_each_forking_from_its_parent(self):
        sessions, made = self.stub_run()
        self.assertEqual(list(sessions), ["p1", "p2", "p3", "p4", "p5", "p6", "p7"])
        calls = {executor.calls[0].label: executor.calls[0] for executor in made}
        parents = {"p1": None, "p2": "p1", "p3": "p1", "p4": None, "p5": "p4", "p6": "p4", "p7": "p6"}
        for name, parent in parents.items():
            self.assertEqual(calls[name].parent, sessions[parent].id if parent else None, name)
            self.assertEqual(calls[name].fork, parent is not None, name)

    def test_the_probes_differ_from_their_roots_only_where_the_smoke_needs_it(self):
        _, made = self.stub_run()
        calls = {executor.calls[0].label: executor.calls[0].spec for executor in made}
        self.assertIsNone(calls["p1"].json_schema)
        self.assertIsNotNone(calls["p2"].json_schema, "the schema flag the root lacked")
        self.assertEqual(set(calls["p3"].tools) - set(calls["p1"].tools), {"WebFetch"})
        for name in ("p5", "p6", "p7"):
            self.assertEqual(calls[name], calls["p4"], f"{name} starts from its root's specification")
        for spec in calls.values():
            self.assertEqual(spec.model, "claude-sonnet-5-5")

    def test_the_stub_run_passes_the_assertions_with_equal_system_prompts(self):
        sessions, _ = self.stub_run()
        results = smoke.checks(sessions, {name: "same" for name in sessions})
        self.assertTrue(all(held for _, held, _ in results), results)

    def test_a_probe_that_does_not_answer_stops_the_smoke_naming_it(self):
        executor = ex.StubExecutor([ex.Reply(is_error=True, text="boom", exit_code=1)])
        with self.assertRaises(smoke.SmokeFailure) as caught:
            smoke.run_probes(lambda: executor, "/work/smoke")
        self.assertIn("p1", str(caught.exception))
        self.assertIn("boom", str(caught.exception))

    def test_probe_messages_hold_two_synthetic_images_and_nothing_of_this_machine(self):
        for probe in smoke.PROBES:
            event = json.loads(probe.message)
            blocks = event["message"]["content"]
            images = [block for block in blocks if block["type"] == "image"]
            self.assertEqual(len(images), 2 if probe.parent is None else 0, probe.name)
            self.assertNotIn("/Users/", probe.message)
        self.assertEqual(len({probe.name for probe in smoke.PROBES}), 7)

    def test_the_synthetic_images_are_valid_distinct_pngs(self):
        first, second = smoke.png(160, 120, 0), smoke.png(160, 120, 128)
        self.assertNotEqual(first, second)
        self.assertEqual(first, smoke.png(160, 120, 0))
        self.assertEqual(first[:8], b"\x89PNG\r\n\x1a\n")
        width, height = struct.unpack(">II", first[16:24])
        self.assertEqual((width, height), (160, 120))
        position, data = 8, b""
        while position < len(first):
            length, kind = struct.unpack(">I4s", first[position:position + 8])
            body = first[position + 8:position + 8 + length]
            self.assertEqual(struct.unpack(">I", first[position + 8 + length:position + 12 + length])[0],
                             zlib.crc32(kind + body) & 0xFFFFFFFF)
            data += body if kind == b"IDAT" else b""
            position += 12 + length
        self.assertEqual(len(zlib.decompress(data)), 120 * (1 + 160))


class CliTests(unittest.TestCase):
    def run_main(self, argv, environ):
        out, err = io.StringIO(), io.StringIO()
        status = smoke.main(argv, out=out, err=err, environ=environ)
        return status, out.getvalue(), err.getvalue()

    # SOL-HW-REVIEW-KIT.C2: when the agent command line is missing or not logged in the smoke prints a CANNOT RUN line naming
    # the cause and what to do, and exits 2
    def test_a_missing_command_line_prints_cannot_run_and_exits_2(self):
        with tempfile.TemporaryDirectory() as folder:
            status, out, err = self.run_main(["--out", folder], {ex.AGENT_ENV: "no-such-agent-program"})
            self.assertEqual(status, 2)
            self.assertEqual(out, "")
            self.assertTrue(err.startswith("CANNOT RUN | "), err)
            self.assertEqual(len(err.strip().splitlines()), 1)
            self.assertIn("no-such-agent-program", err)
            self.assertIn("not on the search path", err)
            self.assertIn(ex.AGENT_ENV, err, "it says what to do")
            self.assertEqual(os.listdir(folder), [], "nothing was started or written")

    def test_a_command_line_that_is_not_logged_in_prints_cannot_run_and_exits_2(self):
        with tempfile.TemporaryDirectory() as folder:
            program = os.path.join(folder, "agent")
            with open(program, "w", encoding="utf-8") as handle:
                handle.write('#!/bin/sh\necho \'{"loggedIn": false}\'\n')
            os.chmod(program, os.stat(program).st_mode | stat.S_IXUSR)
            out_folder = os.path.join(folder, "out")
            status, out, err = self.run_main(["--out", out_folder], {ex.AGENT_ENV: program})
            self.assertEqual(status, 2)
            self.assertTrue(err.startswith("CANNOT RUN | "), err)
            self.assertIn("not logged in", err)
            self.assertIn("log it in", err)
            self.assertFalse(os.path.exists(out_folder), "no probe was started")

    def test_the_output_folder_is_required(self):
        with self.assertRaises(SystemExit) as caught:
            with unittest.mock.patch("sys.stderr", io.StringIO()):
                smoke.main([], environ={})
        self.assertEqual(caught.exception.code, 2)


import unittest.mock  # noqa: E402

if __name__ == "__main__":
    unittest.main()
