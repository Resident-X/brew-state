#!/usr/bin/env python3
"""The review kit's session specification: how every session of a review is started, and what its start report may show.

Run against the stub executor, which keeps the arguments each call was built with. No model is used.
"""

from __future__ import annotations

import os
import sys
import unittest
from dataclasses import fields, replace

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)

from review_kit import executor as ex  # noqa: E402
from review_kit import session as sess  # noqa: E402

SPEC = sess.SessionSpec(("Read", "Glob"), "/work/review", model="claude-sonnet-5-5", system="You are a reviewer.",
                        append_system="Judge only what you can see.", json_schema='{"type": "object"}')
MESSAGE = sess.user_message([sess.text_block("hold this")])


def without_continuation(arguments):
    """The arguments less the resume and fork arguments, the only ones that may differ between sessions of a review."""
    found, skip = [], False
    for argument in arguments:
        if skip:
            skip = False
        elif argument == "--resume":
            skip = True
        elif argument != "--fork-session":
            found.append(argument)
    return found


def flag_value(arguments, name):
    return arguments[arguments.index(name) + 1]


class SameStartTests(unittest.TestCase):
    def play(self):
        """The root, a fork of it, a repair turn in the fork's session and an adjudication turn in a second fork."""
        stub = ex.StubExecutor()
        root = stub.run(sess.Call(SPEC, MESSAGE, label="root"))
        fork = stub.run(sess.Call(SPEC, sess.user_message([sess.text_block("unit one")]), parent=root.session.id,
                                  fork=True, label="fork"))
        repair = stub.run(sess.Call(SPEC, sess.user_message([sess.text_block("fix these")]), parent=fork.session.id,
                                    label="repair"))
        adjudication = stub.run(sess.Call(SPEC, sess.user_message([sess.text_block("disagreements")]),
                                          parent=root.session.id, fork=True, label="adjudication"))
        return stub, root, fork, repair, adjudication

    # SOL-HW-REVIEW-KIT.C1: the root, a fork, a repair turn and an adjudication turn are each started with the same
    # system prompt, appended system prompt, tool list, model and schema arguments, and differ only in the message and
    # the resume and fork arguments
    def test_four_kinds_of_session_share_every_argument_but_resume_and_fork(self):
        stub, root, fork, repair, adjudication = self.play()
        self.assertEqual(len(stub.arguments), 4)
        base = without_continuation(stub.arguments[0])
        for arguments in stub.arguments:
            self.assertEqual(without_continuation(arguments), base)
            self.assertEqual(flag_value(arguments, "--system-prompt"), SPEC.system)
            self.assertEqual(flag_value(arguments, "--append-system-prompt"), SPEC.append_system)
            self.assertEqual(flag_value(arguments, "--tools"), "Read,Glob")
            self.assertEqual(flag_value(arguments, "--allowedTools"), "Read,Glob")
            self.assertEqual(flag_value(arguments, "--model"), SPEC.model)
            self.assertEqual(flag_value(arguments, "--json-schema"), SPEC.json_schema)
            self.assertEqual(flag_value(arguments, "--input-format"), "stream-json")
            self.assertEqual(flag_value(arguments, "--output-format"), "stream-json")
            self.assertIn("-p", arguments)

    # SOL-HW-REVIEW-KIT.C1: differ only in the message and the resume and fork arguments
    def test_resume_and_fork_arguments_follow_the_kind_of_session(self):
        stub, root, fork, repair, adjudication = self.play()
        root_args, fork_args, repair_args, adjudication_args = stub.arguments
        self.assertNotIn("--resume", root_args)
        self.assertNotIn("--fork-session", root_args)
        self.assertEqual(flag_value(fork_args, "--resume"), root.session.id)
        self.assertIn("--fork-session", fork_args)
        self.assertEqual(flag_value(repair_args, "--resume"), fork.session.id)
        self.assertNotIn("--fork-session", repair_args)
        self.assertEqual(flag_value(adjudication_args, "--resume"), root.session.id)
        self.assertIn("--fork-session", adjudication_args)
        self.assertNotEqual(root.session.id, fork.session.id)
        self.assertEqual(repair.session.id, fork.session.id)  # a repair turn is a turn of the unit's own session

    # SOL-HW-REVIEW-KIT.C1: the message is the one thing that differs, and it is not an argument
    def test_the_message_is_on_standard_input_not_in_the_arguments(self):
        stub = self.play()[0]
        for call, arguments in zip(stub.calls, stub.arguments):
            self.assertNotIn(call.message, arguments)
            self.assertFalse(any("hold this" in argument or "unit one" in argument for argument in arguments))
        self.assertEqual(len({call.message for call in stub.calls}), 4)

    # SOL-HW-REVIEW-KIT.C1: the agent command line's arguments are built from the specification alone
    def test_arguments_are_a_function_of_the_specification_alone(self):
        self.assertEqual(sess.arguments(SPEC), sess.arguments(replace(SPEC)))
        self.assertEqual(sess.Call(SPEC, "one").arguments, sess.Call(SPEC, "another message").arguments)
        for field, changed in (("tools", ("Read",)), ("model", "claude-haiku-5-5"), ("system", "another"),
                               ("append_system", "another"), ("json_schema", '{"type": "array"}')):
            self.assertNotEqual(sess.arguments(replace(SPEC, **{field: changed})), sess.arguments(SPEC), field)

    # SOL-HW-REVIEW-KIT.C1: a flag the specification does not give is not passed, so no setup-only prompt exists
    def test_a_flag_without_a_value_is_left_out(self):
        bare = sess.SessionSpec(("Read",), "/work")
        arguments = sess.arguments(bare)
        for flag in ("--system-prompt", "--append-system-prompt", "--model", "--json-schema", "--resume", "--fork-session"):
            self.assertNotIn(flag, arguments)
        self.assertEqual(flag_value(arguments, "--tools"), "Read")

    # SOL-HW-REVIEW-KIT.C1: no MCP server and none of the instruction sources the command line can exclude
    def test_the_quiet_flags_are_always_passed(self):
        arguments = sess.arguments(SPEC, "parent", True)
        for flag in ("--strict-mcp-config", "--disable-slash-commands", "--exclude-dynamic-system-prompt-sections"):
            self.assertIn(flag, arguments)
        self.assertEqual(flag_value(arguments, "--setting-sources"), "")
        self.assertEqual(flag_value(arguments, "--permission-mode"), "dontAsk")

    # SOL-HW-REVIEW-KIT.C1: a fork needs a parent
    def test_a_fork_with_no_parent_is_refused(self):
        with self.assertRaises(ValueError):
            sess.Call(SPEC, MESSAGE, fork=True)

    def test_the_key_of_a_call_follows_the_specification_the_parent_and_the_message(self):
        base = sess.Call(SPEC, "m", parent="p")
        self.assertEqual(base.key, sess.Call(SPEC, "m", parent="p", label="other label").key)
        for other in (sess.Call(replace(SPEC, model="x"), "m", parent="p"), sess.Call(SPEC, "m2", parent="p"),
                      sess.Call(SPEC, "m", parent="q"), sess.Call(SPEC, "m")):
            self.assertNotEqual(base.key, other.key)


class ChangedSpecTests(unittest.TestCase):
    CHANGES = {"tools": ("Read",), "cwd": "/elsewhere", "model": "claude-haiku-5-5", "system": "a setup-only rule",
               "append_system": "another", "json_schema": '{"type": "array"}'}

    # SOL-HW-REVIEW-KIT.C1: a specification that changes after the first session of a review has started is refused naming the field
    def test_each_changed_field_is_refused_naming_it(self):
        self.assertEqual({field.name for field in fields(sess.SessionSpec)}, set(self.CHANGES))
        for field, changed in self.CHANGES.items():
            with self.subTest(field=field):
                stub = ex.StubExecutor(check_start=False)
                stub.run(sess.Call(SPEC, MESSAGE, label="root"))
                with self.assertRaises(sess.SpecChanged) as caught:
                    stub.run(sess.Call(replace(SPEC, **{field: changed}), MESSAGE, label="later"))
                self.assertEqual(caught.exception.field, field)
                self.assertIn(field, str(caught.exception))
                self.assertEqual(len(stub.calls), 1, "no session was started with the changed specification")

    # SOL-HW-REVIEW-KIT.C1: the first session's specification is the review's; the same specification passes again
    def test_the_same_specification_is_accepted_again_and_the_first_is_not_refused(self):
        stub = ex.StubExecutor()
        stub.run(sess.Call(SPEC, MESSAGE, label="root"))
        stub.run(sess.Call(replace(SPEC), MESSAGE + " ", label="again"))
        self.assertEqual(len(stub.calls), 2)

    # SOL-HW-REVIEW-KIT.C1: two executors of one review share the one specification when they share a guard
    def test_a_shared_guard_holds_the_specification_across_executors(self):
        guard = sess.SpecGuard()
        ex.StubExecutor(guard=guard).run(sess.Call(SPEC, MESSAGE, label="root"))
        with self.assertRaises(sess.SpecChanged):
            ex.StubExecutor(guard=guard).run(sess.Call(replace(SPEC, system=None), MESSAGE, label="later"))


def start(**overrides):
    """A recorded start report of a well-behaved session started from SPEC, with the given fields changed."""
    report = {"type": "system", "subtype": "init", "session_id": "s-1", "cwd": SPEC.cwd, "model": SPEC.model,
              "tools": ["Read", "Glob", "StructuredOutput"], "mcp_servers": [], "skills": [], "slash_commands": [],
              "plugins": [{"name": "agents-md", "path": "builtin"}]}
    report.update(overrides)
    return report


def session_with(start_report, succeeded=True):
    import json
    lines = [json.dumps(start_report)] if start_report is not None else []
    usage = {"input_tokens": 2, "cache_creation_input_tokens": 5, "cache_read_input_tokens": 0, "output_tokens": 3}
    lines += [json.dumps({"type": "assistant", "message": {"id": "m1", "content": [{"type": "text", "text": "ok"}],
                                                           "usage": usage}}),
              json.dumps({"type": "result", "is_error": not succeeded, "total_cost_usd": 0.1, "duration_api_ms": 5,
                          "num_turns": 1, "result": "ok", "usage": usage})]
    return ex.parse_stream("\n".join(lines) + "\n")


class StartReportTests(unittest.TestCase):
    def problems(self, report, spec=SPEC):
        return ex.start_problems(session_with(report), "unit-b", spec)

    # SOL-HW-REVIEW-KIT.C1: over recorded start reports, a well-behaved session shows nothing
    def test_a_start_report_matching_the_specification_has_no_problem(self):
        self.assertEqual(self.problems(start()), [])
        self.assertEqual(self.problems(start(tools=["Read", "Glob"]), replace(SPEC, json_schema=None)), [])

    # SOL-HW-REVIEW-KIT.C1: a session that reports other tools than the specification grants fails the run naming the session
    def test_other_tools_than_the_grant_are_named(self):
        for tools in (["Read", "Glob", "StructuredOutput", "Bash"], ["Read", "StructuredOutput"], ["Read", "Glob"]):
            with self.subTest(tools=tools):
                found = self.problems(start(tools=tools))
                self.assertEqual(len(found), 1)
                self.assertIn("session unit-b", found[0])
                self.assertIn("tools", found[0])
        self.assertTrue(self.problems(start(tools=["Read", "Glob", "StructuredOutput"]), replace(SPEC, json_schema=None)),
                        "the schema's tool is granted only to a specification with a schema")

    # SOL-HW-REVIEW-KIT.C1: another model fails the run naming the session
    def test_another_model_is_named(self):
        found = self.problems(start(model="claude-haiku-5-5"))
        self.assertEqual(len(found), 1)
        self.assertIn("session unit-b", found[0])
        self.assertIn("claude-haiku-5-5", found[0])
        self.assertEqual(self.problems(start(model="anything"), replace(SPEC, model=None)), [])

    # SOL-HW-REVIEW-KIT.C1: any MCP server fails the run naming the session
    def test_any_mcp_server_is_named(self):
        found = self.problems(start(mcp_servers=[{"name": "konnect", "status": "connected"}]))
        self.assertEqual(len(found), 1)
        self.assertIn("session unit-b", found[0])
        self.assertIn("MCP", found[0])

    # SOL-HW-REVIEW-KIT.C1: an instruction source the command line was asked to exclude fails the run naming the session
    def test_an_excluded_instruction_source_is_named(self):
        cases = {"skills": ["repo-board-design"], "slash_commands": ["/init"],
                 "plugins": [{"name": "user-plugin", "path": "/home/someone/plugin"}]}
        for key, value in cases.items():
            with self.subTest(key=key):
                found = self.problems(start(**{key: value}))
                self.assertEqual(len(found), 1)
                self.assertIn("session unit-b", found[0])
                self.assertIn("asked to exclude", found[0])
        self.assertEqual(self.problems(start(plugins=[{"name": "a", "path": "builtin"}, {"name": "b", "path": "builtin"}])), [])

    # SOL-HW-REVIEW-KIT.C1: another working directory fails the run naming the session
    def test_another_working_directory_is_named(self):
        found = self.problems(start(cwd="/somewhere/else"))
        self.assertEqual(len(found), 1)
        self.assertIn("session unit-b", found[0])
        self.assertIn("/somewhere/else", found[0])

    # SOL-HW-REVIEW-KIT.C1: a field the command relies on that is absent or mistyped is a problem naming it, never a default
    def test_missing_and_mistyped_fields_are_named(self):
        report = start()
        for key in ("tools", "model", "cwd", "mcp_servers", "skills", "slash_commands", "plugins", "session_id"):
            absent = {k: v for k, v in report.items() if k != key}
            found = ex.start_problems(session_with(absent), "unit-b", SPEC)
            self.assertTrue(any(key in why for why in found), (key, found))
            mistyped = self.problems(start(**{key: 7}))
            self.assertTrue(any(key in why for why in mistyped), (key, mistyped))
        self.assertTrue(any("no start report" in why for why in ex.start_problems(session_with(None), "unit-b", SPEC)))

    # SOL-HW-REVIEW-KIT.C1: the run fails, not just reports: the executor raises naming the session, after keeping the stream
    def test_the_executor_fails_the_run_naming_the_session_and_keeps_its_stream(self):
        import tempfile
        with tempfile.TemporaryDirectory() as out:
            stub = ex.StubExecutor([ex.Reply(), ex.Reply(model="claude-haiku-5-5", mcp_servers=[{"name": "x"}])], out=out)
            stub.run(sess.Call(SPEC, MESSAGE, label="root"))
            with self.assertRaises(ex.StartReportFailed) as caught:
                stub.run(sess.Call(SPEC, MESSAGE + "2", label="unit-b"))
            self.assertEqual(caught.exception.label, "unit-b")
            self.assertEqual(len(caught.exception.problems), 2)
            self.assertIn("session unit-b", str(caught.exception))
            self.assertEqual(len([name for name in os.listdir(out) if name.endswith(".jsonl")]), 2)

    # SOL-HW-REVIEW-KIT.C1: a result report missing its figures is named too, since cost and answer cannot be told
    def test_a_result_report_without_figures_is_named(self):
        import json
        usage = {"input_tokens": 2, "cache_creation_input_tokens": 5, "cache_read_input_tokens": 0, "output_tokens": 3}
        lines = [json.dumps(start()), json.dumps({"type": "result", "is_error": False, "result": "ok", "usage": usage})]
        found = ex.start_problems(ex.parse_stream("\n".join(lines)), "unit-b", SPEC)
        self.assertEqual(len(found), 1)
        self.assertIn("total_cost_usd", found[0])


class MessageTests(unittest.TestCase):
    def test_a_user_message_is_one_stream_json_line_with_its_blocks(self):
        import json
        line = sess.user_message([sess.text_block("a\nb"), sess.image_block(b"\x89PNG-bytes")])
        self.assertNotIn("\n", line)
        event = json.loads(line)
        self.assertEqual(event["type"], "user")
        blocks = event["message"]["content"]
        self.assertEqual([block["type"] for block in blocks], ["text", "image"])
        self.assertEqual(blocks[0]["text"], "a\nb")
        self.assertEqual(blocks[1]["source"]["media_type"], "image/png")


if __name__ == "__main__":
    unittest.main()
