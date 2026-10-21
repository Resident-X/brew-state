#!/usr/bin/env python3
"""The review kit's shared-context message: its blocks, its determinism, its hash and its measured size.

Synthetic review folders in temporary directories; the message is built and read back, never sent.
"""

from __future__ import annotations

import base64
import json
import os
import sys
import tempfile
import unittest

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import review_kit_fixtures as fx  # noqa: E402
from review_kit import catalogue, decl, messages, streams  # noqa: E402

BIG_GUIDE = "A line of guidance that the sessions share. " * 500


def build(folder, raw=None):
    declaration = decl.parse(json.dumps(raw or fx.declaration_dict()), "caller.json")
    return declaration, messages.shared_context(catalogue.admit(declaration, folder))


def blocks_of(shared):
    return json.loads(shared.message)["message"]["content"]


class SharedContextTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.review = fx.review_folder(os.path.join(self.tmp.name, "review"), guide=BIG_GUIDE)

    def test_message_is_one_user_message_of_text_and_image_blocks_in_name_order(self):
        # SOL-HW-REVIEW-KIT.C5: the shared context holds every artefact any unit needs, in a fixed order, as text and image blocks in one message
        _, shared = build(self.review)
        message = json.loads(shared.message)
        self.assertEqual((message["type"], message["message"]["role"]), ("user", "user"))
        self.assertNotIn("\n", shared.message)
        kinds = [(b["type"], b["text"].split("\n")[0] if b["type"] == "text" else b["source"]["media_type"]) for b in blocks_of(shared)]
        self.assertEqual(kinds[0][0], "text")
        self.assertEqual(kinds[1:-1], [("text", "=== facts.txt ==="), ("text", "=== guide.md ==="),
                                       ("text", "=== image: view_a.png ==="), ("image", "image/png"),
                                       ("text", "=== image: view_b.png ==="), ("image", "image/png")])
        self.assertEqual(blocks_of(shared)[-1]["text"], messages.ENDING)
        self.assertEqual([name for name, _ in shared.blocks], ["facts.txt", "guide.md", "view_a.png", "view_b.png"])

    def test_image_blocks_carry_the_file_bytes_as_base64(self):
        # SOL-HW-REVIEW-KIT.C5: the shared context holds the image artefacts as image blocks
        _, shared = build(self.review)
        images = [b for b in blocks_of(shared) if b["type"] == "image"]
        self.assertEqual(images[0]["source"]["type"], "base64")
        self.assertEqual(base64.b64decode(images[0]["source"]["data"]), fx.png(300, 200, 10))

    def test_message_holds_no_unit_prompt_and_asks_for_no_tool_use(self):
        # SOL-HW-REVIEW-KIT.C5: the shared context holds no unit's prompt and asks for no tool use
        declaration, shared = build(self.review)
        for unit in declaration.units:
            self.assertNotIn(messages.unit_prompt(declaration, unit), shared.message)
        text = " ".join(b["text"] for b in blocks_of(shared) if b["type"] == "text" and not b["text"].startswith("==="))
        for item in ("i1", "j1", "k1", "m1"):
            self.assertNotIn(f"- {item}", shared.message)
        self.assertIn("do not use a tool", text)
        self.assertEqual(set(json.loads(shared.message)), {"type", "message"})
        self.assertEqual(set(json.loads(shared.message)["message"]), {"role", "content"})
        self.assertEqual(messages.ACK, "ACK")
        self.assertIn("answer only ACK", messages.ENDING)

    def test_two_builds_are_byte_identical_with_the_same_prefix_hash(self):
        # SOL-HW-REVIEW-KIT.C5: the same declaration and review folder give byte-identical bytes and the same prefix hash
        _, first = build(self.review)
        _, second = build(self.review)
        self.assertEqual(first.message.encode("utf-8"), second.message.encode("utf-8"))
        self.assertEqual(first.prefix_sha, second.prefix_sha)
        self.assertEqual(first.prefix_sha, messages.sha256(first.message))

    def test_declaration_order_does_not_change_the_bytes(self):
        # SOL-HW-REVIEW-KIT.C5: the shared context holds every artefact in a fixed order
        raw = fx.declaration_dict()
        raw["artefacts"] = dict(reversed(list(raw["artefacts"].items())))
        _, reordered = build(self.review, raw)
        _, first = build(self.review)
        self.assertEqual(first.message, reordered.message)

    def test_changing_one_artefact_changes_its_block_and_the_prefix_hash(self):
        # SOL-HW-REVIEW-KIT.C5: changing one artefact changes its block and the prefix hash
        _, before = build(self.review)
        fx.write(self.review, "extracts/facts.txt", "fact one changed\n")
        _, after = build(self.review)
        self.assertNotEqual(before.prefix_sha, after.prefix_sha)
        differing = [a[0] for a, b in zip(before.blocks, after.blocks) if a != b]
        self.assertEqual(differing, ["facts.txt"])
        old, new = blocks_of(before), blocks_of(after)
        self.assertEqual([i for i, (a, b) in enumerate(zip(old, new)) if a != b], [1])

    def test_an_artefact_no_unit_needs_is_not_in_the_message(self):
        # SOL-HW-REVIEW-KIT.C5: the shared context holds every artefact any unit needs
        raw = fx.declaration_dict()
        raw["artefacts"]["spare.md"] = {"kind": "text", "source": "docs/spare.md"}
        fx.write(self.review, "docs/spare.md", "spare text")
        _, shared = build(self.review, raw)
        self.assertNotIn("spare", shared.message)

    def test_measured_size_is_within_five_per_cent_of_the_artefacts(self):
        # SOL-HW-REVIEW-KIT.C5: the shared context's measured size is within five per cent of the sum of the artefacts' measured sizes
        declaration = decl.parse(json.dumps(fx.declaration_dict()), "caller.json")
        found = catalogue.admit(declaration, self.review)
        shared = messages.shared_context(found)
        total = sum(a.tokens for a in found.artefacts)
        self.assertGreater(total, 20000)
        self.assertLessEqual(abs(shared.tokens - total) / total, 0.05)
        self.assertEqual(shared.tokens, total + shared.framing_tokens)
        # re-measured from the message's own blocks, not from the catalogue
        self.assertEqual(messages.measured_size(shared.message), shared.tokens)

    def test_recorded_counts_are_what_the_size_is_summed_from(self):
        # SOL-HW-REVIEW-KIT.C5: a text is measured by its token count when one is recorded
        raw = fx.declaration_dict()
        raw["artefacts"]["guide.md"]["tokens"] = 5000
        declaration = decl.parse(json.dumps(raw), "caller.json")
        found = catalogue.admit(declaration, self.review)
        shared = messages.shared_context(found)
        self.assertEqual(found.get("guide.md").tokens, 5000)
        self.assertEqual(shared.tokens, found.tokens + shared.framing_tokens)

    def test_text_is_carried_exactly_including_non_ascii(self):
        # SOL-HW-REVIEW-KIT.C5: byte-identical bytes
        fx.write(self.review, "docs/guide.md", "Spannung 230 V ± 10 %\n  line\n")
        _, shared = build(self.review)
        block = [b for b in blocks_of(shared) if b["type"] == "text" and b["text"].startswith("=== guide.md ===")][0]
        self.assertEqual(block["text"], "=== guide.md ===\nSpannung 230 V ± 10 %\n  line\n")

    def test_unit_message_and_spec_use_the_shared_schema(self):
        # SOL-HW-REVIEW-KIT.C5: the schema given to the sessions is derived from the declared tables
        declaration, _ = build(self.review)
        spec = messages.make_spec(declaration, ("Read",), "/work", "claude-sonnet-5-5")
        self.assertEqual(spec.json_schema, declaration.json_schema())
        again = messages.make_spec(declaration, ("Read",), "/work", "claude-sonnet-5-5")
        self.assertEqual(spec.digest, again.digest)
        prompt = json.loads(messages.prompt_message("hello"))
        self.assertEqual(prompt["message"]["content"], [{"type": "text", "text": "hello"}])

    def test_context_is_the_form_the_stream_checks_read(self):
        # SOL-HW-REVIEW-KIT.C5: the header lines name each artefact as the stream reduction recognises them
        _, shared = build(self.review)
        names = [m.group("name") for b in blocks_of(shared) if b["type"] == "text" for m in streams.HEADER.finditer(b["text"])]
        self.assertEqual(names, ["facts.txt", "guide.md", "view_a.png", "view_b.png"])


if __name__ == "__main__":
    unittest.main()
