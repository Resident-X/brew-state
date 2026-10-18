#!/usr/bin/env python3
"""The schematic sheet drawing command, run against the real kicad-cli on synthetic designs in throwaway repositories.

Each repository is written from text in a temporary folder outside this one:
a design with a sheet below its root, a second design in another folder, and
variations that cannot be drawn. The command is run through its own entry point
and, once, through the shipped task. Nothing is skipped when KiCad is absent:
a command that cannot be exercised has not been shown to work.
"""

from __future__ import annotations

import contextlib
import io
import os
import re
import stat
import subprocess
import sys
import tempfile
import unittest

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import board_check  # noqa: E402
import board_fixtures  # noqa: E402
import schematic_sheets  # noqa: E402

REPO = os.path.dirname(os.path.dirname(TOOLS))
KICAD_CLI = os.environ.get("KICAD_CLI") or "kicad-cli"

_SCRATCH = []


def setUpModule():
    board_fixtures.require_tools(KICAD_CLI)


def tearDownModule():
    board_fixtures.cleanup()
    while _SCRATCH:
        _SCRATCH.pop().cleanup()


def schematic(identifier: int, sheets=()) -> str:
    """A schematic holding no part, with a sub-sheet for each (name, file) of `sheets`."""
    boxes = "".join(
        f'\t(sheet (at 20 {20 + 30 * index}) (size 30 20) (uuid "00000000-0000-4000-8000-{identifier * 10 + index + 1:012d}")\n'
        f'\t\t(property "Sheetname" "{name}" (at 20 {19 + 30 * index} 0))\n'
        f'\t\t(property "Sheetfile" "{file}" (at 20 {41 + 30 * index} 0))\n'
        f'\t\t(instances (project "proof" (path "/00000000-0000-4000-8000-{identifier:012d}" (page "{index + 2}"))))\n\t)\n'
        for index, (name, file) in enumerate(sheets))
    return ('(kicad_sch\n\t(version 20250114)\n\t(generator "eeschema")\n\t(generator_version "10.0")\n'
            f'\t(uuid "00000000-0000-4000-8000-{identifier:012d}")\n\t(paper "A4")\n\t(lib_symbols)\n' + boxes +
            '\t(sheet_instances (path "/" (page "1")))\n\t(embedded_fonts no)\n)\n')


class Repository:
    """A git repository in a temporary folder, with a working folder beside it for what the command writes."""

    def __init__(self):
        scratch = tempfile.TemporaryDirectory(prefix="schematic-sheets-test-")
        _SCRATCH.append(scratch)
        self.base = scratch.name
        self.root = os.path.join(self.base, "repository")
        os.makedirs(self.root)
        self.out = os.path.join(self.base, "sheets")
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.email", "test@example.invalid")
        self.git("config", "user.name", "test")

    def git(self, *args):
        result = subprocess.run(["git", "-C", self.root, *args], capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
        return result.stdout

    def write(self, path: str, text: str) -> None:
        full = os.path.join(self.root, path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as handle:
            handle.write(text)

    def design(self, folder: str, name: str, sheets=(), identifier: int = 1) -> None:
        """A design called `name` in `folder`: its project, schematic and layout, and a file for each sub-sheet."""
        self.write(f"{folder}/{name}.kicad_pro", board_fixtures.project())
        self.write(f"{folder}/{name}.kicad_pcb", board_fixtures.layout([]))
        self.write(f"{folder}/{name}.kicad_sch", schematic(identifier, sheets))
        for index, (_, file) in enumerate(sheets):
            self.write(f"{folder}/{file}", schematic(identifier + 100 + index))

    def commit(self) -> None:
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "designs")

    def listing(self):
        """Every file and folder under the repository, git's own folder aside, with its modification time and size."""
        found = {}
        for folder, names, files in os.walk(self.root):
            names[:] = [name for name in names if name != ".git"]
            for name in names + files:
                path = os.path.join(folder, name)
                found[os.path.relpath(path, self.root)] = (os.stat(path).st_mtime_ns, os.stat(path).st_size)
        return found

    def run(self, kicad_cli: str = KICAD_CLI, out: str = None):
        """The command's exit status and its printed lines."""
        stream = io.StringIO()
        status = schematic_sheets.sheets(self.root, self.out if out is None else out, kicad_cli, out=stream)
        return status, stream.getvalue().splitlines()

    def written(self, out: str = None):
        """Every file under the output folder, relative to it."""
        out = self.out if out is None else out
        return sorted(os.path.relpath(os.path.join(folder, name), out)
                      for folder, _, files in os.walk(out) for name in files)


def two_designs() -> Repository:
    repo = Repository()
    repo.design("boards/controller", "controller", [("Power input", "power.kicad_sch"), ("Sense", "sense.kicad_sch")])
    repo.design("boards/panel", "panel", identifier=2)
    repo.commit()
    return repo


class Draws(unittest.TestCase):
    def test_every_sheet_of_every_tracked_design_is_written_as_its_own_vector_image(self):
        # SOL-BOARD-SCHEMATIC-DRAWING-CONVENTION.C3: A command of the project's task runner writes one image file per sheet of every board design git tracks
        repo = two_designs()
        status, lines = repo.run()
        self.assertEqual(status, 0, "\n".join(lines))
        self.assertEqual(repo.written(), [
            "boards/controller/controller-Power input.svg", "boards/controller/controller-Sense.svg",
            "boards/controller/controller.svg", "boards/panel/panel.svg"])
        for name in repo.written():
            with open(os.path.join(repo.out, name), encoding="utf-8") as handle:
                self.assertRegex(handle.read(), r"<svg\s", f"{name} is not a vector image")
        self.assertEqual(sum(line.startswith("SHEET | ") for line in lines), 4, lines)
        self.assertEqual(lines[-1].split(" | ")[:2], ["RESULT", "PASS"], lines)

    def test_two_designs_of_one_name_in_different_folders_do_not_overwrite_each_other(self):
        # SOL-BOARD-SCHEMATIC-DRAWING-CONVENTION.C3: A command of the project's task runner writes one image file per sheet of every board design git tracks
        repo = Repository()
        repo.design("one", "board", [("Supply", "supply.kicad_sch")])
        repo.design("two", "board", identifier=2)
        repo.commit()
        status, lines = repo.run()
        self.assertEqual(status, 0, "\n".join(lines))
        self.assertEqual(repo.written(), ["one/board-Supply.svg", "one/board.svg", "two/board.svg"])

    def test_the_drawing_comes_from_the_tracked_files_and_not_from_a_file_beside_them(self):
        # SOL-BOARD-SCHEMATIC-DRAWING-CONVENTION.C3: from a copy of the tracked files as the pre-order check reads a design
        repo = two_designs()
        repo.write("boards/panel/stray.kicad_sch", schematic(900))
        repo.write("boards/panel/notes.txt", "left lying beside the design\n")
        status, lines = repo.run()
        self.assertEqual(status, 0, "\n".join(lines))
        self.assertNotIn("boards/panel/stray.svg", repo.written())
        self.assertEqual(len(repo.written()), 4)

    def test_a_sheet_git_does_not_track_fails_its_design_by_name_and_the_rest_are_still_drawn(self):
        # SOL-BOARD-SCHEMATIC-DRAWING-CONVENTION.C3: fails a design it cannot read by name
        repo = two_designs()
        repo.git("rm", "-q", "--cached", "boards/controller/sense.kicad_sch")
        status, lines = repo.run()
        self.assertEqual(status, 1, "\n".join(lines))
        failed = [line for line in lines if line.startswith("DESIGN | ") and "| FAIL |" in line]
        self.assertEqual(len(failed), 1, lines)
        self.assertIn("boards/controller/controller.kicad_pro", failed[0])
        self.assertIn("sense.kicad_sch", failed[0])
        self.assertEqual(repo.written(), ["boards/panel/panel.svg"])
        self.assertEqual(lines[-1].split(" | ")[:2], ["RESULT", "FAIL"], lines)


class Hierarchy(unittest.TestCase):
    def test_a_three_level_hierarchy_with_a_sheet_file_placed_twice_is_written_one_image_per_sheet_instance(self):
        # SOL-BOARD-SCHEMATIC-DRAWING-CONVENTION.C3: A command of the project's task runner writes one image file per sheet of every board design git tracks
        repo = Repository()
        repo.write("d/d.kicad_pro", board_fixtures.project())
        repo.write("d/d.kicad_pcb", board_fixtures.layout([]))
        repo.write("d/d.kicad_sch", schematic(1, [("Left", "unit.kicad_sch"), ("Right", "unit.kicad_sch"), ("Misc", "misc.kicad_sch")]))
        repo.write("d/unit.kicad_sch", schematic(2, [("Deep", "deep.kicad_sch")]))
        repo.write("d/misc.kicad_sch", schematic(3))
        repo.write("d/deep.kicad_sch", schematic(4))
        repo.commit()
        status, lines = repo.run()
        self.assertEqual(status, 0, "\n".join(lines))
        self.assertEqual(repo.written(), ["d/d-Left-Deep.svg", "d/d-Left.svg", "d/d-Misc.svg", "d/d-Right-Deep.svg",
                                          "d/d-Right.svg", "d/d.svg"])
        self.assertTrue(any(line.startswith("DESIGN | ") and "| PASS | 6 sheets" in line for line in lines), lines)

    def test_the_expected_sheets_are_read_from_the_tracked_schematics_one_for_each_place_a_sheet_file_is_placed(self):
        # SOL-BOARD-SCHEMATIC-DRAWING-CONVENTION.C3: A command of the project's task runner writes one image file per sheet of every board design git tracks
        repo = Repository()
        repo.design("d", "d", [("Left", "unit.kicad_sch"), ("Right", "unit.kicad_sch")])
        repo.commit()
        replica = repo.root
        expected = board_check.sheet_instances(replica, "d/d.kicad_sch", set(board_check.tracked_files("git", replica)))
        self.assertEqual(expected, [(), ("Left",), ("Right",)])

    def test_the_expected_sheets_include_every_level_of_nesting_and_end_at_a_schematic_that_contains_itself(self):
        # SOL-BOARD-SCHEMATIC-DRAWING-CONVENTION.C3: A command of the project's task runner writes one image file per sheet of every board design git tracks
        repo = Repository()
        repo.write("d/d.kicad_sch", schematic(1, [("Left", "unit.kicad_sch"), ("Right", "unit.kicad_sch"), ("Misc", "misc.kicad_sch")]))
        repo.write("d/unit.kicad_sch", schematic(2, [("Deep", "deep.kicad_sch")]))
        repo.write("d/misc.kicad_sch", schematic(3, [("Again", "misc.kicad_sch")]))
        repo.write("d/deep.kicad_sch", schematic(4))
        repo.commit()
        expected = board_check.sheet_instances(repo.root, "d/d.kicad_sch", set(board_check.tracked_files("git", repo.root)))
        self.assertEqual(expected, [(), ("Left",), ("Left", "Deep"), ("Right",), ("Right", "Deep"), ("Misc",), ("Misc", "Again")])


class FailsWhatItCannotRead(unittest.TestCase):
    def test_a_schematic_kicad_cannot_read_fails_its_design_by_name_and_another_design_is_still_drawn(self):
        # SOL-BOARD-SCHEMATIC-DRAWING-CONVENTION.C3: fails a design it cannot read by name
        repo = two_designs()
        repo.write("boards/panel/panel.kicad_sch", "(kicad_sch (version 20250114) (this is not\n")
        repo.commit()
        status, lines = repo.run()
        self.assertEqual(status, 1, "\n".join(lines))
        failed = [line for line in lines if "| FAIL |" in line and line.startswith("DESIGN | ")]
        self.assertEqual(len(failed), 1, lines)
        self.assertIn("boards/panel/panel.kicad_pro", failed[0])
        self.assertIn("boards/controller/controller.svg", repo.written())
        self.assertFalse(any(name.startswith("boards/panel/") for name in repo.written()), repo.written())

    def test_a_schematic_that_is_empty_fails_its_design_rather_than_writing_nothing_and_passing(self):
        # SOL-BOARD-SCHEMATIC-DRAWING-CONVENTION.C3: fails a design it cannot read by name
        repo = two_designs()
        repo.write("boards/panel/panel.kicad_sch", "")
        repo.commit()
        status, lines = repo.run()
        self.assertEqual(status, 1, "\n".join(lines))
        self.assertTrue(any("boards/panel/panel.kicad_pro" in line and "| FAIL |" in line for line in lines), lines)

    def partial_kicad(self, repo: Repository) -> str:
        """The real design tool wrapped so that drawing a schematic exits 0 having kept only the root sheet's image."""
        path = os.path.join(repo.base, "partial-kicad-cli")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(f'#!/bin/sh\n"{KICAD_CLI}" "$@"\nstatus=$?\n'
                         'if [ "$1" = "sch" ]; then\n'
                         '  stem=$(basename "$6" .kicad_sch)\n'
                         '  for f in "$5"/*.svg; do [ "$f" = "$5/$stem.svg" ] || rm -f "$f"; done\n'
                         '  exit 0\nfi\nexit $status\n')
        os.chmod(path, os.stat(path).st_mode | stat.S_IXUSR)
        return path

    def test_a_tool_that_exits_zero_having_drawn_fewer_images_than_the_design_has_sheets_fails_the_design_naming_the_sheets(self):
        # SOL-BOARD-SCHEMATIC-DRAWING-CONVENTION.C3: fails a design it cannot read by name
        repo = Repository()
        repo.design("boards/controller", "controller", [("Power input", "power.kicad_sch"), ("Sense", "sense.kicad_sch")])
        repo.design("boards/panel", "panel", identifier=2)
        repo.commit()
        status, lines = repo.run(self.partial_kicad(repo))
        self.assertEqual(status, 1, "\n".join(lines))
        failed = [line for line in lines if line.startswith("DESIGN | ") and "| FAIL |" in line]
        self.assertEqual(len(failed), 1, lines)
        self.assertIn("boards/controller/controller.kicad_pro", failed[0])
        self.assertIn("/Power input", failed[0])
        self.assertIn("/Sense", failed[0])
        self.assertNotIn("(root)", failed[0])
        self.assertEqual(repo.written(), ["boards/panel/panel.svg"])
        self.assertEqual(lines[-1].split(" | ")[:2], ["RESULT", "FAIL"], lines)

    def test_a_sheet_file_a_tracked_schematic_names_that_the_repository_does_not_hold_fails_its_design_by_name(self):
        # SOL-BOARD-SCHEMATIC-DRAWING-CONVENTION.C3: fails a design it cannot read by name
        repo = two_designs()
        repo.git("rm", "-q", "-f", "boards/controller/power.kicad_sch")
        repo.git("commit", "-q", "-m", "remove a sheet")
        status, lines = repo.run()
        self.assertEqual(status, 1, "\n".join(lines))
        failed = [line for line in lines if line.startswith("DESIGN | ") and "| FAIL |" in line]
        self.assertEqual(len(failed), 1, lines)
        self.assertIn("boards/controller/controller.kicad_pro", failed[0])
        self.assertIn("power.kicad_sch", failed[0])
        self.assertEqual(repo.written(), ["boards/panel/panel.svg"])

    def test_a_project_with_no_tracked_schematic_fails_by_name(self):
        # SOL-BOARD-SCHEMATIC-DRAWING-CONVENTION.C3: fails a design it cannot read by name
        repo = two_designs()
        repo.git("rm", "-q", "--cached", "boards/panel/panel.kicad_sch")
        status, lines = repo.run()
        self.assertEqual(status, 1, "\n".join(lines))
        self.assertTrue(any("boards/panel/panel.kicad_pro" in line and "| FAIL |" in line for line in lines), lines)

    def test_a_schematic_tracked_without_a_project_fails_by_name(self):
        # SOL-BOARD-SCHEMATIC-DRAWING-CONVENTION.C3: fails a design it cannot read by name
        repo = two_designs()
        repo.write("boards/loose/loose.kicad_sch", schematic(7))
        repo.commit()
        status, lines = repo.run()
        self.assertEqual(status, 1, "\n".join(lines))
        self.assertTrue(any("boards/loose/loose.kicad_sch" in line and "| FAIL |" in line for line in lines), lines)

    def test_an_empty_set_of_designs_fails_and_writes_nothing(self):
        # SOL-BOARD-SCHEMATIC-DRAWING-CONVENTION.C3: an empty set of designs fails rather than succeeds
        repo = Repository()
        repo.write("notes.md", "no board here\n")
        repo.commit()
        status, lines = repo.run()
        self.assertEqual(status, 1, "\n".join(lines))
        self.assertTrue(any(line.startswith("REFUSED | no board design was found") for line in lines), lines)
        self.assertFalse(os.path.exists(repo.out))

    def test_a_repository_tracking_nothing_fails_too(self):
        # SOL-BOARD-SCHEMATIC-DRAWING-CONVENTION.C3: an empty set of designs fails rather than succeeds
        repo = Repository()
        status, lines = repo.run()
        self.assertEqual(status, 1, "\n".join(lines))
        self.assertFalse(os.path.exists(repo.out))


class WritesOnlyWhereItShould(unittest.TestCase):
    def test_nothing_is_written_into_the_repository_and_its_tracked_files_are_untouched(self):
        # SOL-BOARD-SCHEMATIC-DRAWING-CONVENTION.C3: It writes nothing into the repository's tracked paths.
        repo = two_designs()
        before, status_before = repo.listing(), repo.git("status", "--porcelain=v1", "--ignored")
        status, lines = repo.run()
        self.assertEqual(status, 0, "\n".join(lines))
        self.assertEqual(repo.listing(), before)
        self.assertEqual(repo.git("status", "--porcelain=v1", "--ignored"), status_before)
        self.assertEqual(status_before, "")

    def test_nothing_is_written_into_the_repository_when_a_design_fails(self):
        # SOL-BOARD-SCHEMATIC-DRAWING-CONVENTION.C3: It writes nothing into the repository's tracked paths.
        repo = two_designs()
        repo.write("boards/panel/panel.kicad_sch", "(kicad_sch (not closed\n")
        repo.commit()
        before = repo.listing()
        status, _ = repo.run()
        self.assertEqual(status, 1)
        self.assertEqual(repo.listing(), before)

    def test_an_output_folder_inside_a_designs_folder_is_refused_and_nothing_is_written(self):
        # SOL-BOARD-SCHEMATIC-DRAWING-CONVENTION.C3: into a new or empty folder outside every design's folder
        repo = two_designs()
        for inside in ("boards/panel/sheets", "boards/panel", "boards/controller/deeper/still"):
            out = os.path.join(repo.root, inside)
            before = repo.listing()
            status, lines = repo.run(out=out)
            self.assertEqual(status, 1, f"{inside}: " + "\n".join(lines))
            self.assertTrue(any(line.startswith("REFUSED | ") and "design's folder" in line for line in lines), lines)
            self.assertEqual(repo.listing(), before, inside)

    def test_an_output_folder_already_holding_files_is_refused_and_left_as_it_was(self):
        # SOL-BOARD-SCHEMATIC-DRAWING-CONVENTION.C3: into a new or empty folder
        repo = two_designs()
        os.makedirs(repo.out)
        with open(os.path.join(repo.out, "earlier.svg"), "w", encoding="utf-8") as handle:
            handle.write("<svg/>")
        status, lines = repo.run()
        self.assertEqual(status, 1, "\n".join(lines))
        self.assertTrue(any(line.startswith("REFUSED | ") and "already holds files" in line for line in lines), lines)
        self.assertEqual(repo.written(), ["earlier.svg"])

    def test_an_output_path_that_is_a_file_is_refused(self):
        # SOL-BOARD-SCHEMATIC-DRAWING-CONVENTION.C3: into a new or empty folder
        repo = two_designs()
        with open(repo.out, "w", encoding="utf-8") as handle:
            handle.write("a file\n")
        status, lines = repo.run()
        self.assertEqual(status, 1, "\n".join(lines))
        self.assertTrue(any(line.startswith("REFUSED | ") and "is a file" in line for line in lines), lines)

    def test_an_existing_empty_output_folder_is_accepted(self):
        # SOL-BOARD-SCHEMATIC-DRAWING-CONVENTION.C3: into a new or empty folder
        repo = two_designs()
        os.makedirs(repo.out)
        status, lines = repo.run()
        self.assertEqual(status, 0, "\n".join(lines))
        self.assertEqual(len(repo.written()), 4)


class NamesTheTool(unittest.TestCase):
    def main(self, kicad_cli: str, repo: Repository):
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr), contextlib.redirect_stdout(io.StringIO()):
            status = schematic_sheets.main(["--root", repo.root, "--kicad-cli", kicad_cli, "--out", repo.out])
        return status, stderr.getvalue()

    def fake(self, repo: Repository, said: str) -> str:
        path = os.path.join(repo.base, "fake-kicad-cli")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(f"#!/bin/sh\necho '{said}'\n")
        os.chmod(path, os.stat(path).st_mode | stat.S_IXUSR)
        return path

    def test_a_missing_kicad_stops_with_a_line_naming_the_tool_and_writes_nothing(self):
        # SOL-BOARD-SCHEMATIC-DRAWING-CONVENTION.C3: It stops with a line naming the tool when the design tool is missing or too old
        repo = two_designs()
        status, said = self.main(os.path.join(repo.base, "no-such-kicad-cli"), repo)
        self.assertEqual(status, 2)
        self.assertRegex(said, r"^CANNOT RUN \| kicad-cli was not found")
        self.assertIn("no-such-kicad-cli", said)
        self.assertFalse(os.path.exists(repo.out))

    def test_a_kicad_older_than_the_minimum_stops_with_a_line_naming_the_tool_and_writes_nothing(self):
        # SOL-BOARD-SCHEMATIC-DRAWING-CONVENTION.C3: It stops with a line naming the tool when the design tool is missing or too old
        repo = two_designs()
        status, said = self.main(self.fake(repo, "9.0.7"), repo)
        self.assertEqual(status, 2)
        self.assertRegex(said, r"^CANNOT RUN \| kicad-cli at .*is KiCad 9\.0\.7, older than the 10\.0")
        self.assertFalse(os.path.exists(repo.out))

    def test_a_tool_that_reports_no_version_stops_with_a_line_naming_the_tool(self):
        # SOL-BOARD-SCHEMATIC-DRAWING-CONVENTION.C3: It stops with a line naming the tool when the design tool is missing or too old
        repo = two_designs()
        status, said = self.main(self.fake(repo, "nothing useful"), repo)
        self.assertEqual(status, 2)
        self.assertRegex(said, r"^CANNOT RUN \| .*did not report a KiCad version")

    def test_the_tool_is_checked_before_an_empty_set_of_designs_is(self):
        # SOL-BOARD-SCHEMATIC-DRAWING-CONVENTION.C3: It stops with a line naming the tool when the design tool is missing or too old
        repo = Repository()
        status, said = self.main(os.path.join(repo.base, "no-such-kicad-cli"), repo)
        self.assertEqual(status, 2)
        self.assertIn("CANNOT RUN", said)


class TheTask(unittest.TestCase):
    def test_the_shipped_task_draws_every_sheet_of_the_repository_it_is_given(self):
        # SOL-BOARD-SCHEMATIC-DRAWING-CONVENTION.C3: One task-runner command renders every sheet of every tracked design from the tracked files
        repo = two_designs()
        result = subprocess.run(["task", "-t", os.path.join(REPO, "Taskfile.yml"), "hw:sheets", f"KICAD_CLI={KICAD_CLI}", "--", "--out", repo.out],
                                cwd=repo.base, capture_output=True, text=True, timeout=600)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        # The task reads this repository's designs, not the throwaway one's, from where it is called.
        drawn = repo.written()
        tracked = subprocess.run(["git", "-C", REPO, "ls-files", "*.kicad_pro"], capture_output=True, text=True).stdout.split()
        self.assertTrue(tracked)
        for project in tracked:
            self.assertTrue(os.path.join(os.path.dirname(project), os.path.basename(project)[:-len(".kicad_pro")] + ".svg") in drawn,
                            f"no root sheet drawn for {project}: {drawn}")
        self.assertEqual([name for name in drawn if name.startswith("boards/")], [])
        self.assertRegex(result.stdout, r"RESULT \| PASS \| every sheet of all \d+ designs")

    def test_the_shipped_task_names_the_tool_when_it_is_missing(self):
        # SOL-BOARD-SCHEMATIC-DRAWING-CONVENTION.C3: It stops with a line naming the tool when the design tool is missing or too old
        out = tempfile.TemporaryDirectory(prefix="schematic-sheets-task-")
        _SCRATCH.append(out)
        target = os.path.join(out.name, "sheets")
        result = subprocess.run(["task", "-t", os.path.join(REPO, "Taskfile.yml"), "hw:sheets", "KICAD_CLI=/nonexistent/kicad-cli", "--", "--out", target],
                                cwd=out.name, capture_output=True, text=True, timeout=600)
        self.assertEqual(result.returncode, 201, result.stdout + result.stderr)
        self.assertRegex(result.stderr, r"CANNOT RUN \| kicad-cli was not found")
        self.assertFalse(os.path.exists(target))


if __name__ == "__main__":
    unittest.main()
