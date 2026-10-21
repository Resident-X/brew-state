#!/usr/bin/env python3
"""The reduction tool that makes the recorded-stream fixtures, and the fixtures it made.

The tool is run as shipped over synthetic recordings written to a temporary folder, and the committed fixtures are
walked to show that no path of the recording machine and no image byte remains in any of them. No model, no network and
no KiCad are used.
"""

from __future__ import annotations

import base64
import contextlib
import io
import json
import os
import re
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
sys.path.insert(0, TOOLS)

from review_kit import reduce, streams  # noqa: E402

FIXTURES = os.path.join(HERE, "fixtures", "review_streams")
#: A path of the machines recordings are made on, spelt as the recordings spell them.
MACHINE = re.compile(r"/Users/|/private/tmp|/home/[a-z]|/var/folders|claude-501|-Users-|-private-tmp-")
PNG = bytes(range(256)) * 20


def lines(*events):
    return "\n".join(json.dumps(event) for event in events) + "\n"


def image_block(data=PNG):
    return {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": base64.b64encode(data).decode()}}


def recording(root="/Users/someone/work/review"):
    """A stream-json recording as the agent command line prints it, with an image in the message it was sent."""
    return lines(
        {"type": "system", "subtype": "init", "session_id": "s-1", "cwd": f"{root}/cwd", "tools": ["Read"], "model": "m",
         "mcp_servers": [], "scratchpad_path": f"{root}/scratch", "capabilities": ["x"], "uuid": "u0"},
        {"type": "rate_limit_event", "rate_limit_info": {}},
        {"type": "user", "session_id": "s-1", "message": {"role": "user", "content": [
            {"type": "text", "text": "=== image: a.png ==="}, image_block()]}},
        {"type": "assistant", "session_id": "s-1", "message": {"id": "m1", "model": "m", "role": "assistant", "content": [
            {"type": "thinking", "thinking": "", "signature": "S" * 300},
            {"type": "text", "text": f"I opened {root}/views/a.png."},
            {"type": "tool_use", "id": "t1", "name": "Read", "input": {"file_path": f"{root}/views/a.png"}}],
            "usage": {"input_tokens": 2, "cache_read_input_tokens": 5, "cache_creation_input_tokens": 7, "output_tokens": 3,
                      "iterations": [{"x": 1}]}}},
        {"type": "user", "session_id": "s-1", "message": {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": "t1", "is_error": False, "content": [image_block(b"abc")]}]}},
        {"type": "result", "session_id": "s-1", "is_error": False, "result": "done", "total_cost_usd": 0.5, "duration_ms": 9,
         "duration_api_ms": 8, "num_turns": 2, "usage": {"output_tokens": 3, "iterations": [1]}, "modelUsage": {"x": 1},
         "time_to_request_phases_ms": {"y": 2}})


def reduced(text, **options):
    out, counts = reduce.reduce_text(text, **options)
    return [json.loads(line) for line in out.splitlines()], counts, out


class Reduction(unittest.TestCase):
    def test_image_bytes_are_replaced_by_their_size(self):
        # SOL-HW-REVIEW-KIT.C4: with image bytes replaced by their size
        records, counts, out = reduced(recording())
        self.assertEqual(counts["images"], 2)
        images = [block for record in records if record["type"] == "user" for block in record["message"]["content"]
                  if isinstance(block, dict) and (block.get("type") == "image" or block.get("type") == "tool_result")]
        self.assertEqual(images[0], {"type": "image", "source": {"type": "base64", "media_type": "image/png", "bytes": len(PNG)}})
        self.assertEqual(images[1]["content"][0]["source"]["bytes"], 3)
        self.assertNotIn(base64.b64encode(PNG).decode()[:80], out)
        self.assertEqual(reduce.leftovers(out), [])

    def test_an_absolute_path_of_the_recording_machine_is_replaced(self):
        # SOL-HW-REVIEW-KIT.C4: with absolute paths of the recording machine scrubbed
        root = "/Users/someone/work/review"
        records, _, out = reduced(recording(root), roots=[root])
        use = records[2]["message"]["content"][2]
        self.assertEqual(use["input"], {"file_path": "views/a.png"})
        self.assertEqual(records[2]["message"]["content"][1]["text"], "I opened views/a.png.")  # the full stop is the sentence's
        self.assertEqual(records[0]["cwd"], "cwd")
        self.assertIsNone(MACHINE.search(out))

    def test_a_path_under_no_root_keeps_only_its_file_name(self):
        # SOL-HW-REVIEW-KIT.C4: with absolute paths of the recording machine scrubbed
        records, _, out = reduced(recording("/private/tmp/claude-501/-Users-x/run/review"))
        self.assertEqual(records[2]["message"]["content"][2]["input"], {"file_path": "<path>/a.png"})
        self.assertEqual(records[0]["cwd"], "<path>/cwd")
        self.assertIsNone(MACHINE.search(out))

    def test_the_forms_of_path_the_recordings_use_are_all_replaced(self):
        # SOL-HW-REVIEW-KIT.C4: with absolute paths of the recording machine scrubbed
        reduction = reduce.Reduction(["/Users/a/repo"], 1500, 400)
        for text, expected in (
                ("/Users/a/repo/hardware/x.md", "hardware/x.md"),
                ("read '/Users/a/repo/x.md', then \"/home/b/y.txt\"", "read 'x.md', then \"<path>/y.txt\""),
                ("(/private/tmp/z/w.png)", "(<path>/w.png)"),
                ("in /var/folders/ab/cd/T/t.json; and /tmp/q", "in <path>/t.json; and <path>/q"),
                ("-Users-a-repo-wt-7 and -private-tmp-claude-501-x", "<recording-dir> and <recording-dir>"),
                ("relative/dir/file.png and /usr/lib/x are left", "relative/dir/file.png and /usr/lib/x are left"),
                ("hardware/tmp/x and a/Users/b", "hardware/tmp/x and a/Users/b")):
            self.assertEqual(reduction.scrub(text), expected, text)

    def test_the_longest_root_wins(self):
        # SOL-HW-REVIEW-KIT.C4: with absolute paths of the recording machine scrubbed
        reduction = reduce.Reduction(["/Users/a", "/Users/a/review"], 1500, 400)
        self.assertEqual(reduction.scrub("/Users/a/review/views/x.png /Users/a/other.md"), "views/x.png other.md")

    def test_what_the_checks_read_is_kept(self):
        # SOL-HW-REVIEW-KIT.C4: a reduction that keeps everything the checks read
        records, _, _ = reduced(recording(), roots=["/Users/someone/work/review"])
        self.assertEqual([record["type"] for record in records], ["system", "user", "assistant", "user", "result"])
        start = records[0]
        self.assertEqual((start["session_id"], start["tools"], start["model"], start["mcp_servers"]), ("s-1", ["Read"], "m", []))
        self.assertNotIn("capabilities", start)
        call = records[2]["message"]
        self.assertEqual((call["id"], call["usage"]), ("m1", {"input_tokens": 2, "cache_read_input_tokens": 5,
                                                              "cache_creation_input_tokens": 7, "output_tokens": 3}))
        self.assertEqual(call["content"][0], {"type": "thinking", "thinking": ""})
        self.assertEqual(records[3]["message"]["content"][0]["tool_use_id"], "t1")
        self.assertIs(records[3]["message"]["content"][0]["is_error"], False)
        result = records[4]
        self.assertEqual((result["total_cost_usd"], result["duration_api_ms"], result["num_turns"], result["usage"]),
                         (0.5, 8, 2, {"output_tokens": 3, "iterations": [1]}))
        self.assertNotIn("modelUsage", result)
        stream = streams.read_stream("\n".join(json.dumps(record) for record in records))
        self.assertEqual([opened.path for opened in stream.opens()], ["views/a.png"])
        self.assertEqual(streams.held_names(stream), ["a.png"])

    def test_an_error_flag_and_redacted_thinking_survive(self):
        # SOL-HW-REVIEW-KIT.C4: a reduction that keeps everything the checks read
        records, _, _ = reduced(lines(
            {"type": "assistant", "message": {"id": "m", "content": [{"type": "redacted_thinking", "data": "X" * 500}]}},
            {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "t", "is_error": True, "content": "no"}]}}))
        self.assertEqual(records[0]["message"]["content"], [{"type": "redacted_thinking"}])
        self.assertIs(records[1]["message"]["content"][0]["is_error"], True)

    def test_a_long_text_keeps_its_start_its_header_lines_and_a_count(self):
        # SOL-HW-REVIEW-KIT.C4: a reduction that keeps everything the checks read
        body = "=== docs/a.md (section: one) ===\n" + "x" * 3000 + "\n=== image: tile.png ===\n" + "y" * 500
        records, _, _ = reduced(lines({"type": "user", "message": {"content": [{"type": "text", "text": body}]}}), limit=100)
        text = records[0]["message"]["content"][0]["text"]
        self.assertTrue(text.startswith("=== docs/a.md (section: one) ===\nxxx"))
        self.assertIn("\n=== image: tile.png ===\n", text)
        self.assertTrue(text.endswith(f"[{len(body) - 100} characters omitted]"))
        stream = streams.read_stream(json.dumps(records[0]))
        self.assertEqual(streams.held_names(stream), ["a.md", "tile.png"])

    def test_a_tool_result_is_cut_shorter_than_a_message(self):
        # SOL-HW-REVIEW-KIT.C4: a reduction that keeps everything the checks read
        records, _, _ = reduced(lines({"type": "user", "message": {"content": [
            {"type": "tool_result", "tool_use_id": "t", "content": "z" * 1000}]}}), limit=900, result_limit=50)
        self.assertEqual(records[0]["message"]["content"][0]["content"], "z" * 50 + "\n[950 characters omitted]")

    def test_the_system_prompt_of_a_transcript_is_kept_with_the_tool_names(self):
        # SOL-HW-REVIEW-KIT.C4: the system prompt a session used is read from the transcript Claude Code writes for that session
        shape = {"type": "api-request-shape", "sessionId": "s-9", "shapeHash": "abc", "extra": 1,
                 "shape": {"system": [{"type": "text", "text": "rule in /Users/q/x"}], "tools": [{"name": "Read", "schema": {}}, "Grep"]}}
        records, _, _ = reduced(lines(shape, shape, {"type": "queue-operation"}, {"type": "attachment"}))
        self.assertEqual(records, [{"type": "api-request-shape", "sessionId": "s-9", "shapeHash": "abc",
                                    "shape": {"system": [{"type": "text", "text": "rule in <path>/x"}], "tools": ["Read", "Grep"]}}])

    def test_reducing_a_reduction_changes_nothing(self):
        # SOL-HW-REVIEW-KIT.C4: a reduction tool whose own output is a fixture the tool can read again
        once = reduced(recording(), roots=["/Users/someone/work/review"])[2]
        self.assertEqual(reduced(once)[2], once)

    def test_the_records_of_a_parent_session_are_left_out(self):
        # SOL-HW-REVIEW-KIT.C4: a fork's transcript repeats its parent's records, which are not the fork's
        mine = {"type": "assistant", "uuid": "own", "message": {"id": "m2", "content": [{"type": "text", "text": "mine"}]}}
        inherited = {"type": "assistant", "uuid": "old", "message": {"id": "m1", "content": [{"type": "text", "text": "theirs"}]}}
        out, _ = reduce.reduce_text(lines(inherited, mine), skip=frozenset({"old"}))
        self.assertEqual([json.loads(line)["message"]["id"] for line in out.splitlines()], ["m2"])

    def test_a_line_that_is_not_json_is_counted_and_passed_over(self):
        # SOL-HW-REVIEW-KIT.C4: a reduction that says what it left out
        _, counts, out = reduced("not json\n" + lines({"type": "result", "total_cost_usd": 1}) + "[1]\n")
        self.assertEqual((counts["read"], counts["kept"], counts["dropped_unreadable"]), (3, 1, 2))
        self.assertEqual(len(out.splitlines()), 1)

    def test_what_a_reduction_would_still_hold_is_named(self):
        # SOL-HW-REVIEW-KIT.C4: a reduction tool whose own test shows no path or image byte remains
        found = reduce.leftovers("a /Users/x/y.png b -Users-x-y c " + "A" * 250 + " /private/tmp/z")
        self.assertEqual(len(found), 4)
        self.assertTrue(found[0].startswith("absolute path '/Users/x/y.png'"))
        self.assertIn("base64 run of 250 characters", " ".join(found))
        self.assertEqual(reduce.leftovers("relative/path.png and a short AAAA run"), [])


class Command(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)

    def path(self, name):
        return os.path.join(self.folder.name, name)

    def write(self, name, text):
        with open(self.path(name), "w", encoding="utf-8") as handle:
            handle.write(text)
        return self.path(name)

    def run_main(self, *argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            status = reduce.main(list(argv))
        return status, out.getvalue()

    def test_the_command_writes_the_reduction_and_reports_what_it_did(self):
        # SOL-HW-REVIEW-KIT.C4: made by a reduction tool whose own test shows no path or image byte remains
        source = self.write("in.jsonl", recording("/Users/someone/work/review"))
        status, said = self.run_main(source, self.path("out.jsonl"), "--root", "/Users/someone/work/review")
        self.assertEqual(status, 0)
        self.assertIn("RESULT: wrote", said)
        self.assertIn("replaced 2 image(s) by their size", said)
        with open(self.path("out.jsonl"), encoding="utf-8") as handle:
            written = handle.read()
        self.assertEqual(reduce.leftovers(written), [])
        self.assertIsNone(MACHINE.search(written))
        self.assertNotIn("data", [key for record in map(json.loads, written.splitlines())
                                  for block in (record.get("message", {}).get("content") or []) if isinstance(block, dict)
                                  for key in (block.get("source") or {})])

    def test_the_command_runs_as_a_script(self):
        # SOL-HW-REVIEW-KIT.C4: a CLI entry python3 hardware/tools/review_kit/reduce.py <in> <out>
        import subprocess
        source = self.write("in.jsonl", recording())
        done = subprocess.run([sys.executable, "-I", os.path.join(TOOLS, "review_kit", "reduce.py"), source, self.path("out.jsonl")],
                              capture_output=True, text=True, check=False)
        self.assertEqual((done.returncode, done.stderr), (0, ""))
        self.assertTrue(os.path.exists(self.path("out.jsonl")))

    def test_an_input_that_cannot_be_read_cannot_run(self):
        # SOL-HW-REVIEW-KIT.C4: a command that says why it cannot run
        status, said = self.run_main(self.path("missing.jsonl"), self.path("out.jsonl"))
        self.assertEqual(status, 2)
        self.assertTrue(said.startswith("CANNOT RUN: the input "))
        self.assertIn("name a recorded stream or transcript", said)
        self.assertFalse(os.path.exists(self.path("out.jsonl")))

    def test_an_output_that_cannot_be_written_cannot_run(self):
        # SOL-HW-REVIEW-KIT.C4: a command that says why it cannot run
        source = self.write("in.jsonl", recording())
        status, said = self.run_main(source, self.path("no-such-folder/out.jsonl"))
        self.assertEqual(status, 2)
        self.assertIn("CANNOT RUN: the output ", said)

    def test_the_input_named_as_the_output_is_refused_and_left_alone(self):
        # SOL-HW-REVIEW-KIT.C4: a command that refuses to overwrite a recording
        source = self.write("in.jsonl", recording())
        status, said = self.run_main(source, source)
        self.assertEqual(status, 1)
        self.assertIn("REFUSED: the output is the input", said)
        with open(source, encoding="utf-8") as handle:
            self.assertEqual(handle.read(), recording())

    def test_a_limit_below_one_is_refused(self):
        # SOL-HW-REVIEW-KIT.C4: a command that refuses a limit it cannot honour
        source = self.write("in.jsonl", recording())
        for option in ("--limit", "--result-limit"):
            status, said = self.run_main(source, self.path("out.jsonl"), option, "0")
            self.assertEqual((status, said.startswith("REFUSED: --limit and --result-limit")), (1, True))

    def test_an_output_that_would_still_hold_image_bytes_is_refused_and_not_written(self):
        # SOL-HW-REVIEW-KIT.C4: a reduction tool whose own test shows no path or image byte remains
        hidden = base64.b64encode(PNG).decode()
        source = self.write("in.jsonl", lines({"type": "assistant", "message": {"id": "m", "content": [
            {"type": "text", "text": "the bytes are " + hidden}]}}))
        status, said = self.run_main(source, self.path("out.jsonl"), "--limit", "5000")
        self.assertEqual(status, 1)
        self.assertIn("REFUSED: the reduction would still hold 1 thing(s) a fixture may not: base64 run of", said)
        self.assertFalse(os.path.exists(self.path("out.jsonl")))

    def test_the_parent_transcript_leaves_out_what_the_fork_inherited(self):
        # SOL-HW-REVIEW-KIT.C4: a fork's transcript repeats its parent's records
        parent = self.write("parent.jsonl", lines({"type": "user", "uuid": "p1", "message": {"content": "hold this"}}))
        fork = self.write("fork.jsonl", lines({"type": "user", "uuid": "p1", "message": {"content": "hold this"}},
                                              {"type": "user", "uuid": "f1", "message": {"content": "judge"}}))
        status, _ = self.run_main(fork, self.path("out.jsonl"), "--after", parent)
        self.assertEqual(status, 0)
        with open(self.path("out.jsonl"), encoding="utf-8") as handle:
            self.assertEqual([json.loads(line)["message"]["content"] for line in handle], ["judge"])
        status, said = self.run_main(fork, self.path("out2.jsonl"), "--after", self.path("absent.jsonl"))
        self.assertEqual((status, said.startswith("CANNOT RUN: the parent transcript")), (2, True))

    def test_the_system_prompt_is_taken_from_the_transcript_found_by_the_session_identifier(self):
        # SOL-HW-REVIEW-KIT.C4: the system prompt a session used is read from the transcript Claude Code writes for that session, found by the session's identifier, because the start report carries none
        projects = os.path.join(self.folder.name, "projects")
        os.makedirs(os.path.join(projects, "-some-directory"))
        shape = {"type": "api-request-shape", "sessionId": "s-1", "shapeHash": "h",
                 "shape": {"system": [{"type": "text", "text": "the rule"}], "tools": ["Read"]}}
        with open(os.path.join(projects, "-some-directory", "s-1.jsonl"), "w", encoding="utf-8") as handle:
            handle.write(lines(shape))
        source = self.write("in.jsonl", recording())
        status, _ = self.run_main(source, self.path("out.jsonl"), "--transcripts", projects)
        self.assertEqual(status, 0)
        read = streams.read_stream_file(self.path("out.jsonl"))
        self.assertEqual((read.system_prompt, read.tools, read.session_id), ("the rule", ("Read",), "s-1"))
        self.assertEqual(len(read.calls), 1)
        os.remove(os.path.join(projects, "-some-directory", "s-1.jsonl"))
        status, said = self.run_main(source, self.path("out3.jsonl"), "--transcripts", projects)
        self.assertEqual(status, 1)
        self.assertIn("REFUSED: no transcript named s-1.jsonl lies under", said)
        self.assertFalse(os.path.exists(self.path("out3.jsonl")))

    def test_a_stream_that_already_holds_a_system_prompt_is_not_looked_up(self):
        # SOL-HW-REVIEW-KIT.C4: the system prompt a session used is read from the transcript
        shape = {"type": "api-request-shape", "sessionId": "s-1", "shapeHash": "h",
                 "shape": {"system": [{"type": "text", "text": "already"}], "tools": []}}
        source = self.write("in.jsonl", lines(shape) + recording())
        status, _ = self.run_main(source, self.path("out.jsonl"), "--transcripts", os.path.join(self.folder.name, "nowhere"))
        self.assertEqual(status, 0)
        self.assertEqual(streams.read_stream_file(self.path("out.jsonl")).system_prompt, "already")


class Fixtures(unittest.TestCase):
    def files(self):
        found = [os.path.join(directory, name) for directory, _, names in os.walk(FIXTURES) for name in names]
        self.assertGreater(len(found), 30)
        return found

    def test_no_committed_fixture_holds_a_path_of_the_recording_machine_or_an_image_byte(self):
        # SOL-HW-REVIEW-KIT.C4: the fixtures are reductions of recorded sessions, with image bytes replaced by their size and absolute paths of the recording machine scrubbed
        for path in self.files():
            with open(path, encoding="utf-8") as handle:
                text = handle.read()
            name = os.path.relpath(path, FIXTURES)
            self.assertIsNone(MACHINE.search(text), name)
            self.assertEqual(reduce.leftovers(text), [], name)
            self.assertNotIn("base64,", text, name)
            for number, line in enumerate(text.splitlines(), 1):
                self.assertNotRegex(line, r'"data": ?"[A-Za-z0-9+/=]{40,}', f"{name} line {number}")

    def test_every_image_in_a_fixture_is_a_size(self):
        # SOL-HW-REVIEW-KIT.C4: with image bytes replaced by their size
        seen = 0

        def walk(value):
            nonlocal seen
            if isinstance(value, dict):
                if value.get("type") == "image":
                    seen += 1
                    self.assertEqual(sorted(value["source"]), ["bytes", "media_type", "type"])
                    self.assertIsInstance(value["source"]["bytes"], int)
                    self.assertGreater(value["source"]["bytes"], 0)
                for item in value.values():
                    walk(item)
            elif isinstance(value, list):
                for item in value:
                    walk(item)

        for path in self.files():
            if path.endswith(".jsonl"):
                with open(path, encoding="utf-8") as handle:
                    for line in handle:
                        walk(json.loads(line))
        self.assertGreater(seen, 300)  # the layout run's forks were sent and opened hundreds of views

    def test_every_fixture_stream_is_read_without_a_malformed_line_and_names_its_session(self):
        # SOL-HW-REVIEW-KIT.C4: the fixtures are reductions of recorded sessions the checks read
        for path in self.files():
            if path.endswith(".jsonl"):
                stream = streams.read_stream_file(path)
                name = os.path.relpath(path, FIXTURES)
                self.assertEqual(stream.malformed, [], name)
                self.assertTrue(stream.session_id, name)
                self.assertIsNotNone(stream.system, name)

    def test_the_fixtures_stay_small(self):
        # SOL-HW-REVIEW-KIT.C4: the fixtures are small reductions
        total = sum(os.path.getsize(path) for path in self.files())
        self.assertLess(total, 1_500_000)

    def test_the_fixtures_the_criterion_names_are_all_present(self):
        # SOL-HW-REVIEW-KIT.C4: the narrated setup, the acknowledgement, the schema-flag cache miss, the layout run with its opens and the setup-rule start reports are among the fixtures
        with open(os.path.join(FIXTURES, "manifest.json"), encoding="utf-8") as handle:
            manifest = json.load(handle)
        named = [manifest["setup_narrated"]["file"], manifest["probes"]["p1"]["file"], manifest["probes"]["p2"]["file"],
                 manifest["layout_run"]["setup"], manifest["layout_run"]["rows"], manifest["setup_rule"]["fork"],
                 *(f"layout_run/{unit}.jsonl" for unit in manifest["layout_run"]["units"]),
                 *(entry["file"] for entry in manifest["probes"].values()), *manifest["validation"]["roots"].values(),
                 *(f"validation/{name}.jsonl" for arm in manifest["validation"]["forks"].values() for name in arm)]
        for name in named:
            self.assertTrue(os.path.isfile(os.path.join(FIXTURES, name)), name)
        self.assertEqual(len(manifest["layout_run"]["units"]), 13)
        self.assertEqual(len(manifest["validation"]["forks"]["sonnet"]) + len(manifest["validation"]["forks"]["haiku"]), 12)


if __name__ == "__main__":
    unittest.main()
