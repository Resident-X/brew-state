#!/usr/bin/env python3
"""The chain runner, driven on a synthetic board and steps that are small scripts written by the test."""

from __future__ import annotations

import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import chain_runner  # noqa: E402
import zone_refill  # noqa: E402
from layout_tool_fixtures import Work, board_text, require_kicad_python, square, zone  # noqa: E402

#: A step that copies its input to its output with a line naming the step appended.
APPEND = """import sys
name, source, target = sys.argv[1:4]
text = open(source, encoding="utf-8", newline="").read()
open(target, "w", encoding="utf-8", newline="").write(text + "(step " + name + ")\\n")
"""

#: A step that appends something different on every run.
RANDOM = """import os, sys
source, target = sys.argv[1:3]
text = open(source, encoding="utf-8", newline="").read()
open(target, "w", encoding="utf-8", newline="").write(text + "(random " + os.urandom(8).hex() + ")\\n")
"""

FAIL = "import sys\nsys.stderr.write('the step broke here')\nsys.exit(3)\n"

NOTHING = "pass\n"

#: A step that needs the project file beside its input and beside its output.
NEEDS_PROJECT = """import os, shutil, sys
source, target = sys.argv[1:3]
for path in (source, target):
    if not os.path.exists(os.path.splitext(path)[0] + ".kicad_pro"):
        sys.stderr.write("no project file beside " + path)
        sys.exit(4)
shutil.copyfile(source, target)
"""


class TheChainRunner(Work):
    def setUp(self):
        super().setUp()
        self.text = "(kicad_pcb (version 20260206))\n"
        self.board = self.write("in/b.kicad_pcb", self.text)
        self.output = self.path("out/b.kicad_pcb")
        os.makedirs(os.path.dirname(self.output))

    def step(self, name, script, *args):
        """A step running the script `script` (its text) with `args` before the input and output paths."""
        self.write(f"steps/{name}.py", script)
        return {"name": name, "command": [sys.executable, "{steps_dir}/" + name + ".py", *args, "{input}", "{output}"]}

    def run_chain(self, steps, *extra, as_json=False, board=None):
        steps_path = self.write("steps/steps.json", json.dumps(steps))
        argv = ["--board", board or self.board, "--steps", steps_path, "--output", self.output, *extra]
        if as_json:
            return self.run_json(chain_runner.main, *argv)
        return self.run_tool(chain_runner.main, *argv)

    def test_identical_runs_write_the_board_and_report_each_steps_checksum(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C4: Run twice over a synthetic board and ordered steps, the runner writes a board whose bytes are identical on both runs and reports success. When a step's output differs between the runs it fails and names the first such step. Tests cover identical runs, a step made nondeterministic, a step that fails and an empty step list, in text and in JSON. This does not cover the content of any board's own steps, which their own folders hold.
        steps = [self.step("one", APPEND, "one"), self.step("two", APPEND, "two"), self.step("three", APPEND, "three")]
        status, lines = self.run_chain(steps)
        self.assertEqual(status, 0, lines)
        final = self.text + "(step one)\n(step two)\n(step three)\n"
        shas = [hashlib.sha256((self.text + "".join("(step %s)\n" % n for n in names)).encode()).hexdigest()
                for names in (["one"], ["one", "two"], ["one", "two", "three"])]
        self.assertEqual(self.read(self.output), final)
        self.assertEqual([line.split(" | ")[:3] for line in lines[:3]],
                         [["STEP", f"{i} {n}", sha] for i, (n, sha) in enumerate(zip(("one", "two", "three"), shas), 1)])
        self.assertTrue(all(line.endswith("identical on both runs") for line in lines[:3]), lines)
        self.assertTrue(lines[-1].startswith(f"RESULT | REPRODUCED | 3 steps run twice with identical output at every step; board sha256 {shas[-1]}"), lines)
        status, found = self.run_chain(steps, as_json=True)
        self.assertEqual((status, found["result"], found["output_sha256"]), (0, "REPRODUCED", shas[-1]))
        self.assertEqual([(s["name"], s["sha256_first"], s["identical"]) for s in found["steps"]],
                         [(n, sha, True) for n, sha in zip(("one", "two", "three"), shas)])
        self.assertEqual(found["input_sha256"], hashlib.sha256(self.text.encode()).hexdigest())

    def test_a_nondeterministic_step_fails_naming_the_first_such_step_and_writes_no_board(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C4: Run twice over a synthetic board and ordered steps, the runner writes a board whose bytes are identical on both runs and reports success. When a step's output differs between the runs it fails and names the first such step. Tests cover identical runs, a step made nondeterministic, a step that fails and an empty step list, in text and in JSON. This does not cover the content of any board's own steps, which their own folders hold.
        steps = [self.step("one", APPEND, "one"), self.step("loose", RANDOM), self.step("later", RANDOM), self.step("last", APPEND, "last")]
        status, lines = self.run_chain(steps)
        self.assertEqual(status, 1, lines)
        differs = [line for line in lines if line.startswith("DIFFERS | ")]
        self.assertEqual(len(differs), 1, lines)
        self.assertTrue(differs[0].startswith("DIFFERS | step 2 loose | "), differs)
        self.assertTrue(lines[-1].startswith("RESULT | FAIL | step 'loose' is the first whose output differs"), lines)
        self.assertFalse(os.path.exists(self.output))
        status, found = self.run_chain(steps, as_json=True)
        self.assertEqual(status, 1)
        self.assertEqual([(s["name"], s["identical"]) for s in found["steps"]], [("one", True), ("loose", False)])
        self.assertEqual(found["findings"][0]["item"], "step 2 loose")

    def test_a_first_step_that_is_nondeterministic_is_the_one_named_when_later_ones_also_are(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C4: Run twice over a synthetic board and ordered steps, the runner writes a board whose bytes are identical on both runs and reports success. When a step's output differs between the runs it fails and names the first such step. Tests cover identical runs, a step made nondeterministic, a step that fails and an empty step list, in text and in JSON. This does not cover the content of any board's own steps, which their own folders hold.
        status, found = self.run_chain([self.step("first", RANDOM), self.step("second", RANDOM)], as_json=True)
        self.assertEqual(status, 1)
        self.assertEqual(found["findings"][0]["item"], "step 1 first")

    def test_a_step_that_fails_names_itself_and_the_run_and_writes_no_board(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C4: Run twice over a synthetic board and ordered steps, the runner writes a board whose bytes are identical on both runs and reports success. When a step's output differs between the runs it fails and names the first such step. Tests cover identical runs, a step made nondeterministic, a step that fails and an empty step list, in text and in JSON. This does not cover the content of any board's own steps, which their own folders hold.
        steps = [self.step("one", APPEND, "one"), self.step("broken", FAIL), self.step("after", APPEND, "after")]
        status, lines = self.run_chain(steps)
        self.assertEqual(status, 1, lines)
        self.assertTrue(lines[-2].startswith("FAILED | step 2 broken (run 1) | exited 3: the step broke here"), lines)
        self.assertTrue(lines[-1].startswith("RESULT | FAIL | step 'broken' failed"), lines)
        self.assertFalse(os.path.exists(self.output))
        status, found = self.run_chain(steps, as_json=True)
        self.assertEqual((status, found["result"], found["findings"][0]["finding"]), (1, "FAIL", "FAILED"))
        self.assertEqual([s["name"] for s in found["steps"]], ["one"])

    def test_a_step_that_writes_no_board_or_cannot_be_run_fails(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C4: Run twice over a synthetic board and ordered steps, the runner writes a board whose bytes are identical on both runs and reports success. When a step's output differs between the runs it fails and names the first such step. Tests cover identical runs, a step made nondeterministic, a step that fails and an empty step list, in text and in JSON. This does not cover the content of any board's own steps, which their own folders hold.
        status, lines = self.run_chain([self.step("quiet", NOTHING)])
        self.assertEqual(status, 1, lines)
        self.assertIn("exited 0 but wrote no board", lines[0])
        missing = {"name": "ghost", "command": [self.path("no-such-program"), "{input}"]}
        status, lines = self.run_chain([missing])
        self.assertEqual(status, 1, lines)
        self.assertTrue(lines[0].startswith("FAILED | step 1 ghost (run 1) | the command could not be run"), lines)

    def test_an_empty_list_of_steps_is_refused_in_either_form(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C4: Run twice over a synthetic board and ordered steps, the runner writes a board whose bytes are identical on both runs and reports success. When a step's output differs between the runs it fails and names the first such step. Tests cover identical runs, a step made nondeterministic, a step that fails and an empty step list, in text and in JSON. This does not cover the content of any board's own steps, which their own folders hold.
        for document in ([], {"steps": []}):
            with self.subTest(document=document):
                status, lines = self.run_chain(document)
                self.assertEqual(status, 1, lines)
                self.assertTrue(lines[0].startswith("REFUSED | "), lines)
                self.assertIn("lists no steps", lines[0])
                self.assertTrue(lines[-1].startswith("RESULT | REFUSED | the chain was not run"), lines)
                self.assertFalse(os.path.exists(self.output))
                status, found = self.run_chain(document, as_json=True)
                self.assertEqual((status, found["result"], found["steps"]), (1, "REFUSED", []))

    def test_malformed_steps_and_a_missing_board_are_refused(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C4: Run twice over a synthetic board and ordered steps, the runner writes a board whose bytes are identical on both runs and reports success. When a step's output differs between the runs it fails and names the first such step. Tests cover identical runs, a step made nondeterministic, a step that fails and an empty step list, in text and in JSON. This does not cover the content of any board's own steps, which their own folders hold.
        good = self.step("one", APPEND, "one")
        cases = {
            "no name": [{"command": ["x"]}],
            "empty name": [{"name": " ", "command": ["x"]}],
            "name twice": [good, dict(good)],
            "no command": [{"name": "a"}],
            "empty command": [{"name": "a", "command": []}],
            "command not strings": [{"name": "a", "command": ["x", 3]}],
            "not a list": {"steps": "one"},
            "a bare string": "one",
        }
        for label, document in cases.items():
            with self.subTest(label):
                status, lines = self.run_chain(document)
                self.assertEqual(status, 1, lines)
                self.assertTrue(lines[0].startswith("REFUSED | "), lines)
                self.assertFalse(os.path.exists(self.output))
        steps_path = self.write("steps/broken.json", "{not json")
        status, lines = self.run_tool(chain_runner.main, "--board", self.board, "--steps", steps_path, "--output", self.output)
        self.assertEqual(status, 1, lines)
        self.assertIn("cannot be read", lines[0])
        status, lines = self.run_chain([good], board=self.path("absent.kicad_pcb"))
        self.assertEqual(status, 1, lines)
        self.assertIn("cannot be read (no such file)", lines[0])

    def test_the_boards_project_file_is_beside_every_steps_input_and_output(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C4: Run twice over a synthetic board and ordered steps, the runner writes a board whose bytes are identical on both runs and reports success. When a step's output differs between the runs it fails and names the first such step. Tests cover identical runs, a step made nondeterministic, a step that fails and an empty step list, in text and in JSON. This does not cover the content of any board's own steps, which their own folders hold.
        self.write("in/b.kicad_pro", "{}")
        status, lines = self.run_chain([self.step("needs", NEEDS_PROJECT), self.step("again", NEEDS_PROJECT)])
        self.assertEqual(status, 0, lines)
        os.remove(self.path("in/b.kicad_pro"))
        status, lines = self.run_chain([self.step("needs", NEEDS_PROJECT)])
        self.assertEqual(status, 1, lines)
        self.assertIn("no project file beside", lines[0])

    def test_a_work_folder_is_kept_when_given_and_refused_when_not_empty(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C4: Run twice over a synthetic board and ordered steps, the runner writes a board whose bytes are identical on both runs and reports success. When a step's output differs between the runs it fails and names the first such step. Tests cover identical runs, a step made nondeterministic, a step that fails and an empty step list, in text and in JSON. This does not cover the content of any board's own steps, which their own folders hold.
        work = self.path("kept")
        status, lines = self.run_chain([self.step("one", APPEND, "one")], "--work", work)
        self.assertEqual(status, 0, lines)
        self.assertTrue(os.path.isfile(os.path.join(work, "run1", "01-one", "out", "b.kicad_pcb")))
        self.assertTrue(os.path.isfile(os.path.join(work, "run2", "01-one", "out", "b.kicad_pcb")))
        status, lines = self.run_chain([self.step("one", APPEND, "one")], "--work", work)
        self.assertEqual(status, 1, lines)
        self.assertIn("is not empty", lines[0])

    def test_a_real_kicad_chain_refill_then_refill_again_is_reproduced_byte_for_byte(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C4: Run twice over a synthetic board and ordered steps, the runner writes a board whose bytes are identical on both runs and reports success. When a step's output differs between the runs it fails and names the first such step. Tests cover identical runs, a step made nondeterministic, a step that fails and an empty step list, in text and in JSON. This does not cover the content of any board's own steps, which their own folders hold.
        python = require_kicad_python()
        board = self.write("in/real.kicad_pcb", board_text([zone("Z1", "/PWR", "B.Cu", square(30, 30, 10), "(clearance 0.75)")],
                                                           (("MAINS", "present"),)))
        refill = os.path.join(os.path.dirname(os.path.abspath(zone_refill.__file__)), "zone_refill.py")
        steps = [{"name": "refill", "command": [sys.executable, refill, "--board", "{input}", "--output", "{output}"]},
                 {"name": "refill-again", "command": [sys.executable, refill, "--board", "{input}", "--output", "{output}",
                                                      "--kicad-python", "{kicad_python}"]}]
        output = self.path("out/real.kicad_pcb")
        steps_path = self.write("steps/real.json", json.dumps({"steps": steps}))
        status, lines = self.run_tool(chain_runner.main, "--board", board, "--steps", steps_path, "--output", output,
                                      "--kicad-python", python)
        self.assertEqual(status, 0, lines)
        self.assertTrue(lines[-1].startswith("RESULT | REPRODUCED | 2 steps"), lines)
        self.assertIn("(filled_polygon", self.read(output))
        self.assertEqual(len(self.property_lines(self.read(output))), 1)


if __name__ == "__main__":
    import unittest
    unittest.main()
