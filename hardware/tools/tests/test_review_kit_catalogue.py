#!/usr/bin/env python3
"""The review kit's catalogue: admission of a declaration's artefacts against a review folder, and their measures.

Synthetic review folders in temporary directories; no session is started and none could be.
"""

from __future__ import annotations

import hashlib
import json
import os
import struct
import sys
import tempfile
import unittest

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import review_kit_fixtures as fx  # noqa: E402
from review_kit import catalogue, decl  # noqa: E402


def declared(**changes):
    return decl.parse(json.dumps(fx.declaration_dict(**changes)), "caller.json")


def rule_of(refused, artefact):
    return [r.rule for r in refused.exception.refusals if r.artefact == artefact]


class AdmissionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.review = fx.review_folder(os.path.join(self.tmp.name, "review"))
        self.out = os.path.join(self.tmp.name, "out")
        os.makedirs(self.out)

    def with_artefact(self, name, **entry):
        raw = fx.declaration_dict()
        raw["artefacts"][name] = entry
        raw["units"]["u4"]["needs"].append(name)
        return decl.parse(json.dumps(raw), "caller.json")

    def test_clean_folder_is_admitted_in_name_order(self):
        # SOL-HW-REVIEW-KIT.C5: every artefact lies inside the review folder, none matches the deny list, and no result of another unit is among them
        found = catalogue.admit(declared(), self.review, results_folder=self.out)
        self.assertEqual([a.name for a in found.artefacts], ["facts.txt", "guide.md", "view_a.png", "view_b.png"])

    def test_source_outside_the_folder_is_refused_naming_artefact_and_rule(self):
        # SOL-HW-REVIEW-KIT.C5: an artefact whose source lies outside the folder is refused naming the artefact and the rule
        fx.write(self.tmp.name, "secret.md", "outside")
        for source in ("../secret.md", os.path.join(self.tmp.name, "secret.md")):
            with self.subTest(source=source):
                with self.assertRaises(catalogue.Refused) as refused:
                    catalogue.admit(self.with_artefact("note.md", kind="text", source=source), self.review)
                line = refused.exception.refusals[0].line()
                self.assertEqual(rule_of(refused, "note.md"), [catalogue.OUTSIDE])
                self.assertIn("artefact note.md", line)
                self.assertIn(repr(catalogue.OUTSIDE), line)

    def test_link_out_of_the_folder_is_refused(self):
        # SOL-HW-REVIEW-KIT.C5: an artefact whose source lies outside the folder is refused naming the artefact and the rule
        target = fx.write(self.tmp.name, "elsewhere.md", "outside")
        os.symlink(target, os.path.join(self.review, "docs", "link.md"))
        with self.assertRaises(catalogue.Refused) as refused:
            catalogue.admit(self.with_artefact("note.md", kind="text", source="docs/link.md"), self.review)
        self.assertEqual(rule_of(refused, "note.md"), [catalogue.OUTSIDE])

    def test_deny_list_refuses_by_path_and_by_name(self):
        # SOL-HW-REVIEW-KIT.C5: an artefact matching the deny list is refused naming the artefact and the rule
        fx.write(self.review, "docs/seed-list.md", "seeds")
        fx.write(self.review, "private/notes.md", "notes")
        for name, source, pattern in (("seeds.md", "docs/seed-list.md", "*seed*"), ("notes.md", "private/notes.md", "private/*")):
            with self.subTest(name=name):
                with self.assertRaises(catalogue.Refused) as refused:
                    catalogue.admit(self.with_artefact(name, kind="text", source=source), self.review)
                self.assertEqual(rule_of(refused, name), [catalogue.DENIED])
                self.assertIn(pattern, refused.exception.refusals[0].detail)

    def test_result_of_another_unit_is_refused(self):
        # SOL-HW-REVIEW-KIT.C5: a result of another unit of this round among the artefacts is refused naming the artefact and the rule
        fx.write(self.out, "results/u1.json", "{}")
        raw = fx.declaration_dict()
        raw["artefacts"]["prior.json"] = {"kind": "text", "source": "../out/results/u1.json"}
        raw["units"]["u4"]["needs"].append("prior.json")
        with self.assertRaises(catalogue.Refused) as refused:
            catalogue.admit(decl.parse(json.dumps(raw), "caller.json"), self.review, results_folder=self.out)
        self.assertEqual(rule_of(refused, "prior.json"), [catalogue.RESULT])
        self.assertIn("results folder", refused.exception.refusals[0].detail)

    def test_every_refusal_is_listed_and_artefacts_no_unit_needs_are_ignored(self):
        # SOL-HW-REVIEW-KIT.C5: a refusal names the artefact and the rule, and nothing is started
        raw = fx.declaration_dict()
        raw["artefacts"]["escape.md"] = {"kind": "text", "source": "../x.md"}
        raw["artefacts"]["unused.md"] = {"kind": "text", "source": "../y.md"}
        raw["units"]["u4"]["needs"].append("escape.md")
        raw["artefacts"]["gone.md"] = {"kind": "text", "source": "docs/gone.md"}
        raw["units"]["u4"]["needs"].append("gone.md")
        with self.assertRaises(catalogue.Refused) as refused:
            catalogue.admit(decl.parse(json.dumps(raw), "caller.json"), self.review)
        self.assertEqual(sorted(r.artefact for r in refused.exception.refusals), ["escape.md", "gone.md"])

    def test_missing_extract_names_its_producer(self):
        # SOL-HW-REVIEW-KIT.C5: an artefact has a kind, a source inside the review folder and, for an extract, a producer
        os.unlink(os.path.join(self.review, "extracts", "facts.txt"))
        with self.assertRaises(catalogue.Refused) as refused:
            catalogue.admit(declared(), self.review)
        self.assertEqual(rule_of(refused, "facts.txt"), [catalogue.UNREADABLE])
        self.assertIn("'make_facts'", refused.exception.refusals[0].detail)

    def test_wrong_content_for_the_kind_is_refused(self):
        # SOL-HW-REVIEW-KIT.C5: an image is measured by the patch formula, so bytes that are not an image are refused
        fx.write(self.review, "views/view_a.png", b"not an image")
        fx.write(self.review, "docs/guide.md", b"\xff\xfe binary")
        with self.assertRaises(catalogue.Refused) as refused:
            catalogue.admit(declared(), self.review)
        self.assertEqual(rule_of(refused, "view_a.png"), [catalogue.NOT_IMAGE])
        self.assertEqual(rule_of(refused, "guide.md"), [catalogue.NOT_TEXT])


class MeasureTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.review = fx.review_folder(os.path.join(self.tmp.name, "review"), guide="word " * 100)

    def test_text_is_measured_by_length_as_a_bound_and_hashed(self):
        # SOL-HW-REVIEW-KIT.C5: a text is measured by its length as an upper bound and given its content hash
        found = catalogue.admit(declared(), self.review).get("guide.md")
        self.assertEqual((found.tokens, found.bound), (500, True))
        self.assertEqual(found.sha256, hashlib.sha256(("word " * 100).encode()).hexdigest())

    def test_recorded_token_count_is_used_when_given(self):
        # SOL-HW-REVIEW-KIT.C5: a text is measured by its token count when one is recorded
        raw = fx.declaration_dict()
        raw["artefacts"]["guide.md"]["tokens"] = 123
        found = catalogue.admit(decl.parse(json.dumps(raw), "caller.json"), self.review).get("guide.md")
        self.assertEqual((found.tokens, found.bound), (123, False))

    def test_image_is_measured_by_the_patch_formula(self):
        # SOL-HW-REVIEW-KIT.C5: an image is measured by the patch formula
        found = catalogue.admit(declared(), self.review)
        # 300 x 200 pixels: 11 x 8 patches of 28 pixels, with the 4 per cent allowance
        self.assertEqual(found.get("view_a.png").tokens, 92)
        self.assertEqual(found.get("view_a.png").size, (300, 200))
        self.assertEqual(found.get("view_b.png").tokens, 208)  # 20 x 10 patches
        self.assertEqual(found.get("view_a.png").media_type, "image/png")
        self.assertEqual(found.get("view_a.png").sha256, hashlib.sha256(fx.png(300, 200, 10)).hexdigest())

    def test_a_change_to_one_artefact_changes_its_hash_only(self):
        # SOL-HW-REVIEW-KIT.C5: each artefact is given its content hash
        before = catalogue.admit(declared(), self.review)
        fx.write(self.review, "views/view_b.png", png_other())
        after = catalogue.admit(declared(), self.review)
        changed = [a.name for a, b in zip(before.artefacts, after.artefacts) if a.sha256 != b.sha256]
        self.assertEqual(changed, ["view_b.png"])

    def test_image_sizes_are_read_from_png_and_jpeg_headers(self):
        # SOL-HW-REVIEW-KIT.C5: an image is measured by the patch formula
        self.assertEqual(catalogue.image_size(fx.png(7, 9)), ("image/png", 7, 9))
        jpeg = (b"\xff\xd8" + b"\xff\xe0" + struct.pack(">H", 16) + b"JFIF\0" + b"\0" * 9
                + b"\xff\xc0" + struct.pack(">HBHHB", 11, 8, 40, 60, 3) + b"\0" * 20)
        self.assertEqual(catalogue.image_size(jpeg), ("image/jpeg", 60, 40))
        for junk in (b"", b"\x89PNG", b"\xff\xd8", b"GIF89a", b"\xff\xd8\x00\x00" + b"\0" * 20):
            self.assertIsNone(catalogue.image_size(junk))
        self.assertEqual(catalogue.image_tokens(28, 28), 2)  # one patch, 1.04 rounded up
        self.assertEqual(catalogue.image_tokens(29, 28), 3)  # two patches


def png_other():
    return fx.png(560, 280, 99)


if __name__ == "__main__":
    unittest.main()
