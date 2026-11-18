#!/usr/bin/env python3
"""The KiCad interpreter of the layout tools: named by KICAD_PYTHON or an argument, and refused by name when it is neither."""

from __future__ import annotations

import contextlib
import io
import json
import os
import re
import stat
import subprocess
import sys
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import chain_runner  # noqa: E402
import kicad_scripting  # noqa: E402
import zone_fill_diff  # noqa: E402
import zone_refill  # noqa: E402
from layout_tool_fixtures import TOOLS, Work, board_text, require_kicad_python, square, zone  # noqa: E402

#: Every tracked layout tool this set holds that needs KiCad's scripting interface or sits beside one that does, and the shared helper.
TOOL_FILES = ("kicad_scripting.py", "zone_refill.py", "zone_fill_diff.py", "chain_runner.py", "locked_copper.py")


class TheInterpreterIsNamedByTheVariableOrAnArgument(Work):
    def setUp(self):
        super().setUp()
        self.board = self.write("b.kicad_pcb", board_text([zone("Z1", "/PWR", "B.Cu", square(30, 30, 10))]))
        self.steps = self.write("steps.json", json.dumps([{"name": "load", "command": ["{kicad_python}", "-I", "-c", "import shutil, sys, pcbnew; shutil.copyfile(sys.argv[1], sys.argv[2])", "{input}", "{output}"]}]))
        self.env = dict(os.environ)

    def tools(self):
        """Each tool as a function of the interpreter argument (a list, possibly empty) to its (status, stdout, stderr)."""
        def refill(extra, fmt):
            return zone_refill.main(["--board", self.board, "--output", self.path("o.kicad_pcb"), *extra, *fmt], out=sys.stdout)

        def diff(extra, fmt):
            return zone_fill_diff.main(["--first", self.board, "--second", self.board, *extra, *fmt], out=sys.stdout)

        def chain(extra, fmt):
            return chain_runner.main(["--board", self.board, "--steps", self.steps, "--output", self.path("c.kicad_pcb"), *extra, *fmt], out=sys.stdout)

        return {"zone_refill": refill, "zone_fill_diff": diff, "chain_runner": chain}

    def capture(self, tool, variable, extra=(), fmt=()):
        env = {k: v for k, v in os.environ.items() if k != kicad_scripting.VARIABLE}
        if variable is not None:
            env[kicad_scripting.VARIABLE] = variable
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.dict(os.environ, env, clear=True), contextlib.redirect_stderr(err), contextlib.redirect_stdout(out):
            status = self.tools()[tool](list(extra), list(fmt))
        return status, out.getvalue(), err.getvalue()

    def assertCannotRun(self, tool, variable, reason, extra=()):
        status, out, err = self.capture(tool, variable, extra)
        self.assertEqual(status, 2, (out, err))
        self.assertTrue(err.startswith("CANNOT RUN | "), err)
        self.assertIn("KICAD_PYTHON", err)
        self.assertIn(reason, err)
        self.assertEqual(out, "", "a tool that cannot run reports nothing as a result")
        status, out, err = self.capture(tool, variable, extra, ["--format", "json"])
        self.assertEqual(status, 2)
        report = json.loads(out)
        self.assertEqual(report["result"], "CANNOT RUN")
        self.assertIn("KICAD_PYTHON", report["detail"])
        self.assertIn(reason, report["detail"])

    def test_the_variable_unset_stops_each_tool_naming_it(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C12: Each tracked layout tool that needs KiCad's scripting interface runs it in the interpreter named by a documented environment variable, and the tool and its tests fail naming that variable when it is unset or names nothing runnable. The silkscreen command names the missing package when numpy, shapely or Pillow is not installed. No tool holds a path fixed to one machine: every tool, interpreter and board path is an argument or an environment variable. Tests cover the variable unset, the variable naming a missing file, a missing package and a path given as an argument, in text and in JSON.
        for tool in self.tools():
            with self.subTest(tool=tool):
                self.assertCannotRun(tool, None, "KICAD_PYTHON is not set")

    def test_the_variable_naming_a_missing_file_or_a_file_that_is_not_runnable_stops_each_tool_naming_it(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C12: Each tracked layout tool that needs KiCad's scripting interface runs it in the interpreter named by a documented environment variable, and the tool and its tests fail naming that variable when it is unset or names nothing runnable. The silkscreen command names the missing package when numpy, shapely or Pillow is not installed. No tool holds a path fixed to one machine: every tool, interpreter and board path is an argument or an environment variable. Tests cover the variable unset, the variable naming a missing file, a missing package and a path given as an argument, in text and in JSON.
        plain = self.write("plain.txt", "not a program")
        for tool in self.tools():
            with self.subTest(tool=tool, case="missing"):
                self.assertCannotRun(tool, self.path("no-such-python"), "which is not a runnable file")
            with self.subTest(tool=tool, case="not executable"):
                os.chmod(plain, stat.S_IRUSR | stat.S_IWUSR)
                self.assertCannotRun(tool, plain, "which is not a runnable file")
            with self.subTest(tool=tool, case="empty"):
                self.assertCannotRun(tool, "", "KICAD_PYTHON is not set")

    def test_an_interpreter_that_cannot_import_pcbnew_stops_each_tool_naming_the_variable(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C12: Each tracked layout tool that needs KiCad's scripting interface runs it in the interpreter named by a documented environment variable, and the tool and its tests fail naming that variable when it is unset or names nothing runnable. The silkscreen command names the missing package when numpy, shapely or Pillow is not installed. No tool holds a path fixed to one machine: every tool, interpreter and board path is an argument or an environment variable. Tests cover the variable unset, the variable naming a missing file, a missing package and a path given as an argument, in text and in JSON.
        for tool in self.tools():
            with self.subTest(tool=tool):
                self.assertCannotRun(tool, sys.executable, "which cannot import pcbnew")

    def test_a_path_given_as_an_argument_is_used_when_the_variable_is_unset_and_wins_over_a_bad_variable(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C12: Each tracked layout tool that needs KiCad's scripting interface runs it in the interpreter named by a documented environment variable, and the tool and its tests fail naming that variable when it is unset or names nothing runnable. The silkscreen command names the missing package when numpy, shapely or Pillow is not installed. No tool holds a path fixed to one machine: every tool, interpreter and board path is an argument or an environment variable. Tests cover the variable unset, the variable naming a missing file, a missing package and a path given as an argument, in text and in JSON.
        python = require_kicad_python()
        for variable in (None, self.path("no-such-python")):
            with self.subTest(variable=variable):
                status, out, err = self.capture("zone_refill", variable, ["--kicad-python", python])
                self.assertEqual(status, 0, (out, err))
                self.assertIn("RESULT | REFILLED", out)
                status, out, err = self.capture("zone_fill_diff", variable, ["--kicad-python", python], ["--format", "json"])
                self.assertEqual((status, json.loads(out)["result"]), (0, "SAME"), (out, err))
                status, out, err = self.capture("chain_runner", variable, ["--kicad-python", python])
                self.assertEqual(status, 0, (out, err))
        status, out, err = self.capture("zone_refill", python, ["--kicad-python", self.path("no-such-python")])
        self.assertEqual(status, 2, "the argument wins even over a good variable")
        self.assertIn("the --kicad-python argument", err)

    def test_the_command_line_of_each_tool_exits_two_naming_the_variable_when_it_is_unset(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C12: Each tracked layout tool that needs KiCad's scripting interface runs it in the interpreter named by a documented environment variable, and the tool and its tests fail naming that variable when it is unset or names nothing runnable. The silkscreen command names the missing package when numpy, shapely or Pillow is not installed. No tool holds a path fixed to one machine: every tool, interpreter and board path is an argument or an environment variable. Tests cover the variable unset, the variable naming a missing file, a missing package and a path given as an argument, in text and in JSON.
        env = {k: v for k, v in os.environ.items() if k != kicad_scripting.VARIABLE}
        commands = {
            "zone_refill.py": ["--board", self.board, "--output", self.path("o.kicad_pcb")],
            "zone_fill_diff.py": ["--first", self.board, "--second", self.board],
            "chain_runner.py": ["--board", self.board, "--steps", self.steps, "--output", self.path("c.kicad_pcb")],
        }
        for script, argv in commands.items():
            with self.subTest(script=script):
                done = subprocess.run([sys.executable, os.path.join(TOOLS, script), *argv], capture_output=True, text=True, env=env, timeout=300)
                self.assertEqual(done.returncode, 2, done.stderr)
                self.assertTrue(done.stderr.startswith("CANNOT RUN | KICAD_PYTHON is not set"), done.stderr)
                done = subprocess.run([sys.executable, os.path.join(TOOLS, script), "--help"], capture_output=True, text=True, env=env, timeout=300)
                self.assertEqual(done.returncode, 0, done.stderr)
                self.assertIn("--format", done.stdout)

    def test_a_step_that_does_not_name_the_interpreter_needs_no_variable(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C12: Each tracked layout tool that needs KiCad's scripting interface runs it in the interpreter named by a documented environment variable, and the tool and its tests fail naming that variable when it is unset or names nothing runnable. The silkscreen command names the missing package when numpy, shapely or Pillow is not installed. No tool holds a path fixed to one machine: every tool, interpreter and board path is an argument or an environment variable. Tests cover the variable unset, the variable naming a missing file, a missing package and a path given as an argument, in text and in JSON.
        steps = self.write("plain-steps.json", json.dumps([{"name": "copy", "command": [sys.executable, "-c",
                           "import shutil, sys; shutil.copyfile(sys.argv[1], sys.argv[2])", "{input}", "{output}"]}]))
        status, out, err = self.capture("chain_runner", None)
        self.assertEqual(status, 2)
        env = {k: v for k, v in os.environ.items() if k != kicad_scripting.VARIABLE}
        output = io.StringIO()
        with mock.patch.dict(os.environ, env, clear=True):
            status = chain_runner.main(["--board", self.board, "--steps", steps, "--output", self.path("plain.kicad_pcb")], out=output)
        self.assertEqual(status, 0, output.getvalue())

    def test_no_layout_tool_holds_a_path_fixed_to_one_machine(self):
        # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C12: Each tracked layout tool that needs KiCad's scripting interface runs it in the interpreter named by a documented environment variable, and the tool and its tests fail naming that variable when it is unset or names nothing runnable. The silkscreen command names the missing package when numpy, shapely or Pillow is not installed. No tool holds a path fixed to one machine: every tool, interpreter and board path is an argument or an environment variable. Tests cover the variable unset, the variable naming a missing file, a missing package and a path given as an argument, in text and in JSON.
        fixed = re.compile(r"(/Users/|/home/[a-z]|/Applications/|/opt/homebrew|/usr/local/|/Library/|[A-Za-z]:\\|\bProgram Files\b)")
        for name in TOOL_FILES:
            with self.subTest(tool=name):
                with open(os.path.join(TOOLS, name), encoding="utf-8") as handle:
                    found = [line.strip() for line in handle if fixed.search(line)]
                self.assertEqual(found, [], f"{name} names a place on one machine")


if __name__ == "__main__":
    import unittest
    unittest.main()
