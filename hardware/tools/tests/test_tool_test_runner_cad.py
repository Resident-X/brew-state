#!/usr/bin/env python3
"""The shared runner of the tooling tests gives files that each need the one installed CAD tool a pass side by side.

The board tooling's tests run through the runner in firmware/tools one process per
file, several at once. The files that run KiCad share the one installed tool, so
this builds two synthetic files that each run it and runs them side by side.
A missing KiCad fails the module with a `CANNOT RUN | ...` line, as it does every
board test, rather than skipping it.
"""

import os
import subprocess
import sys
import tempfile
import textwrap
import unittest

TESTS = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(TESTS)))
sys.path.insert(0, TESTS)
sys.path.insert(0, os.path.dirname(TESTS))

import board_fixtures  # noqa: E402

KICAD_CLI = os.environ.get("KICAD_CLI") or "kicad-cli"
RUNNER = os.path.join(REPO, "firmware", "tools", "run_tool_tests.py")

#: A synthetic test file that runs KiCad's design rule check on the throwaway design, in a configuration of its own.
CAD_FILE = """
import os, subprocess, sys, tempfile, unittest
sys.path.insert(0, {tools!r})
import board_check

class RunsTheCadTool(unittest.TestCase):
    def test_runs_the_design_rule_check(self):
        version = board_check.require_kicad({kicad!r})
        with tempfile.TemporaryDirectory() as scratch:
            home = os.path.join(scratch, "config")
            os.mkdir(home)
            environment = board_check.isolate_kicad({kicad!r}, version, home)
            out = os.path.join(scratch, "drc.json")
            done = subprocess.run([{kicad!r}, "pcb", "drc", "--format", "json", "-o", out, {pcb!r}],
                                  env=environment, cwd=scratch, capture_output=True, text=True)
            self.assertEqual(0, done.returncode, done.stdout + done.stderr)
            self.assertTrue(os.path.getsize(out) > 0)
"""


def setUpModule():
    board_fixtures.require_tools(KICAD_CLI)


class TwoFilesThatEachNeedTheCadToolPassSideBySide(unittest.TestCase):
    def test_two_files_each_running_the_installed_tool_both_pass_together(self):
        """Two synthetic files that each run KiCad pass side by side on two workers, and on one."""
        # SOL-BOARD-TIER-TESTS-RUN-SIDE-BY-SIDE.C1: Over a synthetic directory of test files, the stage runs each file in a process of its own from the serial run's working directory, with the serial run's environment and test selection, several at once, at most four unless asked for more; reports each file's result as it finishes; and exits non-zero naming every file that fails, a file that crashes or cannot be imported included. A directory holding no test file fails the stage rather than passing. A file that cannot run because a tool it needs is missing makes the stage report that tool by name on its error output in the form the round reads as a failure to look, once however many files report it, so the round stops naming the tool rather than reporting a finding. The stage gives the same verdict run side by side as run one file after another, and two synthetic files that each need the one installed CAD tool both pass when run side by side. The on-demand full run of the board tooling's tests runs its files the same way. A test file divided to shorten the stage keeps every test it held, each in exactly one of the files it is divided into: the stage runs the same tests before and after the division, and the tests that need the seeded-fault proof stay outside the stage and inside the on-demand full run, as before. Tests of one class that only read a copy of a proof design and the result of checking it share one copy and one check made for the class, and a test that changes its copy has a copy of its own, so a test that changed a shared copy would be caught and no test sees another's change. Every test process the stage starts makes its git commits unsigned, whatever signing the user's own git configuration asks for, so scratch commits neither queue on one signing agent across the files run at once nor wait on a passphrase. The stage states its wall time and how many files it ran at once when it finishes. Out of scope: selecting tiers by changed path and the seeded-fault proof.
        pcb = os.path.join(board_fixtures.REPO, "hardware", "proof", "gate-proof", "gate-proof.kicad_pcb")
        with tempfile.TemporaryDirectory() as directory:
            for name in ("test_cad_one", "test_cad_two"):
                with open(os.path.join(directory, name + ".py"), "w", encoding="utf-8") as handle:
                    handle.write(textwrap.dedent(CAD_FILE.format(tools=os.path.dirname(TESTS), kicad=KICAD_CLI, pcb=pcb)))
            for workers in ("2", "1"):
                result = subprocess.run(
                    [sys.executable, RUNNER, "--tests", directory, "--cwd", REPO, "--workers", workers],
                    capture_output=True, text=True, check=False,
                )
                self.assertEqual(0, result.returncode, result.stdout + result.stderr)
                self.assertIn("PASSED: 2 modules, 2 tests, 0 failed", result.stdout)


if __name__ == "__main__":
    unittest.main()
