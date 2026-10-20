#!/usr/bin/env python3
"""The review folder command, and the seeding command's generalised copy, over synthetic repositories.

The command is run as shipped against a temporary git repository holding a synthetic board. No KiCad and no model is
used, and no real design or specification is named.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import board_prove  # noqa: E402
import layout_fixtures as fx  # noqa: E402
import review_folder  # noqa: E402
import review_seed  # noqa: E402

REPO = os.path.dirname(os.path.dirname(TOOLS))
EXPECTED = {
    "check-report.txt", "round.json", "docs/board-design-method.md", "hardware/README.md", "views/index.txt", "views/facts.txt",
    "views/layer-F.Cu.png", "placement/index.txt", "placement/measures.txt",
    *(f"{fx.DESIGN}/{name}" for name in ("board.kicad_pro", "board.kicad_pcb", "board.kicad_sch", "board.kicad_dru", "fp-lib-table",
                                          "board.pretty/part.kicad_mod", "layout-plan.md", "design-rules.md", "constraints.md",
                                          "separation-basis.yaml"))}


def files_under(folder):
    return {os.path.relpath(os.path.join(directory, name), folder) for directory, _, names in os.walk(folder) for name in names}


class Case(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="review-folder-test-")
        self.addCleanup(shutil.rmtree, self.root, True)
        self.repo = fx.make_repo(self.root)
        self.inputs = fx.make_views(self.root)
        self.out = os.path.join(self.root, "review")

    def run_with(self, *extra, number=1, kind="full", out=None, repo=None, drop=()):
        argv = fx.folder_argv(repo or self.repo, out or self.out, self.inputs, number, kind, extra=extra)
        for flag in drop:
            while flag in argv:
                at = argv.index(flag)
                del argv[at:at + 2]
        return fx.run_folder(argv)

    def read(self, *path):
        with open(os.path.join(self.out, *path), encoding="utf-8") as handle:
            return handle.read()

    def refused(self, *words, **how):
        status, text = self.run_with(**how)
        self.assertEqual(status, 1, text)
        self.assertEqual(text.splitlines()[-1], "RESULT | REFUSED | nothing was written")
        for word in words:
            self.assertIn(word, text)
        self.assertFalse(os.path.exists(how.get("out") or self.out), "a refused command writes nothing")
        return text


class TheFolder(Case):
    def test_the_folder_holds_what_the_review_step_gives_a_reviewer_and_nothing_else(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C5: Over a synthetic repository with a committed board, a command writes a review folder outside the repository holding the board's design files as the commit holds them, its plan, rules table and the records those name, the method, the hardware notes, the rendered views and placement view the round's first step names, and the check's report, together with one round file holding the round's number, kind, commit judged, views, check lines and, for a narrow round, listed items with a reason for each, changed regions and the line saying why every other item is not judged, taken from the command's arguments, and holds no session or notes file and no other file the commit does not hold; it holds no review record for a first round, and for a later round only the earlier rounds of the record as recorded, because a verdict row may cite a finding an earlier round closed by a reason. It refuses a folder inside the repository, a folder that is not new or empty, a commit that does not hold a board, views that are missing, and round fields of the set in use that are missing or malformed, the set being a parameter of the command, a narrow round without its reasons, changed regions or why-others line included. An add-view mode adds a rendered view and its command to a folder the command wrote, in the folder and in the round file's Views field, and records the item whose cannot judge asked for it with that Why, and refuses a view that does not exist or a folder the command did not write. The review seeding command's copy of the commit's files is generalised to take the repository, commit and design, with the documents optionally from a second repository, rendering stays in the seeding command, and the seeding command's existing tests still pass. Out of scope: rendering the views and running the check.
        status, text = self.run_with("--documents-repo", self.repo)
        self.assertEqual(status, 0, text)
        self.assertEqual(files_under(self.out), EXPECTED)
        for name in ("designer-notes.md", "session.txt", "layout-review.md"):
            self.assertFalse(os.path.exists(os.path.join(self.out, fx.DESIGN, name)), name)

    def test_the_design_files_are_the_commits_not_the_working_tree(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C5: Over a synthetic repository with a committed board, a command writes a review folder outside the repository holding the board's design files as the commit holds them, its plan, rules table and the records those name, the method, the hardware notes, the rendered views and placement view the round's first step names, and the check's report, together with one round file holding the round's number, kind, commit judged, views, check lines and, for a narrow round, listed items with a reason for each, changed regions and the line saying why every other item is not judged, taken from the command's arguments, and holds no session or notes file and no other file the commit does not hold; it holds no review record for a first round, and for a later round only the earlier rounds of the record as recorded, because a verdict row may cite a finding an earlier round closed by a reason. It refuses a folder inside the repository, a folder that is not new or empty, a commit that does not hold a board, views that are missing, and round fields of the set in use that are missing or malformed, the set being a parameter of the command, a narrow round without its reasons, changed regions or why-others line included. An add-view mode adds a rendered view and its command to a folder the command wrote, in the folder and in the round file's Views field, and records the item whose cannot judge asked for it with that Why, and refuses a view that does not exist or a folder the command did not write. The review seeding command's copy of the commit's files is generalised to take the repository, commit and design, with the documents optionally from a second repository, rendering stays in the seeding command, and the seeding command's existing tests still pass. Out of scope: rendering the views and running the check.
        first = fx.git(self.repo, "rev-parse", "HEAD")
        fx.write(os.path.join(self.repo, fx.DESIGN, "board.kicad_pcb"), "(kicad_pcb edited later)\n")
        fx.write(os.path.join(self.repo, fx.DESIGN, "untracked.kicad_sch"), "beside it\n")
        fx.git(self.repo, "add", "-A")
        fx.git(self.repo, "commit", "-q", "-m", "a later edit")
        status, text = self.run_with("--documents-repo", self.repo, "--commit", first)
        self.assertEqual(status, 0, text)
        self.assertEqual(self.read(fx.DESIGN, "board.kicad_pcb"), "(kicad_pcb committed)\n")
        self.assertFalse(os.path.exists(os.path.join(self.out, fx.DESIGN, "untracked.kicad_sch")))
        self.assertEqual(json.loads(self.read("round.json"))["commit"], first)

    def test_the_round_file_holds_the_rounds_fields_from_the_arguments(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C5: Over a synthetic repository with a committed board, a command writes a review folder outside the repository holding the board's design files as the commit holds them, its plan, rules table and the records those name, the method, the hardware notes, the rendered views and placement view the round's first step names, and the check's report, together with one round file holding the round's number, kind, commit judged, views, check lines and, for a narrow round, listed items with a reason for each, changed regions and the line saying why every other item is not judged, taken from the command's arguments, and holds no session or notes file and no other file the commit does not hold; it holds no review record for a first round, and for a later round only the earlier rounds of the record as recorded, because a verdict row may cite a finding an earlier round closed by a reason. It refuses a folder inside the repository, a folder that is not new or empty, a commit that does not hold a board, views that are missing, and round fields of the set in use that are missing or malformed, the set being a parameter of the command, a narrow round without its reasons, changed regions or why-others line included. An add-view mode adds a rendered view and its command to a folder the command wrote, in the folder and in the round file's Views field, and records the item whose cannot judge asked for it with that Why, and refuses a view that does not exist or a folder the command did not write. The review seeding command's copy of the commit's files is generalised to take the repository, commit and design, with the documents optionally from a second repository, rendering stays in the seeding command, and the seeding command's existing tests still pass. Out of scope: rendering the views and running the check.
        fx.write(os.path.join(self.repo, fx.DESIGN, "layout-review.md"), "# a record that holds no round yet\n")
        fx.git(self.repo, "add", "-A")
        fx.git(self.repo, "commit", "-q", "-m", "no rounds")
        status, text = self.run_with("--documents-repo", self.repo, *fx.NARROW, number=3, kind="narrow")
        self.assertEqual(status, 1, "round 3 cites earlier rounds the record lacks")
        self.assertIn("round 3 cites the earlier rounds of the review record, and the commit's layout-review.md holds none", text)
        self.assertFalse(os.path.exists(self.out))
        record = self.record_with_rounds(3)
        fx.write(os.path.join(self.repo, fx.DESIGN, "layout-review.md"), record)
        fx.git(self.repo, "add", "-A")
        fx.git(self.repo, "commit", "-q", "-m", "rounds 1 to 3")
        status, text = self.run_with("--documents-repo", self.repo, *fx.NARROW, number=3, kind="narrow")
        self.assertEqual(status, 0, text)
        content = json.loads(self.read("round.json"))
        self.assertEqual(content["number"], 3)
        self.assertEqual(content["kind"], "narrow")
        self.assertEqual(content["views"], fx.VIEW_COMMANDS)
        self.assertEqual(content["check"], fx.CHECK_LINES)
        self.assertEqual(content["items"], [{"item": "FLOOR-1", "reason": "the changed region holds its parts"},
                                            {"item": "CLOCK-1", "reason": "the crystal moved"}])
        self.assertEqual(content["regions"], ["region low voltage, net XTAL1"])
        self.assertEqual(content["others"], "no other item touches a changed region or net")
        self.assertEqual(content["fields"], list(review_folder.LAYOUT_FIELDS))
        self.assertEqual(content["cannot_judge"], [])
        full = os.path.join(self.root, "full")
        status, _ = self.run_with("--documents-repo", self.repo, out=full)
        self.assertEqual(status, 0)
        with open(os.path.join(full, "round.json"), encoding="utf-8") as handle:
            self.assertNotIn("items", json.load(handle), "a full round holds no narrow fields")

    @staticmethod
    def record_with_rounds(count):
        rounds = "\n".join(fx.RECORD.split("\n## Round 1\n")[1].join(["\n## Round 1\n", ""]).replace("Round 1", f"Round {n}")
                           .replace("1.1", f"{n}.1") for n in range(1, count + 1))
        return "# Layout review of the synthetic board\n" + rounds

    def test_a_first_round_holds_no_review_record_and_a_later_one_the_earlier_rounds_as_recorded(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C5: Over a synthetic repository with a committed board, a command writes a review folder outside the repository holding the board's design files as the commit holds them, its plan, rules table and the records those name, the method, the hardware notes, the rendered views and placement view the round's first step names, and the check's report, together with one round file holding the round's number, kind, commit judged, views, check lines and, for a narrow round, listed items with a reason for each, changed regions and the line saying why every other item is not judged, taken from the command's arguments, and holds no session or notes file and no other file the commit does not hold; it holds no review record for a first round, and for a later round only the earlier rounds of the record as recorded, because a verdict row may cite a finding an earlier round closed by a reason. It refuses a folder inside the repository, a folder that is not new or empty, a commit that does not hold a board, views that are missing, and round fields of the set in use that are missing or malformed, the set being a parameter of the command, a narrow round without its reasons, changed regions or why-others line included. An add-view mode adds a rendered view and its command to a folder the command wrote, in the folder and in the round file's Views field, and records the item whose cannot judge asked for it with that Why, and refuses a view that does not exist or a folder the command did not write. The review seeding command's copy of the commit's files is generalised to take the repository, commit and design, with the documents optionally from a second repository, rendering stays in the seeding command, and the seeding command's existing tests still pass. Out of scope: rendering the views and running the check.
        record = self.record_with_rounds(3)
        fx.write(os.path.join(self.repo, fx.DESIGN, "layout-review.md"), record)
        fx.git(self.repo, "add", "-A")
        fx.git(self.repo, "commit", "-q", "-m", "rounds 1 to 3")
        status, _ = self.run_with("--documents-repo", self.repo)
        self.assertEqual(status, 0)
        self.assertNotIn(fx.DESIGN + "/layout-review.md", files_under(self.out), "a first round holds no review record")
        for number in (2, 3):
            out = os.path.join(self.root, f"round-{number}")
            status, text = self.run_with("--documents-repo", self.repo, number=number, out=out)
            self.assertEqual(status, 0, text)
            with open(os.path.join(out, fx.DESIGN, "layout-review.md"), encoding="utf-8") as handle:
                held = handle.read()
            self.assertTrue(record.startswith(held), "the earlier rounds are held as recorded")
            self.assertIn(f"## Round {number - 1}\n", held)
            self.assertNotIn(f"## Round {number}\n", held, "the round under review is not in the folder")
            self.assertEqual(files_under(out) - EXPECTED, {fx.DESIGN + "/layout-review.md"})

    def test_a_later_round_refuses_a_record_that_lacks_a_round_between_the_first_and_its_own(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C5: Over a synthetic repository with a committed board, a command writes a review folder outside the repository holding the board's design files as the commit holds them, its plan, rules table and the records those name, the method, the hardware notes, the rendered views and placement view the round's first step names, and the check's report, together with one round file holding the round's number, kind, commit judged, views, check lines and, for a narrow round, listed items with a reason for each, changed regions and the line saying why every other item is not judged, taken from the command's arguments, and holds no session or notes file and no other file the commit does not hold; it holds no review record for a first round, and for a later round only the earlier rounds of the record as recorded, because a verdict row may cite a finding an earlier round closed by a reason. It refuses a folder inside the repository, a folder that is not new or empty, a commit that does not hold a board, views that are missing, and round fields of the set in use that are missing or malformed, the set being a parameter of the command, a narrow round without its reasons, changed regions or why-others line included. An add-view mode adds a rendered view and its command to a folder the command wrote, in the folder and in the round file's Views field, and records the item whose cannot judge asked for it with that Why, and refuses a view that does not exist or a folder the command did not write. The review seeding command's copy of the commit's files is generalised to take the repository, commit and design, with the documents optionally from a second repository, rendering stays in the seeding command, and the seeding command's existing tests still pass. Out of scope: rendering the views and running the check.
        status, text = self.run_with("--documents-repo", self.repo, number=5)
        self.assertEqual(status, 1, text)
        self.assertIn("lacks round 2, 3, 4", text)
        self.assertFalse(os.path.exists(self.out))
        status, text = self.run_with("--documents-repo", self.repo, number=2)
        self.assertEqual(status, 0, text)

    def test_a_round_heading_inside_a_code_fence_does_not_end_the_earlier_rounds(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C5: Over a synthetic repository with a committed board, a command writes a review folder outside the repository holding the board's design files as the commit holds them, its plan, rules table and the records those name, the method, the hardware notes, the rendered views and placement view the round's first step names, and the check's report, together with one round file holding the round's number, kind, commit judged, views, check lines and, for a narrow round, listed items with a reason for each, changed regions and the line saying why every other item is not judged, taken from the command's arguments, and holds no session or notes file and no other file the commit does not hold; it holds no review record for a first round, and for a later round only the earlier rounds of the record as recorded, because a verdict row may cite a finding an earlier round closed by a reason. It refuses a folder inside the repository, a folder that is not new or empty, a commit that does not hold a board, views that are missing, and round fields of the set in use that are missing or malformed, the set being a parameter of the command, a narrow round without its reasons, changed regions or why-others line included. An add-view mode adds a rendered view and its command to a folder the command wrote, in the folder and in the round file's Views field, and records the item whose cannot judge asked for it with that Why, and refuses a view that does not exist or a folder the command did not write. The review seeding command's copy of the commit's files is generalised to take the repository, commit and design, with the documents optionally from a second repository, rendering stays in the seeding command, and the seeding command's existing tests still pass. Out of scope: rendering the views and running the check.
        text = fx.RECORD.replace("### Verdicts", "```\n## Round 2\n```\n\n### Verdicts") + "\n## Round 2\n\n### Verdicts\n\nlater\n"
        held = review_folder.earlier_rounds(text, 2)
        self.assertIn("```\n## Round 2\n```", held)
        self.assertNotIn("later", held)
        self.assertIsNone(review_folder.earlier_rounds(text, 1))
        self.assertIsNone(review_folder.earlier_rounds("# no rounds\n", 2))

    def test_a_folder_inside_either_repository_a_folder_not_new_or_empty_and_a_file_are_refused(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C5: Over a synthetic repository with a committed board, a command writes a review folder outside the repository holding the board's design files as the commit holds them, its plan, rules table and the records those name, the method, the hardware notes, the rendered views and placement view the round's first step names, and the check's report, together with one round file holding the round's number, kind, commit judged, views, check lines and, for a narrow round, listed items with a reason for each, changed regions and the line saying why every other item is not judged, taken from the command's arguments, and holds no session or notes file and no other file the commit does not hold; it holds no review record for a first round, and for a later round only the earlier rounds of the record as recorded, because a verdict row may cite a finding an earlier round closed by a reason. It refuses a folder inside the repository, a folder that is not new or empty, a commit that does not hold a board, views that are missing, and round fields of the set in use that are missing or malformed, the set being a parameter of the command, a narrow round without its reasons, changed regions or why-others line included. An add-view mode adds a rendered view and its command to a folder the command wrote, in the folder and in the round file's Views field, and records the item whose cannot judge asked for it with that Why, and refuses a view that does not exist or a folder the command did not write. The review seeding command's copy of the commit's files is generalised to take the repository, commit and design, with the documents optionally from a second repository, rendering stays in the seeding command, and the seeding command's existing tests still pass. Out of scope: rendering the views and running the check.
        inside = os.path.join(self.repo, "review")
        status, text = self.run_with("--documents-repo", self.repo, out=inside)
        self.assertEqual((status, os.path.exists(inside)), (1, False))
        self.assertIn(f"the review folder {inside} is inside the repository {self.repo}", text)
        documents = fx.make_repo(os.path.join(self.root, "documents"))
        inside = os.path.join(documents, "review")
        status, text = self.run_with("--documents-repo", documents, out=inside)
        self.assertEqual((status, os.path.exists(inside)), (1, False))
        self.assertIn(f"the review folder {inside} is inside the documents repository {documents}", text)
        os.makedirs(self.out)
        fx.write(os.path.join(self.out, "held.txt"), "held")
        status, text = self.run_with("--documents-repo", self.repo)
        self.assertIn("already holds files; give a new or empty folder", text)
        self.assertEqual(os.listdir(self.out), ["held.txt"], "what a folder held is left alone")
        shutil.rmtree(self.out)
        fx.write(self.out, "a file")
        status, text = self.run_with("--documents-repo", self.repo)
        self.assertIn("is a file; give a new or empty folder", text)
        self.assertEqual((status, self.read_file()), (1, "a file"))
        os.remove(self.out)
        os.makedirs(self.out)
        status, text = self.run_with("--documents-repo", self.repo)
        self.assertEqual(status, 0, "an empty folder is accepted")

    def read_file(self):
        with open(self.out, encoding="utf-8") as handle:
            return handle.read()

    def test_a_commit_that_holds_no_board_or_is_not_in_the_repository_is_refused(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C5: Over a synthetic repository with a committed board, a command writes a review folder outside the repository holding the board's design files as the commit holds them, its plan, rules table and the records those name, the method, the hardware notes, the rendered views and placement view the round's first step names, and the check's report, together with one round file holding the round's number, kind, commit judged, views, check lines and, for a narrow round, listed items with a reason for each, changed regions and the line saying why every other item is not judged, taken from the command's arguments, and holds no session or notes file and no other file the commit does not hold; it holds no review record for a first round, and for a later round only the earlier rounds of the record as recorded, because a verdict row may cite a finding an earlier round closed by a reason. It refuses a folder inside the repository, a folder that is not new or empty, a commit that does not hold a board, views that are missing, and round fields of the set in use that are missing or malformed, the set being a parameter of the command, a narrow round without its reasons, changed regions or why-others line included. An add-view mode adds a rendered view and its command to a folder the command wrote, in the folder and in the round file's Views field, and records the item whose cannot judge asked for it with that Why, and refuses a view that does not exist or a folder the command did not write. The review seeding command's copy of the commit's files is generalised to take the repository, commit and design, with the documents optionally from a second repository, rendering stays in the seeding command, and the seeding command's existing tests still pass. Out of scope: rendering the views and running the check.
        bare = os.path.join(self.root, "bare")
        os.makedirs(bare)
        fx.git(bare, "init", "-q")
        fx.write(os.path.join(bare, "README.md"), "no board\n")
        fx.write(os.path.join(bare, "docs", "board-design-method.md"), fx.METHOD)
        fx.write(os.path.join(bare, "hardware", "README.md"), fx.README)
        fx.git(bare, "add", "-A")
        fx.git(bare, "commit", "-q", "-m", "no board")
        status, text = self.run_with("--documents-repo", bare, repo=bare)
        self.assertEqual(status, 1)
        self.assertIn(f"holds no board at {fx.DESIGN}", text)
        self.assertIn("holds 0 projects and 0 layouts there", text)
        status, text = self.run_with("--documents-repo", self.repo, "--commit", "0" * 40)
        self.assertIn("is not in the repository", text)
        fx.git(self.repo, "rm", "-q", f"{fx.DESIGN}/board.kicad_pcb")
        fx.git(self.repo, "commit", "-q", "-m", "no layout")
        status, text = self.run_with("--documents-repo", self.repo)
        self.assertIn("holds 1 projects and 0 layouts there", text)
        self.assertFalse(os.path.exists(self.out))

    def test_views_a_placement_view_or_a_report_that_is_missing_are_refused_naming_each(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C5: Over a synthetic repository with a committed board, a command writes a review folder outside the repository holding the board's design files as the commit holds them, its plan, rules table and the records those name, the method, the hardware notes, the rendered views and placement view the round's first step names, and the check's report, together with one round file holding the round's number, kind, commit judged, views, check lines and, for a narrow round, listed items with a reason for each, changed regions and the line saying why every other item is not judged, taken from the command's arguments, and holds no session or notes file and no other file the commit does not hold; it holds no review record for a first round, and for a later round only the earlier rounds of the record as recorded, because a verdict row may cite a finding an earlier round closed by a reason. It refuses a folder inside the repository, a folder that is not new or empty, a commit that does not hold a board, views that are missing, and round fields of the set in use that are missing or malformed, the set being a parameter of the command, a narrow round without its reasons, changed regions or why-others line included. An add-view mode adds a rendered view and its command to a folder the command wrote, in the folder and in the round file's Views field, and records the item whose cannot judge asked for it with that Why, and refuses a view that does not exist or a folder the command did not write. The review seeding command's copy of the commit's files is generalised to take the repository, commit and design, with the documents optionally from a second repository, rendering stays in the seeding command, and the seeding command's existing tests still pass. Out of scope: rendering the views and running the check.
        os.remove(os.path.join(self.inputs["views"], "index.txt"))
        shutil.rmtree(self.inputs["placement"])
        os.remove(self.inputs["report"])
        status, text = self.run_with("--documents-repo", self.repo)
        self.assertEqual(status, 1)
        for words in ("the views folder", "the placement view folder", "is missing or holds no index.txt", "the pre-order check's report",
                      "does not exist"):
            self.assertIn(words, text)
        self.assertFalse(os.path.exists(self.out))

    def test_a_round_field_missing_or_malformed_is_refused_naming_the_field(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C5: Over a synthetic repository with a committed board, a command writes a review folder outside the repository holding the board's design files as the commit holds them, its plan, rules table and the records those name, the method, the hardware notes, the rendered views and placement view the round's first step names, and the check's report, together with one round file holding the round's number, kind, commit judged, views, check lines and, for a narrow round, listed items with a reason for each, changed regions and the line saying why every other item is not judged, taken from the command's arguments, and holds no session or notes file and no other file the commit does not hold; it holds no review record for a first round, and for a later round only the earlier rounds of the record as recorded, because a verdict row may cite a finding an earlier round closed by a reason. It refuses a folder inside the repository, a folder that is not new or empty, a commit that does not hold a board, views that are missing, and round fields of the set in use that are missing or malformed, the set being a parameter of the command, a narrow round without its reasons, changed regions or why-others line included. An add-view mode adds a rendered view and its command to a folder the command wrote, in the folder and in the round file's Views field, and records the item whose cannot judge asked for it with that Why, and refuses a view that does not exist or a folder the command did not write. The review seeding command's copy of the commit's files is generalised to take the repository, commit and design, with the documents optionally from a second repository, rendering stays in the seeding command, and the seeding command's existing tests still pass. Out of scope: rendering the views and running the check.
        docs = ("--documents-repo", self.repo)
        cases = (
            (dict(number=0), (), "the round's number is 0"), (dict(kind="medium"), (), "the round's kind is 'medium'"),
            (dict(), ("--number",), "the round's number is None"), (dict(), ("--kind",), "the round's kind is None"),
            (dict(), ("--view-command",), "the views are []"), (dict(), ("--check-line",), "the pre-order check's lines are []"),
            (dict(extra=("--view-command", "two\nlines")), (), "the views are"),
            (dict(extra=("--check-line", "RESULT | PASS")), (), "the pre-order check's lines are"),
            (dict(extra=("--item", "FLOOR-1=r")), (), "a round that is not narrow gives items"),
            (dict(extra=("--others", "why")), (), "a round that is not narrow gives others"),
            (dict(kind="narrow", extra=("--item", "FLOOR-1=r", "--region", "r")), (), "line saying why every other item is not judged is None"),
            (dict(kind="narrow", extra=("--item", "FLOOR-1=r", "--others", "why")), (), "changed regions are []"),
            (dict(kind="narrow", extra=("--region", "r", "--others", "why")), (), "a narrow round's listed items are []"),
            (dict(kind="narrow", extra=("--item", "FLOOR-1", "--region", "r", "--others", "why")), (), "a narrow round's listed items are"),
            (dict(kind="narrow", extra=("--item", "FLOOR-1=", "--region", "r", "--others", "why")), (), "a narrow round's listed items are"),
            (dict(kind="narrow", extra=("--item", "FLOOR-1=r", "--item", "FLOOR-1=s", "--region", "r", "--others", "why")), (),
             "lists an item twice"))
        for how, drop, word in cases:
            with self.subTest(word=word, how=how, drop=drop):
                extra = how.get("extra", ())
                status, text = self.run_with(*docs, *extra, number=how.get("number", 1), kind=how.get("kind", "full"), drop=drop)
                self.assertEqual(status, 1, text)
                self.assertIn(word, text)
                self.assertFalse(os.path.exists(self.out))

    def test_the_set_of_round_fields_is_a_parameter_of_the_command(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C5: Over a synthetic repository with a committed board, a command writes a review folder outside the repository holding the board's design files as the commit holds them, its plan, rules table and the records those name, the method, the hardware notes, the rendered views and placement view the round's first step names, and the check's report, together with one round file holding the round's number, kind, commit judged, views, check lines and, for a narrow round, listed items with a reason for each, changed regions and the line saying why every other item is not judged, taken from the command's arguments, and holds no session or notes file and no other file the commit does not hold; it holds no review record for a first round, and for a later round only the earlier rounds of the record as recorded, because a verdict row may cite a finding an earlier round closed by a reason. It refuses a folder inside the repository, a folder that is not new or empty, a commit that does not hold a board, views that are missing, and round fields of the set in use that are missing or malformed, the set being a parameter of the command, a narrow round without its reasons, changed regions or why-others line included. An add-view mode adds a rendered view and its command to a folder the command wrote, in the folder and in the round file's Views field, and records the item whose cannot judge asked for it with that Why, and refuses a view that does not exist or a folder the command did not write. The review seeding command's copy of the commit's files is generalised to take the repository, commit and design, with the documents optionally from a second repository, rendering stays in the seeding command, and the seeding command's existing tests still pass. Out of scope: rendering the views and running the check.
        argv = ["--repo", self.repo, "--commit", "HEAD", "--design", fx.DESIGN, "--out", self.out, "--views", self.inputs["views"],
                "--placement", self.inputs["placement"], "--check-report", self.inputs["report"], "--documents-repo", self.repo,
                "--round-fields", "number,commit,views", "--number", "2", "--view-command", "a view command"]
        status, text = fx.run_folder(argv)
        self.assertEqual(status, 0, text)
        content = json.loads(self.read("round.json"))
        self.assertEqual(content["fields"], ["number", "commit", "views"])
        self.assertEqual((content["number"], content["views"]), (2, ["a view command"]))
        self.assertNotIn("kind", content)
        self.assertNotIn("check", content)
        shutil.rmtree(self.out)
        status, text = fx.run_folder(argv[:-4] + ["--round-fields", "number,commit,views"])
        self.assertEqual(status, 1)
        self.assertIn("the round's number is None", text)
        self.assertIn("the views are []", text)
        status, text = fx.run_folder(argv + ["--item", "FLOOR-1=r"])
        self.assertIn("a round that is not narrow gives items", text, "a set without a kind has no narrow round")
        status, text = fx.run_folder(argv[:-6] + ["--round-fields", "number,colour", "--number", "1"])
        self.assertIn("the round fields colour are not fields of a round", text)

    def test_the_command_reports_in_text_and_in_json(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C5: Over a synthetic repository with a committed board, a command writes a review folder outside the repository holding the board's design files as the commit holds them, its plan, rules table and the records those name, the method, the hardware notes, the rendered views and placement view the round's first step names, and the check's report, together with one round file holding the round's number, kind, commit judged, views, check lines and, for a narrow round, listed items with a reason for each, changed regions and the line saying why every other item is not judged, taken from the command's arguments, and holds no session or notes file and no other file the commit does not hold; it holds no review record for a first round, and for a later round only the earlier rounds of the record as recorded, because a verdict row may cite a finding an earlier round closed by a reason. It refuses a folder inside the repository, a folder that is not new or empty, a commit that does not hold a board, views that are missing, and round fields of the set in use that are missing or malformed, the set being a parameter of the command, a narrow round without its reasons, changed regions or why-others line included. An add-view mode adds a rendered view and its command to a folder the command wrote, in the folder and in the round file's Views field, and records the item whose cannot judge asked for it with that Why, and refuses a view that does not exist or a folder the command did not write. The review seeding command's copy of the commit's files is generalised to take the repository, commit and design, with the documents optionally from a second repository, rendering stays in the seeding command, and the seeding command's existing tests still pass. Out of scope: rendering the views and running the check.
        status, text = self.run_with("--documents-repo", self.repo)
        sha = fx.git(self.repo, "rev-parse", "HEAD")
        lines = text.splitlines()
        self.assertEqual(status, 0)
        self.assertEqual(lines[0], f"FOLDER | {self.out} | commit {sha} | design {fx.DESIGN}")
        self.assertTrue(lines[1].startswith("ROUND | number 1 | kind full | commit "))
        self.assertEqual(lines[-1], f"RESULT | WRITTEN | {self.out}")
        shutil.rmtree(self.out)
        status, text = self.run_with("--documents-repo", self.repo, "--json")
        report = json.loads(text)
        self.assertEqual((status, report["result"], report["commit"], report["folder"]), (0, "WRITTEN", sha, self.out))
        self.assertEqual(report["documents"], ["docs/board-design-method.md", "hardware/README.md"])
        self.assertIn("board.kicad_pcb", report["design_files"])
        status, text = self.run_with("--documents-repo", self.repo, "--json", number=0, out=os.path.join(self.root, "x"))
        refused = json.loads(text)
        self.assertEqual((status, refused["result"]), (1, "REFUSED"))
        self.assertIn("the round's number is 0", refused["refusals"][0])


class TheAddViewMode(Case):
    def setUp(self):
        super().setUp()
        status, text = self.run_with("--documents-repo", self.repo)
        self.assertEqual(status, 0, text)
        self.view = os.path.join(self.root, "crop-Y1.svg")
        fx.write(self.view, "<svg/>")

    def add(self, *extra, folder=None, view=None):
        argv = ["--add-view", folder or self.out, "--cannot-judge-item", "CLOCK-1", "--cannot-judge-why", "needs crop-Y1: none rendered",
                "--view-command", "kicad-cli pcb export svg ...", "--view", view or self.view]
        for flag in extra:
            at = argv.index(flag)
            del argv[at:at + 2]
        return fx.run_folder(argv)

    def test_a_view_and_its_command_are_added_to_the_folder_and_the_round_files_views_with_the_item_and_why(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C5: Over a synthetic repository with a committed board, a command writes a review folder outside the repository holding the board's design files as the commit holds them, its plan, rules table and the records those name, the method, the hardware notes, the rendered views and placement view the round's first step names, and the check's report, together with one round file holding the round's number, kind, commit judged, views, check lines and, for a narrow round, listed items with a reason for each, changed regions and the line saying why every other item is not judged, taken from the command's arguments, and holds no session or notes file and no other file the commit does not hold; it holds no review record for a first round, and for a later round only the earlier rounds of the record as recorded, because a verdict row may cite a finding an earlier round closed by a reason. It refuses a folder inside the repository, a folder that is not new or empty, a commit that does not hold a board, views that are missing, and round fields of the set in use that are missing or malformed, the set being a parameter of the command, a narrow round without its reasons, changed regions or why-others line included. An add-view mode adds a rendered view and its command to a folder the command wrote, in the folder and in the round file's Views field, and records the item whose cannot judge asked for it with that Why, and refuses a view that does not exist or a folder the command did not write. The review seeding command's copy of the commit's files is generalised to take the repository, commit and design, with the documents optionally from a second repository, rendering stays in the seeding command, and the seeding command's existing tests still pass. Out of scope: rendering the views and running the check.
        status, text = self.add()
        self.assertEqual(status, 0, text)
        self.assertEqual(text.splitlines()[-1], "RESULT | ADDED | added-views/crop-Y1.svg | cannot judge of CLOCK-1")
        self.assertEqual(self.read("added-views", "crop-Y1.svg"), "<svg/>")
        content = json.loads(self.read("round.json"))
        self.assertEqual(content["views"], fx.VIEW_COMMANDS + ["kicad-cli pcb export svg ... (added view: added-views/crop-Y1.svg)"])
        self.assertEqual(content["cannot_judge"], [{"item": "CLOCK-1", "why": "needs crop-Y1: none rendered",
                                                    "view": "added-views/crop-Y1.svg"}])
        self.assertEqual(review_folder.read_round(self.out)["number"], 1, "the round file is still one the command reads")
        second = os.path.join(self.root, "crop-Y2.svg")
        fx.write(second, "<svg2/>")
        status, text = self.add(view=second)
        self.assertEqual(status, 0)
        self.assertEqual(len(json.loads(self.read("round.json"))["cannot_judge"]), 2)
        status, as_json = fx.run_folder(["--add-view", self.out, "--cannot-judge-item", "CLOCK-1", "--cannot-judge-why", "w",
                                         "--view-command", "c", "--view", os.path.join(self.root, "crop-Y3.svg"), "--json"])
        self.assertEqual(status, 1)
        self.assertEqual(json.loads(as_json)["result"], "REFUSED")

    def test_json_names_the_view_added(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C5: Over a synthetic repository with a committed board, a command writes a review folder outside the repository holding the board's design files as the commit holds them, its plan, rules table and the records those name, the method, the hardware notes, the rendered views and placement view the round's first step names, and the check's report, together with one round file holding the round's number, kind, commit judged, views, check lines and, for a narrow round, listed items with a reason for each, changed regions and the line saying why every other item is not judged, taken from the command's arguments, and holds no session or notes file and no other file the commit does not hold; it holds no review record for a first round, and for a later round only the earlier rounds of the record as recorded, because a verdict row may cite a finding an earlier round closed by a reason. It refuses a folder inside the repository, a folder that is not new or empty, a commit that does not hold a board, views that are missing, and round fields of the set in use that are missing or malformed, the set being a parameter of the command, a narrow round without its reasons, changed regions or why-others line included. An add-view mode adds a rendered view and its command to a folder the command wrote, in the folder and in the round file's Views field, and records the item whose cannot judge asked for it with that Why, and refuses a view that does not exist or a folder the command did not write. The review seeding command's copy of the commit's files is generalised to take the repository, commit and design, with the documents optionally from a second repository, rendering stays in the seeding command, and the seeding command's existing tests still pass. Out of scope: rendering the views and running the check.
        status, text = fx.run_folder(["--add-view", self.out, "--cannot-judge-item", "CLOCK-1", "--cannot-judge-why", "w",
                                      "--view-command", "c", "--view", self.view, "--json"])
        self.assertEqual(status, 0, text)
        self.assertEqual(json.loads(text), {"result": "ADDED", "folder": self.out, "view": "added-views/crop-Y1.svg", "item": "CLOCK-1"})

    def test_a_view_that_does_not_exist_and_a_folder_the_command_did_not_write_are_refused(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C5: Over a synthetic repository with a committed board, a command writes a review folder outside the repository holding the board's design files as the commit holds them, its plan, rules table and the records those name, the method, the hardware notes, the rendered views and placement view the round's first step names, and the check's report, together with one round file holding the round's number, kind, commit judged, views, check lines and, for a narrow round, listed items with a reason for each, changed regions and the line saying why every other item is not judged, taken from the command's arguments, and holds no session or notes file and no other file the commit does not hold; it holds no review record for a first round, and for a later round only the earlier rounds of the record as recorded, because a verdict row may cite a finding an earlier round closed by a reason. It refuses a folder inside the repository, a folder that is not new or empty, a commit that does not hold a board, views that are missing, and round fields of the set in use that are missing or malformed, the set being a parameter of the command, a narrow round without its reasons, changed regions or why-others line included. An add-view mode adds a rendered view and its command to a folder the command wrote, in the folder and in the round file's Views field, and records the item whose cannot judge asked for it with that Why, and refuses a view that does not exist or a folder the command did not write. The review seeding command's copy of the commit's files is generalised to take the repository, commit and design, with the documents optionally from a second repository, rendering stays in the seeding command, and the seeding command's existing tests still pass. Out of scope: rendering the views and running the check.
        before = open(os.path.join(self.out, "round.json"), encoding="utf-8").read()
        status, text = self.add(view=os.path.join(self.root, "missing.svg"))
        self.assertEqual(status, 1)
        self.assertIn("does not exist; render it, then give the file", text)
        stranger = os.path.join(self.root, "stranger")
        fx.write(os.path.join(stranger, "round.json"), json.dumps({"number": 1}))
        for folder, word in ((stranger, "not one the folder command wrote"), (os.path.join(self.root, "nowhere"), "cannot be read"),
                             (self.root, "cannot be read")):
            status, text = self.add(folder=folder)
            self.assertEqual(status, 1, text)
            self.assertIn("is not a review folder the command wrote and can add to", text)
            self.assertIn(word, text)
        self.assertEqual(open(os.path.join(self.out, "round.json"), encoding="utf-8").read(), before)
        self.assertFalse(os.path.exists(os.path.join(self.out, "added-views")))

    def test_a_missing_item_why_or_command_a_repeated_name_and_a_set_without_views_are_refused(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C5: Over a synthetic repository with a committed board, a command writes a review folder outside the repository holding the board's design files as the commit holds them, its plan, rules table and the records those name, the method, the hardware notes, the rendered views and placement view the round's first step names, and the check's report, together with one round file holding the round's number, kind, commit judged, views, check lines and, for a narrow round, listed items with a reason for each, changed regions and the line saying why every other item is not judged, taken from the command's arguments, and holds no session or notes file and no other file the commit does not hold; it holds no review record for a first round, and for a later round only the earlier rounds of the record as recorded, because a verdict row may cite a finding an earlier round closed by a reason. It refuses a folder inside the repository, a folder that is not new or empty, a commit that does not hold a board, views that are missing, and round fields of the set in use that are missing or malformed, the set being a parameter of the command, a narrow round without its reasons, changed regions or why-others line included. An add-view mode adds a rendered view and its command to a folder the command wrote, in the folder and in the round file's Views field, and records the item whose cannot judge asked for it with that Why, and refuses a view that does not exist or a folder the command did not write. The review seeding command's copy of the commit's files is generalised to take the repository, commit and design, with the documents optionally from a second repository, rendering stays in the seeding command, and the seeding command's existing tests still pass. Out of scope: rendering the views and running the check.
        for flag, word in (("--cannot-judge-item", "the item whose cannot judge asked for the view"),
                           ("--cannot-judge-why", "the cannot judge's Why"), ("--view-command", "the command the view was rendered with")):
            status, text = self.add(flag)
            self.assertEqual(status, 1)
            self.assertIn(word, text)
        self.assertEqual(self.add()[0], 0)
        status, text = self.add()
        self.assertIn("already holds an added view named crop-Y1.svg", text)
        bad = os.path.join(self.root, "bad name.svg")
        fx.write(bad, "x")
        self.assertIn("is not a plain name", self.add(view=bad)[1])
        other = os.path.join(self.root, "other")
        argv = ["--repo", self.repo, "--commit", "HEAD", "--design", fx.DESIGN, "--out", other, "--views", self.inputs["views"],
                "--placement", self.inputs["placement"], "--check-report", self.inputs["report"], "--documents-repo", self.repo,
                "--round-fields", "number,commit", "--number", "1"]
        self.assertEqual(fx.run_folder(argv)[0], 0)
        status, text = self.add(folder=other)
        self.assertEqual(status, 1)
        self.assertIn("hold no views, so it has no Views field", text)


# --- The seeding command's generalised copy --------------------------------------------------------


class TheGeneralisedCopy(Case):
    def test_the_copy_takes_the_repository_the_commit_and_the_design_and_the_documents_from_a_second_repository(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C5: Over a synthetic repository with a committed board, a command writes a review folder outside the repository holding the board's design files as the commit holds them, its plan, rules table and the records those name, the method, the hardware notes, the rendered views and placement view the round's first step names, and the check's report, together with one round file holding the round's number, kind, commit judged, views, check lines and, for a narrow round, listed items with a reason for each, changed regions and the line saying why every other item is not judged, taken from the command's arguments, and holds no session or notes file and no other file the commit does not hold; it holds no review record for a first round, and for a later round only the earlier rounds of the record as recorded, because a verdict row may cite a finding an earlier round closed by a reason. It refuses a folder inside the repository, a folder that is not new or empty, a commit that does not hold a board, views that are missing, and round fields of the set in use that are missing or malformed, the set being a parameter of the command, a narrow round without its reasons, changed regions or why-others line included. An add-view mode adds a rendered view and its command to a folder the command wrote, in the folder and in the round file's Views field, and records the item whose cannot judge asked for it with that Why, and refuses a view that does not exist or a folder the command did not write. The review seeding command's copy of the commit's files is generalised to take the repository, commit and design, with the documents optionally from a second repository, rendering stays in the seeding command, and the seeding command's existing tests still pass. Out of scope: rendering the views and running the check.
        first = fx.git(self.repo, "rev-parse", "HEAD")
        fx.write(os.path.join(self.repo, fx.DESIGN, "board.kicad_pcb"), "(kicad_pcb second)\n")
        fx.write(os.path.join(self.repo, "docs", "board-design-method.md"), "a changed method\n")
        fx.git(self.repo, "add", "-A")
        fx.git(self.repo, "commit", "-q", "-m", "second")
        out = os.path.join(self.root, "copy")
        written = review_seed.copy_commit(out, self.repo, first, fx.DESIGN, self.repo, first)
        self.assertIn("board.kicad_pcb", written)
        self.assertNotIn("designer-notes.md", written)
        self.assertEqual(open(os.path.join(out, fx.DESIGN, "board.kicad_pcb"), encoding="utf-8").read(), "(kicad_pcb committed)\n")
        self.assertEqual(open(os.path.join(out, "docs", "board-design-method.md"), encoding="utf-8").read(), fx.METHOD)
        latest = os.path.join(self.root, "copy-latest")
        review_seed.copy_commit(latest, self.repo, "HEAD", fx.DESIGN, self.repo)
        self.assertEqual(open(os.path.join(latest, "docs", "board-design-method.md"), encoding="utf-8").read(), "a changed method\n")
        other = os.path.join(self.root, "copy-host")
        review_seed.copy_commit(other, self.repo, first, fx.DESIGN)
        held = board_prove.committed("docs/board-design-method.md")
        if held is not None:
            host = held["docs/board-design-method.md"]
        else:
            with open(os.path.join(REPO, "docs", "board-design-method.md"), "rb") as handle:
                host = handle.read()
        self.assertEqual(open(os.path.join(other, "docs", "board-design-method.md"), "rb").read(), host,
                         "without a second repository the documents are this repository's, as the seeding command takes them")

    def test_a_documents_repository_that_lacks_a_document_and_a_design_that_is_not_there_are_not_taken(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C5: Over a synthetic repository with a committed board, a command writes a review folder outside the repository holding the board's design files as the commit holds them, its plan, rules table and the records those name, the method, the hardware notes, the rendered views and placement view the round's first step names, and the check's report, together with one round file holding the round's number, kind, commit judged, views, check lines and, for a narrow round, listed items with a reason for each, changed regions and the line saying why every other item is not judged, taken from the command's arguments, and holds no session or notes file and no other file the commit does not hold; it holds no review record for a first round, and for a later round only the earlier rounds of the record as recorded, because a verdict row may cite a finding an earlier round closed by a reason. It refuses a folder inside the repository, a folder that is not new or empty, a commit that does not hold a board, views that are missing, and round fields of the set in use that are missing or malformed, the set being a parameter of the command, a narrow round without its reasons, changed regions or why-others line included. An add-view mode adds a rendered view and its command to a folder the command wrote, in the folder and in the round file's Views field, and records the item whose cannot judge asked for it with that Why, and refuses a view that does not exist or a folder the command did not write. The review seeding command's copy of the commit's files is generalised to take the repository, commit and design, with the documents optionally from a second repository, rendering stays in the seeding command, and the seeding command's existing tests still pass. Out of scope: rendering the views and running the check.
        with self.assertRaises(review_seed.Refused) as caught:
            review_seed.documents(self.repo, "0" * 40)
        self.assertIn("holds no docs/board-design-method.md", str(caught.exception))
        self.assertEqual(review_seed.design_files(self.repo, "HEAD", "hardware/nothing"), {})
        self.assertEqual(review_seed.archived(self.repo, "0" * 40, fx.DESIGN), {})
        status, text = self.run_with("--documents-repo", self.repo, "--documents-commit", "0" * 40)
        self.assertEqual(status, 1)
        self.assertIn("holds no docs/board-design-method.md", text)

    def test_the_files_given_to_a_reviewer_are_still_kicads_files_and_the_named_records(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C5: Over a synthetic repository with a committed board, a command writes a review folder outside the repository holding the board's design files as the commit holds them, its plan, rules table and the records those name, the method, the hardware notes, the rendered views and placement view the round's first step names, and the check's report, together with one round file holding the round's number, kind, commit judged, views, check lines and, for a narrow round, listed items with a reason for each, changed regions and the line saying why every other item is not judged, taken from the command's arguments, and holds no session or notes file and no other file the commit does not hold; it holds no review record for a first round, and for a later round only the earlier rounds of the record as recorded, because a verdict row may cite a finding an earlier round closed by a reason. It refuses a folder inside the repository, a folder that is not new or empty, a commit that does not hold a board, views that are missing, and round fields of the set in use that are missing or malformed, the set being a parameter of the command, a narrow round without its reasons, changed regions or why-others line included. An add-view mode adds a rendered view and its command to a folder the command wrote, in the folder and in the round file's Views field, and records the item whose cannot judge asked for it with that Why, and refuses a view that does not exist or a folder the command did not write. The review seeding command's copy of the commit's files is generalised to take the repository, commit and design, with the documents optionally from a second repository, rendering stays in the seeding command, and the seeding command's existing tests still pass. Out of scope: rendering the views and running the check.
        held = review_seed.design_files(self.repo, "HEAD", fx.DESIGN)
        self.assertEqual(sorted(held), sorted([*fx.BOARD_FILES, "layout-plan.md"]))


# --- The seeding command's opt-in flag --------------------------------------------------------------


class TheKeptWorkTree(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="review-keep-test-")
        self.addCleanup(shutil.rmtree, self.root, True)

    def test_a_kept_work_tree_folder_must_be_new_outside_the_repository_and_apart_from_the_review_folder_and_the_seeds(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C5: Over a synthetic repository with a committed board, a command writes a review folder outside the repository holding the board's design files as the commit holds them, its plan, rules table and the records those name, the method, the hardware notes, the rendered views and placement view the round's first step names, and the check's report, together with one round file holding the round's number, kind, commit judged, views, check lines and, for a narrow round, listed items with a reason for each, changed regions and the line saying why every other item is not judged, taken from the command's arguments, and holds no session or notes file and no other file the commit does not hold; it holds no review record for a first round, and for a later round only the earlier rounds of the record as recorded, because a verdict row may cite a finding an earlier round closed by a reason. It refuses a folder inside the repository, a folder that is not new or empty, a commit that does not hold a board, views that are missing, and round fields of the set in use that are missing or malformed, the set being a parameter of the command, a narrow round without its reasons, changed regions or why-others line included. An add-view mode adds a rendered view and its command to a folder the command wrote, in the folder and in the round file's Views field, and records the item whose cannot judge asked for it with that Why, and refuses a view that does not exist or a folder the command did not write. The review seeding command's copy of the commit's files is generalised to take the repository, commit and design, with the documents optionally from a second repository, rendering stays in the seeding command, and the seeding command's existing tests still pass. Out of scope: rendering the views and running the check.
        out, seeds = os.path.join(self.root, "review"), os.path.join(self.root, "seeds.json")
        self.assertEqual(review_seed.keep_refusals(os.path.join(self.root, "kept"), seeds, out), [])
        for keep, word in ((os.path.join(REPO, "kept"), "is inside the repository"), (os.path.join(out, "kept"), "hold one another"),
                           (self.root, "hold one another"), (os.path.join(self.root, "seeds.json", "kept"), "")):
            if not word:
                continue
            self.assertIn(word, "; ".join(review_seed.keep_refusals(keep, seeds, out)), keep)
        held = os.path.join(self.root, "held")
        os.makedirs(held)
        fx.write(os.path.join(held, "a.txt"), "a")
        self.assertIn("already holds files", "; ".join(review_seed.keep_refusals(held, seeds, out)))
        fx.write(os.path.join(self.root, "afile"), "a")
        self.assertIn("is a file", "; ".join(review_seed.keep_refusals(os.path.join(self.root, "afile"), seeds, out)))
        self.assertIn("the seed list", "; ".join(review_seed.keep_refusals(os.path.join(self.root, "kept"), os.path.join(self.root, "kept", "s.json"), out)))

    def test_a_refused_flag_stops_the_command_before_anything_is_made(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C5: Over a synthetic repository with a committed board, a command writes a review folder outside the repository holding the board's design files as the commit holds them, its plan, rules table and the records those name, the method, the hardware notes, the rendered views and placement view the round's first step names, and the check's report, together with one round file holding the round's number, kind, commit judged, views, check lines and, for a narrow round, listed items with a reason for each, changed regions and the line saying why every other item is not judged, taken from the command's arguments, and holds no session or notes file and no other file the commit does not hold; it holds no review record for a first round, and for a later round only the earlier rounds of the record as recorded, because a verdict row may cite a finding an earlier round closed by a reason. It refuses a folder inside the repository, a folder that is not new or empty, a commit that does not hold a board, views that are missing, and round fields of the set in use that are missing or malformed, the set being a parameter of the command, a narrow round without its reasons, changed regions or why-others line included. An add-view mode adds a rendered view and its command to a folder the command wrote, in the folder and in the round file's Views field, and records the item whose cannot judge asked for it with that Why, and refuses a view that does not exist or a folder the command did not write. The review seeding command's copy of the commit's files is generalised to take the repository, commit and design, with the documents optionally from a second repository, rendering stays in the seeding command, and the seeding command's existing tests still pass. Out of scope: rendering the views and running the check.
        out = io.StringIO()
        inside = os.path.join(REPO, "never-kept")
        with contextlib.redirect_stdout(out):
            status = review_seed.main(["--seeds", os.path.join(self.root, "s.json"), "--out", os.path.join(self.root, "review"),
                                       "--keep-work-tree", inside])
        self.assertEqual(status, 1)
        self.assertIn("REFUSED | the work tree folder", out.getvalue())
        self.assertFalse(os.path.exists(inside))

    def fake_tools(self):
        """The seeding command with KiCad and the check stood in for: the seeds are placed for real in the copy, the check
        passes it after committing it, and the views are not rendered."""
        def check(seed, kicad_cli):
            board_prove.git(seed, "add", "-A")
            fx.git(seed.root, "commit", "-q", "--allow-empty", "-m", "seeded copy")
            return 0, ["DESIGN | x | PASS"], ""

        def assemble(seed, out, report, kicad_cli, resvg):
            os.makedirs(out, exist_ok=True)
            return True, "RESULT | views\nRESULT | placement"
        return [mock.patch.object(review_seed.board_check, name, lambda *a, **k: None)
                for name in ("require_python", "require_yaml", "require_kicad")] + [
            mock.patch.object(review_seed, "settle_layout", lambda seed, kicad: None),
            mock.patch.object(review_seed.board_prove, "check", check), mock.patch.object(review_seed, "assemble", assemble)]

    def run_seed(self, *extra):
        out = io.StringIO()
        with contextlib.ExitStack() as stack, contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            for patch in self.fake_tools():
                stack.enter_context(patch)
            status = review_seed.main(["--seeds", os.path.join(self.root, "seeds.json"), "--out", os.path.join(self.root, "review"),
                                       *extra])
        return status, out.getvalue().splitlines()

    def test_the_flag_keeps_the_seeded_copys_work_tree_and_names_its_commit_and_without_it_nothing_is_kept(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C5: Over a synthetic repository with a committed board, a command writes a review folder outside the repository holding the board's design files as the commit holds them, its plan, rules table and the records those name, the method, the hardware notes, the rendered views and placement view the round's first step names, and the check's report, together with one round file holding the round's number, kind, commit judged, views, check lines and, for a narrow round, listed items with a reason for each, changed regions and the line saying why every other item is not judged, taken from the command's arguments, and holds no session or notes file and no other file the commit does not hold; it holds no review record for a first round, and for a later round only the earlier rounds of the record as recorded, because a verdict row may cite a finding an earlier round closed by a reason. It refuses a folder inside the repository, a folder that is not new or empty, a commit that does not hold a board, views that are missing, and round fields of the set in use that are missing or malformed, the set being a parameter of the command, a narrow round without its reasons, changed regions or why-others line included. An add-view mode adds a rendered view and its command to a folder the command wrote, in the folder and in the round file's Views field, and records the item whose cannot judge asked for it with that Why, and refuses a view that does not exist or a folder the command did not write. The review seeding command's copy of the commit's files is generalised to take the repository, commit and design, with the documents optionally from a second repository, rendering stays in the seeding command, and the seeding command's existing tests still pass. Out of scope: rendering the views and running the check.
        status, lines = self.run_seed()
        self.assertEqual(status, 0, lines)
        self.assertFalse([line for line in lines if line.startswith("KEPT |")], "nothing is kept or named without the flag")
        shutil.rmtree(os.path.join(self.root, "review"))
        kept = os.path.join(self.root, "kept")
        status, lines = self.run_seed("--keep-work-tree", kept)
        self.assertEqual(status, 0, lines)
        mark = next(line for line in lines if line.startswith("KEPT |")).split(" | ")
        repository = os.path.join(kept, "repository")
        self.assertEqual(mark[1], repository)
        self.assertEqual(mark[2], fx.git(repository, "rev-parse", "HEAD"))
        self.assertTrue(os.path.isfile(os.path.join(repository, review_seed.DESIGN, review_seed.NAME + ".kicad_pcb")))
        self.assertGreater(len(review_seed.design_files(repository, mark[2], review_seed.DESIGN)), 3)
        self.assertEqual(lines[-1], f"RESULT | WRITTEN | {os.path.join(self.root, 'review')}")

    def test_a_command_that_fails_keeps_nothing(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C5: Over a synthetic repository with a committed board, a command writes a review folder outside the repository holding the board's design files as the commit holds them, its plan, rules table and the records those name, the method, the hardware notes, the rendered views and placement view the round's first step names, and the check's report, together with one round file holding the round's number, kind, commit judged, views, check lines and, for a narrow round, listed items with a reason for each, changed regions and the line saying why every other item is not judged, taken from the command's arguments, and holds no session or notes file and no other file the commit does not hold; it holds no review record for a first round, and for a later round only the earlier rounds of the record as recorded, because a verdict row may cite a finding an earlier round closed by a reason. It refuses a folder inside the repository, a folder that is not new or empty, a commit that does not hold a board, views that are missing, and round fields of the set in use that are missing or malformed, the set being a parameter of the command, a narrow round without its reasons, changed regions or why-others line included. An add-view mode adds a rendered view and its command to a folder the command wrote, in the folder and in the round file's Views field, and records the item whose cannot judge asked for it with that Why, and refuses a view that does not exist or a folder the command did not write. The review seeding command's copy of the commit's files is generalised to take the repository, commit and design, with the documents optionally from a second repository, rendering stays in the seeding command, and the seeding command's existing tests still pass. Out of scope: rendering the views and running the check.
        kept = os.path.join(self.root, "kept")
        failing = lambda seed, out, report, kicad, resvg: (False, "no views")  # noqa: E731
        out = io.StringIO()
        with contextlib.ExitStack() as stack, contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            for patch in self.fake_tools():
                stack.enter_context(patch)
            stack.enter_context(mock.patch.object(review_seed, "assemble", failing))
            status = review_seed.main(["--seeds", os.path.join(self.root, "seeds.json"), "--out", os.path.join(self.root, "review"),
                                       "--keep-work-tree", kept])
        self.assertEqual(status, 2)
        self.assertFalse(os.path.exists(kept), "a seeded copy the command could not finish is not kept")

    def test_without_the_flag_the_temporary_folder_is_deleted_and_with_it_the_folder_is_left(self):
        # SOL-HW-REVIEW-FAN-OUT-LAYOUT.C5: Over a synthetic repository with a committed board, a command writes a review folder outside the repository holding the board's design files as the commit holds them, its plan, rules table and the records those name, the method, the hardware notes, the rendered views and placement view the round's first step names, and the check's report, together with one round file holding the round's number, kind, commit judged, views, check lines and, for a narrow round, listed items with a reason for each, changed regions and the line saying why every other item is not judged, taken from the command's arguments, and holds no session or notes file and no other file the commit does not hold; it holds no review record for a first round, and for a later round only the earlier rounds of the record as recorded, because a verdict row may cite a finding an earlier round closed by a reason. It refuses a folder inside the repository, a folder that is not new or empty, a commit that does not hold a board, views that are missing, and round fields of the set in use that are missing or malformed, the set being a parameter of the command, a narrow round without its reasons, changed regions or why-others line included. An add-view mode adds a rendered view and its command to a folder the command wrote, in the folder and in the round file's Views field, and records the item whose cannot judge asked for it with that Why, and refuses a view that does not exist or a folder the command did not write. The review seeding command's copy of the commit's files is generalised to take the repository, commit and design, with the documents optionally from a second repository, rendering stays in the seeding command, and the seeding command's existing tests still pass. Out of scope: rendering the views and running the check.
        with review_seed.scratch_folder(None) as temporary:
            self.assertTrue(os.path.isdir(temporary))
            self.assertTrue(os.path.basename(temporary).startswith("review-seed-"))
        self.assertFalse(os.path.exists(temporary))
        kept = os.path.join(self.root, "kept")
        with review_seed.scratch_folder(kept) as folder:
            self.assertEqual(folder, kept)
        self.assertTrue(os.path.isdir(kept))


if __name__ == "__main__":
    unittest.main()
