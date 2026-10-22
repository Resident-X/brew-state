#!/usr/bin/env python3
"""The key the recorded layout and production-files review baselines hold as the design, driven on throwaway git repositories.

Each review's baseline is keyed over the files that review reads of the proof
design, by one helper given the list, and not over the git tree of the design's
whole folder. What is under test is that a change to a file the review does not
read, such as the catalogue extract or a record the pre-order check alone reads,
leaves the key as it was, that a change to a file it reads moves it, that the
key does not depend on the order files are listed in, and that the stored keys
are the ones the files give. No KiCad, resvg or model is involved.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import tempfile
import unittest

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)

import board_prove  # noqa: E402
import layout_review_proof as lrp  # noqa: E402
import production_files_review_proof as pfp  # noqa: E402
import production_seed  # noqa: E402
import review_seed  # noqa: E402
from review_kit import proof  # noqa: E402

REPO = os.path.dirname(os.path.dirname(TOOLS))
DESIGN = review_seed.DESIGN
BASELINES = os.path.join(TOOLS, "tests", "fixtures", "review_baselines")


class Repository(unittest.TestCase):
    """A throwaway git repository holding the committed proof design's files, which a test edits and commits again."""

    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory(prefix="baseline-key-")
        self.addCleanup(self.scratch.cleanup)
        self.root = self.scratch.name
        subprocess.run(["git", "init", "-q", self.root], check=True)
        held = board_prove.committed(DESIGN)
        self.assertIsNotNone(held, "git holds the proof design")
        for path, content in held.items():
            self.put(path, content)
        self.commit()

    def put(self, path: str, content) -> None:
        full = os.path.join(self.root, path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "wb") as handle:
            handle.write(content if isinstance(content, bytes) else content.encode())

    def edit(self, name: str, text: str = "\n# edited\n") -> None:
        """Append `text` to the design's file `name` and commit."""
        path = os.path.join(self.root, DESIGN, name)
        with open(path, "ab") as handle:
            handle.write(text.encode())
        self.commit()

    def commit(self) -> None:
        subprocess.run(["git", "-C", self.root, "add", "-A"], check=True)
        subprocess.run(["git", "-C", self.root, "-c", "user.email=a@b", "-c", "user.name=n", "commit", "-q", "--allow-empty",
                        "-m", "edit"], check=True)

    def keys(self):
        return lrp.design_key(self.root, "HEAD", DESIGN), pfp.design_key(self.root, "HEAD", DESIGN)


class TheKeyIsOverTheFilesTheReviewReads(Repository):
    def test_a_change_to_a_file_the_review_does_not_read_leaves_both_keys_as_they_were(self):
        # SOL-PRE-ORDER-CHECK-DATED-RECORDS-MINIMUMS-AND-LIFECYCLE.C8: a change to a file the review does not read, such as the catalogue extract or a record the check alone reads, leaves every recorded baseline valid
        before = self.keys()
        for name in ("catalogue-extract.yaml", "board-rules.yaml", "pin-limits.yaml", "derating-policy.yaml", "pin-allocation.yaml",
                     "layout-review.md"):
            with self.subTest(name=name):
                self.edit(name)
                self.assertEqual(self.keys(), before)
        self.put(os.path.join(DESIGN, "manufacturer-limits.yaml"), "synthetic: true\n")
        self.put(os.path.join(os.path.dirname(DESIGN), "manufacturer-limits.yaml"), "synthetic: true\n")
        self.commit()
        self.assertEqual(self.keys(), before, "a record added beside the design, or above it, is no file the review reads")

    def test_a_change_to_a_file_the_layout_review_reads_moves_its_key_and_a_production_only_change_does_not(self):
        # SOL-PRE-ORDER-CHECK-DATED-RECORDS-MINIMUMS-AND-LIFECYCLE.C8: the layout review's key is over the design files its seeding gives a reviewer (KiCad files, library tables and its named records); a change to a file it reads changes the key
        layout, production = self.keys()
        for name in ("layout-plan.md", "design-rules.md", "constraints.md", "separation-basis.yaml"):
            with self.subTest(name=name):
                self.edit(name)
                moved, same = self.keys()
                self.assertNotEqual(moved, layout)
                self.assertEqual(same, production, "the production-files review reads none of the layout review's records")
                layout = moved

    def test_a_change_to_the_parts_specification_moves_only_the_production_files_key(self):
        # SOL-PRE-ORDER-CHECK-DATED-RECORDS-MINIMUMS-AND-LIFECYCLE.C8: the production-files review's key is over the design's KiCad files and library tables and its parts specification record
        layout, production = self.keys()
        self.edit("parts-specification.yaml")
        moved_layout, moved_production = self.keys()
        self.assertEqual(moved_layout, layout)
        self.assertNotEqual(moved_production, production)

    def test_a_change_to_a_kicad_file_or_a_library_table_moves_both_keys(self):
        # SOL-PRE-ORDER-CHECK-DATED-RECORDS-MINIMUMS-AND-LIFECYCLE.C8: each review's key over its own read list; a change to a file it reads changes the key
        for name in ("review-proof.kicad_pcb", "review-proof.kicad_sch", "review-proof.kicad_pro", "review-proof.kicad_dru",
                     "fp-lib-table", "review-proof.pretty/QFN-20-1EP_4x4mm_P0.5mm_EP2.6x2.6mm.kicad_mod"):
            with self.subTest(name=name):
                before = self.keys()
                self.edit(name, "\n")
                after = self.keys()
                self.assertNotEqual(after[0], before[0])
                self.assertNotEqual(after[1], before[1])

    def test_a_file_the_review_reads_added_or_removed_moves_the_key(self):
        # SOL-PRE-ORDER-CHECK-DATED-RECORDS-MINIMUMS-AND-LIFECYCLE.C8: a change to a file it reads changes the key
        before = self.keys()
        self.put(os.path.join(DESIGN, "sym-lib-table"), "(sym_lib_table)\n")
        self.commit()
        added = self.keys()
        self.assertNotEqual(added[0], before[0])
        self.assertNotEqual(added[1], before[1])
        os.remove(os.path.join(self.root, DESIGN, "sym-lib-table"))
        self.commit()
        self.assertEqual(self.keys(), before, "taking the file away again restores the key")
        os.remove(os.path.join(self.root, DESIGN, "layout-plan.md"))
        self.commit()
        self.assertNotEqual(lrp.design_key(self.root, "HEAD", DESIGN), before[0])

    def test_the_key_depends_on_what_the_files_hold_and_where_and_not_on_the_order_they_are_listed_in(self):
        # SOL-PRE-ORDER-CHECK-DATED-RECORDS-MINIMUMS-AND-LIFECYCLE.C8: computed by one helper given the list
        files = {"b/two": b"2", "a": b"1", "c": b"3"}
        self.assertEqual(review_seed.key_of(files), review_seed.key_of(dict(sorted(files.items(), reverse=True))))
        self.assertNotEqual(review_seed.key_of(files), review_seed.key_of(dict(files, a=b"9")))
        self.assertNotEqual(review_seed.key_of({"a": b"1"}), review_seed.key_of({"b": b"1"}), "the path is part of the key")
        self.assertNotEqual(review_seed.key_of({"a": b"1", "b": b""}), review_seed.key_of({"a": b"1"}), "an empty file is a file")

    def test_the_key_is_the_hash_of_the_sorted_path_and_content_hash_lines_pinned_here(self):
        # SOL-PRE-ORDER-CHECK-DATED-RECORDS-MINIMUMS-AND-LIFECYCLE.C8: one helper given the list, a hash over the sorted (path, hash of content) pairs
        files = {"b/two": b"2", "a": b"1"}
        lines = "".join(f"{name}\0{hashlib.sha256(files[name]).hexdigest()}\n" for name in ("a", "b/two"))
        self.assertEqual(review_seed.key_of(files), hashlib.sha256(lines.encode()).hexdigest())
        self.assertEqual(review_seed.key_of(files), "003fd7f7f46ddc42278a43bea5b92d7a094f4683427b2e1db831ec06b959a46e")

    def test_each_review_hands_its_own_list_to_the_one_helper(self):
        # SOL-PRE-ORDER-CHECK-DATED-RECORDS-MINIMUMS-AND-LIFECYCLE.C8: each review's key being over its own read list ... computed by one helper given the list
        layout = review_seed.design_files(self.root, "HEAD", DESIGN, review_seed.given)
        production = review_seed.design_files(self.root, "HEAD", DESIGN, production_seed.reads)
        self.assertEqual(sorted(layout), ["constraints.md", "design-rules.md", "fp-lib-table", "layout-plan.md", "review-proof.kicad_dru",
                                          "review-proof.kicad_pcb", "review-proof.kicad_pro", "review-proof.kicad_sch",
                                          "review-proof.pretty/QFN-20-1EP_4x4mm_P0.5mm_EP2.6x2.6mm.kicad_mod", "separation-basis.yaml"])
        self.assertEqual(sorted(production), ["fp-lib-table", "parts-specification.yaml", "review-proof.kicad_dru",
                                              "review-proof.kicad_pcb", "review-proof.kicad_pro", "review-proof.kicad_sch",
                                              "review-proof.pretty/QFN-20-1EP_4x4mm_P0.5mm_EP2.6x2.6mm.kicad_mod"])
        self.assertEqual(lrp.design_key(self.root, "HEAD", DESIGN), review_seed.key_of(layout))
        self.assertEqual(pfp.design_key(self.root, "HEAD", DESIGN), review_seed.key_of(production))

    def test_a_design_holding_none_of_the_files_a_review_reads_is_refused(self):
        # SOL-PRE-ORDER-CHECK-DATED-RECORDS-MINIMUMS-AND-LIFECYCLE.C8: a key over no files would stand for no design at all
        with self.assertRaises(lrp.Refused) as raised:
            lrp.design_key(self.root, "HEAD", "hardware/proof/no-such-design")
        self.assertIn("cannot be read", str(raised.exception))
        with self.assertRaises(pfp.Refused):
            pfp.design_key(self.root, "HEAD", "hardware/proof/no-such-design")
        with self.assertRaises(lrp.Refused):
            lrp.design_key(self.root, "no-such-commit", DESIGN)


class TheStoredKeysAreTheOnesTheFilesGive(unittest.TestCase):
    def stored(self, name: str):
        loaded = proof.load_baselines(os.path.join(BASELINES, name))
        return [key.design for key in loaded.keys.values()]

    def test_the_recorded_layout_and_production_files_baselines_hold_the_keys_the_committed_files_give(self):
        # SOL-PRE-ORDER-CHECK-DATED-RECORDS-MINIMUMS-AND-LIFECYCLE.C8: The stored keys are rewritten to the hash of those files as the tree the stored key names holds them, so no run is repeated
        self.assertEqual(self.stored("layout_single_runs.json"), [lrp.design_key()])
        self.assertEqual(self.stored("production_files_single_runs.json"), [pfp.design_key()])

    def test_the_stored_keys_are_no_longer_a_git_tree_id(self):
        # SOL-PRE-ORDER-CHECK-DATED-RECORDS-MINIMUMS-AND-LIFECYCLE.C8: keyed on the files the review reads, and not on the git tree of the whole design folder
        tree = subprocess.run(["git", "-C", REPO, "rev-parse", f"HEAD:{DESIGN}"], capture_output=True, text=True).stdout.strip()
        for name in ("layout_single_runs.json", "production_files_single_runs.json"):
            self.assertNotIn(tree, self.stored(name))
        self.assertNotEqual(lrp.design_key(), pfp.design_key(), "each review keys over its own list")


if __name__ == "__main__":
    unittest.main()
