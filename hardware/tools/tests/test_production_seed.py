#!/usr/bin/env python3
"""The seeding command of the ordering step's blind proof, against KiCad and gerbonara themselves.

The command is run as shipped, on a copy of hardware/proof/review-proof in a
temporary git work tree outside the repository, with the real kicad-cli named by
KICAD_CLI, the real resvg named by RESVG (or found on the search path) and the
Python that holds gerbonara 1.6.3 named by GERBONARA_PYTHON (or python3 on the
search path). Nothing is skipped when a tool is absent: a missing tool fails the
run with a CANNOT RUN line naming it, because a command that cannot be exercised
has not been shown to work.

What these tests cannot do is the check itself, which a session following the
ordering step does from the folder the command writes; they show that the folder
and the seed list are what that check needs and nothing more, and that every seed
lands in the file it names.
"""

from __future__ import annotations

import contextlib
import csv
import io
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)

import board_fixtures  # noqa: E402
import board_prove  # noqa: E402
import production_files  # noqa: E402
import production_seed  # noqa: E402
import review_seed  # noqa: E402
import sexpr  # noqa: E402

REPO = os.path.dirname(os.path.dirname(TOOLS))
KICAD_CLI = os.environ.get("KICAD_CLI") or "kicad-cli"
RESVG = os.environ.get("RESVG") or "resvg"
GERBONARA_PYTHON = os.environ.get("GERBONARA_PYTHON") or "python3"
METHOD = os.path.join(REPO, "docs", "board-design-method.md")
README = os.path.join(REPO, "hardware", "README.md")
CRITERION = "SOL-BOARD-PRODUCTION-FILES-CHECKED-BEFORE-PAYMENT"


def setUpModule():
    board_fixtures.require_tools(KICAD_CLI, RESVG)
    board_fixtures.require_gerbonara(GERBONARA_PYTHON)


def run(argv):
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
        status = production_seed.main(argv)
    return status, out.getvalue().splitlines()


def tools():
    return ["--kicad-cli", KICAD_CLI, "--resvg", RESVG, "--gerbonara-python", GERBONARA_PYTHON]


def files_under(folder):
    return sorted(os.path.relpath(os.path.join(directory, name), folder)
                  for directory, _, names in os.walk(folder) for name in names)


def read_csv(path):
    with open(path, encoding="utf-8", newline="") as handle:
        return list(csv.reader(handle))


#: Phrases that say which defects the seeding command places. They belong in no file a follower reads, and none of them is in the step's own checks.
SEED_KINDS = ("a part rotated", "polarised part reversed", "first pin turned and a part moved",
              "number replaced", "replaced by another",
              "is missing content", "missing content, shifted and mirrored", "polarised surface-mount diode")


def seed_kinds_in(text):
    squeezed = re.sub(r"\s+", " ", text)
    return [phrase for phrase in SEED_KINDS if phrase in squeezed]


def ordering_section():
    with open(METHOD, encoding="utf-8") as handle:
        found = re.search(r"^## Ordering[ \t]*\n(.*?)(?=^## |\Z)", handle.read(), re.M | re.S)
    return found.group(1) if found else ""


class TheSeededProductionFolder(unittest.TestCase):
    """SOL-BOARD-PRODUCTION-FILES-CHECKED-BEFORE-PAYMENT.C3: Following the ordering step blind on seeded production files finds every seeded defect."""

    @classmethod
    def setUpClass(cls):
        cls.work = tempfile.mkdtemp(prefix="production-seed-test-")
        cls.out = os.path.join(cls.work, "production")
        cls.seeds = os.path.join(cls.work, "seeds.json")
        cls.status, cls.lines = run(["--seeds", cls.seeds, "--out", cls.out] + tools())
        scratch = os.path.join(cls.work, "clean")
        clean = board_prove.prepare(scratch, production_seed.DESIGN, production_seed.NAME)
        cls.clean_rows, cls.clean_parts = production_seed.export_parts(clean, KICAD_CLI, os.path.join(scratch, "parts"))
        production_seed.export_fabrication(clean, KICAD_CLI, os.path.join(scratch, "files"))
        cls.clean_files = production_seed.fabrication_files(os.path.join(scratch, "files"))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.work, ignore_errors=True)

    def test_the_folder_and_the_seed_list_are_written_and_each_seed_is_reported_landed(self):
        # SOL-BOARD-PRODUCTION-FILES-CHECKED-BEFORE-PAYMENT.C3: Following the ordering step blind on seeded production files finds every seeded defect
        self.assertEqual(self.status, 0, "\n".join(self.lines))
        self.assertEqual(self.lines[-1], f"RESULT | WRITTEN | {self.out}")
        self.assertEqual([line for line in self.lines if line.startswith("SEED | ")],
                         [f"SEED | {seed.ident} | landed | {seed.target}" for seed in production_seed.SEEDS])
        self.assertIn(f"SEEDS | {len(production_seed.SEEDS)} seeds | {self.seeds}", self.lines)
        for kind in ("LAYERS", "VIEWS", "PLACEMENT"):
            self.assertTrue(any(line.startswith(f"{kind} | RESULT | WRITTEN | ") for line in self.lines), self.lines)

    def test_the_folder_holds_only_what_the_ordering_step_gives_a_follower(self):
        # SOL-BOARD-PRODUCTION-FILES-CHECKED-BEFORE-PAYMENT.C3: Following the ordering step blind on seeded production files finds every seeded defect
        self.assertEqual(sorted(os.listdir(self.out)), ["docs", "hardware", "placement", "production", "views"])
        files = files_under(self.out)
        others = [path for path in files if not path.startswith(("views/", "placement/", "production/"))]
        self.assertEqual(others, ["docs/board-design-method.md", "docs/board-manufacturer-jlcpcb.md",
                                  "hardware/README.md", "hardware/proof/review-proof/parts-specification.yaml"])
        production = sorted(path for path in files if path.startswith("production/") and not path.startswith(
            ("production/layers/", "production/gerbers/", "production/footprints/")))
        self.assertEqual(production, ["production/parts-list.csv", "production/placement.csv"])
        self.assertEqual(sorted(os.listdir(os.path.join(self.out, "production", "layers"))),
                         sorted(["index.txt", "index.json"] + [f"layer-{name}.png" for name in (
                             "F.Cu", "F.Mask", "F.SilkS", "B.Cu", "B.Mask", "B.SilkS", "In1.Cu", "In2.Cu", "Edge.Cuts", "drill")]))
        gerbers = sorted(os.listdir(os.path.join(self.out, "production", "gerbers")))
        self.assertEqual(gerbers, sorted(self.clean_files), "the exported files are not the commands' files")
        views = sorted(os.listdir(os.path.join(self.out, "views")))
        for name in ("index.txt", "index.json", "facts.txt", "assembly-top-r1c1.png", "assembly-bottom-r1c1.png", "3d-top.png",
                     "3d-bottom.png", "layer-F.Cu-r1c1.png", "layer-F.SilkS-r1c1.png", "layer-F.Mask-r1c1.png"):
            self.assertIn(name, views)
        placement = sorted(os.listdir(os.path.join(self.out, "placement")))
        self.assertLessEqual({"index.txt", "index.json", "measures.txt", "measures.json"}, set(placement))
        for document in production_seed.DOCUMENTS:
            with open(os.path.join(self.out, document), "rb") as given:
                self.assertEqual(given.read(), board_prove.committed(document)[document], f"{document} is given as committed")
        record = production_seed.RECORD
        design = f"{production_seed.DESIGN}/{record}"
        with open(os.path.join(self.out, design), "rb") as given:
            self.assertEqual(given.read(), board_prove.committed(design)[design])

    def test_the_converted_placement_file_differs_from_the_designs_in_the_seeded_parts_only(self):
        # SOL-BOARD-PRODUCTION-FILES-CHECKED-BEFORE-PAYMENT.C1: The method's ordering step compares every placed part's position, rotation and polarity with the assembler's preview before payment
        # SOL-BOARD-PRODUCTION-FILES-CHECKED-BEFORE-PAYMENT.C3: Following the ordering step blind on seeded production files finds every seeded defect
        rows = read_csv(os.path.join(self.out, "production", "placement.csv"))
        self.assertEqual(rows[0], production_files.PLACEMENT_COLUMNS)
        seeded = {row[0]: row for row in rows[1:]}
        clean = {row[0]: row for row in self.clean_rows}
        self.assertEqual([row[0] for row in rows[1:]], [row[0] for row in self.clean_rows], "a part was dropped or reordered")
        self.assertEqual({key for key in clean if seeded[key] != clean[key]}, {"U3", "D1", "U4", "R4"})
        self.assertEqual(float(seeded["U3"][4]), (float(clean["U3"][4]) + 90) % 360, "a part rotated")
        self.assertEqual(float(seeded["D1"][4]), (float(clean["D1"][4]) + 180) % 360, "a polarised part reversed")
        self.assertEqual(float(seeded["U4"][4]), (float(clean["U4"][4]) + 90) % 360, "a first pin turned")
        self.assertEqual(seeded["U3"][1:4], clean["U3"][1:4])
        self.assertAlmostEqual(float(seeded["R4"][1]), float(clean["R4"][1]) + 4)
        self.assertEqual((seeded["R4"][2:]), clean["R4"][2:], "a part moved along X only")

    def test_the_parts_list_differs_from_the_designs_in_one_position_catalogue_number_only(self):
        # SOL-BOARD-PRODUCTION-FILES-CHECKED-BEFORE-PAYMENT.C1: The method's ordering step compares every placed part's position, rotation and polarity with the assembler's preview before payment
        # SOL-BOARD-PRODUCTION-FILES-CHECKED-BEFORE-PAYMENT.C3: Following the ordering step blind on seeded production files finds every seeded defect
        rows = read_csv(os.path.join(self.out, "production", "parts-list.csv"))
        self.assertEqual(rows[0], ["Designator", "Comment", "Footprint", "LCSC"])
        seeded = {row[0]: row for row in rows[1:]}
        clean = {row["Designator"]: [row[field] for field in rows[0]] for row in self.clean_parts}
        self.assertEqual(set(seeded), set(clean))
        self.assertEqual({key for key in clean if seeded[key] != clean[key]}, {"R2"})
        self.assertEqual(seeded["R2"][:3], clean["R2"][:3])
        self.assertEqual(seeded["R2"][3], production_seed.OTHER_NUMBER)
        self.assertNotEqual(seeded["R2"][3], clean["R2"][3])
        self.assertEqual(len(seeded), len(clean), "the seeded row is still a row of its own")
        self.assertEqual(sum(row[3] == seeded["R2"][3] for row in seeded.values()), 1, "no other position carries the number")
        self.assertNotIn(production_seed.OTHER_NUMBER, [row[3] for row in clean.values()])

    def test_the_exported_layers_differ_from_the_designs_in_the_seeded_layers_only(self):
        # SOL-BOARD-PRODUCTION-FILES-CHECKED-BEFORE-PAYMENT.C2: The method's ordering step has every rendered fabrication layer looked at before ordering
        # SOL-BOARD-PRODUCTION-FILES-CHECKED-BEFORE-PAYMENT.C3: Following the ordering step blind on seeded production files finds every seeded defect
        seeded = production_seed.fabrication_files(os.path.join(self.out, "production", "gerbers"))
        changed = sorted(name for name in seeded if seeded[name] != self.clean_files[name])
        self.assertEqual(changed, ["review-proof-B_Mask.gbs", "review-proof-F_Mask.gts", "review-proof-F_Silkscreen.gto", "review-proof.drl"])
        for name in seeded:
            if name.endswith((".gtl", ".gbl", ".g1", ".g2", ".gm1", ".gbo")):
                self.assertEqual(seeded[name], self.clean_files[name], f"{name} changed, though no seed names its layer")

    def test_the_layer_images_are_drawn_from_the_seeded_files_not_from_the_design(self):
        # SOL-BOARD-PRODUCTION-FILES-CHECKED-BEFORE-PAYMENT.C2: The method's ordering step has every rendered fabrication layer looked at before ordering
        with tempfile.TemporaryDirectory(prefix="production-seed-images-") as scratch:
            status = subprocess.run([GERBONARA_PYTHON, os.path.join(TOOLS, "production_files.py"), "render", "--gerbers",
                                     os.path.join(self.out, "production", "gerbers"), "--out", os.path.join(scratch, "again"),
                                     "--resvg", RESVG], capture_output=True, text=True)
            self.assertEqual(status.returncode, 0, status.stdout + status.stderr)
            for name in ("layer-F.SilkS.png", "layer-F.Mask.png", "layer-drill.png", "layer-F.Cu.png"):
                with open(os.path.join(scratch, "again", name), "rb") as again, \
                        open(os.path.join(self.out, "production", "layers", name), "rb") as given:
                    self.assertEqual(again.read(), given.read(), f"{name} is not the render of the seeded files")

    def test_the_seed_list_is_written_apart_with_each_seed_located(self):
        # SOL-BOARD-PRODUCTION-FILES-CHECKED-BEFORE-PAYMENT.C3: Following the ordering step blind on seeded production files finds every seeded defect
        with open(self.seeds, encoding="utf-8") as handle:
            listed = json.load(handle)
        self.assertEqual(listed["design"], production_seed.DESIGN)
        self.assertEqual([seed["id"] for seed in listed["seeds"]], [seed.ident for seed in production_seed.SEEDS])
        self.assertEqual(len({seed["id"] for seed in listed["seeds"]}), len(listed["seeds"]))
        for seed in listed["seeds"]:
            self.assertEqual(set(seed), {"id", "area", "target", "description"})
            self.assertTrue(all(isinstance(seed[key], str) and seed[key] for key in seed), seed)
        self.assertFalse(review_seed.inside(self.seeds, self.out))

    def test_the_folder_holds_the_drawing_of_every_placed_parts_footprint_at_rotation_0_with_the_rule_for_reading_a_rotation_against_it(self):
        # SOL-BOARD-PRODUCTION-FILES-CHECKED-BEFORE-PAYMENT.C3: Following the ordering step blind on seeded production files finds every seeded defect
        folder = os.path.join(self.out, "production", "footprints")
        with open(os.path.join(folder, "index.json"), encoding="utf-8") as handle:
            index = json.load(handle)
        drawn = {designator: image["file"] for image in index["images"] for designator in image["used_by"]}
        placed = [row[0] for row in read_csv(os.path.join(self.out, "production", "placement.csv"))[1:]]
        self.assertEqual(len(placed), 28)
        for designator in placed:
            self.assertIn(designator, drawn, f"the folder holds no drawing of {designator}'s footprint")
            self.assertTrue(os.path.isfile(os.path.join(folder, drawn[designator])), designator)
        self.assertEqual(sorted(os.listdir(folder)), sorted(["index.txt", "index.json"] + sorted(set(drawn.values()))))
        with open(os.path.join(folder, "index.txt"), encoding="utf-8") as handle:
            text = handle.read()
        self.assertIn(f"RULE | {production_files.ROTATION_RULE}", text)
        self.assertEqual(index["board"], f"{production_seed.NAME}.kicad_pcb", "the index names the board by file name only")

    def test_nothing_in_the_folder_names_the_seeds_or_the_repository(self):
        # SOL-BOARD-PRODUCTION-FILES-CHECKED-BEFORE-PAYMENT.C3: Following the ordering step blind on seeded production files finds every seeded defect
        tell = [REPO, os.path.realpath(REPO), self.seeds, "seeds.json", "production_seed", "production-seed"]
        tell += [seed.description for seed in production_seed.SEEDS] + [seed.area for seed in production_seed.SEEDS]
        for path in files_under(self.out):
            if path.endswith(".png"):
                continue
            with open(os.path.join(self.out, path), encoding="utf-8", errors="replace") as handle:
                text = handle.read()
            self.assertEqual(seed_kinds_in(text), [], f"{path} lists the seeded defects")
            if path in ("docs/board-design-method.md", "hardware/README.md"):
                continue  # the documents are the ones the repository commits, which name the command that makes this folder
            for word in tell:
                self.assertNotIn(word, text, f"{path} names {word!r}")
        for path in files_under(self.out):
            self.assertNotIn("seed", os.path.basename(path).lower(), path)

    def test_every_file_and_folder_carries_one_time(self):
        # SOL-BOARD-PRODUCTION-FILES-CHECKED-BEFORE-PAYMENT.C3: Following the ordering step blind on seeded production files finds every seeded defect
        times = {os.stat(os.path.join(directory, name)).st_mtime
                 for directory, folders, names in os.walk(self.out) for name in names + folders}
        times.add(os.stat(self.out).st_mtime)
        self.assertEqual(len(times), 1, "files in the folder carry different times, so an edited one stands out")

    def test_the_views_and_their_indexes_are_the_unseeded_designs_and_name_no_path_of_the_work_tree(self):
        # SOL-BOARD-PRODUCTION-FILES-CHECKED-BEFORE-PAYMENT.C3: Following the ordering step blind on seeded production files finds every seeded defect
        with open(os.path.join(self.out, "views", "index.txt"), encoding="utf-8") as handle:
            index = handle.read()
        self.assertIn("BOARD | hardware/proof/review-proof/review-proof.kicad_pcb", index)
        self.assertNotIn("production-seed-", index)
        self.assertNotIn(os.path.realpath(tempfile.gettempdir()), index)
        with open(os.path.join(self.out, "views", "index.json"), encoding="utf-8") as handle:
            self.assertNotIn("production-seed-", handle.read())

    def test_the_prompt_names_nothing_seeded_and_every_file_it_names_is_in_the_folder(self):
        # SOL-BOARD-PRODUCTION-FILES-CHECKED-BEFORE-PAYMENT.C3: Following the ordering step blind on seeded production files finds every seeded defect
        status, lines = run(["--print-prompt"])
        self.assertEqual(status, 0)
        prompt = "\n".join(lines)
        self.assertIn('"Ordering" section of docs/board-design-method.md', prompt)
        for seed in production_seed.SEEDS:
            self.assertNotIn(seed.description, prompt)
            self.assertNotIn(seed.area, prompt)
            self.assertNotIn(seed.target + " ", prompt.replace("\n", " "), f"the prompt names {seed.target}")
        self.assertNotIn("seed", prompt.lower())
        for path in ("production/placement.csv", "production/parts-list.csv", "hardware/proof/review-proof/parts-specification.yaml",
                     "production/gerbers/", "production/layers/", "production/footprints/", "placement/", "views/", "docs/board-manufacturer-jlcpcb.md",
                     "docs/board-design-method.md", "views/index.txt"):
            self.assertIn(path, prompt)
            self.assertTrue(os.path.exists(os.path.join(self.out, path)), f"the prompt names {path}, which the folder lacks")
        with open(os.path.join(self.out, "docs", "board-design-method.md"), encoding="utf-8") as handle:
            self.assertRegex(handle.read(), r"(?m)^## Ordering$")


class TheDocumentsAFollowerReads(unittest.TestCase):
    """SOL-BOARD-PRODUCTION-FILES-CHECKED-BEFORE-PAYMENT.C3: Following the ordering step blind on seeded production files finds every seeded defect."""

    def test_the_method_and_the_readme_say_the_files_are_seeded_without_saying_with_what(self):
        # SOL-BOARD-PRODUCTION-FILES-CHECKED-BEFORE-PAYMENT.C3: Following the ordering step blind on seeded production files finds every seeded defect
        for path in (METHOD, README):
            with open(path, encoding="utf-8") as handle:
                text = handle.read()
            self.assertEqual(seed_kinds_in(text), [], f"{os.path.basename(path)} lists the seeded defects")
        self.assertIn("seeds them with known defects", ordering_section())
        self.assertIn("seeds known defects into the placement file", open(README, encoding="utf-8").read())

    def test_the_prompt_says_nothing_of_the_seeded_defects(self):
        # SOL-BOARD-PRODUCTION-FILES-CHECKED-BEFORE-PAYMENT.C3: Following the ordering step blind on seeded production files finds every seeded defect
        self.assertEqual(seed_kinds_in(production_seed.PROMPT), [])

    def test_the_check_for_seeded_kinds_catches_the_lists_it_was_written_against(self):
        # SOL-BOARD-PRODUCTION-FILES-CHECKED-BEFORE-PAYMENT.C3: Following the ordering step blind on seeded production files finds every seeded defect
        listed = ("the seeded placement file, with a part rotated, a polarised part reversed, an integrated circuit's first pin\nturned "
                  "and a part moved; in the parts list, a position's catalogue number replaced by another's; a layer is missing content")
        self.assertEqual(seed_kinds_in(listed), ["a part rotated", "polarised part reversed", "first pin turned and a part moved",
                                                  "number replaced", "replaced by another", "is missing content"])
        self.assertEqual(seed_kinds_in("A part reversed or with its first pin turned differs; so that a part moved across a bound fails"), [])
        self.assertEqual(seed_kinds_in("seeds them with known defects"), [])


class TheSeeds(unittest.TestCase):
    """SOL-BOARD-PRODUCTION-FILES-CHECKED-BEFORE-PAYMENT.C3: Following the ordering step blind on seeded production files finds every seeded defect."""

    def test_the_seeds_include_a_rotated_part_a_reversed_polarised_part_and_each_kind_of_layer_defect(self):
        # SOL-BOARD-PRODUCTION-FILES-CHECKED-BEFORE-PAYMENT.C3: Following the ordering step blind on seeded production files finds every seeded defect
        areas = [seed.area for seed in production_seed.SEEDS]
        for area in ("placement file: rotation", "placement file: polarity", "placement file: first-pin orientation",
                     "placement file: position", "parts list: catalogue part", "fabrication layer: missing content",
                     "fabrication layer: shifted content", "fabrication layer: mirrored content"):
            self.assertIn(area, areas)
        self.assertEqual(len({seed.ident for seed in production_seed.SEEDS}), len(production_seed.SEEDS))
        self.assertEqual({seed.kind for seed in production_seed.SEEDS}, {"placement", "parts", "layer"})
        design = sexpr.parse_one(board_prove.committed(f"{production_seed.DESIGN}/{production_seed.NAME}.kicad_pcb")
                                 [f"{production_seed.DESIGN}/{production_seed.NAME}.kicad_pcb"].decode("utf-8"))
        references = {prop[2] for fp in sexpr.children(design, "footprint") for prop in sexpr.children(fp, "property") if prop[1] == "Reference"}
        for seed in production_seed.SEEDS:
            if seed.designator:
                self.assertIn(seed.designator, references, f"seed {seed.ident} names a part the design lacks")
        for seed in production_seed.SEEDS:
            if seed.kind == "layer":
                self.assertTrue(seed.files, f"layer seed {seed.ident} names no exported file it changes")

    def test_a_row_seed_changes_its_row_as_it_says_and_no_other(self):
        # SOL-BOARD-PRODUCTION-FILES-CHECKED-BEFORE-PAYMENT.C3: Following the ordering step blind on seeded production files finds every seeded defect
        rows = {"A": ["A", "10", "-5", "Top", "350"], "B": ["B", "1", "2", "Top", "0"]}
        production_seed.turned("A", 20)(rows)
        self.assertEqual(rows, {"A": ["A", "10", "-5", "Top", "10"], "B": ["B", "1", "2", "Top", "0"]})
        production_seed.moved("B", 4, -1.5)(rows)
        self.assertEqual(rows["B"], ["B", "5", "0.5", "Top", "0"])
        parts = {"R2": {"Designator": "R2", "LCSC": "C1"}, "R3": {"Designator": "R3", "LCSC": "C2"}}
        production_seed.number_replaced("R2", "C9")(parts)
        self.assertEqual((parts["R2"]["LCSC"], parts["R3"]["LCSC"]), ("C9", "C2"))
        with self.assertRaises(production_seed.Refused) as shared:
            production_seed.number_replaced("R2", "C2")(parts)
        self.assertIn("R3", str(shared.exception), "a number another position carries would share a row in a real export")
        self.assertEqual(parts["R2"]["LCSC"], "C9", "a refused edit changes nothing")

    def test_the_layer_seeds_edit_only_what_they_name(self):
        # SOL-BOARD-PRODUCTION-FILES-CHECKED-BEFORE-PAYMENT.C3: Following the ordering step blind on seeded production files finds every seeded defect
        def footprint(reference, layer, justify=None, at=(0, 0)):
            effects = ["effects", ["font", ["size", "1", "1"]]] + ([["justify"] + justify] if justify is not None else [])
            return ["footprint", "x", ["at", str(at[0]), str(at[1])],
                    ["property", "Reference", reference, ["at", "0", "0", "0"], ["layer", layer], effects],
                    ["property", "Value", "v", ["at", "0", "1", "0"], ["layer", "F.Fab"], list(effects)],
                    ["pad", "1", "thru_hole", "circle", ["at", "0", "0"], ["layers", "*.Cu", "*.Mask"]]]
        tree = ["kicad_pcb", footprint("A1", "F.SilkS"), footprint("B1", "F.SilkS", ["left"]), footprint("C1", "B.SilkS"),
                ["gr_text", "T", ["at", "1", "1"], ["layer", "F.SilkS"], ["effects", ["font", ["size", "1", "1"]]]]]
        production_seed.legend_mirrored(tree)
        justify = lambda node: sexpr.child(sexpr.child(node, "effects"), "justify")
        self.assertEqual(justify(sexpr.children(tree[1], "property")[0]), ["justify", "mirror"])
        self.assertEqual(justify(sexpr.children(tree[2], "property")[0]), ["justify", "left", "mirror"])
        self.assertIsNone(justify(sexpr.children(tree[1], "property")[1]), "a text on another layer was mirrored")
        self.assertIsNone(justify(sexpr.children(tree[3], "property")[0]), "a bottom-side text was mirrored")
        self.assertEqual(justify(tree[4]), ["justify", "mirror"])
        production_seed.legend_mirrored(tree)
        self.assertEqual(justify(sexpr.children(tree[2], "property")[0]), ["justify", "left", "mirror"], "mirrored twice")

        board = ["kicad_pcb", footprint("J1", "F.SilkS"), footprint("J2", "F.SilkS", at=(5, 5))]
        production_seed.mask_openings_missing("J1")(board)
        self.assertEqual(sexpr.child(sexpr.children(board[1], "pad")[0], "layers"), ["layers", "*.Cu"])
        self.assertEqual(sexpr.child(sexpr.children(board[2], "pad")[0], "layers"), ["layers", "*.Cu", "*.Mask"])
        production_seed.hole_moved("J2", 4, 4)(board)
        self.assertEqual(sexpr.child(board[2], "at")[1:], ["9", "9"])
        self.assertEqual(sexpr.child(board[1], "at")[1:], ["0", "0"])

    def test_a_seed_naming_a_part_the_design_lacks_is_refused(self):
        # SOL-BOARD-PRODUCTION-FILES-CHECKED-BEFORE-PAYMENT.C3: Following the ordering step blind on seeded production files finds every seeded defect
        absent = production_seed.Fault("X1", "placement file: rotation", "Z99", "a part the design lacks", "placement",
                                       production_seed.turned("Z99", 90), designator="Z99")
        with self.assertRaises(production_seed.Refused) as refused:
            production_seed.landed([absent], [["R1", "1", "2", "Top", "0"]], [{"Designator": "R1", "LCSC": "C1"}], KICAD_CLI, "", {})
        self.assertIn("seed X1 names Z99", str(refused.exception))


class TheMethodAndTheReadme(unittest.TestCase):
    """SOL-BOARD-PRODUCTION-FILES-CHECKED-BEFORE-PAYMENT.C1: The method's ordering step compares every placed part's position, rotation and polarity with the assembler's preview before payment."""

    def test_the_ordering_section_follows_the_layout_review_and_the_order_of_sections_names_it(self):
        # SOL-BOARD-PRODUCTION-FILES-CHECKED-BEFORE-PAYMENT.C1: The method's ordering step compares every placed part's position, rotation and polarity with the assembler's preview before payment
        with open(METHOD, encoding="utf-8") as handle:
            text = handle.read()
        headings = re.findall(r"(?m)^## (.+)$", text)
        self.assertEqual(headings[headings.index("Layout review") + 1], "Ordering")
        self.assertEqual(headings[headings.index("Ordering") + 1], "Layout review views")
        order = re.search(r"The sections after the tools, up to and including the ([^,]+), are carried out in the order they appear\.", text)
        self.assertIsNotNone(order)
        self.assertEqual(order.group(1), "ordering step")
        self.assertIn("the ordering step then checks the board's production files against the assembler's preview and on rendered layers "
                      "before the board is paid for", text)
        self.assertEqual(len(re.findall(r"(?m)^## Ordering$", text)), 1)

    def test_the_step_names_the_export_commands_the_seeding_command_runs(self):
        # SOL-BOARD-PRODUCTION-FILES-CHECKED-BEFORE-PAYMENT.C1: The method's ordering step compares every placed part's position, rotation and polarity with the assembler's preview before payment
        section = ordering_section()
        for template, last in ((production_seed.POSITIONS_COMMAND, "--output"), (production_seed.PARTS_COMMAND, "--output"),
                               (production_seed.GERBERS_COMMAND, "--layers"), (production_seed.DRILL_COMMAND, "--output")):
            self.assertIn(" ".join(["kicad-cli"] + template[:template.index(last) + 1]), section)
        layers = production_seed.GERBERS_COMMAND[production_seed.GERBERS_COMMAND.index("--layers") + 1]
        self.assertEqual(layers, f"{production_seed.COPPER},F.Mask,B.Mask,F.SilkS,B.SilkS,Edge.Cuts")
        self.assertIn('--layers "<each copper layer>,F.Mask,B.Mask,F.SilkS,B.SilkS,Edge.Cuts"', section)
        self.assertIn("kicad-cli pcb export drill --output <work>/gerbers/ <board>.kicad_pcb", section)

    def test_the_step_and_the_prompt_name_the_footprint_drawings_as_an_input_of_the_rotation_and_first_pin_judgement(self):
        # SOL-BOARD-PRODUCTION-FILES-CHECKED-BEFORE-PAYMENT.C1: The method's ordering step compares every placed part's position, rotation and polarity with the assembler's preview before payment
        section = re.sub(r"\s+", " ", ordering_section())
        self.assertIn("hardware/tools/production_files.py footprints --board <board>.kicad_pcb --out <work>/footprints", section)
        self.assertIn("the drawing of every footprint the board carries at rotation 0 with the index that gives the rule for reading "
                      "a rotation against it (`production/footprints/`)", section)
        status, lines = run(["--print-prompt"])
        self.assertEqual(status, 0)
        self.assertIn("production/footprints/", " ".join(lines))

    def test_the_commands_the_method_names_export_the_files_the_follower_is_given(self):
        # SOL-BOARD-PRODUCTION-FILES-CHECKED-BEFORE-PAYMENT.C1: The method's ordering step compares every placed part's position, rotation and polarity with the assembler's preview before payment
        scratch = tempfile.mkdtemp(prefix="production-method-commands-")
        try:
            seed = board_prove.prepare(scratch, production_seed.DESIGN, production_seed.NAME)
            rows, parts = production_seed.export_parts(seed, KICAD_CLI, os.path.join(scratch, "parts"))
            production_seed.export_fabrication(seed, KICAD_CLI, os.path.join(scratch, "files"))
            self.assertEqual(len(rows), 28)
            self.assertEqual(len(parts), 28)
            self.assertEqual(list(parts[0]), ["Designator", "Comment", "Footprint", "LCSC"])
            names = sorted(os.listdir(os.path.join(scratch, "files")))
            self.assertEqual(sorted(name.rsplit(".", 1)[-1] for name in names if not name.endswith("job.gbrjob")),
                             sorted(["gtl", "gbl", "g1", "g2", "gts", "gbs", "gto", "gbo", "gm1", "drl"]))
        finally:
            shutil.rmtree(scratch, ignore_errors=True)

    def test_the_step_has_the_approver_count_the_records_rows_against_the_placement_files(self):
        # SOL-BOARD-PRODUCTION-FILES-CHECKED-BEFORE-PAYMENT.C1: The method's ordering step compares every placed part's position, rotation and polarity with the assembler's preview before payment
        squeezed = re.sub(r"\s+", " ", ordering_section())
        self.assertIn("Count the record's part rows against the placement file's rows: a record with fewer rows than the file has parts "
                      "is not complete and blocks the order", squeezed)

    def test_the_step_claims_only_that_the_converted_coordinates_agree_with_the_gerber_files(self):
        # SOL-BOARD-PRODUCTION-FILES-CHECKED-BEFORE-PAYMENT.C1: The method's ordering step compares every placed part's position, rotation and polarity with the assembler's preview before payment
        squeezed = re.sub(r"\s+", " ", ordering_section())
        self.assertIn("keeps the export's two coordinates, which agree with the Gerber files exported with them", squeezed)
        self.assertIn("how the assembler reads the file is what its own preview shows in step 3 and step 4 checks", squeezed)
        self.assertIn("does not test the assembler's own reading of the placement file's coordinates, rotation or bottom-side parts", squeezed)
        self.assertNotIn("the Gerber files it is laid on", squeezed)
        with open(os.path.join(REPO, "hardware", "tools", "production_files.py"), encoding="utf-8") as handle:
            self.assertNotIn("the assembler lays", re.sub(r"\s+", " ", handle.read()))

    def test_the_step_names_the_proof_design_the_command_and_the_stand_in(self):
        # SOL-BOARD-PRODUCTION-FILES-CHECKED-BEFORE-PAYMENT.C3: Following the ordering step blind on seeded production files finds every seeded defect
        section = ordering_section()
        self.assertIn("`hardware/proof/review-proof`", section)
        self.assertIn("task hw:production-seed -- --seeds <file> --out <folder>", section)
        self.assertIn("task hw:production-seed -- --print-prompt", section)
        self.assertIn("needs an account and an upload that a read-only session cannot hold", section)
        self.assertIn("rendered placement view", section)

    def test_the_ordering_step_compares_every_part_and_has_every_layer_looked_at_with_a_verdict_each(self):
        # SOL-BOARD-PRODUCTION-FILES-CHECKED-BEFORE-PAYMENT.C1: The method's ordering step compares every placed part's position, rotation and polarity with the assembler's preview before payment
        # SOL-BOARD-PRODUCTION-FILES-CHECKED-BEFORE-PAYMENT.C2: The method's ordering step has every rendered fabrication layer looked at before ordering
        section = ordering_section()
        for words in ("`production-files-check.md`",
                      "| Part | Position (file / preview) | Rotation (file / preview) | Polarity or first pin (file / preview) | "
                      "Catalogue part (record / parts list) | Verdict | Why |",
                      "| Layer | File | Compared with | Verdict | Why |",
                      "Give every row of the placement file a row in the record's parts table",
                      "A row that is not `matches` blocks the order, as does a layer not `matches`",
                      "or holds a row or layer not judged, is not ready to pay for",
                      "**Missing content**", "**Shifted content**", "**Mirrored content**",
                      "never plot the layers again from the board", "**Position**", "**Rotation**",
                      "**Polarity or first-pin orientation**", "**Catalogue part**",
                      "each copper layer, the front and back mask, the front and back legend, the outline and the drill file"):
            self.assertIn(words, section)

    def test_the_konnect_section_says_the_ordering_step_governs(self):
        # SOL-BOARD-PRODUCTION-FILES-CHECKED-BEFORE-PAYMENT.C1: The method's ordering step compares every placed part's position, rotation and polarity with the assembler's preview before payment
        with open(METHOD, encoding="utf-8") as handle:
            text = handle.read()
        section = re.search(r"^#### Konnect's skills, and where they conflict with this method[ \t]*\n(.*?)(?=^#### )", text, re.M | re.S).group(1)
        self.assertIn("Konnect's manufacture skill (`kicad-manufacture`)", section)
        self.assertIn("Where the skill's ordering steps differ from the ordering step, the ordering step governs.", section)

    def test_the_readme_describes_the_command_the_gerbonara_install_and_the_nightly_pin(self):
        # SOL-BOARD-PRODUCTION-FILES-CHECKED-BEFORE-PAYMENT.C3: Following the ordering step blind on seeded production files finds every seeded defect
        with open(README, encoding="utf-8") as handle:
            text = handle.read()
        self.assertIn("task hw:production-seed -- --seeds <file> --out <folder>", text)
        self.assertIn("task hw:production-seed -- --print-prompt", text)
        self.assertIn("gerbonara==1.6.3", text)
        self.assertIn("GERBONARA_PYTHON", text)
        proof = text[text.index("`hardware/proof/review-proof` proves"):]
        self.assertIn("task hw:production-seed", proof)
        with open(os.path.join(REPO, "Taskfile.yml"), encoding="utf-8") as handle:
            taskfile = handle.read()
        self.assertIn("hw:production-seed:", taskfile)
        self.assertIn('--gerbonara-python "{{.GERBONARA_PYTHON}}"', taskfile)
        self.assertEqual(taskfile.count('GERBONARA_PYTHON: "{{.GERBONARA_PYTHON}}"'), 2, "hw:test and hw:test:round pass it to the tests")
        with open(os.path.join(REPO, ".github", "workflows", "nightly-verify.yml"), encoding="utf-8") as handle:
            workflow = handle.read()
        self.assertIn('GERBONARA_VERSION: "1.6.3"', workflow)
        self.assertIn('-m pip install "gerbonara==${GERBONARA_VERSION}"', workflow)
        self.assertEqual(production_files.GERBONARA, "1.6.3")

    def test_the_seeding_command_is_in_no_gate(self):
        # SOL-BOARD-PRODUCTION-FILES-CHECKED-BEFORE-PAYMENT.C3: Following the ordering step blind on seeded production files finds every seeded defect
        with open(os.path.join(REPO, "Taskfile.yml"), encoding="utf-8") as handle:
            taskfile = handle.read()
        for gate in re.findall(r"--gate (\S+)", taskfile) + re.findall(r"--(?:board|host|emulation) (\S+)", taskfile):
            self.assertNotEqual(gate, "hw:production-seed")


class TheRefusals(unittest.TestCase):
    """SOL-BOARD-PRODUCTION-FILES-CHECKED-BEFORE-PAYMENT.C3: Following the ordering step blind on seeded production files finds every seeded defect."""

    def setUp(self):
        self.work = tempfile.mkdtemp(prefix="production-seed-refusals-")
        self.out = os.path.join(self.work, "production")

    def tearDown(self):
        shutil.rmtree(self.work, ignore_errors=True)

    def refused(self, seeds, out, because):
        status, lines = run(["--seeds", seeds, "--out", out] + tools())
        self.assertEqual(status, 1, lines)
        self.assertTrue(any(line.startswith("REFUSED | ") and because in line for line in lines), lines)
        self.assertEqual(lines[-1], "RESULT | REFUSED | nothing was written")
        self.assertFalse(os.path.exists(seeds))

    def test_a_seed_list_inside_the_production_files_folder_is_refused(self):
        # SOL-BOARD-PRODUCTION-FILES-CHECKED-BEFORE-PAYMENT.C3: Following the ordering step blind on seeded production files finds every seeded defect
        self.refused(os.path.join(self.out, "seeds.json"), self.out, "is inside the production-files folder")
        self.assertFalse(os.path.exists(self.out))

    def test_a_seed_list_inside_a_design_folder_is_refused(self):
        # SOL-BOARD-PRODUCTION-FILES-CHECKED-BEFORE-PAYMENT.C3: Following the ordering step blind on seeded production files finds every seeded defect
        design = os.path.join(self.work, "board", "deeper")
        os.makedirs(design)
        with open(os.path.join(self.work, "board", "board.kicad_pro"), "w", encoding="utf-8") as handle:
            handle.write("{}")
        self.refused(os.path.join(design, "seeds.json"), self.out, "is inside the design folder")

    def test_a_seed_list_that_is_a_folder_is_refused(self):
        # SOL-BOARD-PRODUCTION-FILES-CHECKED-BEFORE-PAYMENT.C3: Following the ordering step blind on seeded production files finds every seeded defect
        folder = os.path.join(self.work, "list")
        os.makedirs(folder)
        status, lines = run(["--seeds", folder, "--out", self.out] + tools())
        self.assertEqual(status, 1, lines)
        self.assertTrue(any("is a folder" in line for line in lines), lines)
        self.assertEqual(os.listdir(folder), [])

    def test_a_production_files_folder_inside_the_repository_is_refused(self):
        # SOL-BOARD-PRODUCTION-FILES-CHECKED-BEFORE-PAYMENT.C3: Following the ordering step blind on seeded production files finds every seeded defect
        inside = os.path.join(REPO, "production-folder-that-must-not-be-made")
        self.refused(os.path.join(self.work, "seeds.json"), inside, "is inside the repository")
        self.assertFalse(os.path.exists(inside))

    def test_a_production_files_folder_already_holding_files_or_that_is_a_file_is_refused(self):
        # SOL-BOARD-PRODUCTION-FILES-CHECKED-BEFORE-PAYMENT.C3: Following the ordering step blind on seeded production files finds every seeded defect
        os.makedirs(self.out)
        with open(os.path.join(self.out, "left-over.txt"), "w", encoding="utf-8") as handle:
            handle.write("from an earlier run")
        self.refused(os.path.join(self.work, "seeds.json"), self.out, "already holds files")
        self.assertEqual(os.listdir(self.out), ["left-over.txt"])
        shutil.rmtree(self.out)
        with open(self.out, "w", encoding="utf-8") as handle:
            handle.write("not a folder")
        self.refused(os.path.join(self.work, "seeds.json"), self.out, "is a file")

    def test_an_input_missing_stops_the_argument_parser(self):
        # SOL-BOARD-PRODUCTION-FILES-CHECKED-BEFORE-PAYMENT.C3: Following the ordering step blind on seeded production files finds every seeded defect
        for argv in ([], ["--seeds", os.path.join(self.work, "s.json")], ["--out", self.out]):
            with self.subTest(argv=argv), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as stopped:
                    production_seed.main(argv + tools())
                self.assertEqual(stopped.exception.code, 2)

    def test_a_gerbonara_that_is_missing_or_of_another_version_stops_the_command_and_writes_nothing(self):
        # SOL-BOARD-PRODUCTION-FILES-CHECKED-BEFORE-PAYMENT.C2: The method's ordering step has every rendered fabrication layer looked at before ordering
        fake = os.path.join(self.work, "fake-python")
        with open(fake, "w", encoding="utf-8") as handle:
            handle.write("#!/bin/sh\necho 1.0.0\n")
        os.chmod(fake, os.stat(fake).st_mode | stat.S_IXUSR)
        for python, words in ((os.path.join(self.work, "no-such-python"), "could not be run"),
                              (fake, "gerbonara 1.0.0 is installed")):
            with self.subTest(python=python):
                seeds = os.path.join(self.work, "seeds.json")
                out, err = io.StringIO(), io.StringIO()
                with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                    status = production_seed.main(["--seeds", seeds, "--out", self.out, "--kicad-cli", KICAD_CLI, "--resvg", RESVG,
                                                   "--gerbonara-python", python])
                self.assertEqual(status, 2, err.getvalue())
                self.assertTrue(err.getvalue().startswith("CANNOT RUN | "), err.getvalue())
                self.assertIn(words, err.getvalue())
                self.assertIn("gerbonara==1.6.3", err.getvalue())
                self.assertFalse(os.path.exists(self.out))
                self.assertFalse(os.path.exists(seeds))


class TheSeedsThatDoNotLand(unittest.TestCase):
    """SOL-BOARD-PRODUCTION-FILES-CHECKED-BEFORE-PAYMENT.C3: Following the ordering step blind on seeded production files finds every seeded defect."""

    def setUp(self):
        self.work = tempfile.mkdtemp(prefix="production-seed-unlanded-")
        self.out = os.path.join(self.work, "production")
        self.seeds = os.path.join(self.work, "seeds.json")

    def tearDown(self):
        shutil.rmtree(self.work, ignore_errors=True)

    def refused(self, fault, because):
        with mock.patch.object(production_seed, "SEEDS", [fault]):
            status, lines = run(["--seeds", self.seeds, "--out", self.out] + tools())
        self.assertEqual(status, 1, lines)
        self.assertTrue(lines[0].startswith(f"REFUSED | seed {fault.ident} ({fault.description}) did not land"), lines)
        self.assertIn(because, lines[0])
        self.assertEqual(lines[-1], "RESULT | REFUSED | nothing was written")
        self.assertFalse(os.path.exists(self.out))
        self.assertFalse(os.path.exists(self.seeds))

    def test_a_placement_seed_that_leaves_its_row_as_it_was_is_refused_and_nothing_is_written(self):
        # SOL-BOARD-PRODUCTION-FILES-CHECKED-BEFORE-PAYMENT.C3: Following the ordering step blind on seeded production files finds every seeded defect
        self.refused(production_seed.Fault("X1", "placement file: rotation", "U3", "U3 turned by nothing", "placement",
                                           production_seed.turned("U3", 360), designator="U3"), "U3's row is unchanged")

    def test_a_parts_list_seed_that_leaves_its_row_as_it_was_is_refused_and_nothing_is_written(self):
        # SOL-BOARD-PRODUCTION-FILES-CHECKED-BEFORE-PAYMENT.C3: Following the ordering step blind on seeded production files finds every seeded defect
        self.refused(production_seed.Fault("X2", "parts list: catalogue part", "R2", "R2 given its own number", "parts",
                                           production_seed.number_replaced("R2", "C9000015"), designator="R2"), "R2's row is unchanged")

    def test_a_layer_seed_that_changes_no_exported_file_it_names_is_refused_and_nothing_is_written(self):
        # SOL-BOARD-PRODUCTION-FILES-CHECKED-BEFORE-PAYMENT.C3: Following the ordering step blind on seeded production files finds every seeded defect
        self.refused(production_seed.Fault("X3", "fabrication layer: mirrored content", "F.SilkS", "a legend left as it was", "layer",
                                           lambda tree: None, ("F_Silkscreen.gto",)),
                     "the exported file ending F_Silkscreen.gto is the same as the unseeded design's")

    def test_a_layer_seed_that_changes_only_some_of_the_files_it_names_is_refused(self):
        # SOL-BOARD-PRODUCTION-FILES-CHECKED-BEFORE-PAYMENT.C3: Following the ordering step blind on seeded production files finds every seeded defect
        self.refused(production_seed.Fault("X4", "fabrication layer: mirrored content", "F.SilkS", "a legend mirrored, a drill claimed", "layer",
                                           production_seed.legend_mirrored, ("F_Silkscreen.gto", ".drl")),
                     "the exported file ending F_Silkscreen.gto, .drl is the same")


if __name__ == "__main__":
    unittest.main()
