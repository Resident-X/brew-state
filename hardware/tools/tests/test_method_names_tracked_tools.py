#!/usr/bin/env python3
"""The board design method and the hardware notes name the tracked layout tools and no working file outside the repository."""

from __future__ import annotations

import ast
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


def subcommands(script: str) -> set[str]:
    """The names a tool's argparse parser registers with add_parser, read from its source: a literal, or each literal of the
    tuple a loop walks."""
    with open(os.path.join(TOOLS, script), encoding="utf-8") as handle:
        tree = ast.parse(handle.read())
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.For) and isinstance(node.target, ast.Name):
            for call in ast.walk(node):
                if (isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute) and call.func.attr == "add_parser"
                        and call.args and isinstance(call.args[0], ast.Name) and call.args[0].id == node.target.id
                        and isinstance(node.iter, (ast.Tuple, ast.List))):
                    found |= {e.value for e in node.iter.elts if isinstance(e, ast.Constant) and isinstance(e.value, str)}
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "add_parser"
                and node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str)):
            found.add(node.args[0].value)
    return found


#: The words after a tool's script name, the options with their values skipped, that a document gives as its subcommand.
INVOCATION = re.compile(r"hardware/tools/([A-Za-z0-9_]+\.py)((?:\s+(?:--[\w-]+(?:[= ]\S+)?|\"\$\w+\"))*)\s+([a-z][a-z-]*)\b")


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

    def test_every_subcommand_the_method_and_notes_name_exists_in_the_tool_they_name_it_for(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C13: The board design method names each tracked tool's command in place of the working files it used to name, and the hardware notes list each tool's command, inputs, outputs and the table it reads from the board's folder. A check over the method and the notes finds no remaining reference to a working file outside the repository and no tool command the method names that does not exist in the tooling folder.
        seen = set()
        for document in (("docs", "board-design-method.md"), ("hardware", "README.md")):
            for script, _, word in INVOCATION.findall(read(*document)):
                known = subcommands(script)
                if not known:
                    continue
                with self.subTest(document=document[-1], script=script, subcommand=word):
                    self.assertIn(word, known, f"{script} has the subcommands {sorted(known)}")
                seen.add((script, word))
        # the subcommands of the tracked layout tools the documents are expected to show in use
        for expected in (("locked_copper.py", "mains-compare"), ("silkscreen.py", "build"), ("footprint_audit.py", "gaps"),
                         ("footprint_audit.py", "pads"), ("footprint_audit.py", "rotation")):
            self.assertIn(expected, seen)

    def test_the_subcommand_check_would_find_a_name_the_tool_lacks(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C13: The board design method names each tracked tool's command in place of the working files it used to name, and the hardware notes list each tool's command, inputs, outputs and the table it reads from the board's folder. A check over the method and the notes finds no remaining reference to a working file outside the repository and no tool command the method names that does not exist in the tooling folder.
        self.assertEqual(subcommands("footprint_audit.py"), {"gaps", "pads", "rotation"})
        self.assertIn("mains-compare", subcommands("locked_copper.py"))
        self.assertEqual(subcommands("silkscreen.py"), {"build", "prove", "check"})
        self.assertNotIn("compare-mains", subcommands("locked_copper.py"))
        self.assertEqual(subcommands("acceptance_entries.py"), set())
        found = INVOCATION.findall('python3 hardware/tools/locked_copper.py --kicad-cli "$KICAD_CLI" mains-compare --board x')
        self.assertEqual([(script, word) for script, _, word in found], [("locked_copper.py", "mains-compare")])

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
