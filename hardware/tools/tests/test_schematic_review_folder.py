#!/usr/bin/env python3
"""The schematic review folder command, the facts it reads from a netlist and a schematic, and the round-file machinery it shares
with the other review folders, over synthetic repositories.

The command is run as shipped against a temporary git repository holding a synthetic schematic, with a synthetic netlist and
synthetic sheet drawings written where the commands that export and draw them would write them. No KiCad and no model is used.
"""

from __future__ import annotations

import hashlib
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

import layout_fixtures as lfx  # noqa: E402
import review_folder  # noqa: E402
import schematic_facts  # noqa: E402
import schematic_fixtures as sfx  # noqa: E402
import schematic_review_folder  # noqa: E402

REPO = os.path.dirname(os.path.dirname(TOOLS))


def slurp(path, mode="r"):
    with open(path, mode, **({} if "b" in mode else {"encoding": "utf-8"})) as handle:
        return handle.read()


def tree(folder):
    return sorted(os.path.relpath(os.path.join(directory, name), folder).replace(os.sep, "/")
                  for directory, _, names in os.walk(folder) for name in names)


class Case(unittest.TestCase):
    def setUp(self):
        self.root = os.path.realpath(tempfile.mkdtemp(prefix="schematic-folder-test-"))
        self.addCleanup(shutil.rmtree, self.root, True)
        self.repo = sfx.make_repo(self.root)
        self.inputs = sfx.make_inputs(self.root)
        self.out = os.path.join(self.root, "review-folder")

    def argv(self, **changes):
        base = dict(number=1, commit="HEAD", records=tuple(sfx.RECORDS))
        base.update(changes)
        return sfx.folder_argv(self.repo, changes.pop("out", self.out), self.inputs, base["number"], base["commit"], base["records"],
                               changes.get("extra", ()))

    def run_it(self, *extra, out=None, **changes):
        argv = sfx.folder_argv(self.repo, out or self.out, self.inputs, changes.get("number", 1), changes.get("commit", "HEAD"),
                               changes.get("records", tuple(sfx.RECORDS)))
        return sfx.run_folder(argv + list(extra))

    def written(self, **changes):
        status, text = self.run_it(**changes)
        self.assertEqual(status, 0, text)
        return text

    def refused(self, *words, **changes):
        status, text = self.run_it(**changes)
        self.assertEqual(status, 1, text)
        for word in words:
            self.assertIn(word, text)
        self.assertFalse(os.path.exists(self.out) and os.listdir(self.out), "nothing is left in the folder")
        return text

    def commit(self, message="a later edit"):
        lfx.git(self.repo, "add", "-A")
        lfx.git(self.repo, "commit", "-q", "-m", message)


class TheFolder(Case):
    def test_the_folder_holds_what_the_step_gives_a_reviewer_and_nothing_of_the_designers_reasoning(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C4: Over a synthetic repository with a committed schematic, an exported netlist and rendered sheet drawings, a command writes a review folder outside the repository holding the schematic and its project files as the commit holds them, the netlist, every record the review step reads, the sheet drawings, the method, the hardware notes and the check's report, and holds no review record for a first round and, for a later round, only the earlier rounds of the schematic review record as recorded, and no file the commit does not hold. It refuses a folder inside the repository, a folder that is not new or empty, a missing netlist, a netlist whose parts or sheets differ from the committed schematic's, and a sheet with no drawing. The command is `task hw:schematic-review-folder`, with add-view and add-document modes as the layout folder command's. Out of scope: exporting the netlist, drawing the sheets and running the check.
        self.written()
        design = sfx.DESIGN
        self.assertEqual(tree(self.out), sorted([
            "docs/board-design-method.md", "hardware/README.md", "check-report.txt", "method-extract.md", "review.net", "round.json",
            "sheets/board.svg", "sheets/board-Power.svg",
            f"{design}/board.kicad_pro", f"{design}/board.kicad_sch", f"{design}/power.kicad_sch", f"{design}/board.kicad_sym",
            f"{design}/sym-lib-table", f"{design}/fp-lib-table",
            f"{design}/constraints.md", f"{design}/circuit-proof.md", f"{design}/separation-basis.yaml"]))
        held = set(tree(self.out))
        for absent in ("designer-notes.md", "session.txt", "schematic-review.md", "board.kicad_pcb", "board.kicad_dru"):
            self.assertNotIn(f"{design}/{absent}", held, absent)
        text = " ".join(slurp(os.path.join(self.out, path)) for path in held if path.endswith((".md", ".txt", ".json", ".yaml", ".net")))
        self.assertNotIn("Why I drew it so", text)
        self.assertNotIn("the session", text)

    def test_the_schematic_the_records_and_the_netlist_are_as_the_commit_and_the_export_hold_them(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C4: Over a synthetic repository with a committed schematic, an exported netlist and rendered sheet drawings, a command writes a review folder outside the repository holding the schematic and its project files as the commit holds them, the netlist, every record the review step reads, the sheet drawings, the method, the hardware notes and the check's report, and holds no review record for a first round and, for a later round, only the earlier rounds of the schematic review record as recorded, and no file the commit does not hold. It refuses a folder inside the repository, a folder that is not new or empty, a missing netlist, a netlist whose parts or sheets differ from the committed schematic's, and a sheet with no drawing. The command is `task hw:schematic-review-folder`, with add-view and add-document modes as the layout folder command's. Out of scope: exporting the netlist, drawing the sheets and running the check.
        self.written()
        for name in ("board.kicad_sch", "power.kicad_sch", "board.kicad_pro", "board.kicad_sym"):
            self.assertEqual(slurp(os.path.join(self.out, sfx.DESIGN, name), "rb"),
                             slurp(os.path.join(self.repo, sfx.DESIGN, name), "rb"), name)
        for name in sfx.RECORDS:
            self.assertEqual(slurp(os.path.join(self.out, sfx.DESIGN, name)), sfx.RECORDS[name], name)
        self.assertEqual(slurp(os.path.join(self.out, "review.net")), sfx.NETLIST)
        self.assertEqual(slurp(os.path.join(self.out, "check-report.txt")), sfx.CHECK_REPORT)
        self.assertEqual(slurp(os.path.join(self.out, "hardware", "README.md")), sfx.README)
        self.assertEqual(slurp(os.path.join(self.out, "docs", "board-design-method.md")), sfx.METHOD)
        for sheet in sfx.SHEETS:
            name = schematic_review_folder.drawing_name(sfx.NAME, sheet)
            self.assertEqual(slurp(os.path.join(self.out, "sheets", name)), slurp(os.path.join(self.inputs["sheets"], name)))

    def test_a_file_the_working_tree_changed_or_the_commit_lacks_is_not_taken(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C4: Over a synthetic repository with a committed schematic, an exported netlist and rendered sheet drawings, a command writes a review folder outside the repository holding the schematic and its project files as the commit holds them, the netlist, every record the review step reads, the sheet drawings, the method, the hardware notes and the check's report, and holds no review record for a first round and, for a later round, only the earlier rounds of the schematic review record as recorded, and no file the commit does not hold. It refuses a folder inside the repository, a folder that is not new or empty, a missing netlist, a netlist whose parts or sheets differ from the committed schematic's, and a sheet with no drawing. The command is `task hw:schematic-review-folder`, with add-view and add-document modes as the layout folder command's. Out of scope: exporting the netlist, drawing the sheets and running the check.
        sfx.write(os.path.join(self.repo, sfx.DESIGN, "board.kicad_sch"), "(kicad_sch (edited))\n")
        sfx.write(os.path.join(self.repo, sfx.DESIGN, "untracked.md"), "not committed\n")
        self.written()
        self.assertEqual(slurp(os.path.join(self.out, sfx.DESIGN, "board.kicad_sch")), sfx.ROOT_SCH)
        self.assertNotIn("untracked.md", " ".join(tree(self.out)))

    def test_the_round_file_holds_the_number_the_commit_the_netlist_command_and_the_records_read(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C4: Over a synthetic repository with a committed schematic, an exported netlist and rendered sheet drawings, a command writes a review folder outside the repository holding the schematic and its project files as the commit holds them, the netlist, every record the review step reads, the sheet drawings, the method, the hardware notes and the check's report, and holds no review record for a first round and, for a later round, only the earlier rounds of the schematic review record as recorded, and no file the commit does not hold. It refuses a folder inside the repository, a folder that is not new or empty, a missing netlist, a netlist whose parts or sheets differ from the committed schematic's, and a sheet with no drawing. The command is `task hw:schematic-review-folder`, with add-view and add-document modes as the layout folder command's. Out of scope: exporting the netlist, drawing the sheets and running the check.
        self.written()
        sha = lfx.git(self.repo, "rev-parse", "HEAD")
        self.assertEqual(sfx.round_file(self.out), {
            "tool": "review-folder", "fields": ["number", "commit", "netlist", "records"], "number": 1, "commit": sha,
            "netlist": sfx.NETLIST_COMMAND,
            "records": [f"{sfx.DESIGN}/constraints.md", f"{sfx.DESIGN}/circuit-proof.md",
                        f"{sfx.DESIGN}/separation-basis.yaml (accepted_on 2026-10-18)"]})
        self.assertEqual(review_folder.read_round(self.out)["number"], 1)

    def test_the_method_extract_holds_the_three_sections_the_review_needs_and_no_other(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C4: Over a synthetic repository with a committed schematic, an exported netlist and rendered sheet drawings, a command writes a review folder outside the repository holding the schematic and its project files as the commit holds them, the netlist, every record the review step reads, the sheet drawings, the method, the hardware notes and the check's report, and holds no review record for a first round and, for a later round, only the earlier rounds of the schematic review record as recorded, and no file the commit does not hold. It refuses a folder inside the repository, a folder that is not new or empty, a missing netlist, a netlist whose parts or sheets differ from the committed schematic's, and a sheet with no drawing. The command is `task hw:schematic-review-folder`, with add-view and add-document modes as the layout folder command's. Out of scope: exporting the netlist, drawing the sheets and running the check.
        self.written()
        extract = slurp(os.path.join(self.out, "method-extract.md"))
        self.assertTrue(extract.startswith("METHOD EXTRACT from docs/board-design-method.md"))
        self.assertEqual([line for line in extract.splitlines() if line.startswith("## ")],
                         ["## Schematic review", "## Schematic drawing convention", "## Circuit practice catalogue"])
        self.assertNotIn("Unrelated", extract)

    def test_a_first_round_holds_no_review_record_even_when_the_commit_holds_one(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C4: Over a synthetic repository with a committed schematic, an exported netlist and rendered sheet drawings, a command writes a review folder outside the repository holding the schematic and its project files as the commit holds them, the netlist, every record the review step reads, the sheet drawings, the method, the hardware notes and the check's report, and holds no review record for a first round and, for a later round, only the earlier rounds of the schematic review record as recorded, and no file the commit does not hold. It refuses a folder inside the repository, a folder that is not new or empty, a missing netlist, a netlist whose parts or sheets differ from the committed schematic's, and a sheet with no drawing. The command is `task hw:schematic-review-folder`, with add-view and add-document modes as the layout folder command's. Out of scope: exporting the netlist, drawing the sheets and running the check.
        self.written()
        self.assertFalse(os.path.exists(os.path.join(self.out, sfx.DESIGN, "schematic-review.md")))
        self.assertNotIn("1.1", " ".join(slurp(os.path.join(self.out, path)) for path in tree(self.out) if path.endswith(".md")))

    def test_a_later_round_holds_only_the_earlier_rounds_of_the_record_as_recorded(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C4: Over a synthetic repository with a committed schematic, an exported netlist and rendered sheet drawings, a command writes a review folder outside the repository holding the schematic and its project files as the commit holds them, the netlist, every record the review step reads, the sheet drawings, the method, the hardware notes and the check's report, and holds no review record for a first round and, for a later round, only the earlier rounds of the schematic review record as recorded, and no file the commit does not hold. It refuses a folder inside the repository, a folder that is not new or empty, a missing netlist, a netlist whose parts or sheets differ from the committed schematic's, and a sheet with no drawing. The command is `task hw:schematic-review-folder`, with add-view and add-document modes as the layout folder command's. Out of scope: exporting the netlist, drawing the sheets and running the check.
        record = sfx.RECORD + "\n## Round 2\n\n### Verdicts\n\n| Item | Net or part | Verdict | Rests on | Why |\n|---|---|---|---|---|\n"
        record += "| PINV-1 | /IN | pass | x | y |\n\n### Findings\n\nThis round raises no finding.\n"
        sfx.write(os.path.join(self.repo, sfx.DESIGN, "schematic-review.md"), record)
        self.commit()
        self.written(number=2)
        held = slurp(os.path.join(self.out, sfx.DESIGN, "schematic-review.md"))
        self.assertEqual(held, sfx.RECORD.rstrip("\n") + "\n", "the first round exactly as recorded")
        self.assertNotIn("## Round 2", held)
        shutil.rmtree(self.out)
        self.written(number=3)
        held = slurp(os.path.join(self.out, sfx.DESIGN, "schematic-review.md"))
        self.assertIn("## Round 1", held)
        self.assertIn("## Round 2", held)
        self.assertNotIn("## Round 3", held)
        self.assertEqual(sfx.round_file(self.out)["number"], 3)

    def test_a_later_round_whose_commit_holds_no_record_or_lacks_a_round_is_refused_naming_it(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C4: Over a synthetic repository with a committed schematic, an exported netlist and rendered sheet drawings, a command writes a review folder outside the repository holding the schematic and its project files as the commit holds them, the netlist, every record the review step reads, the sheet drawings, the method, the hardware notes and the check's report, and holds no review record for a first round and, for a later round, only the earlier rounds of the schematic review record as recorded, and no file the commit does not hold. It refuses a folder inside the repository, a folder that is not new or empty, a missing netlist, a netlist whose parts or sheets differ from the committed schematic's, and a sheet with no drawing. The command is `task hw:schematic-review-folder`, with add-view and add-document modes as the layout folder command's. Out of scope: exporting the netlist, drawing the sheets and running the check.
        sfx.write(os.path.join(self.repo, sfx.DESIGN, "schematic-review.md"), "# Review\n\nno rounds\n")
        self.commit()
        self.refused("round 2 cites the earlier rounds of the review record", "holds none", number=2)
        sfx.write(os.path.join(self.repo, sfx.DESIGN, "schematic-review.md"), sfx.RECORD)
        self.commit()
        self.refused("which must hold rounds 1 to 2", "lacks round 2", number=3)
        os.remove(os.path.join(self.repo, sfx.DESIGN, "schematic-review.md"))
        self.commit()
        self.refused("holds none", number=2)

    def test_the_folder_is_the_same_whatever_time_it_is_written_and_every_file_has_one_time(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C4: Over a synthetic repository with a committed schematic, an exported netlist and rendered sheet drawings, a command writes a review folder outside the repository holding the schematic and its project files as the commit holds them, the netlist, every record the review step reads, the sheet drawings, the method, the hardware notes and the check's report, and holds no review record for a first round and, for a later round, only the earlier rounds of the schematic review record as recorded, and no file the commit does not hold. It refuses a folder inside the repository, a folder that is not new or empty, a missing netlist, a netlist whose parts or sheets differ from the committed schematic's, and a sheet with no drawing. The command is `task hw:schematic-review-folder`, with add-view and add-document modes as the layout folder command's. Out of scope: exporting the netlist, drawing the sheets and running the check.
        self.written()
        times = {os.stat(os.path.join(self.out, path)).st_mtime for path in tree(self.out)}
        self.assertEqual(len(times), 1, "no file is told from another by when it was written")
        first = {path: hashlib.sha256(slurp(os.path.join(self.out, path), "rb")).hexdigest() for path in tree(self.out)}
        other = os.path.join(self.root, "again")
        self.written(out=other)
        self.assertEqual(first, {path: hashlib.sha256(slurp(os.path.join(other, path), "rb")).hexdigest() for path in tree(other)})

    def test_the_command_reports_in_text_and_in_json(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C4: Over a synthetic repository with a committed schematic, an exported netlist and rendered sheet drawings, a command writes a review folder outside the repository holding the schematic and its project files as the commit holds them, the netlist, every record the review step reads, the sheet drawings, the method, the hardware notes and the check's report, and holds no review record for a first round and, for a later round, only the earlier rounds of the schematic review record as recorded, and no file the commit does not hold. It refuses a folder inside the repository, a folder that is not new or empty, a missing netlist, a netlist whose parts or sheets differ from the committed schematic's, and a sheet with no drawing. The command is `task hw:schematic-review-folder`, with add-view and add-document modes as the layout folder command's. Out of scope: exporting the netlist, drawing the sheets and running the check.
        status, text = self.run_it("--json", out=os.path.join(self.root, "j"))
        report = json.loads(text)
        sha = lfx.git(self.repo, "rev-parse", "HEAD")
        self.assertEqual((status, report["result"], report["commit"], report["design"]), (0, "WRITTEN", sha, sfx.DESIGN))
        self.assertEqual(report["documents"], ["docs/board-design-method.md", "hardware/README.md"])
        self.assertIn("board.kicad_sch", report["design_files"])
        self.assertEqual(report["sheets"], ["board-Power.svg", "board.svg"])
        self.assertEqual(report["round"]["number"], 1)
        status, text = self.run_it()
        lines = text.splitlines()
        self.assertEqual(status, 0)
        self.assertEqual(lines[0], f"FOLDER | {self.out} | commit {sha} | design {sfx.DESIGN}")
        self.assertTrue(lines[1].startswith("ROUND | number 1 | commit "))
        self.assertIn("| netlist kicad-cli sch export netlist", lines[1])
        self.assertEqual(lines[-1], f"RESULT | WRITTEN | {self.out}")


class TheRefusals(Case):
    def refuses(self, name, words, mutate=None, **changes):
        with self.subTest(name=name):
            if mutate:
                mutate()
            status, text = self.run_it(**changes)
            self.assertEqual(status, 1, f"{name}: {text}")
            self.assertTrue(text.splitlines()[0].startswith("REFUSED | "), text)
            self.assertTrue(text.splitlines()[-1].startswith("RESULT | REFUSED"), text)
            for word in words:
                self.assertIn(word, text, name)
            self.assertFalse(os.path.exists(self.out) and os.listdir(self.out), f"{name}: nothing is written")
            status, text = self.run_it("--json", **changes)
            self.assertEqual((status, json.loads(text)["result"]), (1, "REFUSED"), name)
            self.assertTrue(json.loads(text)["refusals"], name)

    def test_a_folder_inside_the_repository_or_not_new_or_empty_or_inside_an_input_is_refused(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C4: Over a synthetic repository with a committed schematic, an exported netlist and rendered sheet drawings, a command writes a review folder outside the repository holding the schematic and its project files as the commit holds them, the netlist, every record the review step reads, the sheet drawings, the method, the hardware notes and the check's report, and holds no review record for a first round and, for a later round, only the earlier rounds of the schematic review record as recorded, and no file the commit does not hold. It refuses a folder inside the repository, a folder that is not new or empty, a missing netlist, a netlist whose parts or sheets differ from the committed schematic's, and a sheet with no drawing. The command is `task hw:schematic-review-folder`, with add-view and add-document modes as the layout folder command's. Out of scope: exporting the netlist, drawing the sheets and running the check.
        self.refuses("a folder inside the repository", ["is inside the repository"], out=os.path.join(self.repo, "review"))
        self.refuses("a folder inside the documents repository", ["is inside the repository"],
                     out=os.path.join(self.repo, "docs", "review"))
        sfx.write(os.path.join(self.root, "full", "a.txt"), "x")
        self.refuses("a folder that holds files", ["already holds files"], out=os.path.join(self.root, "full"))
        sfx.write(os.path.join(self.root, "afile"), "x")
        self.refuses("a folder that is a file", ["is a file"], out=os.path.join(self.root, "afile"))
        self.refuses("a folder inside the sheets folder", ["one of the files or folders it is written from"],
                     out=os.path.join(self.inputs["sheets"], "review"))
        self.refuses("a folder inside the netlist's folder", ["one of the files or folders"],
                     out=os.path.join(self.inputs["netlist"], "review"))
        os.makedirs(os.path.join(self.root, "empty"))
        status, text = self.run_it(out=os.path.join(self.root, "empty"))
        self.assertEqual(status, 0, "an empty folder is taken")

    def test_a_missing_or_unreadable_or_unparseable_netlist_is_refused_naming_it(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C4: Over a synthetic repository with a committed schematic, an exported netlist and rendered sheet drawings, a command writes a review folder outside the repository holding the schematic and its project files as the commit holds them, the netlist, every record the review step reads, the sheet drawings, the method, the hardware notes and the check's report, and holds no review record for a first round and, for a later round, only the earlier rounds of the schematic review record as recorded, and no file the commit does not hold. It refuses a folder inside the repository, a folder that is not new or empty, a missing netlist, a netlist whose parts or sheets differ from the committed schematic's, and a sheet with no drawing. The command is `task hw:schematic-review-folder`, with add-view and add-document modes as the layout folder command's. Out of scope: exporting the netlist, drawing the sheets and running the check.
        os.remove(self.inputs["netlist"])
        self.refuses("a missing netlist", ["the netlist", "does not exist", "kicad-cli sch export netlist"])
        sfx.write(self.inputs["netlist"], b"\xff\xfe not utf-8")
        self.refuses("a netlist that is not text", ["cannot be read"])
        sfx.write(self.inputs["netlist"], "(not a netlist)")
        self.refuses("a netlist that does not begin export", ["is not a KiCad netlist", "export it again"])
        sfx.write(self.inputs["netlist"], "(export (version \"E\"))")
        self.refuses("a netlist of nothing", ["holds no component and no net"])
        sfx.write(self.inputs["netlist"], "(export (")
        self.refuses("a netlist that is cut off", ["cannot be read as KiCad's netlist"])
        os.remove(self.inputs["netlist"])
        os.symlink(os.path.join(self.root, "elsewhere.net"), self.inputs["netlist"])
        sfx.write(os.path.join(self.root, "elsewhere.net"), sfx.NETLIST)
        self.refuses("a netlist that is a link", ["symbolic link"])

    def test_a_netlist_whose_parts_or_sheets_differ_from_the_committed_schematics_is_refused_naming_the_difference(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C4: Over a synthetic repository with a committed schematic, an exported netlist and rendered sheet drawings, a command writes a review folder outside the repository holding the schematic and its project files as the commit holds them, the netlist, every record the review step reads, the sheet drawings, the method, the hardware notes and the check's report, and holds no review record for a first round and, for a later round, only the earlier rounds of the schematic review record as recorded, and no file the commit does not hold. It refuses a folder inside the repository, a folder that is not new or empty, a missing netlist, a netlist whose parts or sheets differ from the committed schematic's, and a sheet with no drawing. The command is `task hw:schematic-review-folder`, with add-view and add-document modes as the layout folder command's. Out of scope: exporting the netlist, drawing the sheets and running the check.
        for name, netlist, words in (
                ("a part the schematic lacks", sfx.NETLIST.replace('(comp (ref "U1") (value "chip"))',
                                                                   '(comp (ref "U1") (value "chip"))(comp (ref "U9") (value "x"))'),
                 ["netlist's parts differ", "holds U9 the schematic lacks"]),
                ("a part the netlist lacks", sfx.NETLIST.replace('(comp (ref "R2") (value "1k"))', ""),
                 ["netlist's parts differ", "it lacks R2 the schematic holds"]),
                ("a part of another name", sfx.NETLIST.replace('"R2"', '"R7"'), ["holds R7", "lacks R2"]),
                ("a sheet the schematic lacks", sfx.NETLIST.replace("(sheet (number \"2\")",
                                                                    "(sheet (number \"3\") (name \"/Extra/\"))(sheet (number \"2\")"),
                 ["netlist's sheets differ", "holds Extra"]),
                ("a sheet the netlist lacks", sfx.NETLIST.replace('(sheet (number "2") (name "/Power/") (tstamps "/a2/"))', ""),
                 ["netlist's sheets differ", "it lacks Power"])):
            self.refuses(name, words + ["was not exported from this commit's schematic"], mutate=lambda n=netlist: sfx.write(self.inputs["netlist"], n))
        sfx.write(self.inputs["netlist"], sfx.NETLIST)
        self.assertEqual(self.run_it()[0], 0, "the netlist of the commit's own schematic is taken")

    def test_a_netlist_of_another_commits_schematic_is_refused_where_the_commit_moved_on(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C4: Over a synthetic repository with a committed schematic, an exported netlist and rendered sheet drawings, a command writes a review folder outside the repository holding the schematic and its project files as the commit holds them, the netlist, every record the review step reads, the sheet drawings, the method, the hardware notes and the check's report, and holds no review record for a first round and, for a later round, only the earlier rounds of the schematic review record as recorded, and no file the commit does not hold. It refuses a folder inside the repository, a folder that is not new or empty, a missing netlist, a netlist whose parts or sheets differ from the committed schematic's, and a sheet with no drawing. The command is `task hw:schematic-review-folder`, with add-view and add-document modes as the layout folder command's. Out of scope: exporting the netlist, drawing the sheets and running the check.
        sfx.write(os.path.join(self.repo, sfx.DESIGN, "board.kicad_sch"),
                  sfx.ROOT_SCH.replace('(property "Reference" "C1")', '(property "Reference" "C2")').replace('(reference "C1")', '(reference "C2")'))
        self.commit()
        self.refuses("the netlist of the earlier commit", ["holds C1 the schematic lacks", "it lacks C2"])

    def test_a_sheet_with_no_drawing_an_empty_one_or_a_link_is_refused_naming_it(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C4: Over a synthetic repository with a committed schematic, an exported netlist and rendered sheet drawings, a command writes a review folder outside the repository holding the schematic and its project files as the commit holds them, the netlist, every record the review step reads, the sheet drawings, the method, the hardware notes and the check's report, and holds no review record for a first round and, for a later round, only the earlier rounds of the schematic review record as recorded, and no file the commit does not hold. It refuses a folder inside the repository, a folder that is not new or empty, a missing netlist, a netlist whose parts or sheets differ from the committed schematic's, and a sheet with no drawing. The command is `task hw:schematic-review-folder`, with add-view and add-document modes as the layout folder command's. Out of scope: exporting the netlist, drawing the sheets and running the check.
        name = schematic_review_folder.drawing_name(sfx.NAME, "Power")
        path = os.path.join(self.inputs["sheets"], name)
        os.remove(path)
        self.refuses("a sheet with no drawing", ["the sheet Power has no drawing", name, "task hw:sheets"])
        sfx.write(path, "")
        self.refuses("an empty drawing", ["the drawing", "of the sheet Power is empty"])
        os.remove(path)
        sfx.write(os.path.join(self.root, "x.svg"), "<svg/>")
        os.symlink(os.path.join(self.root, "x.svg"), path)
        self.refuses("a drawing that is a link", ["symbolic link"])
        os.remove(path)
        sfx.write(path, "<svg/>")
        shutil.rmtree(self.inputs["sheets"])
        self.refuses("no sheets folder", ["is not a folder", "task hw:sheets"])

    def test_the_drawings_are_named_as_the_sheet_command_names_them(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C4: Over a synthetic repository with a committed schematic, an exported netlist and rendered sheet drawings, a command writes a review folder outside the repository holding the schematic and its project files as the commit holds them, the netlist, every record the review step reads, the sheet drawings, the method, the hardware notes and the check's report, and holds no review record for a first round and, for a later round, only the earlier rounds of the schematic review record as recorded, and no file the commit does not hold. It refuses a folder inside the repository, a folder that is not new or empty, a missing netlist, a netlist whose parts or sheets differ from the committed schematic's, and a sheet with no drawing. The command is `task hw:schematic-review-folder`, with add-view and add-document modes as the layout folder command's. Out of scope: exporting the netlist, drawing the sheets and running the check.
        self.assertEqual(schematic_review_folder.drawing_name("board", "board"), "board.svg")
        self.assertEqual(schematic_review_folder.drawing_name("board", "Power"), "board-Power.svg")
        self.assertEqual(schematic_review_folder.drawing_name("board", "Power/Reg"), "board-Power-Reg.svg")
        self.assertEqual(sfx.SHEETS, ["board", "Power"])
        self.assertEqual(sorted(os.listdir(self.inputs["sheets"])), ["board-Power.svg", "board.svg"])

    def test_extra_files_in_the_sheets_folder_are_not_copied(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C4: Over a synthetic repository with a committed schematic, an exported netlist and rendered sheet drawings, a command writes a review folder outside the repository holding the schematic and its project files as the commit holds them, the netlist, every record the review step reads, the sheet drawings, the method, the hardware notes and the check's report, and holds no review record for a first round and, for a later round, only the earlier rounds of the schematic review record as recorded, and no file the commit does not hold. It refuses a folder inside the repository, a folder that is not new or empty, a missing netlist, a netlist whose parts or sheets differ from the committed schematic's, and a sheet with no drawing. The command is `task hw:schematic-review-folder`, with add-view and add-document modes as the layout folder command's. Out of scope: exporting the netlist, drawing the sheets and running the check.
        sfx.write(os.path.join(self.inputs["sheets"], "notes.txt"), "the designer's reasoning")
        sfx.write(os.path.join(self.inputs["sheets"], "other-design.svg"), "<svg/>")
        self.written()
        self.assertEqual(sorted(os.listdir(os.path.join(self.out, "sheets"))), ["board-Power.svg", "board.svg"])

    def test_a_missing_check_report_a_missing_commit_and_a_design_without_a_schematic_are_refused(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C4: Over a synthetic repository with a committed schematic, an exported netlist and rendered sheet drawings, a command writes a review folder outside the repository holding the schematic and its project files as the commit holds them, the netlist, every record the review step reads, the sheet drawings, the method, the hardware notes and the check's report, and holds no review record for a first round and, for a later round, only the earlier rounds of the schematic review record as recorded, and no file the commit does not hold. It refuses a folder inside the repository, a folder that is not new or empty, a missing netlist, a netlist whose parts or sheets differ from the committed schematic's, and a sheet with no drawing. The command is `task hw:schematic-review-folder`, with add-view and add-document modes as the layout folder command's. Out of scope: exporting the netlist, drawing the sheets and running the check.
        os.remove(self.inputs["report"])
        self.refuses("a missing check report", ["the check's report", "does not exist"])
        sfx.write(self.inputs["report"], sfx.CHECK_REPORT)
        self.refuses("a commit the repository lacks", ["is not in the repository"], commit="f" * 40)
        lfx.git(self.repo, "rm", "-q", f"{sfx.DESIGN}/board.kicad_sch")
        self.commit("no schematic")
        self.refuses("a design without its schematic", ["holds no schematic", "board.kicad_sch"])
        lfx.git(self.repo, "rm", "-q", f"{sfx.DESIGN}/board.kicad_pro")
        self.commit("no project")
        self.refuses("a design without a project", ["holds no schematic", "0 projects"])

    def test_a_schematic_that_cannot_be_read_or_names_a_sheet_it_does_not_hold_is_refused(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C4: Over a synthetic repository with a committed schematic, an exported netlist and rendered sheet drawings, a command writes a review folder outside the repository holding the schematic and its project files as the commit holds them, the netlist, every record the review step reads, the sheet drawings, the method, the hardware notes and the check's report, and holds no review record for a first round and, for a later round, only the earlier rounds of the schematic review record as recorded, and no file the commit does not hold. It refuses a folder inside the repository, a folder that is not new or empty, a missing netlist, a netlist whose parts or sheets differ from the committed schematic's, and a sheet with no drawing. The command is `task hw:schematic-review-folder`, with add-view and add-document modes as the layout folder command's. Out of scope: exporting the netlist, drawing the sheets and running the check.
        def edit(text):
            def apply():
                sfx.write(os.path.join(self.repo, sfx.DESIGN, "board.kicad_sch"), text)
                self.commit()
            return apply
        self.refuses("a schematic cut off", ["cannot be read", "commit a schematic KiCad wrote"], mutate=edit("(kicad_sch ("))
        self.refuses("a sheet whose file is not committed", ["power2.kicad_sch is not among the files given"],
                     mutate=edit(sfx.ROOT_SCH.replace("power.kicad_sch", "power2.kicad_sch")))
        self.refuses("a sheet with a slash in its name", ["slash in its name"],
                     mutate=edit(sfx.ROOT_SCH.replace('"Sheetname" "Power"', '"Sheetname" "A/B"')))
        self.refuses("a sheet with no name", ["names no one file or has no name"],
                     mutate=edit(sfx.ROOT_SCH.replace('(property "Sheetname" "Power")', "")))

    def test_a_record_that_is_not_a_record_of_the_design_at_the_commit_is_refused_naming_it(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C4: Over a synthetic repository with a committed schematic, an exported netlist and rendered sheet drawings, a command writes a review folder outside the repository holding the schematic and its project files as the commit holds them, the netlist, every record the review step reads, the sheet drawings, the method, the hardware notes and the check's report, and holds no review record for a first round and, for a later round, only the earlier rounds of the schematic review record as recorded, and no file the commit does not hold. It refuses a folder inside the repository, a folder that is not new or empty, a missing netlist, a netlist whose parts or sheets differ from the committed schematic's, and a sheet with no drawing. The command is `task hw:schematic-review-folder`, with add-view and add-document modes as the layout folder command's. Out of scope: exporting the netlist, drawing the sheets and running the check.
        for name, records, words in (
                ("no record", (), ["no record is named"]),
                ("a record twice", ("constraints.md", "constraints.md"), ["constraints.md is named twice"]),
                ("a record not committed", ("constraints.md", "nothing.md"), ["nothing.md is not a file of"]),
                ("a record outside the design", ("../README.md",), ["not a path in the design's folder"]),
                ("an absolute path", ("/etc/hosts",), ["not a path in the design's folder"]),
                ("an unnormalised path", ("./constraints.md",), ["not a path in the design's folder"]),
                ("a KiCad file", ("board.kicad_sch",), ["not a Markdown or YAML file"]),
                ("the review record", ("schematic-review.md",), ["is the schematic review record"]),
                ("the designer's notes", ("designer-notes.md",), ["designer's reasoning or a review record"]),
                ("a session record", ("session.txt",), ["not a Markdown or YAML file"]),
                ("a layout review record", ("layout-review.md",), ["designer's reasoning or a review record"])):
            if name == "a layout review record":
                sfx.write(os.path.join(self.repo, sfx.DESIGN, "layout-review.md"), "# x\n")
                self.commit()
            if name == "a session record":
                sfx.write(os.path.join(self.repo, sfx.DESIGN, "session.md"), "# x\n")
                self.commit()
                records = ("session.md",)
                words = ["designer's reasoning or a review record"]
            self.refuses(name, words, records=records)
        self.assertEqual(self.run_it(records=("constraints.md",))[0], 0, "a single record is enough")

    def test_a_number_that_is_not_a_whole_number_of_one_or_more_and_a_netlist_command_of_two_lines_are_refused(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C4: Over a synthetic repository with a committed schematic, an exported netlist and rendered sheet drawings, a command writes a review folder outside the repository holding the schematic and its project files as the commit holds them, the netlist, every record the review step reads, the sheet drawings, the method, the hardware notes and the check's report, and holds no review record for a first round and, for a later round, only the earlier rounds of the schematic review record as recorded, and no file the commit does not hold. It refuses a folder inside the repository, a folder that is not new or empty, a missing netlist, a netlist whose parts or sheets differ from the committed schematic's, and a sheet with no drawing. The command is `task hw:schematic-review-folder`, with add-view and add-document modes as the layout folder command's. Out of scope: exporting the netlist, drawing the sheets and running the check.
        self.refuses("a number of zero", ["the round's number is 0"], number=0)
        shutil.rmtree(self.out, ignore_errors=True)
        status, text = sfx.run_folder(sfx.folder_argv(self.repo, self.out, self.inputs, -2))
        self.assertEqual(status, 1)
        self.assertIn("the round's number is -2", text)
        argv = sfx.folder_argv(self.repo, self.out, self.inputs)
        argv[argv.index("--netlist-command") + 1] = "a\nb"
        status, text = sfx.run_folder(argv)
        self.assertEqual(status, 1)
        self.assertIn("the netlist command is 'a\\nb'", text)

    def test_a_required_argument_left_out_is_a_usage_error_naming_it(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C4: Over a synthetic repository with a committed schematic, an exported netlist and rendered sheet drawings, a command writes a review folder outside the repository holding the schematic and its project files as the commit holds them, the netlist, every record the review step reads, the sheet drawings, the method, the hardware notes and the check's report, and holds no review record for a first round and, for a later round, only the earlier rounds of the schematic review record as recorded, and no file the commit does not hold. It refuses a folder inside the repository, a folder that is not new or empty, a missing netlist, a netlist whose parts or sheets differ from the committed schematic's, and a sheet with no drawing. The command is `task hw:schematic-review-folder`, with add-view and add-document modes as the layout folder command's. Out of scope: exporting the netlist, drawing the sheets and running the check.
        for flag in ("--repo", "--commit", "--design", "--out", "--netlist", "--netlist-command", "--sheets", "--check-report", "--number"):
            with self.subTest(flag=flag):
                argv = sfx.folder_argv(self.repo, self.out, self.inputs)
                at = argv.index(flag)
                del argv[at:at + 2]
                with mock.patch("sys.stderr", new=io.StringIO()) as err, self.assertRaises(SystemExit):
                    sfx.run_folder(argv)
                self.assertIn(flag, err.getvalue())

    def test_a_method_lacking_a_section_or_documents_without_one_are_refused_naming_it(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C4: Over a synthetic repository with a committed schematic, an exported netlist and rendered sheet drawings, a command writes a review folder outside the repository holding the schematic and its project files as the commit holds them, the netlist, every record the review step reads, the sheet drawings, the method, the hardware notes and the check's report, and holds no review record for a first round and, for a later round, only the earlier rounds of the schematic review record as recorded, and no file the commit does not hold. It refuses a folder inside the repository, a folder that is not new or empty, a missing netlist, a netlist whose parts or sheets differ from the committed schematic's, and a sheet with no drawing. The command is `task hw:schematic-review-folder`, with add-view and add-document modes as the layout folder command's. Out of scope: exporting the netlist, drawing the sheets and running the check.
        for heading in schematic_review_folder.SECTIONS:
            sfx.write(os.path.join(self.repo, "docs", "board-design-method.md"), sfx.METHOD.replace(f"## {heading}\n", "## Renamed\n"))
            self.commit()
            self.refuses(heading, [f"has no `## {heading}` section"])
        os.remove(os.path.join(self.repo, "docs", "board-design-method.md"))
        self.commit()
        self.refuses("no method", ["holds no docs/board-design-method.md"])

    def test_git_missing_is_exit_2_and_a_refusal_writes_nothing_even_when_the_folder_exists(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C4: Over a synthetic repository with a committed schematic, an exported netlist and rendered sheet drawings, a command writes a review folder outside the repository holding the schematic and its project files as the commit holds them, the netlist, every record the review step reads, the sheet drawings, the method, the hardware notes and the check's report, and holds no review record for a first round and, for a later round, only the earlier rounds of the schematic review record as recorded, and no file the commit does not hold. It refuses a folder inside the repository, a folder that is not new or empty, a missing netlist, a netlist whose parts or sheets differ from the committed schematic's, and a sheet with no drawing. The command is `task hw:schematic-review-folder`, with add-view and add-document modes as the layout folder command's. Out of scope: exporting the netlist, drawing the sheets and running the check.
        with mock.patch.object(review_folder, "git", side_effect=FileNotFoundError(2, "no", "git")):
            status, text = self.run_it()
        self.assertEqual(status, 2)
        self.assertIn("git is not on the search path", text)
        os.makedirs(self.out)
        self.refuses("an empty existing folder stays empty", ["no record"], records=())
        self.assertEqual(os.listdir(self.out), [])


class TheAddModes(Case):
    def setUp(self):
        super().setUp()
        self.written()
        self.view = os.path.join(self.root, "power-large.svg")
        sfx.write(self.view, "<svg/>")
        self.document = os.path.join(self.root, "u1-strap.txt")
        sfx.write(self.document, "Strap high: at least 2.0 V\n")

    def resolutions(self):
        return json.loads(slurp(os.path.join(self.out, "added-views", "resolutions.json")))["resolutions"]

    def test_an_added_view_and_an_added_document_are_recorded_with_the_item_the_why_and_the_net_part_or_sheet(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C4: Over a synthetic repository with a committed schematic, an exported netlist and rendered sheet drawings, a command writes a review folder outside the repository holding the schematic and its project files as the commit holds them, the netlist, every record the review step reads, the sheet drawings, the method, the hardware notes and the check's report, and holds no review record for a first round and, for a later round, only the earlier rounds of the schematic review record as recorded, and no file the commit does not hold. It refuses a folder inside the repository, a folder that is not new or empty, a missing netlist, a netlist whose parts or sheets differ from the committed schematic's, and a sheet with no drawing. The command is `task hw:schematic-review-folder`, with add-view and add-document modes as the layout folder command's. Out of scope: exporting the netlist, drawing the sheets and running the check.
        before = {path: slurp(os.path.join(self.out, path), "rb") for path in tree(self.out)}
        status, text = sfx.run_folder(sfx.add_view_argv(self.out, self.view, "STRAP-1", "needs sheet Power: blurred", "U1"))
        self.assertEqual(status, 0, text)
        self.assertEqual(text.strip(), "RESULT | ADDED | added-views/power-large.svg | cannot judge of STRAP-1")
        status, text = sfx.run_folder(sfx.add_document_argv(self.out, self.document, "datasheet table 3", "DERATE-2",
                                                            "needs the datasheet of C1: x", "Power"))
        self.assertEqual(status, 0, text)
        self.assertEqual(self.resolutions(), [
            {"item": "STRAP-1", "why": "needs sheet Power: blurred", "view": "added-views/power-large.svg",
             "command": "task hw:sheets -- --out <sheets>", "target": "U1"},
            {"kind": "document", "item": "DERATE-2", "why": "needs the datasheet of C1: x", "document": "added-documents/u1-strap.txt",
             "source": "datasheet table 3", "target": "Power"}])
        after = {path: slurp(os.path.join(self.out, path), "rb") for path in before}
        self.assertEqual(before, after, "the round file and the shared context are as they were")
        self.assertEqual(slurp(os.path.join(self.out, "added-views", "power-large.svg")), "<svg/>")
        entries = review_folder.read_resolutions(self.out)
        self.assertEqual([entry["kind"] for entry in entries], ["view", "document"])
        self.assertEqual([entry.get("target") for entry in entries], ["U1", "Power"])

    def test_a_target_is_optional_and_the_free_pass_entry_is_a_known_item(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C4: Over a synthetic repository with a committed schematic, an exported netlist and rendered sheet drawings, a command writes a review folder outside the repository holding the schematic and its project files as the commit holds them, the netlist, every record the review step reads, the sheet drawings, the method, the hardware notes and the check's report, and holds no review record for a first round and, for a later round, only the earlier rounds of the schematic review record as recorded, and no file the commit does not hold. It refuses a folder inside the repository, a folder that is not new or empty, a missing netlist, a netlist whose parts or sheets differ from the committed schematic's, and a sheet with no drawing. The command is `task hw:schematic-review-folder`, with add-view and add-document modes as the layout folder command's. Out of scope: exporting the netlist, drawing the sheets and running the check.
        status, text = sfx.run_folder(sfx.add_view_argv(self.out, self.view, "FREE-PASS", "needs sheet board: blurred"))
        self.assertEqual(status, 0, text)
        self.assertNotIn("target", self.resolutions()[0])
        self.assertEqual(review_folder.known_items(self.out), {"PINV-1", "PINV-2", "STRAP-1", "DERATE-1", "DERATE-2", "FREE-PASS"})

    def test_an_item_off_the_checklist_and_a_net_part_or_sheet_the_schematic_does_not_name_are_refused(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C4: Over a synthetic repository with a committed schematic, an exported netlist and rendered sheet drawings, a command writes a review folder outside the repository holding the schematic and its project files as the commit holds them, the netlist, every record the review step reads, the sheet drawings, the method, the hardware notes and the check's report, and holds no review record for a first round and, for a later round, only the earlier rounds of the schematic review record as recorded, and no file the commit does not hold. It refuses a folder inside the repository, a folder that is not new or empty, a missing netlist, a netlist whose parts or sheets differ from the committed schematic's, and a sheet with no drawing. The command is `task hw:schematic-review-folder`, with add-view and add-document modes as the layout folder command's. Out of scope: exporting the netlist, drawing the sheets and running the check.
        status, text = sfx.run_folder(sfx.add_document_argv(self.out, self.document, item="NOPE-9"))
        self.assertEqual(status, 1)
        self.assertIn("is not on the folder's checklist", text)
        for target in ("/GHOST", "R99", "nowhere"):
            for argv in (sfx.add_view_argv(self.out, self.view, target=target), sfx.add_document_argv(self.out, self.document, target=target)):
                status, text = sfx.run_folder(argv)
                self.assertEqual(status, 1, text)
                self.assertIn(f"the '{target}' the cannot judge was about is no net, part or sheet", text)
        self.assertFalse(os.path.exists(os.path.join(self.out, "added-views")), "nothing was added")
        for target in ("/IN", "GND", "R1", "U1", "Power", "board"):
            shutil.rmtree(os.path.join(self.out, "added-views"), ignore_errors=True)
            status, text = sfx.run_folder(sfx.add_view_argv(self.out, self.view, target=target))
            self.assertEqual(status, 0, f"{target}: {text}")

    def test_the_refusals_of_the_layout_commands_add_modes_hold_for_the_schematic_folders(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C4: Over a synthetic repository with a committed schematic, an exported netlist and rendered sheet drawings, a command writes a review folder outside the repository holding the schematic and its project files as the commit holds them, the netlist, every record the review step reads, the sheet drawings, the method, the hardware notes and the check's report, and holds no review record for a first round and, for a later round, only the earlier rounds of the schematic review record as recorded, and no file the commit does not hold. It refuses a folder inside the repository, a folder that is not new or empty, a missing netlist, a netlist whose parts or sheets differ from the committed schematic's, and a sheet with no drawing. The command is `task hw:schematic-review-folder`, with add-view and add-document modes as the layout folder command's. Out of scope: exporting the netlist, drawing the sheets and running the check.
        missing = os.path.join(self.root, "nothing.svg")
        for name, argv, words in (
                ("a view that does not exist", sfx.add_view_argv(self.out, missing), ["does not exist"]),
                ("a view with an odd name", sfx.add_view_argv(self.out, self.view.replace("power-large.svg", "a b.svg")), ["does not exist"]),
                ("no item", sfx.add_view_argv(self.out, self.view, item=""), ["--cannot-judge-item"]),
                ("no why", sfx.add_view_argv(self.out, self.view, why=""), ["--cannot-judge-why"]),
                ("a document that does not exist", sfx.add_document_argv(self.out, missing), ["does not exist"]),
                ("no source", sfx.add_document_argv(self.out, self.document, source=""), ["--source"]),
                ("a folder the command did not write", sfx.add_view_argv(self.root, self.view), ["is not a review folder the command wrote"])):
            with self.subTest(name=name):
                status, text = sfx.run_folder(argv)
                self.assertEqual(status, 1, text)
                for word in words:
                    self.assertIn(word, text)
        sfx.write(os.path.join(self.root, "big.txt"), "x" * (64 * 1024 + 1))
        status, text = sfx.run_folder(sfx.add_document_argv(self.out, os.path.join(self.root, "big.txt")))
        self.assertIn("larger than 64 KiB", text)
        sfx.write(os.path.join(self.root, "bin.txt"), b"\xff\xfe")
        status, text = sfx.run_folder(sfx.add_document_argv(self.out, os.path.join(self.root, "bin.txt")))
        self.assertIn("not UTF-8 text", text)
        self.assertEqual(sfx.run_folder(sfx.add_view_argv(self.out, self.view))[0], 0)
        status, text = sfx.run_folder(sfx.add_view_argv(self.out, self.view))
        self.assertIn("already holds an added view named", text)
        with mock.patch("sys.stderr", new=io.StringIO()) as err, self.assertRaises(SystemExit):
            sfx.run_folder(sfx.add_view_argv(self.out, self.view) + ["--add-document", self.out])
        self.assertIn("separate modes", err.getvalue())

    def test_an_add_mode_given_a_layout_folder_refuses_a_target_and_the_schematic_command_refuses_nothing_else_of_it(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C4: Over a synthetic repository with a committed schematic, an exported netlist and rendered sheet drawings, a command writes a review folder outside the repository holding the schematic and its project files as the commit holds them, the netlist, every record the review step reads, the sheet drawings, the method, the hardware notes and the check's report, and holds no review record for a first round and, for a later round, only the earlier rounds of the schematic review record as recorded, and no file the commit does not hold. It refuses a folder inside the repository, a folder that is not new or empty, a missing netlist, a netlist whose parts or sheets differ from the committed schematic's, and a sheet with no drawing. The command is `task hw:schematic-review-folder`, with add-view and add-document modes as the layout folder command's. Out of scope: exporting the netlist, drawing the sheets and running the check.
        layout = lfx.write_review_folder(os.path.join(self.root, "layout"))
        status, text = sfx.run_folder(sfx.add_view_argv(layout, self.view, "FLOOR-1", target="x"))
        self.assertEqual(status, 1)
        self.assertIn("names a net, part or sheet, and this folder's review has none", text)
        status, text = lfx.run_folder(["--add-view", layout, "--view", self.view, "--view-command", "c", "--cannot-judge-item", "FLOOR-1",
                                       "--cannot-judge-why", "needs x: y", "--cannot-judge-target", "x"])
        self.assertEqual(status, 1, "the layout folder command refuses it too")
        status, text = sfx.run_folder(sfx.add_view_argv(layout, self.view, "FLOOR-1"))
        self.assertEqual(status, 0, "a layout folder is added to as the layout command adds to it")

    def test_a_target_in_a_resolutions_file_of_a_folder_that_is_not_a_schematic_reviews_is_refused_on_reading(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C4: Over a synthetic repository with a committed schematic, an exported netlist and rendered sheet drawings, a command writes a review folder outside the repository holding the schematic and its project files as the commit holds them, the netlist, every record the review step reads, the sheet drawings, the method, the hardware notes and the check's report, and holds no review record for a first round and, for a later round, only the earlier rounds of the schematic review record as recorded, and no file the commit does not hold. It refuses a folder inside the repository, a folder that is not new or empty, a missing netlist, a netlist whose parts or sheets differ from the committed schematic's, and a sheet with no drawing. The command is `task hw:schematic-review-folder`, with add-view and add-document modes as the layout folder command's. Out of scope: exporting the netlist, drawing the sheets and running the check.
        layout = lfx.write_review_folder(os.path.join(self.root, "layout"))
        status, text = lfx.run_folder(["--add-view", layout, "--view", self.view, "--view-command", "c", "--cannot-judge-item",
                                       "FLOOR-1", "--cannot-judge-why", "needs x: y"])
        self.assertEqual(status, 0, text)
        path = os.path.join(layout, "added-views", "resolutions.json")
        content = json.loads(slurp(path))
        content["resolutions"][0]["target"] = "U1"
        sfx.write(path, json.dumps(content))
        with self.assertRaises(review_folder.ReviewFolderProblem) as caught:
            review_folder.read_resolutions(layout)
        self.assertIn("only a schematic review's folder records", str(caught.exception))
        content["resolutions"][0].pop("target")
        content["resolutions"][0]["bogus"] = "x"
        sfx.write(path, json.dumps(content))
        with self.assertRaises(review_folder.ReviewFolderProblem):
            review_folder.read_resolutions(layout)

    def test_a_round_file_of_another_review_is_not_a_folder_the_schematic_add_modes_add_to_a_view_for(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C4: Over a synthetic repository with a committed schematic, an exported netlist and rendered sheet drawings, a command writes a review folder outside the repository holding the schematic and its project files as the commit holds them, the netlist, every record the review step reads, the sheet drawings, the method, the hardware notes and the check's report, and holds no review record for a first round and, for a later round, only the earlier rounds of the schematic review record as recorded, and no file the commit does not hold. It refuses a folder inside the repository, a folder that is not new or empty, a missing netlist, a netlist whose parts or sheets differ from the committed schematic's, and a sheet with no drawing. The command is `task hw:schematic-review-folder`, with add-view and add-document modes as the layout folder command's. Out of scope: exporting the netlist, drawing the sheets and running the check.
        sfx.set_round(self.out, fields=["number", "commit", "views"], number=1, views=["v"], netlist=None, records=None)
        status, text = sfx.run_folder(sfx.add_view_argv(self.out, self.view, "STRAP-1"))
        self.assertEqual(status, 0, "a critical-routing-shaped folder takes a view as it always did")


class TheSharedRoundFile(Case):
    def test_every_reviews_round_file_is_refused_a_key_it_does_not_own_through_one_helper(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C4: Over a synthetic repository with a committed schematic, an exported netlist and rendered sheet drawings, a command writes a review folder outside the repository holding the schematic and its project files as the commit holds them, the netlist, every record the review step reads, the sheet drawings, the method, the hardware notes and the check's report, and holds no review record for a first round and, for a later round, only the earlier rounds of the schematic review record as recorded, and no file the commit does not hold. It refuses a folder inside the repository, a folder that is not new or empty, a missing netlist, a netlist whose parts or sheets differ from the committed schematic's, and a sheet with no drawing. The command is `task hw:schematic-review-folder`, with add-view and add-document modes as the layout folder command's. Out of scope: exporting the netlist, drawing the sheets and running the check.
        self.assertEqual(review_folder.stray_keys({"tool": "t", "fields": ["number"], "number": 1, "x": 1, "a": 2}, ["number"]), ["a", "x"])
        self.assertEqual(review_folder.stray_keys({"tool": "t", "fields": ["kind"], "kind": "narrow", "items": [], "regions": [], "others": ""},
                                                  ["kind"]), [], "a set with a kind owns a narrow round's three keys")
        self.assertEqual(review_folder.stray_keys({"tool": "t", "fields": ["number"], "number": 1, "items": []}, ["number"]), ["items"])
        self.written()
        good = sfx.round_file(self.out)
        for name, change, word in (("schematic", {"bogus": 1}, "holds bogus"), ("schematic", {"kind": "full"}, "holds kind"),
                                   ("schematic", {"views": ["v"]}, "holds views")):
            with self.subTest(name=name, change=change):
                sfx.write(os.path.join(self.out, "round.json"), json.dumps({**good, **change}))
                with self.assertRaises(review_folder.ReviewFolderProblem) as caught:
                    review_folder.read_round(self.out)
                self.assertIn(word, str(caught.exception))
        layout = lfx.write_review_folder(os.path.join(self.root, "layout"))
        lfx.set_round(layout, bogus=1)
        with self.assertRaises(review_folder.ReviewFolderProblem) as caught:
            review_folder.read_round(layout)
        self.assertIn("holds bogus", str(caught.exception))
        critical = lfx.write_critical_folder(os.path.join(self.root, "critical"))
        lfx.set_round(critical, bogus=1)
        with self.assertRaises(review_folder.ReviewFolderProblem):
            review_folder.read_round(critical)

    def test_the_four_reviews_field_sets_are_told_apart_by_the_whole_set_and_never_by_one_field(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C4: Over a synthetic repository with a committed schematic, an exported netlist and rendered sheet drawings, a command writes a review folder outside the repository holding the schematic and its project files as the commit holds them, the netlist, every record the review step reads, the sheet drawings, the method, the hardware notes and the check's report, and holds no review record for a first round and, for a later round, only the earlier rounds of the schematic review record as recorded, and no file the commit does not hold. It refuses a folder inside the repository, a folder that is not new or empty, a missing netlist, a netlist whose parts or sheets differ from the committed schematic's, and a sheet with no drawing. The command is `task hw:schematic-review-folder`, with add-view and add-document modes as the layout folder command's. Out of scope: exporting the netlist, drawing the sheets and running the check.
        self.assertTrue(review_folder.is_schematic_fields(["number", "commit", "netlist", "records"]))
        self.assertFalse(review_folder.is_schematic_fields(["number", "commit", "netlist"]))
        self.assertFalse(review_folder.is_schematic_fields(["commit", "number", "netlist", "records"]))
        self.assertFalse(review_folder.is_schematic_fields(["number", "commit", "views"]))
        self.assertFalse(review_folder.is_production_fields(["number", "commit", "netlist", "records"]))
        self.assertFalse(review_folder.is_critical_routing_fields(["number", "commit", "netlist", "records"]))
        self.written()
        good = sfx.round_file(self.out)
        for fields in (["number", "commit", "netlist"], ["number", "commit", "records"], ["number", "commit", "netlist", "records", "views"],
                       ["number", "commit", "netlist", "records", "tools"], ["commit", "tools", "commands", "preview", "netlist"]):
            with self.subTest(fields=fields):
                sfx.write(os.path.join(self.out, "round.json"), json.dumps({**good, "fields": fields, "views": ["v"], "tools": "t",
                                                                          "commands": ["c"], "preview": "p"}))
                with self.assertRaises(review_folder.ReviewFolderProblem) as caught:
                    review_folder.read_round(self.out)
                self.assertIn("mixes", str(caught.exception))
        self.assertIn("netlist", review_folder.FIELD_NAMES)
        self.assertIn("records", review_folder.FIELD_NAMES)
        self.assertEqual(review_folder.REVIEW_FIELDS, {"layout": review_folder.LAYOUT_FIELDS,
                                                       "critical-routing": review_folder.CRITICAL_FIELDS})


class TheFacts(unittest.TestCase):
    """The nets, parts and sheets read from a netlist and from a schematic's files, without KiCad."""

    def schematic(self, files, design="board"):
        return schematic_facts.schematic_names(lambda path: files.get(path), design)

    def test_a_netlist_names_its_nets_its_parts_and_its_sheets_the_root_by_the_designs_name(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C2: Over a synthetic netlist, a synthetic sheet list and synthetic unit results, the merge fails naming a catalogue item with no verdict row, a net, part or sheet of the netlist or sheet list that appears in no item's rows, and a row that names a net, part or sheet that does not exist. It rejects a table with a column the method's table does not have, numbers this round's findings at the merge as the kit does, and gives the same record whatever order the units arrive in. It fails a round that still holds a cannot judge, naming the item and what it needs, and renders a resolved one as `cannot judge, then <verdict>`. Out of scope: which nets an item selects, whether a verdict is right, and the free pass.
        found = schematic_facts.netlist_names(sfx.NETLIST, "board")
        self.assertEqual(sorted(found.nets), sorted(sfx.NETS))
        self.assertEqual(sorted(found.parts), sorted(sfx.PARTS))
        self.assertEqual(sorted(found.sheets), ["Power", "board"])
        self.assertEqual(schematic_facts.sheet_of_netlist("/", "d"), "d")
        self.assertEqual(schematic_facts.sheet_of_netlist("/Power/Reg/", "d"), "Power/Reg")
        nameless = sfx.NETLIST.replace('(name "GND")', '(name "")')
        self.assertNotIn("", schematic_facts.netlist_names(nameless, "board").nets, "a net with no name is left out")

    def test_a_schematics_parts_are_its_symbols_references_for_the_project_and_power_symbols_are_no_parts(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C2: Over a synthetic netlist, a synthetic sheet list and synthetic unit results, the merge fails naming a catalogue item with no verdict row, a net, part or sheet of the netlist or sheet list that appears in no item's rows, and a row that names a net, part or sheet that does not exist. It rejects a table with a column the method's table does not have, numbers this round's findings at the merge as the kit does, and gives the same record whatever order the units arrive in. It fails a round that still holds a cannot judge, naming the item and what it needs, and renders a resolved one as `cannot judge, then <verdict>`. Out of scope: which nets an item selects, whether a verdict is right, and the free pass.
        parts, sheets = self.schematic({"board.kicad_sch": sfx.ROOT_SCH, "power.kicad_sch": sfx.POWER_SCH})
        self.assertEqual(sorted(parts), sorted(sfx.PARTS))
        self.assertNotIn("#PWR01", parts)
        self.assertEqual(sorted(sheets), ["Power", "board"])
        other = sfx.POWER_SCH.replace('(project "board"', '(project "elsewhere"')
        parts, _ = self.schematic({"board.kicad_sch": sfx.ROOT_SCH, "power.kicad_sch": other})
        self.assertIn("R2", parts, "references of another project are taken when none is given for this one")
        mixed = sfx.POWER_SCH.replace('(instances (project "board"', '(instances (project "elsewhere" (path "/x" (reference "Z9")))(project "board"', 1)
        parts, _ = self.schematic({"board.kicad_sch": sfx.ROOT_SCH, "power.kicad_sch": mixed})
        self.assertNotIn("Z9", parts, "this project's references win over another's")
        bare = sfx.POWER_SCH.replace('(instances (project "board" (path "/00000000-0000-0000-0000-000000000001/00000000-0000-0000-0000-0000000000a2" (reference "R2") (unit 1))))', "")
        parts, _ = self.schematic({"board.kicad_sch": sfx.ROOT_SCH, "power.kicad_sch": bare})
        self.assertIn("R2", parts, "a symbol with no instances gives its Reference property")

    def test_a_sheet_placed_twice_is_two_sheets_and_a_sheet_below_a_sheet_is_named_by_the_names_leading_to_it(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C2: Over a synthetic netlist, a synthetic sheet list and synthetic unit results, the merge fails naming a catalogue item with no verdict row, a net, part or sheet of the netlist or sheet list that appears in no item's rows, and a row that names a net, part or sheet that does not exist. It rejects a table with a column the method's table does not have, numbers this round's findings at the merge as the kit does, and gives the same record whatever order the units arrive in. It fails a round that still holds a cannot judge, naming the item and what it needs, and renders a resolved one as `cannot judge, then <verdict>`. Out of scope: which nets an item selects, whether a verdict is right, and the free pass.
        root = sfx.ROOT_SCH.replace('(property "Sheetname" "Power") (property "Sheetfile" "power.kicad_sch"))',
                                    '(property "Sheetname" "A") (property "Sheetfile" "sub.kicad_sch"))\n (sheet (at 1 1) (size 1 1) '
                                    '(property "Sheetname" "B") (property "Sheetfile" "sub.kicad_sch"))')
        sub = '(kicad_sch (sheet (at 1 1) (size 1 1) (property "Sheetname" "Inner") (property "Sheetfile" "inner/leaf.kicad_sch")))'
        leaf = sfx.POWER_SCH
        parts, sheets = self.schematic({"board.kicad_sch": root, "sub.kicad_sch": sub, "inner/leaf.kicad_sch": leaf})
        self.assertEqual(sorted(sheets), ["A", "A/Inner", "B", "B/Inner", "board"])
        self.assertEqual(sorted(parts), ["C1", "R1", "R2", "U1"])

    def test_a_schematic_that_places_itself_below_itself_is_followed_once(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C2: Over a synthetic netlist, a synthetic sheet list and synthetic unit results, the merge fails naming a catalogue item with no verdict row, a net, part or sheet of the netlist or sheet list that appears in no item's rows, and a row that names a net, part or sheet that does not exist. It rejects a table with a column the method's table does not have, numbers this round's findings at the merge as the kit does, and gives the same record whatever order the units arrive in. It fails a round that still holds a cannot judge, naming the item and what it needs, and renders a resolved one as `cannot judge, then <verdict>`. Out of scope: which nets an item selects, whether a verdict is right, and the free pass.
        looping = sfx.ROOT_SCH.replace('"power.kicad_sch"', '"board.kicad_sch"')
        parts, sheets = self.schematic({"board.kicad_sch": looping})
        self.assertEqual(sorted(sheets), ["Power", "board"])

    def test_a_schematic_file_that_is_missing_or_cut_off_is_a_problem_naming_it(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C2: Over a synthetic netlist, a synthetic sheet list and synthetic unit results, the merge fails naming a catalogue item with no verdict row, a net, part or sheet of the netlist or sheet list that appears in no item's rows, and a row that names a net, part or sheet that does not exist. It rejects a table with a column the method's table does not have, numbers this round's findings at the merge as the kit does, and gives the same record whatever order the units arrive in. It fails a round that still holds a cannot judge, naming the item and what it needs, and renders a resolved one as `cannot judge, then <verdict>`. Out of scope: which nets an item selects, whether a verdict is right, and the free pass.
        with self.assertRaises(schematic_facts.FactsProblem) as caught:
            self.schematic({"board.kicad_sch": sfx.ROOT_SCH})
        self.assertIn("power.kicad_sch is not among the files given", str(caught.exception))
        with self.assertRaises(schematic_facts.FactsProblem) as caught:
            self.schematic({})
        self.assertIn("board.kicad_sch", str(caught.exception))
        with self.assertRaises(schematic_facts.FactsProblem) as caught:
            self.schematic({"board.kicad_sch": "(kicad_sch ("})
        self.assertIn("cannot be read", str(caught.exception))

    def test_the_design_is_named_by_its_one_project_file(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C2: Over a synthetic netlist, a synthetic sheet list and synthetic unit results, the merge fails naming a catalogue item with no verdict row, a net, part or sheet of the netlist or sheet list that appears in no item's rows, and a row that names a net, part or sheet that does not exist. It rejects a table with a column the method's table does not have, numbers this round's findings at the merge as the kit does, and gives the same record whatever order the units arrive in. It fails a round that still holds a cannot judge, naming the item and what it needs, and renders a resolved one as `cannot judge, then <verdict>`. Out of scope: which nets an item selects, whether a verdict is right, and the free pass.
        self.assertEqual(schematic_facts.design_name(["a.kicad_pro", "a.kicad_sch", "sub/b.kicad_pro"]), "a")
        for names in ([], ["a.kicad_pro", "b.kicad_pro"], ["sub/a.kicad_pro"]):
            with self.assertRaises(schematic_facts.FactsProblem):
                schematic_facts.design_name(names)

    def test_a_folders_names_are_its_netlists_and_its_schematics_and_are_empty_when_it_cannot_be_read(self):
        # SOL-HW-REVIEW-FAN-OUT-SCHEMATIC.C2: Over a synthetic netlist, a synthetic sheet list and synthetic unit results, the merge fails naming a catalogue item with no verdict row, a net, part or sheet of the netlist or sheet list that appears in no item's rows, and a row that names a net, part or sheet that does not exist. It rejects a table with a column the method's table does not have, numbers this round's findings at the merge as the kit does, and gives the same record whatever order the units arrive in. It fails a round that still holds a cannot judge, naming the item and what it needs, and renders a resolved one as `cannot judge, then <verdict>`. Out of scope: which nets an item selects, whether a verdict is right, and the free pass.
        root = tempfile.mkdtemp(prefix="schematic-facts-test-")
        self.addCleanup(shutil.rmtree, root, True)
        folder = sfx.write_review_folder(root)
        self.assertEqual(schematic_facts.folder_names(folder), set(sfx.NETS) | set(sfx.PARTS) | set(sfx.SHEETS))
        os.remove(os.path.join(folder, "review.net"))
        self.assertEqual(schematic_facts.folder_names(folder), set())
        self.assertEqual(schematic_facts.folder_names(os.path.join(root, "nowhere")), set())


if __name__ == "__main__":
    unittest.main()
