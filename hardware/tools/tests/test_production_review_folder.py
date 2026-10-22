#!/usr/bin/env python3
"""The production-files review folder command, over synthetic repositories and synthetic exported files.

The command is run as shipped against a temporary git repository holding a synthetic board. No KiCad, no gerbonara and no model
is used, and no real design, order or specification is named: the exported files are small made-up text and pictures.
"""

from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import layout_fixtures as fx  # noqa: E402
import production_fixtures as pf  # noqa: E402
import production_files  # noqa: E402
import production_review_folder  # noqa: E402
import production_seed  # noqa: E402
import review_folder  # noqa: E402

EXPECTED = {
    "round.json", "docs/board-design-method.md", "docs/board-manufacturer-jlcpcb.md", "hardware/README.md",
    f"{pf.DESIGN}/parts-specification.yaml", "production/placement.csv", "production/parts-list.csv",
    *(f"production/gerbers/{name}" for name in [f"{layer}.gbr" for layer in pf.LAYERS] + ["board.gbrjob"]), "preview/preview-top.png", "views/index.txt",
    "views/layer-F.Cu-r1c1.png", "views/assembly-top-r1c1.png", "placement/index.txt", "placement/placement.png",
    *(f"production/layers/{name}" for name in ["index.txt", "index.json"] + [f"layer-{layer}.png" for layer in pf.LAYERS]),
    *(f"production/footprints/{name}" for name in ["index.txt", "index.json"] + [file for file, _, _ in pf.DRAWINGS])}


def files_under(folder):
    return sorted(os.path.relpath(os.path.join(directory, name), folder).replace(os.sep, "/")
                  for directory, _, names in os.walk(folder) for name in names)


def slurp(path, mode="rb"):
    with open(path, mode, **({} if "b" in mode else {"encoding": "utf-8"})) as handle:
        return handle.read()


class Case(unittest.TestCase):
    def setUp(self):
        self.root = os.path.realpath(tempfile.mkdtemp(prefix="production-review-folder-test-"))
        self.addCleanup(shutil.rmtree, self.root, True)
        self.inputs = pf.make_inputs(self.root)
        self.out = os.path.join(self.root, "review-folder")

    def go(self, extra=(), out=None, commit="HEAD", inputs=None):
        return pf.run(pf.argv(inputs or self.inputs, out or self.out, commit, extra))

    def refused(self, *words, **kwargs):
        status, text = self.go(**kwargs)
        self.assertEqual(status, 1, text)
        for word in words:
            self.assertIn(word, text)
        self.assertTrue(text.splitlines()[-1].startswith("REFUSED") or "REFUSED |" in text)
        self.assertFalse(os.path.exists(kwargs.get("out") or self.out), "nothing was written")
        return text


class TheFolder(Case):
    def test_the_command_writes_a_folder_outside_the_repository_holding_what_the_ordering_step_gives_a_reviewer_and_nothing_else(self):
        # SOL-HW-REVIEW-FAN-OUT-PRODUCTION-FILES.C3: Over a synthetic repository with a committed design and exported production files, a command writes a review folder outside the repository holding the placement file, the parts list, the Gerber and drill files, the image of every layer and the drill file, the footprint drawings with their index and rotation rule, the design's rendered views, the assembler's preview as supplied, the parts specification record, the manufacturer's record, the method and the hardware notes, and holds no check record and no file the commit does not hold. It takes the commit as an input and records it, and refuses, reporting every cause at once, a symbolic link in any supplied folder, a check record already in any supplied folder under any case of its name production-files-check.md, a work folder whose gerbers hold a Gerber or drill file (any file but the job file) that no entry of the layer-images index names as its source, compared without case, an output folder inside the documents repository or inside any input folder, a folder that is not new or empty, a missing preview, a work folder lacking placement.csv, parts-list.csv, or gerbers, layers or footprints files (layers and footprints each holding index.txt and index.json), an unreadable placement file, a views or placement-view folder lacking index.txt, a commit holding no board at the design (one project, one layout) or no parts specification record at the design, a documents repository or commit lacking any of the method, the hardware notes or the manufacturer's record, a tools line, command or preview note that is blank, spans lines or holds a code fence, a check with no command, round-file keys beyond tool, fields, commit, tools, commands and preview, and production field names mixed with another review's; the layout folder command refuses round-file fields naming tools, commands or preview; a failure while writing removes the folder. The command is `task hw:production-review-folder`; it assembles the folder through the assembly the production-files seeding script already holds, whose behaviour and tests are unchanged, and its round file is written through the layout folder command's round-file machinery with the fields commit, tools, commands and preview. Out of scope: exporting and rendering, and obtaining the preview.
        status, text = self.go()
        self.assertEqual(status, 0, text)
        self.assertEqual(set(files_under(self.out)), EXPECTED)
        self.assertEqual(files_under(self.out), sorted(EXPECTED), "no other file")
        self.assertFalse(os.path.realpath(self.out).startswith(os.path.realpath(self.inputs["repo"]) + os.sep))
        for name in files_under(self.out):
            self.assertNotIn("production-files-check", name)
            self.assertNotIn("notes", name)
            self.assertNotIn("session", name)
        self.assertEqual(slurp(os.path.join(self.out, "production", "placement.csv")), slurp(os.path.join(self.inputs["work"], "placement.csv")))
        self.assertEqual(slurp(os.path.join(self.out, "production", "parts-list.csv")), slurp(os.path.join(self.inputs["work"], "parts-list.csv")))
        for folder, source in (("production/gerbers", "gerbers"), ("production/layers", "layers"), ("production/footprints", "footprints")):
            for name in os.listdir(os.path.join(self.inputs["work"], source)):
                self.assertEqual(slurp(os.path.join(self.out, folder, name)), slurp(os.path.join(self.inputs["work"], source, name)), name)
        for folder, source in (("views", "views"), ("placement", "placement"), ("preview", "preview")):
            for name in os.listdir(self.inputs[source]):
                self.assertEqual(slurp(os.path.join(self.out, folder, name)), slurp(os.path.join(self.inputs[source], name)), name)
        self.assertEqual(slurp(os.path.join(self.out, "preview", "preview-top.png")), slurp(os.path.join(self.inputs["preview"], "preview-top.png")),
                         "the assembler's preview as supplied")

    def test_what_the_commit_holds_is_what_the_folder_holds_of_the_design_and_the_documents(self):
        # SOL-HW-REVIEW-FAN-OUT-PRODUCTION-FILES.C3: Over a synthetic repository with a committed design and exported production files, a command writes a review folder outside the repository holding the placement file, the parts list, the Gerber and drill files, the image of every layer and the drill file, the footprint drawings with their index and rotation rule, the design's rendered views, the assembler's preview as supplied, the parts specification record, the manufacturer's record, the method and the hardware notes, and holds no check record and no file the commit does not hold. It takes the commit as an input and records it, and refuses, reporting every cause at once, a symbolic link in any supplied folder, a check record already in any supplied folder under any case of its name production-files-check.md, a work folder whose gerbers hold a Gerber or drill file (any file but the job file) that no entry of the layer-images index names as its source, compared without case, an output folder inside the documents repository or inside any input folder, a folder that is not new or empty, a missing preview, a work folder lacking placement.csv, parts-list.csv, or gerbers, layers or footprints files (layers and footprints each holding index.txt and index.json), an unreadable placement file, a views or placement-view folder lacking index.txt, a commit holding no board at the design (one project, one layout) or no parts specification record at the design, a documents repository or commit lacking any of the method, the hardware notes or the manufacturer's record, a tools line, command or preview note that is blank, spans lines or holds a code fence, a check with no command, round-file keys beyond tool, fields, commit, tools, commands and preview, and production field names mixed with another review's; the layout folder command refuses round-file fields naming tools, commands or preview; a failure while writing removes the folder. The command is `task hw:production-review-folder`; it assembles the folder through the assembly the production-files seeding script already holds, whose behaviour and tests are unchanged, and its round file is written through the layout folder command's round-file machinery with the fields commit, tools, commands and preview. Out of scope: exporting and rendering, and obtaining the preview.
        repo = self.inputs["repo"]
        first = fx.git(repo, "rev-parse", "HEAD")
        fx.write(os.path.join(repo, pf.DESIGN, pf.RECORD), "parts: changed in a later commit\n")
        fx.write(os.path.join(repo, "docs", "board-design-method.md"), "a later method\n")
        fx.git(repo, "add", "-A")
        fx.git(repo, "commit", "-q", "-m", "later")
        fx.write(os.path.join(repo, pf.DESIGN, "designer-notes.md"), "uncommitted reasoning\n")
        status, text = self.go(commit=first, extra=["--documents-commit", first])
        self.assertEqual(status, 0, text)
        self.assertEqual(slurp(os.path.join(self.out, pf.DESIGN, pf.RECORD)), b"parts: synthetic\n")
        self.assertEqual(slurp(os.path.join(self.out, "docs", "board-design-method.md"), "r"), fx.METHOD)
        self.assertEqual(slurp(os.path.join(self.out, "docs", "board-manufacturer-jlcpcb.md"), "r"), pf.MANUFACTURER)
        self.assertEqual(slurp(os.path.join(self.out, "hardware", "README.md"), "r"), fx.README)
        self.assertEqual(os.listdir(os.path.join(self.out, pf.DESIGN)), [pf.RECORD], "the design's folder holds its record alone")
        later = os.path.join(self.root, "later")
        status, text = pf.run(pf.argv(self.inputs, later, "HEAD"))
        self.assertEqual(status, 0, text)
        self.assertEqual(slurp(os.path.join(later, pf.DESIGN, pf.RECORD)), b"parts: changed in a later commit\n")

    def test_the_commit_is_an_input_that_is_recorded_in_full_and_no_mismatch_with_the_files_is_claimed(self):
        # SOL-HW-REVIEW-FAN-OUT-PRODUCTION-FILES.C3: Over a synthetic repository with a committed design and exported production files, a command writes a review folder outside the repository holding the placement file, the parts list, the Gerber and drill files, the image of every layer and the drill file, the footprint drawings with their index and rotation rule, the design's rendered views, the assembler's preview as supplied, the parts specification record, the manufacturer's record, the method and the hardware notes, and holds no check record and no file the commit does not hold. It takes the commit as an input and records it, and refuses, reporting every cause at once, a symbolic link in any supplied folder, a check record already in any supplied folder under any case of its name production-files-check.md, a work folder whose gerbers hold a Gerber or drill file (any file but the job file) that no entry of the layer-images index names as its source, compared without case, an output folder inside the documents repository or inside any input folder, a folder that is not new or empty, a missing preview, a work folder lacking placement.csv, parts-list.csv, or gerbers, layers or footprints files (layers and footprints each holding index.txt and index.json), an unreadable placement file, a views or placement-view folder lacking index.txt, a commit holding no board at the design (one project, one layout) or no parts specification record at the design, a documents repository or commit lacking any of the method, the hardware notes or the manufacturer's record, a tools line, command or preview note that is blank, spans lines or holds a code fence, a check with no command, round-file keys beyond tool, fields, commit, tools, commands and preview, and production field names mixed with another review's; the layout folder command refuses round-file fields naming tools, commands or preview; a failure while writing removes the folder. The command is `task hw:production-review-folder`; it assembles the folder through the assembly the production-files seeding script already holds, whose behaviour and tests are unchanged, and its round file is written through the layout folder command's round-file machinery with the fields commit, tools, commands and preview. Out of scope: exporting and rendering, and obtaining the preview.
        repo = self.inputs["repo"]
        sha = fx.git(repo, "rev-parse", "HEAD")
        fx.git(repo, "branch", "order-branch")
        for name in ("HEAD", "order-branch", sha, sha[:9]):
            with self.subTest(commit=name):
                out = os.path.join(self.root, f"out-{name}")
                status, text = pf.run(pf.argv(self.inputs, out, name))
                self.assertEqual(status, 0, text)
                self.assertEqual(json.loads(slurp(os.path.join(out, "round.json"), "r"))["commit"], sha)
        status, text = pf.run(pf.argv(self.inputs, os.path.join(self.root, "json"), sha, ["--json"]))
        report = json.loads(text)
        self.assertEqual((status, report["result"], report["commit"], report["round"]["commit"]), (0, "WRITTEN", sha, sha))
        self.assertEqual(report["round"]["tools"], pf.TOOLS_LINE)
        self.assertEqual(report["round"]["commands"], pf.COMMANDS)
        self.assertEqual(report["round"]["preview"], pf.PREVIEW_NOTE)
        self.assertEqual(report["design"], pf.DESIGN)

    def test_the_round_file_is_written_through_the_layout_machinery_with_the_commit_tools_commands_and_preview_alone(self):
        # SOL-HW-REVIEW-FAN-OUT-PRODUCTION-FILES.C3: Over a synthetic repository with a committed design and exported production files, a command writes a review folder outside the repository holding the placement file, the parts list, the Gerber and drill files, the image of every layer and the drill file, the footprint drawings with their index and rotation rule, the design's rendered views, the assembler's preview as supplied, the parts specification record, the manufacturer's record, the method and the hardware notes, and holds no check record and no file the commit does not hold. It takes the commit as an input and records it, and refuses, reporting every cause at once, a symbolic link in any supplied folder, a check record already in any supplied folder under any case of its name production-files-check.md, a work folder whose gerbers hold a Gerber or drill file (any file but the job file) that no entry of the layer-images index names as its source, compared without case, an output folder inside the documents repository or inside any input folder, a folder that is not new or empty, a missing preview, a work folder lacking placement.csv, parts-list.csv, or gerbers, layers or footprints files (layers and footprints each holding index.txt and index.json), an unreadable placement file, a views or placement-view folder lacking index.txt, a commit holding no board at the design (one project, one layout) or no parts specification record at the design, a documents repository or commit lacking any of the method, the hardware notes or the manufacturer's record, a tools line, command or preview note that is blank, spans lines or holds a code fence, a check with no command, round-file keys beyond tool, fields, commit, tools, commands and preview, and production field names mixed with another review's; the layout folder command refuses round-file fields naming tools, commands or preview; a failure while writing removes the folder. The command is `task hw:production-review-folder`; it assembles the folder through the assembly the production-files seeding script already holds, whose behaviour and tests are unchanged, and its round file is written through the layout folder command's round-file machinery with the fields commit, tools, commands and preview. Out of scope: exporting and rendering, and obtaining the preview.
        self.assertEqual(self.go()[0], 0)
        content = json.loads(slurp(os.path.join(self.out, "round.json"), "r"))
        self.assertEqual(sorted(content), ["commands", "commit", "fields", "preview", "tool", "tools"])
        self.assertEqual(content["tool"], review_folder.TOOL)
        self.assertEqual(content["fields"], list(review_folder.PRODUCTION_FIELDS))
        self.assertEqual(review_folder.read_round(self.out), content)
        self.assertTrue(review_folder.is_production_fields(content["fields"]))
        self.assertFalse(review_folder.is_critical_routing_fields(content["fields"]))
        self.assertEqual(slurp(os.path.join(self.out, "round.json"), "r"), review_folder.settled(
            review_folder.round_content(review_folder.PRODUCTION_FIELDS, content)))

    def test_every_file_and_folder_carries_one_time(self):
        # SOL-HW-REVIEW-FAN-OUT-PRODUCTION-FILES.C3: Over a synthetic repository with a committed design and exported production files, a command writes a review folder outside the repository holding the placement file, the parts list, the Gerber and drill files, the image of every layer and the drill file, the footprint drawings with their index and rotation rule, the design's rendered views, the assembler's preview as supplied, the parts specification record, the manufacturer's record, the method and the hardware notes, and holds no check record and no file the commit does not hold. It takes the commit as an input and records it, and refuses, reporting every cause at once, a symbolic link in any supplied folder, a check record already in any supplied folder under any case of its name production-files-check.md, a work folder whose gerbers hold a Gerber or drill file (any file but the job file) that no entry of the layer-images index names as its source, compared without case, an output folder inside the documents repository or inside any input folder, a folder that is not new or empty, a missing preview, a work folder lacking placement.csv, parts-list.csv, or gerbers, layers or footprints files (layers and footprints each holding index.txt and index.json), an unreadable placement file, a views or placement-view folder lacking index.txt, a commit holding no board at the design (one project, one layout) or no parts specification record at the design, a documents repository or commit lacking any of the method, the hardware notes or the manufacturer's record, a tools line, command or preview note that is blank, spans lines or holds a code fence, a check with no command, round-file keys beyond tool, fields, commit, tools, commands and preview, and production field names mixed with another review's; the layout folder command refuses round-file fields naming tools, commands or preview; a failure while writing removes the folder. The command is `task hw:production-review-folder`; it assembles the folder through the assembly the production-files seeding script already holds, whose behaviour and tests are unchanged, and its round file is written through the layout folder command's round-file machinery with the fields commit, tools, commands and preview. Out of scope: exporting and rendering, and obtaining the preview.
        self.assertEqual(self.go()[0], 0)
        times = {os.stat(os.path.join(directory, name)).st_mtime for directory, names, files in os.walk(self.out) for name in names + files}
        times.add(os.stat(self.out).st_mtime)
        self.assertEqual(len(times), 1)

    def test_the_text_and_json_reports_say_the_same_thing(self):
        # SOL-HW-REVIEW-FAN-OUT-PRODUCTION-FILES.C3: Over a synthetic repository with a committed design and exported production files, a command writes a review folder outside the repository holding the placement file, the parts list, the Gerber and drill files, the image of every layer and the drill file, the footprint drawings with their index and rotation rule, the design's rendered views, the assembler's preview as supplied, the parts specification record, the manufacturer's record, the method and the hardware notes, and holds no check record and no file the commit does not hold. It takes the commit as an input and records it, and refuses, reporting every cause at once, a symbolic link in any supplied folder, a check record already in any supplied folder under any case of its name production-files-check.md, a work folder whose gerbers hold a Gerber or drill file (any file but the job file) that no entry of the layer-images index names as its source, compared without case, an output folder inside the documents repository or inside any input folder, a folder that is not new or empty, a missing preview, a work folder lacking placement.csv, parts-list.csv, or gerbers, layers or footprints files (layers and footprints each holding index.txt and index.json), an unreadable placement file, a views or placement-view folder lacking index.txt, a commit holding no board at the design (one project, one layout) or no parts specification record at the design, a documents repository or commit lacking any of the method, the hardware notes or the manufacturer's record, a tools line, command or preview note that is blank, spans lines or holds a code fence, a check with no command, round-file keys beyond tool, fields, commit, tools, commands and preview, and production field names mixed with another review's; the layout folder command refuses round-file fields naming tools, commands or preview; a failure while writing removes the folder. The command is `task hw:production-review-folder`; it assembles the folder through the assembly the production-files seeding script already holds, whose behaviour and tests are unchanged, and its round file is written through the layout folder command's round-file machinery with the fields commit, tools, commands and preview. Out of scope: exporting and rendering, and obtaining the preview.
        status, text = self.go()
        self.assertEqual(status, 0)
        lines = text.splitlines()
        self.assertTrue(lines[0].startswith(f"FOLDER | {self.out} | commit "))
        self.assertTrue(lines[1].startswith("ROUND | commit "))
        self.assertIn("| tools kicad-cli 9.9.9", lines[1])
        self.assertEqual(lines[-1], f"RESULT | WRITTEN | {self.out}")
        again = os.path.join(self.root, "again")
        status, text = pf.run(pf.argv(self.inputs, again, extra=["--json"]))
        self.assertEqual(json.loads(text)["folder"], again)


class TheRefusals(Case):
    def test_a_folder_inside_the_repository_or_the_documents_repository_or_an_input_is_refused(self):
        # SOL-HW-REVIEW-FAN-OUT-PRODUCTION-FILES.C3: Over a synthetic repository with a committed design and exported production files, a command writes a review folder outside the repository holding the placement file, the parts list, the Gerber and drill files, the image of every layer and the drill file, the footprint drawings with their index and rotation rule, the design's rendered views, the assembler's preview as supplied, the parts specification record, the manufacturer's record, the method and the hardware notes, and holds no check record and no file the commit does not hold. It takes the commit as an input and records it, and refuses, reporting every cause at once, a symbolic link in any supplied folder, a check record already in any supplied folder under any case of its name production-files-check.md, a work folder whose gerbers hold a Gerber or drill file (any file but the job file) that no entry of the layer-images index names as its source, compared without case, an output folder inside the documents repository or inside any input folder, a folder that is not new or empty, a missing preview, a work folder lacking placement.csv, parts-list.csv, or gerbers, layers or footprints files (layers and footprints each holding index.txt and index.json), an unreadable placement file, a views or placement-view folder lacking index.txt, a commit holding no board at the design (one project, one layout) or no parts specification record at the design, a documents repository or commit lacking any of the method, the hardware notes or the manufacturer's record, a tools line, command or preview note that is blank, spans lines or holds a code fence, a check with no command, round-file keys beyond tool, fields, commit, tools, commands and preview, and production field names mixed with another review's; the layout folder command refuses round-file fields naming tools, commands or preview; a failure while writing removes the folder. The command is `task hw:production-review-folder`; it assembles the folder through the assembly the production-files seeding script already holds, whose behaviour and tests are unchanged, and its round file is written through the layout folder command's round-file machinery with the fields commit, tools, commands and preview. Out of scope: exporting and rendering, and obtaining the preview.
        for where in (os.path.join(self.inputs["repo"], "review"), os.path.join(self.inputs["work"], "review"),
                      os.path.join(self.inputs["preview"], "review")):
            with self.subTest(where=where):
                status, text = pf.run(pf.argv(self.inputs, where))
                self.assertEqual(status, 1, text)
                self.assertIn("is inside the repository" if where.startswith(self.inputs["repo"]) else "one of the folders it is written from", text)
                self.assertFalse(os.path.exists(where))
        other = os.path.join(self.root, "documents-repository")
        os.makedirs(other)
        shutil.copytree(self.inputs["repo"], other + "/r")
        inputs = {**self.inputs}
        argv = pf.argv(inputs, os.path.join(other, "r", "review"))
        argv[argv.index("--documents-repo") + 1] = os.path.join(other, "r")
        status, text = pf.run(argv)
        self.assertEqual(status, 1, text)
        self.assertIn("is inside the documents repository", text)

    def test_a_folder_that_is_not_new_or_empty_is_refused_and_an_empty_one_is_written_into(self):
        # SOL-HW-REVIEW-FAN-OUT-PRODUCTION-FILES.C3: Over a synthetic repository with a committed design and exported production files, a command writes a review folder outside the repository holding the placement file, the parts list, the Gerber and drill files, the image of every layer and the drill file, the footprint drawings with their index and rotation rule, the design's rendered views, the assembler's preview as supplied, the parts specification record, the manufacturer's record, the method and the hardware notes, and holds no check record and no file the commit does not hold. It takes the commit as an input and records it, and refuses, reporting every cause at once, a symbolic link in any supplied folder, a check record already in any supplied folder under any case of its name production-files-check.md, a work folder whose gerbers hold a Gerber or drill file (any file but the job file) that no entry of the layer-images index names as its source, compared without case, an output folder inside the documents repository or inside any input folder, a folder that is not new or empty, a missing preview, a work folder lacking placement.csv, parts-list.csv, or gerbers, layers or footprints files (layers and footprints each holding index.txt and index.json), an unreadable placement file, a views or placement-view folder lacking index.txt, a commit holding no board at the design (one project, one layout) or no parts specification record at the design, a documents repository or commit lacking any of the method, the hardware notes or the manufacturer's record, a tools line, command or preview note that is blank, spans lines or holds a code fence, a check with no command, round-file keys beyond tool, fields, commit, tools, commands and preview, and production field names mixed with another review's; the layout folder command refuses round-file fields naming tools, commands or preview; a failure while writing removes the folder. The command is `task hw:production-review-folder`; it assembles the folder through the assembly the production-files seeding script already holds, whose behaviour and tests are unchanged, and its round file is written through the layout folder command's round-file machinery with the fields commit, tools, commands and preview. Out of scope: exporting and rendering, and obtaining the preview.
        pf.fx.write(os.path.join(self.out, "kept.txt"), "x")
        status, text = self.go()
        self.assertEqual(status, 1, text)
        self.assertIn("already holds files; give a new or empty folder", text)
        self.assertEqual(os.listdir(self.out), ["kept.txt"], "nothing of the folder was touched")
        os.remove(os.path.join(self.out, "kept.txt"))
        self.assertEqual(self.go()[0], 0, "an empty folder is accepted")
        shutil.rmtree(self.out)
        pf.fx.write(self.out, "a file")
        status, text = self.go()
        self.assertEqual(status, 1, text)
        self.assertIn("is a file; give a new or empty folder", text)

    def test_a_missing_preview_is_refused(self):
        # SOL-HW-REVIEW-FAN-OUT-PRODUCTION-FILES.C3: Over a synthetic repository with a committed design and exported production files, a command writes a review folder outside the repository holding the placement file, the parts list, the Gerber and drill files, the image of every layer and the drill file, the footprint drawings with their index and rotation rule, the design's rendered views, the assembler's preview as supplied, the parts specification record, the manufacturer's record, the method and the hardware notes, and holds no check record and no file the commit does not hold. It takes the commit as an input and records it, and refuses, reporting every cause at once, a symbolic link in any supplied folder, a check record already in any supplied folder under any case of its name production-files-check.md, a work folder whose gerbers hold a Gerber or drill file (any file but the job file) that no entry of the layer-images index names as its source, compared without case, an output folder inside the documents repository or inside any input folder, a folder that is not new or empty, a missing preview, a work folder lacking placement.csv, parts-list.csv, or gerbers, layers or footprints files (layers and footprints each holding index.txt and index.json), an unreadable placement file, a views or placement-view folder lacking index.txt, a commit holding no board at the design (one project, one layout) or no parts specification record at the design, a documents repository or commit lacking any of the method, the hardware notes or the manufacturer's record, a tools line, command or preview note that is blank, spans lines or holds a code fence, a check with no command, round-file keys beyond tool, fields, commit, tools, commands and preview, and production field names mixed with another review's; the layout folder command refuses round-file fields naming tools, commands or preview; a failure while writing removes the folder. The command is `task hw:production-review-folder`; it assembles the folder through the assembly the production-files seeding script already holds, whose behaviour and tests are unchanged, and its round file is written through the layout folder command's round-file machinery with the fields commit, tools, commands and preview. Out of scope: exporting and rendering, and obtaining the preview.
        for what in ("absent", "empty", "a file"):
            with self.subTest(what=what):
                preview = os.path.join(self.root, f"preview-{what}")
                if what == "empty":
                    os.makedirs(preview)
                elif what == "a file":
                    pf.fx.write(preview, "x")
                self.refused("preview folder", "is missing or holds no file", "third step", inputs={**self.inputs, "preview": preview})
        argv = pf.argv(self.inputs, self.out)
        at = argv.index("--preview")
        with mock.patch("sys.stderr", io.StringIO()) as err, self.assertRaises(SystemExit):
            pf.run(argv[:at] + argv[at + 2:])
        self.assertIn("--preview is required", err.getvalue())
        self.assertFalse(os.path.exists(self.out))

    def test_a_work_folder_lacking_a_file_a_folder_or_an_index_or_holding_an_unreadable_placement_file_is_refused_naming_it(self):
        # SOL-HW-REVIEW-FAN-OUT-PRODUCTION-FILES.C3: Over a synthetic repository with a committed design and exported production files, a command writes a review folder outside the repository holding the placement file, the parts list, the Gerber and drill files, the image of every layer and the drill file, the footprint drawings with their index and rotation rule, the design's rendered views, the assembler's preview as supplied, the parts specification record, the manufacturer's record, the method and the hardware notes, and holds no check record and no file the commit does not hold. It takes the commit as an input and records it, and refuses, reporting every cause at once, a symbolic link in any supplied folder, a check record already in any supplied folder under any case of its name production-files-check.md, a work folder whose gerbers hold a Gerber or drill file (any file but the job file) that no entry of the layer-images index names as its source, compared without case, an output folder inside the documents repository or inside any input folder, a folder that is not new or empty, a missing preview, a work folder lacking placement.csv, parts-list.csv, or gerbers, layers or footprints files (layers and footprints each holding index.txt and index.json), an unreadable placement file, a views or placement-view folder lacking index.txt, a commit holding no board at the design (one project, one layout) or no parts specification record at the design, a documents repository or commit lacking any of the method, the hardware notes or the manufacturer's record, a tools line, command or preview note that is blank, spans lines or holds a code fence, a check with no command, round-file keys beyond tool, fields, commit, tools, commands and preview, and production field names mixed with another review's; the layout folder command refuses round-file fields naming tools, commands or preview; a failure while writing removes the folder. The command is `task hw:production-review-folder`; it assembles the folder through the assembly the production-files seeding script already holds, whose behaviour and tests are unchanged, and its round file is written through the layout folder command's round-file machinery with the fields commit, tools, commands and preview. Out of scope: exporting and rendering, and obtaining the preview.
        work = self.inputs["work"]
        for name, word in (("placement.csv", "holds no placement.csv"), ("parts-list.csv", "holds no parts-list.csv"),
                           ("gerbers", "holds no gerbers/ with files"), ("layers", "holds no layers/ with files"),
                           ("footprints", "holds no footprints/ with files"), ("layers/index.json", "layers/ holds no index.json"),
                           ("footprints/index.txt", "footprints/ holds no index.txt")):
            with self.subTest(name=name):
                target = os.path.join(work, name)
                backup = os.path.join(self.root, "backup")
                shutil.rmtree(backup, ignore_errors=True)
                shutil.move(target, backup)
                try:
                    self.refused(word)
                finally:
                    shutil.move(backup, target)
        for text, word in (("", "has the columns none"), ("Designator,X\nR1,1\n", "has the columns Designator,X"),
                           ("Designator,Mid X,Mid Y,Layer,Rotation\n", "lists no part"),
                           ("Designator,Mid X,Mid Y,Layer,Rotation\nR1,1,2\n", "has 3 columns")):
            with self.subTest(placement=text):
                good = slurp(os.path.join(work, "placement.csv"), "r")
                pf.fx.write(os.path.join(work, "placement.csv"), text)
                try:
                    self.refused("placement file", "placement.csv", word, "first step")
                finally:
                    pf.fx.write(os.path.join(work, "placement.csv"), good)
        self.refused("is not a folder", inputs={**self.inputs, "work": os.path.join(self.root, "no-such-work")})

    def test_a_views_or_placement_view_folder_with_no_index_is_refused(self):
        # SOL-HW-REVIEW-FAN-OUT-PRODUCTION-FILES.C3: Over a synthetic repository with a committed design and exported production files, a command writes a review folder outside the repository holding the placement file, the parts list, the Gerber and drill files, the image of every layer and the drill file, the footprint drawings with their index and rotation rule, the design's rendered views, the assembler's preview as supplied, the parts specification record, the manufacturer's record, the method and the hardware notes, and holds no check record and no file the commit does not hold. It takes the commit as an input and records it, and refuses, reporting every cause at once, a symbolic link in any supplied folder, a check record already in any supplied folder under any case of its name production-files-check.md, a work folder whose gerbers hold a Gerber or drill file (any file but the job file) that no entry of the layer-images index names as its source, compared without case, an output folder inside the documents repository or inside any input folder, a folder that is not new or empty, a missing preview, a work folder lacking placement.csv, parts-list.csv, or gerbers, layers or footprints files (layers and footprints each holding index.txt and index.json), an unreadable placement file, a views or placement-view folder lacking index.txt, a commit holding no board at the design (one project, one layout) or no parts specification record at the design, a documents repository or commit lacking any of the method, the hardware notes or the manufacturer's record, a tools line, command or preview note that is blank, spans lines or holds a code fence, a check with no command, round-file keys beyond tool, fields, commit, tools, commands and preview, and production field names mixed with another review's; the layout folder command refuses round-file fields naming tools, commands or preview; a failure while writing removes the folder. The command is `task hw:production-review-folder`; it assembles the folder through the assembly the production-files seeding script already holds, whose behaviour and tests are unchanged, and its round file is written through the layout folder command's round-file machinery with the fields commit, tools, commands and preview. Out of scope: exporting and rendering, and obtaining the preview.
        for key, word in (("views", "the views folder"), ("placement", "the placement view folder")):
            with self.subTest(key=key):
                empty = os.path.join(self.root, f"empty-{key}")
                os.makedirs(empty)
                self.refused(word, "holds no index.txt", inputs={**self.inputs, key: empty})

    def test_a_commit_that_holds_no_board_no_record_or_an_unknown_commit_is_refused(self):
        # SOL-HW-REVIEW-FAN-OUT-PRODUCTION-FILES.C3: Over a synthetic repository with a committed design and exported production files, a command writes a review folder outside the repository holding the placement file, the parts list, the Gerber and drill files, the image of every layer and the drill file, the footprint drawings with their index and rotation rule, the design's rendered views, the assembler's preview as supplied, the parts specification record, the manufacturer's record, the method and the hardware notes, and holds no check record and no file the commit does not hold. It takes the commit as an input and records it, and refuses, reporting every cause at once, a symbolic link in any supplied folder, a check record already in any supplied folder under any case of its name production-files-check.md, a work folder whose gerbers hold a Gerber or drill file (any file but the job file) that no entry of the layer-images index names as its source, compared without case, an output folder inside the documents repository or inside any input folder, a folder that is not new or empty, a missing preview, a work folder lacking placement.csv, parts-list.csv, or gerbers, layers or footprints files (layers and footprints each holding index.txt and index.json), an unreadable placement file, a views or placement-view folder lacking index.txt, a commit holding no board at the design (one project, one layout) or no parts specification record at the design, a documents repository or commit lacking any of the method, the hardware notes or the manufacturer's record, a tools line, command or preview note that is blank, spans lines or holds a code fence, a check with no command, round-file keys beyond tool, fields, commit, tools, commands and preview, and production field names mixed with another review's; the layout folder command refuses round-file fields naming tools, commands or preview; a failure while writing removes the folder. The command is `task hw:production-review-folder`; it assembles the folder through the assembly the production-files seeding script already holds, whose behaviour and tests are unchanged, and its round file is written through the layout folder command's round-file machinery with the fields commit, tools, commands and preview. Out of scope: exporting and rendering, and obtaining the preview.
        self.refused("is not in the repository", commit="deadbeef")
        status, text = pf.run(pf.argv(self.inputs, self.out) + ["--design", "hardware/synth/nothing"])
        self.assertEqual(status, 1, text)
        self.assertIn("holds no board at hardware/synth/nothing", text)
        repo = self.inputs["repo"]
        fx.git(repo, "rm", "-q", f"{pf.DESIGN}/{pf.RECORD}")
        fx.git(repo, "commit", "-q", "-m", "no record")
        self.refused("holds no parts-specification.yaml", "parts specification record")

    def test_a_documents_repository_lacking_a_document_is_refused_naming_it(self):
        # SOL-HW-REVIEW-FAN-OUT-PRODUCTION-FILES.C3: Over a synthetic repository with a committed design and exported production files, a command writes a review folder outside the repository holding the placement file, the parts list, the Gerber and drill files, the image of every layer and the drill file, the footprint drawings with their index and rotation rule, the design's rendered views, the assembler's preview as supplied, the parts specification record, the manufacturer's record, the method and the hardware notes, and holds no check record and no file the commit does not hold. It takes the commit as an input and records it, and refuses, reporting every cause at once, a symbolic link in any supplied folder, a check record already in any supplied folder under any case of its name production-files-check.md, a work folder whose gerbers hold a Gerber or drill file (any file but the job file) that no entry of the layer-images index names as its source, compared without case, an output folder inside the documents repository or inside any input folder, a folder that is not new or empty, a missing preview, a work folder lacking placement.csv, parts-list.csv, or gerbers, layers or footprints files (layers and footprints each holding index.txt and index.json), an unreadable placement file, a views or placement-view folder lacking index.txt, a commit holding no board at the design (one project, one layout) or no parts specification record at the design, a documents repository or commit lacking any of the method, the hardware notes or the manufacturer's record, a tools line, command or preview note that is blank, spans lines or holds a code fence, a check with no command, round-file keys beyond tool, fields, commit, tools, commands and preview, and production field names mixed with another review's; the layout folder command refuses round-file fields naming tools, commands or preview; a failure while writing removes the folder. The command is `task hw:production-review-folder`; it assembles the folder through the assembly the production-files seeding script already holds, whose behaviour and tests are unchanged, and its round file is written through the layout folder command's round-file machinery with the fields commit, tools, commands and preview. Out of scope: exporting and rendering, and obtaining the preview.
        repo = self.inputs["repo"]
        fx.git(repo, "rm", "-q", "docs/board-manufacturer-jlcpcb.md")
        fx.git(repo, "commit", "-q", "-m", "no manufacturer record")
        self.refused("holds no docs/board-manufacturer-jlcpcb.md", "the method, the manufacturer's record and the hardware notes")

    def test_a_symbolic_link_or_a_check_record_in_a_folder_given_is_refused(self):
        # SOL-HW-REVIEW-FAN-OUT-PRODUCTION-FILES.C3: Over a synthetic repository with a committed design and exported production files, a command writes a review folder outside the repository holding the placement file, the parts list, the Gerber and drill files, the image of every layer and the drill file, the footprint drawings with their index and rotation rule, the design's rendered views, the assembler's preview as supplied, the parts specification record, the manufacturer's record, the method and the hardware notes, and holds no check record and no file the commit does not hold. It takes the commit as an input and records it, and refuses, reporting every cause at once, a symbolic link in any supplied folder, a check record already in any supplied folder under any case of its name production-files-check.md, a work folder whose gerbers hold a Gerber or drill file (any file but the job file) that no entry of the layer-images index names as its source, compared without case, an output folder inside the documents repository or inside any input folder, a folder that is not new or empty, a missing preview, a work folder lacking placement.csv, parts-list.csv, or gerbers, layers or footprints files (layers and footprints each holding index.txt and index.json), an unreadable placement file, a views or placement-view folder lacking index.txt, a commit holding no board at the design (one project, one layout) or no parts specification record at the design, a documents repository or commit lacking any of the method, the hardware notes or the manufacturer's record, a tools line, command or preview note that is blank, spans lines or holds a code fence, a check with no command, round-file keys beyond tool, fields, commit, tools, commands and preview, and production field names mixed with another review's; the layout folder command refuses round-file fields naming tools, commands or preview; a failure while writing removes the folder. The command is `task hw:production-review-folder`; it assembles the folder through the assembly the production-files seeding script already holds, whose behaviour and tests are unchanged, and its round file is written through the layout folder command's round-file machinery with the fields commit, tools, commands and preview. Out of scope: exporting and rendering, and obtaining the preview.
        target = os.path.join(self.root, "outside.txt")
        pf.fx.write(target, "a file from outside the folder")
        for folder in ("views", "preview", "placement"):
            with self.subTest(link=folder):
                link = os.path.join(self.inputs[folder], "linked.txt")
                os.symlink(target, link)
                try:
                    self.refused("is a symbolic link", link)
                finally:
                    os.remove(link)
        link = os.path.join(self.inputs["work"], "gerbers", "linked.gbr")
        os.symlink(target, link)
        try:
            self.refused("is a symbolic link")
        finally:
            os.remove(link)
        for folder, where in (("preview", ""), ("work", "layers"), ("views", "")):
            with self.subTest(record=folder):
                record = os.path.join(self.inputs[folder], where, "production-files-check.md")
                pf.fx.write(record, "an earlier order's record")
                try:
                    self.refused("is a check record", "production-files-check.md")
                finally:
                    os.remove(record)

    def test_a_gerber_or_drill_file_the_layer_images_index_does_not_list_is_refused_naming_it_and_the_job_file_is_not_one(self):
        # SOL-HW-REVIEW-FAN-OUT-PRODUCTION-FILES.C3: Over a synthetic repository with a committed design and exported production files, a command writes a review folder outside the repository holding the placement file, the parts list, the Gerber and drill files, the image of every layer and the drill file, the footprint drawings with their index and rotation rule, the design's rendered views, the assembler's preview as supplied, the parts specification record, the manufacturer's record, the method and the hardware notes, and holds no check record and no file the commit does not hold. It takes the commit as an input and records it, and refuses, reporting every cause at once, a symbolic link in any supplied folder, a check record already in any supplied folder under any case of its name production-files-check.md, a work folder whose gerbers hold a Gerber or drill file (any file but the job file) that no entry of the layer-images index names as its source, compared without case, an output folder inside the documents repository or inside any input folder, a folder that is not new or empty, a missing preview, a work folder lacking placement.csv, parts-list.csv, or gerbers, layers or footprints files (layers and footprints each holding index.txt and index.json), an unreadable placement file, a views or placement-view folder lacking index.txt, a commit holding no board at the design (one project, one layout) or no parts specification record at the design, a documents repository or commit lacking any of the method, the hardware notes or the manufacturer's record, a tools line, command or preview note that is blank, spans lines or holds a code fence, a check with no command, round-file keys beyond tool, fields, commit, tools, commands and preview, and production field names mixed with another review's; the layout folder command refuses round-file fields naming tools, commands or preview; a failure while writing removes the folder. The command is `task hw:production-review-folder`; it assembles the folder through the assembly the production-files seeding script already holds, whose behaviour and tests are unchanged, and its round file is written through the layout folder command's round-file machinery with the fields commit, tools, commands and preview. Out of scope: exporting and rendering, and obtaining the preview.
        gerbers = os.path.join(self.inputs["work"], "gerbers")
        for name in ("board-B_Paste.gbp", "second.drl", "sub/F.Fab.gbr"):
            with self.subTest(file=name):
                pf.fx.write(os.path.join(gerbers, name), "G04 synthetic*\n")
                try:
                    self.refused(f"gerbers/{name}", "lists as no image's source")
                finally:
                    os.remove(os.path.join(gerbers, name))
        os.rename(os.path.join(gerbers, "F.Cu.gbr"), os.path.join(gerbers, "f.cu.GBR"))
        self.assertEqual(self.go()[0], 0, "an index entry's source is matched without case, and the job file needs no entry")

    def test_a_check_record_is_refused_under_any_case_of_its_name_and_a_case_variant_of_a_required_name_is_not_that_name(self):
        # SOL-HW-REVIEW-FAN-OUT-PRODUCTION-FILES.C3: Over a synthetic repository with a committed design and exported production files, a command writes a review folder outside the repository holding the placement file, the parts list, the Gerber and drill files, the image of every layer and the drill file, the footprint drawings with their index and rotation rule, the design's rendered views, the assembler's preview as supplied, the parts specification record, the manufacturer's record, the method and the hardware notes, and holds no check record and no file the commit does not hold. It takes the commit as an input and records it, and refuses, reporting every cause at once, a symbolic link in any supplied folder, a check record already in any supplied folder under any case of its name production-files-check.md, a work folder whose gerbers hold a Gerber or drill file (any file but the job file) that no entry of the layer-images index names as its source, compared without case, an output folder inside the documents repository or inside any input folder, a folder that is not new or empty, a missing preview, a work folder lacking placement.csv, parts-list.csv, or gerbers, layers or footprints files (layers and footprints each holding index.txt and index.json), an unreadable placement file, a views or placement-view folder lacking index.txt, a commit holding no board at the design (one project, one layout) or no parts specification record at the design, a documents repository or commit lacking any of the method, the hardware notes or the manufacturer's record, a tools line, command or preview note that is blank, spans lines or holds a code fence, a check with no command, round-file keys beyond tool, fields, commit, tools, commands and preview, and production field names mixed with another review's; the layout folder command refuses round-file fields naming tools, commands or preview; a failure while writing removes the folder. The command is `task hw:production-review-folder`; it assembles the folder through the assembly the production-files seeding script already holds, whose behaviour and tests are unchanged, and its round file is written through the layout folder command's round-file machinery with the fields commit, tools, commands and preview. Out of scope: exporting and rendering, and obtaining the preview.
        for name in ("Production-Files-Check.MD", "PRODUCTION-FILES-CHECK.md"):
            with self.subTest(name=name):
                record = os.path.join(self.inputs["views"], name)
                pf.fx.write(record, "an earlier order's record")
                try:
                    self.refused("is a check record", name)
                finally:
                    os.remove(record)
        placement = os.path.join(self.inputs["work"], "placement.csv")
        moved = os.path.join(self.inputs["work"], "Placement.CSV")
        os.rename(placement, moved)
        try:
            if not os.path.exists(placement):
                self.refused("holds no placement.csv")
        finally:
            os.rename(moved, placement)

    def test_a_tools_line_commands_or_preview_line_that_is_missing_or_malformed_is_refused_naming_it(self):
        # SOL-HW-REVIEW-FAN-OUT-PRODUCTION-FILES.C3: Over a synthetic repository with a committed design and exported production files, a command writes a review folder outside the repository holding the placement file, the parts list, the Gerber and drill files, the image of every layer and the drill file, the footprint drawings with their index and rotation rule, the design's rendered views, the assembler's preview as supplied, the parts specification record, the manufacturer's record, the method and the hardware notes, and holds no check record and no file the commit does not hold. It takes the commit as an input and records it, and refuses, reporting every cause at once, a symbolic link in any supplied folder, a check record already in any supplied folder under any case of its name production-files-check.md, a work folder whose gerbers hold a Gerber or drill file (any file but the job file) that no entry of the layer-images index names as its source, compared without case, an output folder inside the documents repository or inside any input folder, a folder that is not new or empty, a missing preview, a work folder lacking placement.csv, parts-list.csv, or gerbers, layers or footprints files (layers and footprints each holding index.txt and index.json), an unreadable placement file, a views or placement-view folder lacking index.txt, a commit holding no board at the design (one project, one layout) or no parts specification record at the design, a documents repository or commit lacking any of the method, the hardware notes or the manufacturer's record, a tools line, command or preview note that is blank, spans lines or holds a code fence, a check with no command, round-file keys beyond tool, fields, commit, tools, commands and preview, and production field names mixed with another review's; the layout folder command refuses round-file fields naming tools, commands or preview; a failure while writing removes the folder. The command is `task hw:production-review-folder`; it assembles the folder through the assembly the production-files seeding script already holds, whose behaviour and tests are unchanged, and its round file is written through the layout folder command's round-file machinery with the fields commit, tools, commands and preview. Out of scope: exporting and rendering, and obtaining the preview.
        base = pf.argv(self.inputs, self.out)

        def without(flag, count=1):
            kept, skip = [], 0
            for at, item in enumerate(base):
                if item == flag:
                    skip = 2
                if skip:
                    skip -= 1
                    continue
                kept.append(item)
            return kept
        for argv, word in ((without("--tools"), "the tools are None"), (without("--command"), "the commands are []"),
                           (without("--preview-note"), "the preview line is None"),
                           (without("--tools") + ["--tools", "two\nlines"], "the tools are"),
                           (without("--tools") + ["--tools", "```"], "the tools are"),
                           (without("--command") + ["--command", "bad\nline"], "the commands are"),
                           (without("--preview-note") + ["--preview-note", "  "], "the preview line is")):
            with self.subTest(word=word, argv=argv[-2:]):
                status, text = pf.run(argv)
                self.assertEqual(status, 1, text)
                self.assertIn(word, text)
                self.assertFalse(os.path.exists(self.out))
        with mock.patch("sys.stderr", io.StringIO()) as err, self.assertRaises(SystemExit):
            pf.run(without("--repo"))
        self.assertIn("--repo is required", err.getvalue())

    def test_the_reports_of_a_refusal_are_the_same_in_text_and_in_json_and_git_missing_is_cannot_run(self):
        # SOL-HW-REVIEW-FAN-OUT-PRODUCTION-FILES.C3: Over a synthetic repository with a committed design and exported production files, a command writes a review folder outside the repository holding the placement file, the parts list, the Gerber and drill files, the image of every layer and the drill file, the footprint drawings with their index and rotation rule, the design's rendered views, the assembler's preview as supplied, the parts specification record, the manufacturer's record, the method and the hardware notes, and holds no check record and no file the commit does not hold. It takes the commit as an input and records it, and refuses, reporting every cause at once, a symbolic link in any supplied folder, a check record already in any supplied folder under any case of its name production-files-check.md, a work folder whose gerbers hold a Gerber or drill file (any file but the job file) that no entry of the layer-images index names as its source, compared without case, an output folder inside the documents repository or inside any input folder, a folder that is not new or empty, a missing preview, a work folder lacking placement.csv, parts-list.csv, or gerbers, layers or footprints files (layers and footprints each holding index.txt and index.json), an unreadable placement file, a views or placement-view folder lacking index.txt, a commit holding no board at the design (one project, one layout) or no parts specification record at the design, a documents repository or commit lacking any of the method, the hardware notes or the manufacturer's record, a tools line, command or preview note that is blank, spans lines or holds a code fence, a check with no command, round-file keys beyond tool, fields, commit, tools, commands and preview, and production field names mixed with another review's; the layout folder command refuses round-file fields naming tools, commands or preview; a failure while writing removes the folder. The command is `task hw:production-review-folder`; it assembles the folder through the assembly the production-files seeding script already holds, whose behaviour and tests are unchanged, and its round file is written through the layout folder command's round-file machinery with the fields commit, tools, commands and preview. Out of scope: exporting and rendering, and obtaining the preview.
        status, text = self.go(commit="deadbeef")
        self.assertEqual((status, text.splitlines()[-1]), (1, "RESULT | REFUSED | nothing was written"))
        status, text = pf.run(pf.argv(self.inputs, self.out, "deadbeef", ["--json"]))
        report = json.loads(text)
        self.assertEqual((status, report["result"], report["detail"]), (1, "REFUSED", "nothing was written"))
        self.assertTrue(any("deadbeef" in cause for cause in report["refusals"]))
        with mock.patch.object(review_folder, "git", side_effect=FileNotFoundError(2, "no", "git")):
            status, text = self.go()
        self.assertEqual(status, 2, text)
        self.assertIn("RESULT | CANNOT RUN | git is not on the search path", text)

    def test_every_cause_is_reported_at_once_and_a_failure_while_writing_leaves_nothing_behind(self):
        # SOL-HW-REVIEW-FAN-OUT-PRODUCTION-FILES.C3: Over a synthetic repository with a committed design and exported production files, a command writes a review folder outside the repository holding the placement file, the parts list, the Gerber and drill files, the image of every layer and the drill file, the footprint drawings with their index and rotation rule, the design's rendered views, the assembler's preview as supplied, the parts specification record, the manufacturer's record, the method and the hardware notes, and holds no check record and no file the commit does not hold. It takes the commit as an input and records it, and refuses, reporting every cause at once, a symbolic link in any supplied folder, a check record already in any supplied folder under any case of its name production-files-check.md, a work folder whose gerbers hold a Gerber or drill file (any file but the job file) that no entry of the layer-images index names as its source, compared without case, an output folder inside the documents repository or inside any input folder, a folder that is not new or empty, a missing preview, a work folder lacking placement.csv, parts-list.csv, or gerbers, layers or footprints files (layers and footprints each holding index.txt and index.json), an unreadable placement file, a views or placement-view folder lacking index.txt, a commit holding no board at the design (one project, one layout) or no parts specification record at the design, a documents repository or commit lacking any of the method, the hardware notes or the manufacturer's record, a tools line, command or preview note that is blank, spans lines or holds a code fence, a check with no command, round-file keys beyond tool, fields, commit, tools, commands and preview, and production field names mixed with another review's; the layout folder command refuses round-file fields naming tools, commands or preview; a failure while writing removes the folder. The command is `task hw:production-review-folder`; it assembles the folder through the assembly the production-files seeding script already holds, whose behaviour and tests are unchanged, and its round file is written through the layout folder command's round-file machinery with the fields commit, tools, commands and preview. Out of scope: exporting and rendering, and obtaining the preview.
        pf.fx.write(os.path.join(self.out, "kept.txt"), "x")
        shutil.rmtree(self.inputs["preview"])
        status, text = self.go(commit="deadbeef")
        self.assertEqual(status, 1)
        self.assertGreaterEqual(text.count("REFUSED | "), 4, text)
        shutil.rmtree(self.out)
        pf.fx.write(os.path.join(self.inputs["preview"], "preview-top.png"), "x")
        with mock.patch.object(production_seed, "write_folder", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                self.go()
        self.assertFalse(os.path.exists(self.out), "a folder half written is removed")


class TheSharedAssembly(Case):
    def test_the_folder_command_and_the_seeding_script_assemble_through_one_function(self):
        # SOL-HW-REVIEW-FAN-OUT-PRODUCTION-FILES.C3: Over a synthetic repository with a committed design and exported production files, a command writes a review folder outside the repository holding the placement file, the parts list, the Gerber and drill files, the image of every layer and the drill file, the footprint drawings with their index and rotation rule, the design's rendered views, the assembler's preview as supplied, the parts specification record, the manufacturer's record, the method and the hardware notes, and holds no check record and no file the commit does not hold. It takes the commit as an input and records it, and refuses, reporting every cause at once, a symbolic link in any supplied folder, a check record already in any supplied folder under any case of its name production-files-check.md, a work folder whose gerbers hold a Gerber or drill file (any file but the job file) that no entry of the layer-images index names as its source, compared without case, an output folder inside the documents repository or inside any input folder, a folder that is not new or empty, a missing preview, a work folder lacking placement.csv, parts-list.csv, or gerbers, layers or footprints files (layers and footprints each holding index.txt and index.json), an unreadable placement file, a views or placement-view folder lacking index.txt, a commit holding no board at the design (one project, one layout) or no parts specification record at the design, a documents repository or commit lacking any of the method, the hardware notes or the manufacturer's record, a tools line, command or preview note that is blank, spans lines or holds a code fence, a check with no command, round-file keys beyond tool, fields, commit, tools, commands and preview, and production field names mixed with another review's; the layout folder command refuses round-file fields naming tools, commands or preview; a failure while writing removes the folder. The command is `task hw:production-review-folder`; it assembles the folder through the assembly the production-files seeding script already holds, whose behaviour and tests are unchanged, and its round file is written through the layout folder command's round-file machinery with the fields commit, tools, commands and preview. Out of scope: exporting and rendering, and obtaining the preview.
        calls = []
        real = production_seed.write_folder

        def recorded(out, design, record, documents, placement, parts, fabrication, draw):
            calls.append((design, sorted(documents), record, placement, parts, os.path.basename(fabrication)))
            return real(out, design, record, documents, placement, parts, fabrication, draw)
        with mock.patch.object(production_seed, "write_folder", recorded):
            self.assertEqual(self.go()[0], 0)
        self.assertEqual(len(calls), 1)
        design, documents, record, placement, parts, fabrication = calls[0]
        self.assertEqual((design, record, fabrication), (pf.DESIGN, b"parts: synthetic\n", "gerbers"))
        self.assertEqual(documents, sorted(production_seed.DOCUMENTS))
        self.assertEqual(placement, pf.placement_text())
        seeded = os.path.join(self.root, "seeded")
        scratch = os.path.join(self.root, "scratch")
        pf.fx.write(os.path.join(scratch, production_seed.RECORD), "parts: proof\n")
        gerbers = os.path.join(self.root, "seed-gerbers")
        pf.fx.write(os.path.join(gerbers, "board.gtl"), "G04*\n")

        class Clean:
            def path(self, name):
                return os.path.join(scratch, name)
        drawn = subprocess.CompletedProcess([], 0, "RESULT | WRITTEN | 3 images\n", "")
        os.makedirs(seeded)
        with mock.patch.object(production_seed, "write_folder", recorded), \
                mock.patch.object(production_seed.subprocess, "run", return_value=drawn), \
                mock.patch.object(production_files, "footprints", return_value=0), \
                mock.patch.object(production_seed, "render_views", return_value=(True, "RESULT | WRITTEN | views")), \
                mock.patch.object(production_seed, "documents", return_value={"docs/board-design-method.md": b"method\n"}):
            done, said = production_seed.assemble(Clean(), seeded, {"R1": ["R1", "1", "2", "Top", "0"]}, ["R1"],
                                                  [{"Designator": "R1", "LCSC": "C1"}], ["Designator", "LCSC"], gerbers, "kicad-cli",
                                                  "resvg", "python3")
        self.assertTrue(done)
        self.assertIn("RESULT | WRITTEN | views", said)
        self.assertEqual(len(calls), 2, "the seeding script's folder is written by the same function")
        self.assertEqual(calls[1][:3], (production_seed.DESIGN, ["docs/board-design-method.md"], b"parts: proof\n"))
        self.assertEqual(slurp(os.path.join(seeded, "production", "placement.csv"), "r"),
                         "Designator,Mid X,Mid Y,Layer,Rotation\nR1,1,2,Top,0\n")
        self.assertEqual(slurp(os.path.join(seeded, "production", "parts-list.csv"), "r"), "Designator,LCSC\nR1,C1\n")
        self.assertEqual(slurp(os.path.join(seeded, "production", "gerbers", "board.gtl"), "r"), "G04*\n")
        self.assertEqual(slurp(os.path.join(seeded, production_seed.DESIGN, production_seed.RECORD), "r"), "parts: proof\n")
        times = {os.stat(os.path.join(directory, name)).st_mtime for directory, names, files in os.walk(seeded) for name in names + files}
        self.assertEqual(len(times), 1)

    def test_the_seeding_scripts_failures_to_draw_are_reported_as_they_were(self):
        # SOL-HW-REVIEW-FAN-OUT-PRODUCTION-FILES.C3: Over a synthetic repository with a committed design and exported production files, a command writes a review folder outside the repository holding the placement file, the parts list, the Gerber and drill files, the image of every layer and the drill file, the footprint drawings with their index and rotation rule, the design's rendered views, the assembler's preview as supplied, the parts specification record, the manufacturer's record, the method and the hardware notes, and holds no check record and no file the commit does not hold. It takes the commit as an input and records it, and refuses, reporting every cause at once, a symbolic link in any supplied folder, a check record already in any supplied folder under any case of its name production-files-check.md, a work folder whose gerbers hold a Gerber or drill file (any file but the job file) that no entry of the layer-images index names as its source, compared without case, an output folder inside the documents repository or inside any input folder, a folder that is not new or empty, a missing preview, a work folder lacking placement.csv, parts-list.csv, or gerbers, layers or footprints files (layers and footprints each holding index.txt and index.json), an unreadable placement file, a views or placement-view folder lacking index.txt, a commit holding no board at the design (one project, one layout) or no parts specification record at the design, a documents repository or commit lacking any of the method, the hardware notes or the manufacturer's record, a tools line, command or preview note that is blank, spans lines or holds a code fence, a check with no command, round-file keys beyond tool, fields, commit, tools, commands and preview, and production field names mixed with another review's; the layout folder command refuses round-file fields naming tools, commands or preview; a failure while writing removes the folder. The command is `task hw:production-review-folder`; it assembles the folder through the assembly the production-files seeding script already holds, whose behaviour and tests are unchanged, and its round file is written through the layout folder command's round-file machinery with the fields commit, tools, commands and preview. Out of scope: exporting and rendering, and obtaining the preview.
        scratch = os.path.join(self.root, "scratch")
        pf.fx.write(os.path.join(scratch, production_seed.RECORD), "parts: proof\n")
        gerbers = os.path.join(self.root, "seed-gerbers")
        pf.fx.write(os.path.join(gerbers, "board.gtl"), "G04*\n")

        class Clean:
            def path(self, name):
                return os.path.join(scratch, name)
        arguments = (Clean(), None, {"R1": ["R1", "1", "2", "Top", "0"]}, ["R1"], [{"Designator": "R1"}], ["Designator"], gerbers,
                     "kicad-cli", "resvg", "python3")
        failed = subprocess.CompletedProcess([], 1, "", "gerbonara could not read it")
        for name, patches, expected in (
                ("the layers cannot be drawn", {"run": failed}, (False, "gerbonara could not read it")),
                ("the footprints cannot be drawn", {"run": subprocess.CompletedProcess([], 0, "layers ok", ""), "footprints": 2},
                 (False, "layers ok")),
                ("the views cannot be rendered", {"run": subprocess.CompletedProcess([], 0, "layers ok", ""), "footprints": 0,
                                                  "views": (False, "views failed")}, (False, "layers ok\nviews failed"))):
            with self.subTest(name=name):
                out = os.path.join(self.root, "seed-" + name.replace(" ", "-"))
                os.makedirs(out)
                with mock.patch.object(production_seed.subprocess, "run", return_value=patches["run"]), \
                        mock.patch.object(production_files, "footprints", return_value=patches.get("footprints", 0)), \
                        mock.patch.object(production_seed, "render_views", return_value=patches.get("views", (True, ""))), \
                        mock.patch.object(production_seed, "documents", return_value={}):
                    done, said = production_seed.assemble(*(arguments[0], out) + arguments[2:])
                self.assertEqual((done, said), expected)


class TheRoundFileMachinery(unittest.TestCase):
    def test_the_production_fields_are_checked_by_the_same_function_as_the_layout_reviews_and_the_layout_set_is_unchanged(self):
        # SOL-HW-REVIEW-FAN-OUT-PRODUCTION-FILES.C3: Over a synthetic repository with a committed design and exported production files, a command writes a review folder outside the repository holding the placement file, the parts list, the Gerber and drill files, the image of every layer and the drill file, the footprint drawings with their index and rotation rule, the design's rendered views, the assembler's preview as supplied, the parts specification record, the manufacturer's record, the method and the hardware notes, and holds no check record and no file the commit does not hold. It takes the commit as an input and records it, and refuses, reporting every cause at once, a symbolic link in any supplied folder, a check record already in any supplied folder under any case of its name production-files-check.md, a work folder whose gerbers hold a Gerber or drill file (any file but the job file) that no entry of the layer-images index names as its source, compared without case, an output folder inside the documents repository or inside any input folder, a folder that is not new or empty, a missing preview, a work folder lacking placement.csv, parts-list.csv, or gerbers, layers or footprints files (layers and footprints each holding index.txt and index.json), an unreadable placement file, a views or placement-view folder lacking index.txt, a commit holding no board at the design (one project, one layout) or no parts specification record at the design, a documents repository or commit lacking any of the method, the hardware notes or the manufacturer's record, a tools line, command or preview note that is blank, spans lines or holds a code fence, a check with no command, round-file keys beyond tool, fields, commit, tools, commands and preview, and production field names mixed with another review's; the layout folder command refuses round-file fields naming tools, commands or preview; a failure while writing removes the folder. The command is `task hw:production-review-folder`; it assembles the folder through the assembly the production-files seeding script already holds, whose behaviour and tests are unchanged, and its round file is written through the layout folder command's round-file machinery with the fields commit, tools, commands and preview. Out of scope: exporting and rendering, and obtaining the preview.
        good = {"commit": "abc1234", "tools": "kicad-cli 9", "commands": ["one"], "preview": "saved 2030-01-01"}
        self.assertEqual(review_folder.round_problems(good, review_folder.PRODUCTION_FIELDS), [])
        for change, word in (({"commit": "xyz"}, "the commit judged"), ({"tools": ""}, "the tools"), ({"commands": [""]}, "the commands"),
                             ({"preview": None}, "the preview line"), ({"commands": "x"}, "the commands")):
            problems = review_folder.round_problems({**good, **change}, review_folder.PRODUCTION_FIELDS)
            self.assertEqual(len(problems), 1, change)
            self.assertIn(word, problems[0])
        self.assertEqual(review_folder.LAYOUT_FIELDS, ("number", "kind", "commit", "views", "check"))
        self.assertEqual(review_folder.CRITICAL_FIELDS, ("number", "commit", "views"))
        self.assertEqual(review_folder.PRODUCTION_FIELDS, ("commit", "tools", "commands", "preview"))
        self.assertEqual(review_folder.round_problems({"number": 1, "kind": "full", "commit": "abc1234", "views": ["v"],
                                                       "check": ["DESIGN | x"]}, review_folder.LAYOUT_FIELDS), [])

    def test_the_layout_folder_command_refuses_the_production_fields_and_accepts_no_others(self):
        # SOL-HW-REVIEW-FAN-OUT-PRODUCTION-FILES.C3: Over a synthetic repository with a committed design and exported production files, a command writes a review folder outside the repository holding the placement file, the parts list, the Gerber and drill files, the image of every layer and the drill file, the footprint drawings with their index and rotation rule, the design's rendered views, the assembler's preview as supplied, the parts specification record, the manufacturer's record, the method and the hardware notes, and holds no check record and no file the commit does not hold. It takes the commit as an input and records it, and refuses, reporting every cause at once, a symbolic link in any supplied folder, a check record already in any supplied folder under any case of its name production-files-check.md, a work folder whose gerbers hold a Gerber or drill file (any file but the job file) that no entry of the layer-images index names as its source, compared without case, an output folder inside the documents repository or inside any input folder, a folder that is not new or empty, a missing preview, a work folder lacking placement.csv, parts-list.csv, or gerbers, layers or footprints files (layers and footprints each holding index.txt and index.json), an unreadable placement file, a views or placement-view folder lacking index.txt, a commit holding no board at the design (one project, one layout) or no parts specification record at the design, a documents repository or commit lacking any of the method, the hardware notes or the manufacturer's record, a tools line, command or preview note that is blank, spans lines or holds a code fence, a check with no command, round-file keys beyond tool, fields, commit, tools, commands and preview, and production field names mixed with another review's; the layout folder command refuses round-file fields naming tools, commands or preview; a failure while writing removes the folder. The command is `task hw:production-review-folder`; it assembles the folder through the assembly the production-files seeding script already holds, whose behaviour and tests are unchanged, and its round file is written through the layout folder command's round-file machinery with the fields commit, tools, commands and preview. Out of scope: exporting and rendering, and obtaining the preview.
        root = os.path.realpath(tempfile.mkdtemp(prefix="production-fields-test-"))
        self.addCleanup(shutil.rmtree, root, True)
        repo = fx.make_repo(root)
        inputs = fx.make_views(root)
        argv = fx.folder_argv(repo, os.path.join(root, "out"), inputs, extra=["--round-fields", "commit,tools"])
        status, text = fx.run_folder(argv)
        self.assertEqual(status, 1, text)
        self.assertIn("the round fields tools are not fields of a round; the fields are number, kind, commit, views, check", text)
        self.assertFalse(os.path.exists(os.path.join(root, "out")))


if __name__ == "__main__":
    unittest.main()
