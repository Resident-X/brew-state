#!/usr/bin/env python3
"""The seeding command of the layout review's blind proof, against KiCad itself.

The command is run as shipped, on a copy of hardware/proof/review-proof in a
temporary git work tree outside the repository, with the real kicad-cli named by
KICAD_CLI and the real resvg named by RESVG (or found on the search path).
Nothing is skipped when a tool is absent: a missing tool fails the run, because a
command that cannot be exercised has not been shown to work.

What these tests cannot do is the review itself, which a reviewing session does
from the folder the command writes; they show that the folder and the seed list
are what that review needs and nothing more.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import re
import shutil
import sys
import tempfile
import unittest
from unittest import mock

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)

import board_check  # noqa: E402
import board_prove  # noqa: E402
import review_seed  # noqa: E402
import sexpr  # noqa: E402

REPO = os.path.dirname(os.path.dirname(TOOLS))
KICAD_CLI = os.environ.get("KICAD_CLI") or "kicad-cli"
RESVG = os.environ.get("RESVG") or "resvg"
METHOD = os.path.join(REPO, "docs", "board-design-method.md")


def setUpModule():
    board_check.require_kicad(KICAD_CLI)


def run(argv):
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
        status = review_seed.main(argv)
    return status, out.getvalue().splitlines()


def catalogue_items():
    with open(METHOD, encoding="utf-8") as handle:
        return re.findall(r"^#### ([A-Z]+-\d+)\. ", handle.read(), re.M)


def contents(folder):
    """Every file directly in `folder`, by name, as bytes."""
    found = {}
    for name in os.listdir(folder):
        if os.path.isfile(os.path.join(folder, name)):
            with open(os.path.join(folder, name), "rb") as handle:
                found[name] = handle.read()
    return found


def files_under(folder):
    return sorted(os.path.relpath(os.path.join(directory, name), folder)
                  for directory, _, names in os.walk(folder) for name in names)


class TheSeededReviewFolder(unittest.TestCase):
    """SOL-BOARD-LAYOUT-REVIEW-SEEDED-PROOF.C1: Following the review step blind on a seeded copy of a proof design reports every seeded layout defect."""

    @classmethod
    def setUpClass(cls):
        cls.work = tempfile.mkdtemp(prefix="review-seed-test-")
        cls.out = os.path.join(cls.work, "review")
        cls.seeds = os.path.join(cls.work, "seeds.json")
        cls.status, cls.lines = run(["--seeds", cls.seeds, "--out", cls.out, "--kicad-cli", KICAD_CLI, "--resvg", RESVG])

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.work, ignore_errors=True)

    def test_the_seeded_copy_passes_the_pre_order_check_and_the_folder_is_written(self):
        # SOL-BOARD-LAYOUT-REVIEW-SEEDED-PROOF.C1: Every seed leaves the copy passing the automated pre-order check, as a real board does before its review begins.
        self.assertEqual(self.status, 0, "\n".join(self.lines))
        self.assertEqual(self.lines[-1], f"RESULT | WRITTEN | {self.out}")
        with open(os.path.join(self.out, review_seed.REPORT), encoding="utf-8") as handle:
            report = handle.read().splitlines()
        self.assertIn(f"DESIGN | {review_seed.DESIGN}/{review_seed.NAME}.kicad_pro | PASS", report)
        self.assertEqual(report[-1], "RESULT | PASS | all 1 designs passed")

    def test_the_folder_holds_only_what_the_review_step_gives_a_reviewer(self):
        # SOL-BOARD-LAYOUT-REVIEW-SEEDED-PROOF.C1: The review is given only the copy's design files, the checklist, the rendered views, the pre-order check's report on the copy, and the committed floorplan and plan.
        self.assertEqual(sorted(os.listdir(self.out)), ["check-report.txt", "docs", "hardware", "views"])
        files = files_under(self.out)
        others = [path for path in files if not path.startswith(("views/", review_seed.DESIGN + "/"))]
        self.assertEqual(others, ["check-report.txt", "docs/board-design-method.md", "hardware/README.md"])
        design = [path for path in files if path.startswith(review_seed.DESIGN + "/")]
        for name in ("layout-plan.md", "design-rules.md", "constraints.md", "separation-basis.yaml",
                     "review-proof.kicad_pro", "review-proof.kicad_sch", "review-proof.kicad_pcb", "review-proof.kicad_dru"):
            self.assertIn(f"{review_seed.DESIGN}/{name}", design)
        with open(METHOD, encoding="utf-8") as mine, open(os.path.join(self.out, "docs", "board-design-method.md"),
                                                         encoding="utf-8") as given:
            self.assertEqual(given.read(), mine.read(), "the method is given as written")
        with open(os.path.join(self.out, "views", "index.txt"), encoding="utf-8") as handle:
            index = handle.read()
        for view in ("layer-F.Cu", "layer-In1.Cu", "layer-B.Cu", "classes", "assembly-top", "crop-U4", "net-_GND", "3d-angled"):
            self.assertIn(view, index)
        self.assertTrue(os.path.exists(os.path.join(self.out, "views", "facts.txt")))

    def test_the_copy_carries_the_seeds_and_the_committed_design_does_not(self):
        # SOL-BOARD-LAYOUT-REVIEW-SEEDED-PROOF.C1: The seeding script writes a copy of the clean proof design outside the tracked tree carrying deliberately placed layout defects.
        def ground_zones(path):
            with open(path, encoding="utf-8") as handle:
                tree = sexpr.parse_one(handle.read())
            return review_seed.zones(tree, review_seed.GND)
        self.assertEqual(ground_zones(os.path.join(self.out, review_seed.DESIGN, "review-proof.kicad_pcb")), [])
        self.assertEqual(len(ground_zones(os.path.join(REPO, review_seed.DESIGN, "review-proof.kicad_pcb"))), 4)
        self.assertFalse(review_seed.inside(self.out, REPO))

    def test_the_seed_list_is_written_apart_with_each_seed_located(self):
        # SOL-BOARD-LAYOUT-REVIEW-SEEDED-PROOF.C1: The script records the list of seeded defects and where each lies apart from the copy, where the review cannot read it.
        with open(self.seeds, encoding="utf-8") as handle:
            listed = json.load(handle)
        self.assertEqual(listed["design"], review_seed.DESIGN)
        self.assertEqual([seed["id"] for seed in listed["seeds"]], [seed[0] for seed in review_seed.SEEDS])
        items = set(catalogue_items())
        for seed in listed["seeds"]:
            self.assertEqual(set(seed), {"id", "item", "layer", "position", "description"})
            self.assertIn(seed["item"], items)
            self.assertTrue(seed["layer"] and seed["description"])
            self.assertIsInstance(seed["position"]["x"], (int, float))
            self.assertIsInstance(seed["position"]["y"], (int, float))
        self.assertFalse(review_seed.inside(self.seeds, self.out))

    def test_nothing_in_the_folder_names_the_seeds_or_the_repository(self):
        # SOL-BOARD-LAYOUT-REVIEW-SEEDED-PROOF.C1: The reviewing session has no record of what was seeded or where.
        tell = [REPO, os.path.realpath(REPO), self.seeds] + [seed[4] for seed in review_seed.SEEDS]
        for path in files_under(self.out):
            if path.endswith(".png"):
                continue
            with open(os.path.join(self.out, path), encoding="utf-8", errors="replace") as handle:
                text = handle.read()
            for word in tell:
                self.assertNotIn(word, text, f"{path} names {word!r}")


class TheSeeds(unittest.TestCase):
    """SOL-BOARD-LAYOUT-REVIEW-SEEDED-PROOF.C1: Following the review step blind on a seeded copy of a proof design reports every seeded layout defect."""

    def test_every_catalogue_area_has_a_seed_and_the_named_defects_are_among_them(self):
        # SOL-BOARD-LAYOUT-REVIEW-SEEDED-PROOF.C1: At least one seeded defect for each area the catalogue covers, and among them ground drawn as thin traces, a decoupling capacitor routed the long way round to its pin, low-voltage copper inside the mains region, and a high-current pad without the copper it needs.
        items = catalogue_items()
        areas = {item.split("-")[0] for item in items}
        self.assertEqual(len(areas), 11, areas)
        seeded = [seed[1] for seed in review_seed.SEEDS]
        self.assertEqual(areas - {item.split("-")[0] for item in seeded}, set(), "a catalogue area has no seed")
        self.assertLessEqual({"GROUND-1", "DECOUPLE-1", "MAINS-2", "POWER-5"}, set(seeded))
        self.assertEqual(set(seeded) - set(items), set(), "a seed names an item the catalogue does not hold")
        self.assertEqual(len({seed[0] for seed in review_seed.SEEDS}), len(review_seed.SEEDS), "two seeds share an identifier")

    def test_each_seed_changes_the_copy(self):
        # SOL-BOARD-LAYOUT-REVIEW-SEEDED-PROOF.C1: Each seed is a deliberately placed layout defect in the copy.
        for ident, _, _, _, _, edit in review_seed.SEEDS:
            with self.subTest(seed=ident), tempfile.TemporaryDirectory() as scratch:
                seed = board_prove.prepare(scratch, review_seed.DESIGN, review_seed.NAME)
                before = contents(seed.design)
                edit(seed)
                self.assertNotEqual(contents(seed.design), before, f"seed {ident} changed nothing")

    def test_a_seed_the_check_catches_is_refused_and_nothing_is_written(self):
        # SOL-BOARD-LAYOUT-REVIEW-SEEDED-PROOF.C1: The script refuses a copy that does not pass the pre-order check.
        caught = ("X1", "MAINS-1", "F.Cu", (0, 0), "a separation rule below the signed figure",
                  lambda seed: seed.replace(".kicad_dru", "(constraint clearance (min 3mm))", "(constraint clearance (min 2mm))"))
        with tempfile.TemporaryDirectory() as work, mock.patch.object(review_seed, "SEEDS", [caught]):
            out, seeds = os.path.join(work, "review"), os.path.join(work, "seeds.json")
            status, lines = run(["--seeds", seeds, "--out", out, "--kicad-cli", KICAD_CLI, "--resvg", RESVG])
            self.assertEqual(status, 1, lines)
            self.assertTrue(lines[0].startswith("REFUSED | the pre-order check fails the seeded copy"), lines)
            self.assertTrue(any("separation_rule" in line for line in lines), lines)
            self.assertEqual(lines[-1], "RESULT | REFUSED | nothing was written")
            self.assertFalse(os.path.exists(out))
            self.assertFalse(os.path.exists(seeds))

    def test_the_prompt_names_nothing_seeded(self):
        # SOL-BOARD-LAYOUT-REVIEW-SEEDED-PROOF.C1: The reviewing session has no record of what was seeded or where, and follows the method's review step as written.
        status, lines = run(["--print-prompt"])
        self.assertEqual(status, 0)
        prompt = "\n".join(lines)
        self.assertIn('"Layout review" section of docs/board-design-method.md', prompt)
        self.assertIn("views/index.txt", prompt)
        self.assertIn("check-report.txt", prompt)
        for ident, item, _, _, description, _ in review_seed.SEEDS:
            self.assertNotIn(item, prompt)
            self.assertNotIn(description, prompt)
        self.assertNotIn("seed", prompt.lower())


class TheRefusals(unittest.TestCase):
    """SOL-BOARD-LAYOUT-REVIEW-SEEDED-PROOF.C1: Following the review step blind on a seeded copy of a proof design reports every seeded layout defect."""

    def setUp(self):
        self.work = tempfile.mkdtemp(prefix="review-seed-refusals-")
        self.out = os.path.join(self.work, "review")

    def tearDown(self):
        shutil.rmtree(self.work, ignore_errors=True)

    def refused(self, seeds, out, because):
        status, lines = run(["--seeds", seeds, "--out", out, "--kicad-cli", KICAD_CLI, "--resvg", RESVG])
        self.assertEqual(status, 1, lines)
        self.assertTrue(any(line.startswith("REFUSED | ") and because in line for line in lines), lines)
        self.assertEqual(lines[-1], "RESULT | REFUSED | nothing was written")
        self.assertFalse(os.path.exists(seeds))

    def test_a_seed_list_inside_the_review_folder_is_refused(self):
        # SOL-BOARD-LAYOUT-REVIEW-SEEDED-PROOF.C1: The seed list is kept apart from the copy, where the review cannot read it.
        self.refused(os.path.join(self.out, "seeds.json"), self.out, "is inside the review folder")
        self.assertFalse(os.path.exists(self.out))

    def test_a_seed_list_inside_a_design_folder_is_refused(self):
        # SOL-BOARD-LAYOUT-REVIEW-SEEDED-PROOF.C1: The seed list is kept apart from the copy, where the review cannot read it.
        design = os.path.join(self.work, "board", "deeper")
        os.makedirs(design)
        with open(os.path.join(self.work, "board", "board.kicad_pro"), "w", encoding="utf-8") as handle:
            handle.write("{}")
        self.refused(os.path.join(design, "seeds.json"), self.out, "is inside the design folder")

    def test_a_review_folder_inside_the_repository_is_refused(self):
        # SOL-BOARD-LAYOUT-REVIEW-SEEDED-PROOF.C1: The reviewing session has no record of what was seeded or where.
        self.refused(os.path.join(self.work, "seeds.json"), os.path.join(REPO, "review-folder-that-must-not-be-made"),
                     "is inside the repository")
        self.assertFalse(os.path.exists(os.path.join(REPO, "review-folder-that-must-not-be-made")))

    def test_a_review_folder_already_holding_files_is_refused(self):
        # SOL-BOARD-LAYOUT-REVIEW-SEEDED-PROOF.C1: The review is given only what the review step gives a reviewer.
        os.makedirs(self.out)
        with open(os.path.join(self.out, "left-over.txt"), "w", encoding="utf-8") as handle:
            handle.write("from an earlier run")
        self.refused(os.path.join(self.work, "seeds.json"), self.out, "already holds files")
        self.assertEqual(os.listdir(self.out), ["left-over.txt"])

    def test_a_review_folder_that_is_a_file_is_refused(self):
        # SOL-BOARD-LAYOUT-REVIEW-SEEDED-PROOF.C1: The review is given only what the review step gives a reviewer.
        with open(self.out, "w", encoding="utf-8") as handle:
            handle.write("not a folder")
        self.refused(os.path.join(self.work, "seeds.json"), self.out, "is a file")


class TheGeneralisedSeed(unittest.TestCase):
    """SOL-BOARD-LAYOUT-REVIEW-SEEDED-PROOF.C1: Following the review step blind on a seeded copy of a proof design reports every seeded layout defect."""

    def test_the_seeded_fault_mechanics_copy_the_design_they_are_given(self):
        # SOL-BOARD-LAYOUT-REVIEW-SEEDED-PROOF.C1: The seeding script writes a copy of the proof design outside the tracked tree, by the pre-order check's own seeded-fault mechanics.
        with tempfile.TemporaryDirectory() as scratch:
            seed = board_prove.prepare(scratch, review_seed.DESIGN, review_seed.NAME)
            self.assertEqual(seed.name, review_seed.NAME)
            self.assertTrue(os.path.isfile(seed.path(".kicad_pcb")))
            self.assertFalse(os.path.exists(os.path.join(seed.root, board_prove.DESIGN)))
            self.assertFalse(review_seed.inside(seed.root, REPO))
            default = board_prove.prepare(os.path.join(scratch, "default"))
            self.assertEqual(default.name, board_prove.NAME)
            self.assertTrue(os.path.isfile(default.path(".kicad_pcb")))
            self.assertTrue(default.path(".kicad_pcb").endswith(os.path.join(board_prove.DESIGN, "gate-proof.kicad_pcb")))


if __name__ == "__main__":
    unittest.main()
