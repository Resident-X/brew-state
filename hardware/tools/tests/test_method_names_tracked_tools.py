#!/usr/bin/env python3
"""The board design method and the hardware notes name the tracked layout tools and no working file outside the repository."""

from __future__ import annotations

import os
import re
import unittest

TESTS = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(TESTS)
HARDWARE = os.path.dirname(TOOLS)
ROOT = os.path.dirname(HARDWARE)

#: What a working file or script of an earlier working session looked like, and a place on one machine.
OUTSIDE = [
    r"/Users/", r"/home/\w", r"[A-Za-z]:\\\\Users", r"real5", r"\bfable\d*/", r"fpaudit", r"PLAN_E", r"real_bodies",
    r"real-body file", r"file of real bodies", r"working script", r"chain script", r"reconnection script that",
]

#: Each tool command the method has to name, with the board-folder table or the inputs it states.
NAMED = {
    "mains-compare": "hardware/tools/locked_copper.py",
    "zone_refill": "hardware/tools/zone_refill.py",
    "zone_fill_diff": "hardware/tools/zone_fill_diff.py",
    "chain_runner": "hardware/tools/chain_runner.py",
    "acceptance_entries": "hardware/tools/acceptance_entries.py",
    "silkscreen": "hardware/tools/silkscreen.py",
    "footprint_audit": "hardware/tools/footprint_audit.py",
}


def read(*parts: str) -> str:
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as handle:
        return handle.read()


def slugs(markdown: str) -> set[str]:
    """The anchors GitHub gives the headings of a document, and the ids it sets by hand."""
    found = set(re.findall(r'<a id="([^"]+)"', markdown))
    for heading in re.findall(r"^#+ (.+)$", markdown, flags=re.M):
        text = re.sub(r"[`*]", "", heading).lower()
        found.add(re.sub(r"\s", "-", re.sub(r"[^\w\s-]", "", text)))
    return found


class TheMethodAndTheNotesNameTheTrackedTools(unittest.TestCase):
    def test_no_reference_to_a_working_file_or_a_place_outside_the_repository_remains(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C13: The board design method names each tracked tool's command in place of the working files it used to name, and the hardware notes list each tool's command, inputs, outputs and the table it reads from the board's folder. A check over the method and the notes finds no remaining reference to a working file outside the repository and no tool command the method names that does not exist in the tooling folder.
        for document in (("docs", "board-design-method.md"), ("hardware", "README.md")):
            text = read(*document)
            for pattern in OUTSIDE:
                with self.subTest(document=document[-1], pattern=pattern):
                    self.assertEqual([m.group(0) for m in re.finditer(pattern, text)], [])

    def test_the_check_would_find_a_reference_it_is_meant_to_find(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C13: The board design method names each tracked tool's command in place of the working files it used to name, and the hardware notes list each tool's command, inputs, outputs and the table it reads from the board's folder. A check over the method and the notes finds no remaining reference to a working file outside the repository and no tool command the method names that does not exist in the tooling folder.
        for sample in ("run /Users/someone/work/chain_all.py", "keep a file of real bodies", "the chain script runs", "see real5/notes", "C:\\\\Users\\\\x"):
            with self.subTest(sample=sample):
                self.assertTrue(any(re.search(pattern, sample) for pattern in OUTSIDE))

    def test_every_tool_command_the_method_names_exists_in_the_tooling_folder(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C13: The board design method names each tracked tool's command in place of the working files it used to name, and the hardware notes list each tool's command, inputs, outputs and the table it reads from the board's folder. A check over the method and the notes finds no remaining reference to a working file outside the repository and no tool command the method names that does not exist in the tooling folder.
        for document in (("docs", "board-design-method.md"), ("hardware", "README.md")):
            named = set(re.findall(r"hardware/tools/([A-Za-z0-9_]+\.py)", read(*document)))
            self.assertTrue(named, document)
            for script in sorted(named):
                with self.subTest(document=document[-1], script=script):
                    self.assertTrue(os.path.isfile(os.path.join(TOOLS, script)), script)

    def test_the_method_names_the_command_of_each_tracked_tool(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C13: The board design method names each tracked tool's command in place of the working files it used to name, and the hardware notes list each tool's command, inputs, outputs and the table it reads from the board's folder. A check over the method and the notes finds no remaining reference to a working file outside the repository and no tool command the method names that does not exist in the tooling folder.
        method = read("docs", "board-design-method.md")
        for name, path in NAMED.items():
            with self.subTest(tool=name):
                self.assertIn(path, method)
                self.assertTrue(os.path.isfile(os.path.join(ROOT, path)))
        self.assertIn("locked_copper.py --kicad-cli \"$KICAD_CLI\" mains-compare", method)

    def test_the_notes_list_command_inputs_outputs_and_board_tables_of_each_tool_and_the_manual_fetch(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C13: The board design method names each tracked tool's command in place of the working files it used to name, and the hardware notes list each tool's command, inputs, outputs and the table it reads from the board's folder. A check over the method and the notes finds no remaining reference to a working file outside the repository and no tool command the method names that does not exist in the tooling folder.
        notes = read("hardware", "README.md")
        for path in NAMED.values():
            self.assertIn(path, notes, path)
        for table in ("part-bodies.yaml", "acceptance-reasons.yaml", "silkscreen.yaml", "chain.json"):
            with self.subTest(table=table):
                self.assertIn(table, notes)
                self.assertIn(table, read("docs", "board-design-method.md"))
        self.assertRegex(notes, r"(?i)manual step")
        self.assertRegex(notes, r"(?i)assembler's library")
        for heading in ("## The layout tools", "## The main board's layout chain", "## The acceptance-entry generator", "## The silkscreen command"):
            self.assertIn(heading, notes)

    def test_every_link_the_method_makes_into_the_notes_lands_on_a_heading(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C13: The board design method names each tracked tool's command in place of the working files it used to name, and the hardware notes list each tool's command, inputs, outputs and the table it reads from the board's folder. A check over the method and the notes finds no remaining reference to a working file outside the repository and no tool command the method names that does not exist in the tooling folder.
        anchors = slugs(read("hardware", "README.md"))
        links = re.findall(r"\(\.\./hardware/README\.md#([a-z0-9-]+)\)", read("docs", "board-design-method.md"))
        self.assertTrue(links)
        self.assertEqual(sorted({link for link in links if link not in anchors}), [])


if __name__ == "__main__":
    unittest.main()
