"""The hardware notes and the board design method, read against the silkscreen command, clause by clause.

Plain Python: this module needs neither KiCad nor the placement packages.
"""

from __future__ import annotations

import contextlib
import io
import os
import re
import sys
import unittest

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)

import silkscreen  # noqa: E402
import silkscreen_table  # noqa: E402

REPO = os.path.dirname(os.path.dirname(TOOLS))
README = os.path.join(REPO, "hardware", "README.md")
METHOD = os.path.join(REPO, "docs", "board-design-method.md")
TESTS = os.path.join(TOOLS, "tests")


def read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def section(text, heading):
    start = text.index(f"## {heading}\n")
    end = text.find("\n## ", start + 1)
    return text[start:end if end != -1 else len(text)]


def options_of(command):
    """Every `--option` the command's `--help` lists."""
    out = io.StringIO()
    with contextlib.redirect_stdout(out), self_exit():
        silkscreen.main([command, "--help"])
    return sorted(set(re.findall(r"--[a-z][a-z-]*", out.getvalue())) - {"--help"})


@contextlib.contextmanager
def self_exit():
    try:
        yield
    except SystemExit:
        pass


class Notes(unittest.TestCase):
    # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C11: Each tool in this set has a test that runs it on a synthetic design built by the test, and the hardware notes describe each tool's command, its inputs, the board folder table it reads and the manual step of fetching an assembler's library footprints. Checked by reading the hardware notes against the list of tools clause by clause. This does not apply to the fetch of an assembler's library footprints, which stays a documented manual step.
    def test_the_notes_give_the_commands_inputs_outputs_and_the_table_it_reads(self):
        text = section(read(README), "The silkscreen command")
        for command in ("build --board", "prove --input", "check --board"):
            self.assertIn(f"hardware/tools/silkscreen.py {command}", text)
        for clause in ("- Needs:", "- Inputs:", "- What it draws", "- The proof:", "- Outputs:", "- The table it reads", "- Time:", "- Not judged here:"):
            self.assertIn(clause, text)
        self.assertIn("hardware/sunbeam-em7000/main-board/silkscreen.yaml", text)
        self.assertTrue(os.path.isfile(os.path.join(REPO, "hardware", "sunbeam-em7000", "main-board", "silkscreen.yaml")))
        for word in ("DIFFERS", "UNPLACED", "MOVED", "CHECK", "CANNOT RUN", "KICAD_PYTHON", "numpy", "shapely", "Pillow"):
            self.assertIn(word, text)
        self.assertIn("Fetching an assembler's library footprints is an outside service and stays a manual step", read(README))

    # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C11: Each tool in this set has a test that runs it on a synthetic design built by the test, and the hardware notes describe each tool's command, its inputs, the board folder table it reads and the manual step of fetching an assembler's library footprints. Checked by reading the hardware notes against the list of tools clause by clause. This does not apply to the fetch of an assembler's library footprints, which stays a documented manual step.
    def test_the_notes_name_every_option_of_every_command_and_every_key_of_the_table(self):
        text = section(read(README), "The silkscreen command")
        for command in ("build", "prove", "check"):
            for option in options_of(command):
                self.assertIn(option, text, f"{command} takes {option}, which the notes do not name")
        keys = set()
        for key, value in silkscreen_table.DEFAULTS.items():
            keys.add(key)
            if isinstance(value, dict) and key not in ("thickness", "parts"):
                keys |= set(value)
        keys |= silkscreen_table.PART_KEYS | silkscreen_table.LEGEND_KEYS | silkscreen_table.FIXED_KEYS | {"dot", "mark"}
        for key in sorted(keys):
            self.assertIn(f"`{key}`", text.replace("`" + key + ":", "`" + key + "`"), f"the notes do not name the table key {key}")

    # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C11: Each tool in this set has a test that runs it on a synthetic design built by the test, and the hardware notes describe each tool's command, its inputs, the board folder table it reads and the manual step of fetching an assembler's library footprints. Checked by reading the hardware notes against the list of tools clause by clause. This does not apply to the fetch of an assembler's library footprints, which stays a documented manual step.
    def test_the_prerequisites_are_declared_beside_kicad_and_the_tool_has_tests_that_run_it(self):
        needs = section(read(README), "What you need")
        row = next(line for line in needs.splitlines() if "numpy, shapely, Pillow and PyYAML" in line)
        for word in ("silkscreen", "pip install", "CANNOT RUN"):
            self.assertIn(word, row)
        for name in ("test_silkscreen_rebuild.py", "test_silkscreen_refusal.py", "test_silkscreen_environment.py"):
            self.assertIn("silkscreen.main", read(os.path.join(TESTS, name)), f"{name} does not run the command")

    # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C13: The board design method names each tracked tool's command in place of the working files it used to name, and the hardware notes list each tool's command, inputs, outputs and the table it reads from the board's folder. A check over the method and the notes finds no remaining reference to a working file outside the repository and no tool command the method names that does not exist in the tooling folder.
    def test_the_method_names_the_silkscreen_command_and_every_tool_it_names_exists(self):
        method = read(METHOD)
        step = method[method.index("### 7. Rebuild the silkscreen by script, last"):]
        step = step[:step.index("\n### 8.")] if "\n### 8." in step else step[:3000]
        self.assertIn("python3 hardware/tools/silkscreen.py build --board", step)
        self.assertIn("silkscreen.py check --board", step)
        self.assertIn("../hardware/README.md#the-silkscreen-command", step)
        for tool in sorted(set(re.findall(r"hardware/tools/([A-Za-z0-9_]+\.py)", method))):
            self.assertTrue(os.path.isfile(os.path.join(TOOLS, tool)), f"the method names hardware/tools/{tool}, which does not exist")

    # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C13: The board design method names each tracked tool's command in place of the working files it used to name, and the hardware notes list each tool's command, inputs, outputs and the table it reads from the board's folder. A check over the method and the notes finds no remaining reference to a working file outside the repository and no tool command the method names that does not exist in the tooling folder.
    def test_the_silkscreen_text_of_the_method_and_the_notes_names_no_working_file_outside_the_repository(self):
        outside = re.compile(r"(/Users/|real5|apply_silk|place_silk|silkcheck|fable\d+|SILK_PYLIB)")
        method = read(METHOD)
        step = method[method.index("### 7. Rebuild the silkscreen by script, last"):]
        step = step[:step.index("\n### 8.")] if "\n### 8." in step else step[:3000]
        for name, text in (("the method's silkscreen step", step), ("the hardware notes' silkscreen section", section(read(README), "The silkscreen command"))):
            self.assertIsNone(outside.search(text), f"{name} names a working file outside the repository: {outside.search(text)}")


if __name__ == "__main__":
    unittest.main()
