#!/usr/bin/env python3
"""The hardware notes describe each small layout tool: its command, every option, its inputs and outputs and the table it reads."""

from __future__ import annotations

import os
import re
import subprocess
import sys
import unittest

TESTS = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(TESTS)
HARDWARE = os.path.dirname(TOOLS)
sys.path.insert(0, TESTS)

#: Each tool in the group: its script, the arguments that print its help, and the text its README entry opens with.
TOOLS_DESCRIBED = {
    "mains-copper compare": ("locked_copper.py", ["mains-compare", "--help"], "**Mains-copper compare**"),
    "safe zone refill": ("zone_refill.py", ["--help"], "**Safe zone refill**"),
    "fill difference": ("zone_fill_diff.py", ["--help"], "**Fill difference**"),
    "chain runner": ("chain_runner.py", ["--help"], "**Chain runner**"),
}


def section() -> str:
    """The README's layout tools section."""
    with open(os.path.join(HARDWARE, "README.md"), encoding="utf-8") as handle:
        text = handle.read()
    start = text.index("## The layout tools")
    return text[start:text.index("\n## ", start + 1)]


def entry(notes: str, opening: str) -> str:
    """The one bullet of the section that opens with `opening`."""
    bullets = [part for part in re.split(r"\n(?=- )", notes) if part.startswith("- " + opening)]
    assert len(bullets) == 1, (opening, len(bullets))
    return bullets[0]


class TheNotesDescribeEachTool(unittest.TestCase):
    def test_each_tool_has_an_entry_with_its_command_inputs_and_outputs(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C11: Each tool in this set has a test that runs it on a synthetic design built by the test, and the hardware notes describe each tool's command, its inputs, the board folder table it reads and the manual step of fetching an assembler's library footprints. Checked by reading the hardware notes against the list of tools clause by clause. This does not apply to the fetch of an assembler's library footprints, which stays a documented manual step.
        notes = section()
        for name, (script, _, opening) in TOOLS_DESCRIBED.items():
            with self.subTest(tool=name):
                bullet = entry(notes, opening)
                self.assertIn(f"hardware/tools/{script}", bullet, "the command that runs it")
                self.assertRegex(bullet, r"Input", "its inputs")
                self.assertRegex(bullet, r"Output|writes|prints|reports", "its outputs")
                self.assertTrue(os.path.isfile(os.path.join(TOOLS, script)), "the tool the notes name exists")

    def test_each_entry_names_every_option_the_tool_takes(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C11: Each tool in this set has a test that runs it on a synthetic design built by the test, and the hardware notes describe each tool's command, its inputs, the board folder table it reads and the manual step of fetching an assembler's library footprints. Checked by reading the hardware notes against the list of tools clause by clause. This does not apply to the fetch of an assembler's library footprints, which stays a documented manual step.
        notes = section()
        for name, (script, help_args, opening) in TOOLS_DESCRIBED.items():
            with self.subTest(tool=name):
                done = subprocess.run([sys.executable, os.path.join(TOOLS, script), *help_args], capture_output=True, text=True, timeout=300)
                self.assertEqual(done.returncode, 0, done.stderr)
                options = set(re.findall(r"--[a-z][a-z-]+", done.stdout)) - {"--help", "--kicad-cli"}
                self.assertTrue(options, "the tool lists its options")
                bullet = entry(notes, opening)
                self.assertEqual(sorted(option for option in options if option not in bullet), [],
                                 "an option the tool takes that its notes entry does not name")

    def test_the_notes_say_where_the_kicad_interpreter_comes_from_and_which_board_table_each_tool_reads(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C11: Each tool in this set has a test that runs it on a synthetic design built by the test, and the hardware notes describe each tool's command, its inputs, the board folder table it reads and the manual step of fetching an assembler's library footprints. Checked by reading the hardware notes against the list of tools clause by clause. This does not apply to the fetch of an assembler's library footprints, which stays a documented manual step.
        notes = section()
        self.assertIn("KICAD_PYTHON", notes)
        self.assertIn("CANNOT RUN", notes)
        self.assertIn("reads a table from a board's folder", notes)
        self.assertIn("steps file", notes)
        with open(os.path.join(HARDWARE, "README.md"), encoding="utf-8") as handle:
            whole = handle.read()
        needs = whole[whole.index("## What you need"):whole.index("## The commands")]
        self.assertIn("`KICAD_PYTHON`", needs)

    def test_each_tool_has_a_test_that_runs_it_on_a_design_the_test_builds(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C11: Each tool in this set has a test that runs it on a synthetic design built by the test, and the hardware notes describe each tool's command, its inputs, the board folder table it reads and the manual step of fetching an assembler's library footprints. Checked by reading the hardware notes against the list of tools clause by clause. This does not apply to the fetch of an assembler's library footprints, which stays a documented manual step.
        modules = {"mains-copper compare": "test_mains_compare_command.py", "safe zone refill": "test_zone_refill.py",
                   "fill difference": "test_zone_fill_diff.py", "chain runner": "test_chain_runner.py"}
        for name, module in modules.items():
            with self.subTest(tool=name):
                path = os.path.join(TESTS, module)
                self.assertTrue(os.path.isfile(path))
                with open(path, encoding="utf-8") as handle:
                    text = handle.read()
                self.assertIn("kicad_pcb", text)
                self.assertRegex(text, r"tempfile|self\.write|self\.make", "the board is written by the test")


if __name__ == "__main__":
    unittest.main()
