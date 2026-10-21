#!/usr/bin/env python3
"""The review kit's checks over recorded sessions, held to reductions of what ran.

The recorded fixtures are the streams and transcripts of real sessions, reduced by the kit's reduction tool; the
sessions made up here only alter one fact of a recorded one, so each check is shown to fail for the fact it names. No
model, no network and no KiCad are used.
"""

from __future__ import annotations

import copy
import json
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
sys.path.insert(0, TOOLS)

from review_kit import streamcheck, streams, transcripts  # noqa: E402

FIXTURES = os.path.join(HERE, "fixtures", "review_streams")
with open(os.path.join(FIXTURES, "manifest.json"), encoding="utf-8") as handle:
    MANIFEST = json.load(handle)


def recorded(name):
    return streams.read_stream_file(os.path.join(FIXTURES, name))


def probe(name):
    return recorded(MANIFEST["probes"][name]["file"])


def text_of(*events):
    return "\n".join(json.dumps(event) for event in events) + "\n"


def call_event(ident, blocks, session="s-1", **usage):
    return {"type": "assistant", "session_id": session,
            "message": {"id": ident, "role": "assistant", "content": blocks, "usage": {"cache_read_input_tokens": 0, **usage}}}


def ack_stream(blocks=None, extra=()):
    """A one-call session whose answer is the acknowledgement, with the blocks altered by the test."""
    return streams.read_stream(text_of(call_event("m1", [{"type": "text", "text": "ACK"}] if blocks is None else blocks), *extra))


def reasons(flags):
    return [flag.detail for flag in flags]


class NodeShape(unittest.TestCase):
    def test_the_narrated_setup_is_rejected_naming_the_reason(self):
        # SOL-HW-REVIEW-KIT.C4: the stream of a session that read documents in several calls and narrated between them fails the shape check naming the reason
        setup = recorded(MANIFEST["setup_narrated"]["file"])
        found = reasons(streamcheck.node_shape(setup, MANIFEST["setup_narrated"]["ack"]))
        self.assertEqual(len(setup.calls), MANIFEST["setup_narrated"]["calls"])
        self.assertTrue(any(f"made {len(setup.calls)} model calls, not one" in detail and "Read" in detail
                            and "wrote text in 2 of them" in detail for detail in found), found)
        self.assertTrue(any("used the Glob, Read tools" in detail for detail in found), found)
        # The narration is in the recorded stream, so the rejection is of what ran and not of a count alone.
        self.assertIn(MANIFEST["setup_narrated"]["narration"], [call.text for call in setup.calls])

    def test_the_one_call_acknowledgement_passes(self):
        # SOL-HW-REVIEW-KIT.C4: the stream of the one-call acknowledgement passes
        self.assertEqual(streamcheck.node_shape(probe("p1"), "ROOT-READY"), [])
        self.assertEqual(streamcheck.node_shape(recorded(MANIFEST["setup_rule"]["setup"]), MANIFEST["setup_narrated"]["ack"]), [])

    def test_a_node_that_acknowledges_through_the_schema_tool_passes(self):
        # SOL-HW-REVIEW-KIT.C4: no tool use other than the acknowledgement the schema asks for
        for name in ("p4", "p6"):
            self.assertEqual(streamcheck.node_shape(probe(name), MANIFEST["probes"][name]["ack"]), [], name)

    def test_an_answer_that_is_not_the_acknowledgement_fails_in_either_form(self):
        # SOL-HW-REVIEW-KIT.C4: a text other than the acknowledgement fails the shape check
        self.assertEqual(streamcheck.node_shape(ack_stream(), "ACK"), [])
        wrong = streamcheck.node_shape(ack_stream([{"type": "text", "text": "ACK, and the board looks fine"}]), "ACK")
        self.assertEqual(len(wrong), 1)
        self.assertIn("answered 'ACK, and the board looks fine' and not the acknowledgement 'ACK'", wrong[0].detail)
        self.assertEqual(len(streamcheck.node_shape(probe("p4"), "SOMETHING-ELSE")), 1)
        text_and_tool = [{"type": "text", "text": "ACK"}, {"type": "tool_use", "id": "t", "name": "StructuredOutput",
                                                         "input": {"answer": "ACK"}}]
        self.assertEqual(len(streamcheck.node_shape(ack_stream(text_and_tool), "ACK")), 1)
        self.assertEqual(len(streamcheck.node_shape(ack_stream([]), "ACK")), 1)

    def test_a_tool_other_than_the_schema_tool_fails(self):
        # SOL-HW-REVIEW-KIT.C4: no tool use other than the acknowledgement the schema asks for
        read = [{"type": "tool_use", "id": "t", "name": "Read", "input": {"file_path": "a.md"}}]
        found = streamcheck.node_shape(ack_stream(read), "ACK")
        self.assertEqual(len(found), 1)
        self.assertIn("used the Read tool", found[0].detail)
        self.assertEqual(streamcheck.node_shape(ack_stream(read), "ACK", schema_tool="Read")[0].detail.startswith("answered"), True)

    def test_a_thinking_block_that_carries_text_fails_and_an_empty_one_passes(self):
        # SOL-HW-REVIEW-KIT.C4: a thinking block that carries text fails the shape check
        ack = {"type": "text", "text": "ACK"}
        thought = streamcheck.node_shape(ack_stream([{"type": "thinking", "thinking": "I should look at U1 first"}, ack]), "ACK")
        self.assertEqual(len(thought), 1)
        self.assertIn("thinking block with text: 'I should look at U1 first'", thought[0].detail)
        self.assertEqual(streamcheck.node_shape(ack_stream([{"type": "thinking", "thinking": ""}, ack]), "ACK"), [])
        self.assertEqual(streamcheck.node_shape(ack_stream([{"type": "thinking", "thinking": "  \n"}, ack]), "ACK"), [])

    def test_a_redacted_thinking_block_fails(self):
        # SOL-HW-REVIEW-KIT.C4: a redacted thinking block fails the shape check
        found = streamcheck.node_shape(ack_stream([{"type": "redacted_thinking"}, {"type": "text", "text": "ACK"}]), "ACK")
        self.assertEqual(reasons(found), ["carries a redacted thinking block"])

    def test_a_second_call_an_error_result_and_an_unreadable_record_fail(self):
        # SOL-HW-REVIEW-KIT.C4: the shape of a shared-context node is exactly one model call
        two = streams.read_stream(text_of(call_event("m1", [{"type": "text", "text": "ACK"}]),
                                          call_event("m2", [{"type": "text", "text": "ACK"}])))
        self.assertIn("made 2 model calls, not one", reasons(streamcheck.node_shape(two, "ACK"))[0])
        errored = ack_stream(extra=[{"type": "result", "is_error": True, "session_id": "s-1"}])
        self.assertEqual(reasons(streamcheck.node_shape(errored, "ACK")), ["reported an error result"])
        broken = streams.read_stream(text_of(call_event("m1", [{"type": "text", "text": "ACK"}])) + "{not json\n")
        self.assertIn("line 2 is not a JSON object", reasons(streamcheck.node_shape(broken, "ACK"))[0])
        self.assertEqual(reasons(streamcheck.node_shape(streams.read_stream(""), "ACK")),
                         ["made 0 model calls, not one", "made no model call"])

    def test_one_call_split_over_records_is_one_call(self):
        # SOL-HW-REVIEW-KIT.C4: calls are counted by distinct message identifier
        split = streams.read_stream(text_of(call_event("m1", [{"type": "thinking", "thinking": ""}]),
                                            call_event("m1", [{"type": "text", "text": "ACK"}])))
        self.assertEqual(len(split.calls), 1)
        self.assertEqual(streamcheck.node_shape(split, "ACK"), [])


class CacheMiss(unittest.TestCase):
    def prefix(self, *names):
        return streams.lineage_written([probe(name) for name in names])

    def test_the_schema_flag_probe_is_flagged_with_both_figures(self):
        # SOL-HW-REVIEW-KIT.C4: the recorded probe in which the result-schema flag differed between root and fork is flagged
        miss = streamcheck.prefix_miss(probe("p2"), self.prefix("p1"))
        self.assertEqual(self.prefix("p1"), MANIFEST["probe_figures"]["p2"]["prefix_tokens_the_parent_wrote"])
        self.assertEqual(miss.check, "prefix-miss")
        self.assertEqual(miss.subject, probe("p2").session_id)
        self.assertIn("first call read 0 tokens from the cache, below the parent's prefix of 3261 tokens", miss.detail)

    def test_a_fork_that_reads_the_prefix_is_not_flagged(self):
        # SOL-HW-REVIEW-KIT.C4: a fork that reads the prefix is not flagged
        self.assertIsNone(streamcheck.prefix_miss(probe("p5"), self.prefix("p4")))
        self.assertIsNone(streamcheck.prefix_miss(probe("p3"), self.prefix("p1")))
        self.assertEqual(probe("p3").first_call_read, MANIFEST["probe_figures"]["p3"]["first_call_read"])

    def test_a_fork_of_a_fork_reads_the_prefix_both_wrote(self):
        # SOL-HW-REVIEW-KIT.C4: a fork whose first call's cache read is below the parent's prefix size is flagged
        whole = self.prefix("p4", "p6")
        self.assertEqual(whole, MANIFEST["probe_figures"]["p7"]["prefix_tokens_the_lineage_wrote"])
        self.assertIsNone(streamcheck.prefix_miss(probe("p7"), whole))
        flagged = streamcheck.prefix_miss(probe("p7"), whole + 1)
        self.assertIn(f"read {whole} tokens from the cache, below the parent's prefix of {whole + 1} tokens", flagged.detail)
        self.assertIn("1 tokens of it were written again", flagged.detail)

    def test_the_forks_of_the_live_validation_read_their_roots(self):
        # SOL-HW-REVIEW-KIT.C4: a fork that reads the prefix is not flagged
        validation = MANIFEST["validation"]
        for arm, root_file in validation["roots"].items():
            written = streams.lineage_written([recorded(root_file)])
            for name in validation["forks"][arm]:
                self.assertIsNone(streamcheck.prefix_miss(recorded(f"validation/{name}.jsonl"), written), name)

    def test_a_fork_with_no_reported_cache_read_is_flagged(self):
        # SOL-HW-REVIEW-KIT.C4: a fork whose first call's cache read is below the parent's prefix size is flagged
        silent = streams.read_stream("")
        self.assertIn("made no call that reports a cache read", streamcheck.prefix_miss(silent, 10).detail)
        no_usage = streams.read_stream(text_of({"type": "assistant", "message": {"id": "m", "content": []}}))
        self.assertIn("reports a cache read", streamcheck.prefix_miss(no_usage, 10).detail)


class SystemPrompt(unittest.TestCase):
    def named(self, **sessions):
        return dict(sessions)

    def test_the_probes_of_one_review_carry_one_system_prompt(self):
        # SOL-HW-REVIEW-KIT.C4: the streams of one review that carry different system prompts, or a fork whose system prompt differs from its parent's, are flagged
        review = {name: probe(name) for name in ("p1", "p2", "p3")}
        self.assertEqual(streamcheck.same_system(review, {"p2": "p1", "p3": "p1"}), [])

    def test_sessions_of_two_models_carry_different_prompts_and_are_flagged_by_name(self):
        # SOL-HW-REVIEW-KIT.C4: the streams of one review that carry different system prompts are flagged naming the sessions
        sonnet, haiku = recorded(MANIFEST["validation"]["roots"]["sonnet"]), recorded(MANIFEST["validation"]["roots"]["haiku"])
        found = streamcheck.same_system({"sonnet-root": sonnet, "haiku-root": haiku})
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].subject, "haiku-root")
        self.assertIn("differs from sonnet-root's", found[0].detail)
        self.assertIn("first differ at character", found[0].detail)

    def test_a_fork_whose_prompt_differs_from_its_parents_is_flagged(self):
        # SOL-HW-REVIEW-KIT.C4: a fork whose system prompt differs from its parent's is flagged naming the sessions
        parent, fork = probe("p4"), probe("p5")
        changed = copy.deepcopy(fork)
        changed.system = (*fork.system[:-1], fork.system[-1] + " Write nothing.")
        found = streamcheck.same_system({"root": parent, "fork": changed, "sibling": probe("p6")}, {"fork": "root", "sibling": "root"})
        self.assertEqual([flag.subject for flag in found], ["fork"])
        self.assertIn("differs from its parent root's", found[0].detail)
        self.assertEqual(streamcheck.same_system({"root": parent, "fork": fork}, {"fork": "root"}), [])

    def test_a_session_whose_record_holds_no_system_prompt_is_flagged(self):
        # SOL-HW-REVIEW-KIT.C4: the system prompt a session used is read from the transcript Claude Code writes for that session, because the start report carries none
        bare = streams.read_stream(text_of(call_event("m1", [{"type": "text", "text": "ACK"}])))
        self.assertIsNone(bare.system_prompt)
        found = streamcheck.same_system({"root": probe("p1"), "fork": bare}, {"fork": "root"})
        self.assertEqual([(flag.subject, "holds no system prompt" in flag.detail) for flag in found], [("fork", True)])

    def test_the_start_reports_of_the_earlier_runs_carry_the_setup_rule_and_are_rejected(self):
        # SOL-HW-REVIEW-KIT.C4: the recorded start reports of the earlier live runs, whose forks carried the setup session's rule, are fixtures the check rejects
        entry = MANIFEST["setup_rule"]
        setup, fork = recorded(entry["setup"]), recorded(entry["fork"])
        self.assertIn(entry["rule_marker"], setup.system_prompt)
        self.assertEqual(setup.system_prompt, fork.system_prompt)  # inherited, so the two agree with each other
        reviewer_rule = "Judge each item of the checklist you are given, and write your verdicts as the schema asks."
        found = streamcheck.same_system({"setup": setup, "fork": fork}, {"fork": "setup"}, appended=reviewer_rule)
        self.assertEqual([flag.subject for flag in found], ["setup", "fork"])
        for flag in found:
            self.assertIn("does not end with the appended prompt the specification names", flag.detail)
            self.assertIn("Judge nothing and open nothing", flag.detail)

    def test_a_prompt_that_ends_with_the_appended_prompt_passes(self):
        # SOL-HW-REVIEW-KIT.C4: the streams of one review all carry one system prompt
        reviewer_rule = "Judge each item of the checklist you are given."
        review = {}
        for name in ("p4", "p5", "p6"):
            stream = copy.deepcopy(probe(name))
            stream.system = (*stream.system, reviewer_rule)
            review[name] = stream
        self.assertEqual(streamcheck.same_system(review, {"p5": "p4", "p6": "p4"}, appended=reviewer_rule + "\n"), [])


class OpensInContext(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.entry = MANIFEST["layout_run"]
        cls.setup = recorded(cls.entry["setup"])
        cls.forks = {unit: recorded(f"layout_run/{unit}.jsonl") for unit in cls.entry["units"]}

    def test_the_layout_run_gives_the_count_the_fixture_states(self):
        # SOL-HW-REVIEW-KIT.C4: over the recorded layout run whose forks made 390 opens of 91 distinct view tiles, the count of opens of artefacts held in the prefix and of new opens is the count the fixture states
        stated = self.entry["image_opens"]
        opens = streamcheck.reopens_in_context(self.forks.values(), streams.held_names(self.setup), suffixes=(".png",))
        self.assertEqual({"total": opens.total, "held": opens.held, "new": opens.new, "failed": opens.failed,
                          "distinct": opens.distinct, "repeated": opens.repeated},
                         {"total": 390, "held": stated["held"], "new": stated["new"], "failed": stated["failed"],
                          "distinct": 91, "repeated": stated["repeated_within_a_fork"]})
        self.assertEqual(opens.total - opens.distinct, stated["opens_of_a_tile_another_fork_had_opened"])
        self.assertEqual(opens.total, opens.held + opens.new + opens.failed)

    def test_each_fork_gives_its_stated_count(self):
        # SOL-HW-REVIEW-KIT.C4: the count of opens of artefacts held in the prefix and of new opens
        for unit, stream in self.forks.items():
            self.assertEqual(streamcheck.reopens_in_context([stream], [], suffixes=(".png",)).total,
                             self.entry["image_opens_by_unit"][unit], unit)
        self.assertEqual(sum(self.entry["image_opens_by_unit"].values()), 390)

    def test_a_prefix_that_held_every_tile_makes_every_open_one_already_in_context(self):
        # SOL-HW-REVIEW-KIT.C4: the artefacts a unit opened that its prefix already held, against the ones that were new
        every = [name for name in streamcheck.reopens_in_context(self.forks.values(), [], suffixes=(".png",)).names]
        self.assertEqual(len(every), 91)
        opens = streamcheck.reopens_in_context(self.forks.values(), every, suffixes=(".png",))
        self.assertEqual((opens.held, opens.new, opens.failed), (389, 0, 1))
        half = streamcheck.reopens_in_context(self.forks.values(), every[:45], suffixes=(".png",))
        self.assertEqual((half.held + half.new, 0 < half.held < 389), (389, True))

    def test_the_prefix_documents_are_found_by_their_header_lines(self):
        # SOL-HW-REVIEW-KIT.C4: the artefacts a unit opened that its prefix already held
        held = streams.held_names(self.setup)
        for name in ("board-design-method.md", "round.json", "check-report.txt", "measures.txt", "separation-basis.yaml"):
            self.assertIn(name, held)
        text = [{"type": "text", "text": "intro\n=== image: net-_+5V-r2c1.png ===\n=== docs/a.md (section: x y) ===\nbody\n"}]
        self.assertEqual(streams.names_in_message(text), ["net-_+5V-r2c1.png", "a.md"])

    def test_a_failed_open_is_counted_as_failed_and_not_as_held_or_new(self):
        # SOL-HW-REVIEW-KIT.C4: the artefacts a unit opened, counted from the tool uses of its stream
        events = [call_event("m1", [{"type": "tool_use", "id": "t1", "name": "Read", "input": {"file_path": "views/a.png"}},
                                    {"type": "tool_use", "id": "t2", "name": "Read", "input": {"file_path": "views/ghost.png"}},
                                    {"type": "tool_use", "id": "t3", "name": "Grep", "input": {"pattern": "x"}},
                                    {"type": "tool_use", "id": "t4", "name": "Read", "input": {"file_path": "views/a.png"}}]),
                  {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "t2", "is_error": True,
                                                            "content": "no such file"}]}}]
        opens = streamcheck.reopens_in_context([streams.read_stream(text_of(*events))], ["a.png"])
        self.assertEqual(opens.as_dict(), {"total": 3, "held": 2, "new": 0, "repeated": 1, "failed": 1, "distinct": 2})
        by_path = streamcheck.reopens_in_context([streams.read_stream(text_of(*events))], [],
                                                 key=lambda path: path)
        self.assertEqual(by_path.names["views/a.png"], 2)

    def test_a_tile_opened_by_two_sessions_is_one_distinct_tile_and_not_a_repeat(self):
        # SOL-HW-REVIEW-KIT.C4: the opens of a review across its units
        use = [{"type": "tool_use", "id": "t1", "name": "Read", "input": {"file_path": "views/a.png"}}]
        two = [streams.read_stream(text_of(call_event("m1", use))) for _ in range(2)]
        opens = streamcheck.reopens_in_context(two, [])
        self.assertEqual((opens.total, opens.distinct, opens.repeated), (2, 1, 0))


class Citations(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.entry = MANIFEST["layout_run"]
        cls.setup = recorded(cls.entry["setup"])
        with open(os.path.join(FIXTURES, cls.entry["rows"]), encoding="utf-8") as handle:
            cls.rows = json.load(handle)

    def context(self, unit):
        stream = recorded(f"layout_run/{unit}.jsonl")
        return streams.held_names(self.setup), [opened.path for opened in stream.opens() if not opened.failed]

    def test_every_recorded_verdict_row_rests_on_a_view_its_unit_had(self):
        # SOL-HW-REVIEW-KIT.C4: a unit's citations of the view it rested on name only artefacts that its context held
        cited = 0
        for unit, rows in self.rows.items():
            held, opened = self.context(unit)
            cited += sum(len(streamcheck.cited_views(row.get("Rests on"))) for row in rows)
            self.assertEqual(streamcheck.rests_on_within_context(rows, held, opened, unit=unit), [], unit)
        self.assertGreater(cited, 40)

    def test_a_row_citing_a_view_neither_held_nor_opened_is_flagged_naming_the_row(self):
        # SOL-HW-REVIEW-KIT.C4: a recorded verdict row that cites a view neither in the unit's prefix nor opened by it is flagged naming the row
        held, opened = self.context("area-CLOCK")
        rows = copy.deepcopy(self.rows["area-CLOCK"])
        rows[1]["Rests on"] += "; and layer-In3.Cu-r9c9.png"
        found = streamcheck.rests_on_within_context(rows, held, opened, unit="area-CLOCK")
        self.assertEqual([(flag.subject, flag.check) for flag in found], [("area-CLOCK row CLOCK-2", "foreign-citation")])
        self.assertIn("cites layer-In3.Cu-r9c9.png, which neither the unit's prefix held nor the unit opened", found[0].detail)

    def test_a_view_opened_only_by_another_unit_is_foreign_to_this_one(self):
        # SOL-HW-REVIEW-KIT.C4: a unit's citations name only artefacts that its context held, from the prefix or from what it opened
        held, opened = self.context("area-CLOCK")
        mine = {streams.artefact_name(path) for path in opened}
        other = next(path for path in self.context("area-EMI")[1]
                     if path.endswith(".png") and streams.artefact_name(path) not in mine)
        rows = [{"Item": "CLOCK-9", "Rests on": f"{streams.artefact_name(other)} shows it"}]
        self.assertEqual(len(streamcheck.rests_on_within_context(rows, held, opened)), 1)
        self.assertEqual(streamcheck.rests_on_within_context(rows, held, opened + [other]), [])
        self.assertEqual(streamcheck.rests_on_within_context(rows, held + [streams.artefact_name(other)], opened), [])

    def test_a_view_the_unit_tried_to_open_and_could_not_is_not_one_it_had(self):
        # SOL-HW-REVIEW-KIT.C4: a unit's citations name only artefacts that its context held, from the prefix or from what it opened
        broken = [(unit, o.path) for unit in self.entry["units"] for o in recorded(f"layout_run/{unit}.jsonl").opens() if o.failed]
        self.assertEqual(broken, [("area-CLOCK", "views/placement-r1c2.png")])  # a path the run's tool reported missing
        events = [call_event("m1", [{"type": "tool_use", "id": "t1", "name": "Read", "input": {"file_path": "views/ghost.png"}}]),
                  {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "t1", "is_error": True, "content": "x"}]}}]
        stream = streams.read_stream(text_of(*events))
        opened = [o.path for o in stream.opens() if not o.failed]
        rows = [{"Item": "X-1", "Rests on": "ghost.png"}]
        self.assertEqual(opened, [])
        self.assertEqual(len(streamcheck.rests_on_within_context(rows, [], opened)), 1)

    def test_a_row_that_cannot_be_read_is_flagged_and_a_row_without_the_column_cites_nothing(self):
        # SOL-HW-REVIEW-KIT.C4: a recorded verdict row that cites a view neither in the unit's prefix nor opened by it is flagged naming the row
        found = streamcheck.rests_on_within_context(["text", {"Item": "A-1", "Rests on": 7}, {"Item": "A-2"}, {"Item": "A-3", "Rests on": ""}],
                                                    [], [])
        self.assertEqual([flag.subject for flag in found], ["row 1", "row A-1"])
        self.assertIn("is not an object", found[0].detail)
        self.assertIn("'Rests on' that is not text", found[1].detail)

    def test_a_citation_is_found_in_prose_and_by_name_only(self):
        # SOL-HW-REVIEW-KIT.C4: a unit's citations of the view it rested on name only artefacts that its context held
        cell = "crop-U4.png (board x 45.46 to 77.46 mm); layer-F.Cu-r1c2.png and net-_+5V-r2c1.png; layer-F.Cu-r1c2.png again, x 3.5 mm"
        self.assertEqual(streamcheck.cited_views(cell), ["crop-U4.png", "layer-F.Cu-r1c2.png", "net-_+5V-r2c1.png"])
        self.assertEqual(streamcheck.cited_views(None), [])
        rows = [{"Item": "Z-1", "Rests on": cell}]
        self.assertEqual(streamcheck.rests_on_within_context(rows, ["views/crop-U4.png"], ["/x/layer-F.Cu-r1c2.png", "net-_+5V-r2c1.png"]), [])


class Reading(unittest.TestCase):
    def test_the_system_prompt_is_read_from_the_transcript_found_by_the_session_identifier(self):
        # SOL-HW-REVIEW-KIT.C4: the system prompt a session used is read from the transcript Claude Code writes for that session, found by the session's identifier
        shape = {"type": "api-request-shape", "sessionId": "abc-123", "shapeHash": "h",
                 "shape": {"system": [{"type": "text", "text": "one"}, {"type": "text", "text": "two"}], "tools": ["Read", {"name": "Grep"}]}}
        with tempfile.TemporaryDirectory() as projects:
            os.makedirs(os.path.join(projects, "-a-working-directory"))
            path = os.path.join(projects, "-a-working-directory", "abc-123.jsonl")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(text_of({"type": "user", "message": {"content": "hi"}}, shape))
            self.assertEqual(transcripts.find_transcript("abc-123", None, projects), path)
            for absent in ("abc-124", "../abc-123", ""):
                with self.assertRaises(transcripts.TranscriptMissing):
                    transcripts.find_transcript(absent, None, projects)
            self.assertEqual(transcripts.shape_record(path)["shapeHash"], "h")
            read = streams.read_stream_file(path)
        self.assertEqual((read.system, read.tools, read.shape_hash, read.session_id), (("one", "two"), ("Read", "Grep"), "h", "abc-123"))
        self.assertEqual(read.system_prompt, "one\n\ntwo")

    def test_a_transcript_without_a_shape_record_gives_none(self):
        # SOL-HW-REVIEW-KIT.C4: the system prompt a session used is read from the transcript
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "t.jsonl")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(text_of({"type": "user", "message": {"content": "hi"}}))
            self.assertIsNone(transcripts.shape_record(path))

    def test_the_recorded_sessions_read_back_the_figures_they_were_made_from(self):
        # SOL-HW-REVIEW-KIT.C4: calls are counted by distinct message identifier
        stream = recorded("validation/sonnet-FULL-area-EMI.jsonl")
        self.assertEqual(len(stream.calls), 1)
        self.assertEqual([block["type"] for block in stream.calls[0].blocks], ["thinking", "text"])
        self.assertEqual(stream.start["model"], "claude-sonnet-5-5")
        self.assertEqual(stream.result["num_turns"], 1)
        self.assertEqual(stream.malformed, [])
        self.assertTrue(stream.system_prompt.startswith("You are a Claude agent"))

    def test_a_user_message_given_as_a_string_is_kept_and_a_record_without_content_is_listed(self):
        # SOL-HW-REVIEW-KIT.C4: a recorded session is read without defaulting what it does not show
        stream = streams.read_stream(text_of({"type": "user", "message": {"content": "=== a.md ===\nbody"}},
                                             {"type": "assistant", "message": {"id": "m"}},
                                             {"type": "user", "message": {}}, [1], {"no": "type"}))
        self.assertEqual(streams.held_names(stream), ["a.md"])
        self.assertEqual(len(stream.malformed), 4)

    def test_the_artefact_name_is_the_last_path_component(self):
        # SOL-HW-REVIEW-KIT.C4: artefacts are told apart by name whatever the folder they were opened from
        self.assertEqual(streams.artefact_name("/a/b/views/x.png"), "x.png")
        self.assertEqual(streams.artefact_name("views\\x.png"), "x.png")
        self.assertEqual(streams.artefact_name("x.png"), "x.png")


if __name__ == "__main__":
    unittest.main()
