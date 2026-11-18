"""What the silkscreen command needs of its machine: KiCad's interpreter, numpy, shapely and Pillow, and no path fixed to one machine.

A variable or a package is taken away from a real run of the command (in a subprocess where the package is made
unimportable), and the command must stop naming it. The runs that succeed use the interpreter, board and table as
arguments.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import silkscreen_fixtures as fx  # noqa: E402

PYTHON = None
TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COMMAND = os.path.join(TOOLS, "silkscreen.py")


def setUpModule():
    global PYTHON
    PYTHON = fx.require_tools()


import silkscreen  # noqa: E402

SOURCES = ("silkscreen.py", "silkscreen_check.py", "silkscreen_engine.py", "silkscreen_kicad.py", "silkscreen_patch.py",
           "silkscreen_place.py", "silkscreen_table.py")
BLOCKER = ("import sys, runpy\nsys.modules[%r] = None\nsys.argv = ['silkscreen.py'] + sys.argv[1:]\n"
           "runpy.run_path(%r, run_name='__main__')\n")


class Environment(fx.Work):
    def board(self):
        return self.write("in.kicad_pcb", fx.board_text([fx.resistor("R1", 8, 8)]))

    def env(self, **changes):
        env = {k: v for k, v in os.environ.items() if k != "KICAD_PYTHON"}
        env.update(changes)
        return env

    def run_blocked(self, module, *argv, env=None):
        """The command in a process where `module` cannot be imported: (exit status, standard output, standard error)."""
        done = subprocess.run([sys.executable, "-c", BLOCKER % (module, COMMAND), *argv], capture_output=True, text=True,
                              env=env or self.env(KICAD_PYTHON=PYTHON), timeout=300)
        return done.returncode, done.stdout, done.stderr

    # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C12: Each tracked layout tool that needs KiCad's scripting interface runs it in the interpreter named by a documented environment variable, and the tool and its tests fail naming that variable when it is unset or names nothing runnable. The silkscreen command names the missing package when numpy, shapely or Pillow is not installed. No tool holds a path fixed to one machine: every tool, interpreter and board path is an argument or an environment variable. Tests cover the variable unset, the variable naming a missing file, a missing package and a path given as an argument, in text and in JSON.
    def test_the_variable_unset_stops_build_and_check_naming_it_in_text_and_in_json(self):
        board = self.board()
        for command in (["build", "--board", board, "--out", self.path("out.kicad_pcb")], ["check", "--board", board]):
            with mock.patch.dict(os.environ, self.env(), clear=True):
                status, lines = self.run_tool(silkscreen.main, *command)
                status_json, report = self.run_json(silkscreen.main, *command)
            self.assertEqual((status, status_json), (2, 2), command)
            self.assertEqual(lines, [], "the reason goes to standard error, not into a report")
            self.assertEqual(report["result"], "CANNOT RUN")
            self.assertIn("KICAD_PYTHON is not set", report["detail"])
        done = subprocess.run([sys.executable, COMMAND, "build", "--board", board, "--out", self.path("o.kicad_pcb")], capture_output=True,
                              text=True, env=self.env(), timeout=300)
        self.assertEqual(done.returncode, 2)
        self.assertTrue(done.stderr.startswith("CANNOT RUN | KICAD_PYTHON is not set"), done.stderr)

    # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C12: Each tracked layout tool that needs KiCad's scripting interface runs it in the interpreter named by a documented environment variable, and the tool and its tests fail naming that variable when it is unset or names nothing runnable. The silkscreen command names the missing package when numpy, shapely or Pillow is not installed. No tool holds a path fixed to one machine: every tool, interpreter and board path is an argument or an environment variable. Tests cover the variable unset, the variable naming a missing file, a missing package and a path given as an argument, in text and in JSON.
    def test_the_variable_naming_a_missing_file_or_something_that_cannot_import_pcbnew_stops_it_naming_the_variable(self):
        board = self.board()
        out = self.path("out.kicad_pcb")
        with mock.patch.dict(os.environ, self.env(KICAD_PYTHON=self.path("no-such-python")), clear=True):
            status, report = self.run_json(silkscreen.main, "build", "--board", board, "--out", out)
            self.assertEqual(status, 2)
            self.assertIn("KICAD_PYTHON", report["detail"])
            self.assertIn("not a runnable file", report["detail"])
        with mock.patch.dict(os.environ, self.env(KICAD_PYTHON=sys.executable), clear=True):
            status, report = self.run_json(silkscreen.main, "check", "--board", board)
            self.assertEqual(status, 2)
            self.assertIn("KICAD_PYTHON", report["detail"])
            self.assertIn("cannot import pcbnew", report["detail"])
        self.assertFalse(os.path.exists(out))

    # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C12: Each tracked layout tool that needs KiCad's scripting interface runs it in the interpreter named by a documented environment variable, and the tool and its tests fail naming that variable when it is unset or names nothing runnable. The silkscreen command names the missing package when numpy, shapely or Pillow is not installed. No tool holds a path fixed to one machine: every tool, interpreter and board path is an argument or an environment variable. Tests cover the variable unset, the variable naming a missing file, a missing package and a path given as an argument, in text and in JSON.
    def test_a_missing_package_stops_build_and_check_naming_it_in_text_and_in_json(self):
        board = self.board()
        for module, package in (("numpy", "numpy"), ("shapely", "shapely"), ("PIL", "Pillow")):
            for command in (["build", "--board", board, "--out", self.path("out.kicad_pcb")], ["check", "--board", board]):
                status, out, err = self.run_blocked(module, *command)
                self.assertEqual(status, 2, (module, command))
                self.assertTrue(err.startswith(f"CANNOT RUN | the Python package {package} is not installed"), err)
                self.assertEqual(out, "")
                status, out, err = self.run_blocked(module, *command, "--format", "json")
                report = json.loads(out)
                self.assertEqual((status, report["result"]), (2, "CANNOT RUN"))
                self.assertIn(f"the Python package {package} is not installed", report["detail"])
        self.assertFalse(os.path.exists(self.path("out.kicad_pcb")))

    # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C12: Each tracked layout tool that needs KiCad's scripting interface runs it in the interpreter named by a documented environment variable, and the tool and its tests fail naming that variable when it is unset or names nothing runnable. The silkscreen command names the missing package when numpy, shapely or Pillow is not installed. No tool holds a path fixed to one machine: every tool, interpreter and board path is an argument or an environment variable. Tests cover the variable unset, the variable naming a missing file, a missing package and a path given as an argument, in text and in JSON.
    def test_the_proof_and_the_table_need_neither_package_nor_the_interpreter(self):
        board = self.board()
        status, out, err = self.run_blocked("numpy", "prove", "--input", board, "--output", board, env=self.env())
        self.assertEqual((status, err), (0, ""))
        self.assertTrue(out.startswith("RESULT | SILKSCREEN ONLY | "), out)
        status, out, err = self.run_blocked("shapely", "build", "--board", board, "--out", board, env=self.env())
        self.assertEqual(status, 1, "a refusal of the arguments comes before anything needs a package or KiCad")
        self.assertIn("the output is the input board", out)

    # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C12: Each tracked layout tool that needs KiCad's scripting interface runs it in the interpreter named by a documented environment variable, and the tool and its tests fail naming that variable when it is unset or names nothing runnable. The silkscreen command names the missing package when numpy, shapely or Pillow is not installed. No tool holds a path fixed to one machine: every tool, interpreter and board path is an argument or an environment variable. Tests cover the variable unset, the variable naming a missing file, a missing package and a path given as an argument, in text and in JSON.
    def test_interpreter_board_table_and_work_folder_given_as_arguments_are_used_with_the_variable_unset(self):
        board = self.board()
        table = self.write("elsewhere/silkscreen.yaml", "fixed_texts:\n  - {id: t, text: HELLO, size: 1.0, at: [20, 20]}\n")
        out = self.path("another folder/out.kicad_pcb")
        work = self.path("my work")
        with mock.patch.dict(os.environ, self.env(), clear=True):
            status, report = self.run_json(silkscreen.main, "build", "--board", board, "--out", out, "--table", table, "--work", work,
                                           "--kicad-python", PYTHON)
            self.assertEqual((status, report["result"]), (0, "WRITTEN"), report)
            status, lines = self.run_tool(silkscreen.main, "check", "--board", out, "--kicad-python", PYTHON, "--work", work)
        self.assertEqual(status, 0, lines)
        self.assertTrue(lines[-1].startswith("RESULT | CLEAN | "), lines)
        self.assertTrue(os.path.isfile(os.path.join(work, "plan.json")) and os.path.isfile(os.path.join(work, "ink.json")))
        self.assertIn('(gr_text "HELLO"', self.read(out))

    # SOL-BOARD-METHOD-SCRIPTED-LAYOUT-TOOLS-ARE-TRACKED-AND-REUSED-BY-THE-NEXT-BOARD.C12: Each tracked layout tool that needs KiCad's scripting interface runs it in the interpreter named by a documented environment variable, and the tool and its tests fail naming that variable when it is unset or names nothing runnable. The silkscreen command names the missing package when numpy, shapely or Pillow is not installed. No tool holds a path fixed to one machine: every tool, interpreter and board path is an argument or an environment variable. Tests cover the variable unset, the variable naming a missing file, a missing package and a path given as an argument, in text and in JSON.
    def test_no_part_of_the_command_holds_a_path_fixed_to_one_machine(self):
        fixed = re.compile(r"(/Users/|/home/|/Applications/|/opt/homebrew|/usr/local/|C:\\\\|[A-Z]:/|Program Files|\bKiCad\.app\b)")
        for name in SOURCES + ("../sunbeam-em7000/main-board/silkscreen.yaml",):
            with open(os.path.join(TOOLS, name), encoding="utf-8") as handle:
                for number, line in enumerate(handle, 1):
                    self.assertIsNone(fixed.search(line), f"{name}:{number} holds a machine-fixed path: {line.strip()}")


if __name__ == "__main__":
    unittest.main()
