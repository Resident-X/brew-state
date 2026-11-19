#!/usr/bin/env python3
"""The hardware notes describe the footprint audit: its commands, every option, its inputs and outputs and the board table it reads."""

from __future__ import annotations

import os
import re
import subprocess
import sys
import unittest

TESTS = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(TESTS)
HARDWARE = os.path.dirname(TOOLS)

COMMANDS = ("gaps", "pads", "rotation")


def entry() -> str:
    """The one bullet of the layout tools section that opens with the footprint audit."""
    with open(os.path.join(HARDWARE, "README.md"), encoding="utf-8") as handle:
        text = handle.read()
    start = text.index("## The layout tools")
    notes = text[start:text.index("\n## ", start + 1)]
    bullets = [part for part in re.split(r"\n(?=- )", notes) if part.startswith("- **Footprint audit**")]
    assert len(bullets) == 1, len(bullets)
    return bullets[0]


class TheNotesDescribeTheFootprintAudit(unittest.TestCase):
    def test_the_entry_gives_each_command_its_inputs_outputs_and_the_table_it_reads(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C11: Each tool in this set has a test that runs it on a synthetic design built by the test, and the hardware notes describe each tool's command, its inputs, the board folder table it reads and the manual step of fetching an assembler's library footprints. Checked by reading the hardware notes against the list of tools clause by clause. This does not apply to the fetch of an assembler's library footprints, which stays a documented manual step.
        bullet = entry()
        for command in COMMANDS:
            self.assertIn(f"hardware/tools/footprint_audit.py {command}", bullet, "the command that runs it")
        self.assertTrue(os.path.isfile(os.path.join(TOOLS, "footprint_audit.py")))
        self.assertIn("Inputs:", bullet)
        self.assertIn("Output:", bullet)
        self.assertIn("reads from a board's folder", bullet)
        self.assertIn("part-bodies.yaml", bullet)
        self.assertTrue(os.path.isfile(os.path.join(HARDWARE, "sunbeam-em7000", "main-board", "part-bodies.yaml")),
                        "the table the notes name for the main board exists")
        self.assertIn("manual step", bullet, "reading a maker's drawing is said to be manual")

    def test_the_entry_names_every_option_of_every_command(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C11: Each tool in this set has a test that runs it on a synthetic design built by the test, and the hardware notes describe each tool's command, its inputs, the board folder table it reads and the manual step of fetching an assembler's library footprints. Checked by reading the hardware notes against the list of tools clause by clause. This does not apply to the fetch of an assembler's library footprints, which stays a documented manual step.
        bullet = entry()
        for command in COMMANDS:
            with self.subTest(command=command):
                done = subprocess.run([sys.executable, os.path.join(TOOLS, "footprint_audit.py"), command, "--help"],
                                      capture_output=True, text=True, timeout=120)
                self.assertEqual(done.returncode, 0, done.stderr)
                options = set(re.findall(r"--[a-z][a-z-]+", done.stdout)) - {"--help"}
                self.assertTrue(options)
                self.assertEqual(sorted(option for option in options if option not in bullet), [])

    def test_the_notes_command_exists_in_the_tooling_folder_and_names_no_working_file(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C13: The board design method names each tracked tool's command in place of the working files it used to name, and the hardware notes list each tool's command, inputs, outputs and the table it reads from the board's folder. A check over the method and the notes finds no remaining reference to a working file outside the repository and no tool command the method names that does not exist in the tooling folder.
        bullet = entry()
        for script in re.findall(r"hardware/tools/([a-z_]+\.py)", bullet):
            self.assertTrue(os.path.isfile(os.path.join(TOOLS, script)), script)
        self.assertEqual(re.findall(r"(/Users/|/home/[a-z]|real5|fpaudit|\.pkl)", bullet), [])


if __name__ == "__main__":
    unittest.main()
