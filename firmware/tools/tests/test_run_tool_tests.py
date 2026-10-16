#!/usr/bin/env python3
"""The runner of the tool tests runs every module, reports each, and fails on nothing to run.

Each case builds a directory of synthetic test modules and runs the runner on it
as a command, reading the exit status and what it prints.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from unittest import mock

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPOSITORY = os.path.dirname(os.path.dirname(TOOLS))
sys.path.insert(0, TOOLS)

import run_tool_tests  # noqa: E402

PASSING = """
import unittest
class Passes(unittest.TestCase):
    def test_one(self):
        pass
    def test_two(self):
        pass
"""

FAILING = """
import unittest
class Fails(unittest.TestCase):
    def test_breaks(self):
        self.fail("the marker that must reach the output")
"""

NO_TEST = """
import unittest
class Empty(unittest.TestCase):
    pass
"""

UNIMPORTABLE = """
import a_module_that_does_not_exist_anywhere
"""


class TheRunnerRunsEveryModuleAndFailsOnNothingToRun(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)

    def module(self, name: str, source: str) -> None:
        with open(os.path.join(self.directory.name, name + ".py"), "w", encoding="utf-8") as handle:
            handle.write(textwrap.dedent(source))

    def run_runner(self, *extra: str, tests: str | None = None) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, os.path.join(TOOLS, "run_tool_tests.py"), "--tests", tests or self.directory.name, *extra],
            capture_output=True, text=True, check=False,
        )

    def test_passing_modules_pass_and_their_tests_are_counted_across_modules(self):
        """Two passing modules exit 0 and the closing line totals the tests of both."""
        # SOL-TOOL-TESTS-RUN-SIDE-BY-SIDE.C1: The task running the firmware tooling's tests runs each test module in a process of its own, side by side
        self.module("test_a", PASSING)
        self.module("test_b", PASSING)
        result = self.run_runner()
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("ok     test_a: 2 tests", result.stdout)
        self.assertIn("ok     test_b: 2 tests", result.stdout)
        self.assertIn("PASSED: 2 modules, 4 tests, 0 failed", result.stdout)

    def test_a_failing_module_fails_the_run_names_it_and_prints_its_output(self):
        """One failing module among passing ones fails the run, and only it is named with its output."""
        # SOL-TOOL-TESTS-RUN-SIDE-BY-SIDE.C2: The tooling test run fails when it finds nothing to run or any module does not pass
        self.module("test_good", PASSING)
        self.module("test_bad", FAILING)
        result = self.run_runner()
        self.assertEqual(1, result.returncode)
        self.assertIn("FAILED test_bad: 1 tests", result.stdout)
        self.assertIn("ok     test_good", result.stdout)
        self.assertIn("the marker that must reach the output", result.stdout)
        self.assertIn("FAILED: 2 modules, 3 tests, 1 failed", result.stdout)
        self.assertTrue(result.stdout.rstrip().endswith("test_bad"), result.stdout)

    def test_a_directory_with_no_test_module_fails(self):
        """A directory holding no test module fails rather than passing having run nothing."""
        # SOL-TOOL-TESTS-RUN-SIDE-BY-SIDE.C2: The tooling test run fails when it finds nothing to run or any module does not pass
        self.module("helper_not_a_test", PASSING)
        result = self.run_runner()
        self.assertEqual(1, result.returncode)
        self.assertIn("no test module found", result.stderr)
        self.assertNotIn("PASSED", result.stdout)

    def test_a_missing_directory_fails(self):
        """A test directory that does not exist fails as one with nothing in it does."""
        # SOL-TOOL-TESTS-RUN-SIDE-BY-SIDE.C2: The tooling test run fails when it finds nothing to run or any module does not pass
        result = self.run_runner(tests=os.path.join(self.directory.name, "absent"))
        self.assertEqual(1, result.returncode)
        self.assertIn("no test module found", result.stderr)

    def test_a_module_that_cannot_be_imported_fails_the_run_and_shows_why(self):
        """A module that errors on import fails the run and the import error reaches the output."""
        # SOL-TOOL-TESTS-RUN-SIDE-BY-SIDE.C2: The tooling test run fails when it finds nothing to run or any module does not pass
        self.module("test_good", PASSING)
        self.module("test_broken", UNIMPORTABLE)
        result = self.run_runner()
        self.assertEqual(1, result.returncode)
        self.assertIn("FAILED test_broken", result.stdout)
        self.assertIn("a_module_that_does_not_exist_anywhere", result.stdout)

    def test_a_module_that_runs_no_test_fails_the_run(self):
        """A module defining no test is a failure whatever status the Python in use gives an empty run."""
        # SOL-TOOL-TESTS-RUN-SIDE-BY-SIDE.C2: The tooling test run fails when it finds nothing to run or any module does not pass
        self.module("test_empty", NO_TEST)
        result = self.run_runner()
        self.assertEqual(1, result.returncode)
        self.assertIn("FAILED test_empty: 0 tests", result.stdout)

    def test_one_worker_gives_the_same_verdict_as_several(self):
        """Running the modules one at a time passes and fails exactly as running them side by side does."""
        # SOL-TOOL-TESTS-RUN-SIDE-BY-SIDE.C1: The task running the firmware tooling's tests runs each test module in a process of its own, side by side
        self.module("test_a", PASSING)
        self.assertEqual(0, self.run_runner("--workers", "1").returncode)
        self.module("test_bad", FAILING)
        self.assertEqual(1, self.run_runner("--workers", "1").returncode)

    def test_fewer_than_one_worker_is_refused(self):
        """A worker count below one is refused instead of running nothing."""
        # SOL-TOOL-TESTS-RUN-SIDE-BY-SIDE.C2: The tooling test run fails when it finds nothing to run or any module does not pass
        self.module("test_a", PASSING)
        result = self.run_runner("--workers", "0")
        self.assertEqual(2, result.returncode)
        self.assertIn("--workers must be at least 1", result.stderr)

    def test_modules_run_in_separate_processes(self):
        """A module's global state does not reach another: the second sees what the first set as unset."""
        # SOL-TOOL-TESTS-RUN-SIDE-BY-SIDE.C1: The task running the firmware tooling's tests runs each test module in a process of its own, side by side
        self.module("test_sets", """
            import os, unittest
            class Sets(unittest.TestCase):
                def test_sets(self):
                    os.environ["RUN_TOOL_TESTS_LEAK"] = "1"
            """)
        self.module("test_reads", """
            import os, unittest
            class Reads(unittest.TestCase):
                def test_reads(self):
                    self.assertNotIn("RUN_TOOL_TESTS_LEAK", os.environ)
            """)
        result = self.run_runner("--workers", "1")
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)


    def test_each_module_that_passes_alone_also_passes_together(self):
        """Two modules each passing when run alone on one worker pass together, side by side, with the same counts."""
        # SOL-TOOL-TESTS-RUN-SIDE-BY-SIDE.C1: The task running the firmware tooling's tests runs each test module in a process of its own, side by side
        alone = []
        for name in ("test_a", "test_b"):
            with tempfile.TemporaryDirectory() as only:
                with open(os.path.join(only, name + ".py"), "w", encoding="utf-8") as handle:
                    handle.write(textwrap.dedent(PASSING))
                result = self.run_runner("--workers", "1", tests=only)
                self.assertEqual(0, result.returncode, result.stdout + result.stderr)
                self.assertIn(f"ok     {name}: 2 tests", result.stdout)
                alone.append(name)
        for name in alone:
            self.module(name, PASSING)
        together = self.run_runner("--workers", "2")
        self.assertEqual(0, together.returncode, together.stdout + together.stderr)
        for name in alone:
            self.assertIn(f"ok     {name}: 2 tests", together.stdout)
        self.assertIn("PASSED: 2 modules, 4 tests, 0 failed", together.stdout)
        self.assertIn("on 2 workers", together.stdout)

    def test_the_worker_count_asked_for_is_the_one_reported(self):
        """The closing line states the number of workers the run used."""
        # SOL-TOOL-TESTS-RUN-SIDE-BY-SIDE.C1: The task running the firmware tooling's tests runs each test module in a process of its own, side by side
        self.module("test_a", PASSING)
        self.assertIn("on 3 workers", self.run_runner("--workers", "3").stdout)

    def test_without_a_worker_count_the_cpu_count_is_used_up_to_six(self):
        """Unasked, the runner uses the CPU count, never more than six, and one when the count is unknown."""
        # SOL-TOOL-TESTS-RUN-SIDE-BY-SIDE.C1: The task running the firmware tooling's tests runs each test module in a process of its own, side by side
        self.assertEqual(6, run_tool_tests.default_workers(32))
        self.assertEqual(6, run_tool_tests.default_workers(6))
        self.assertEqual(2, run_tool_tests.default_workers(2))
        self.assertEqual(1, run_tool_tests.default_workers(1))
        self.assertEqual(1, run_tool_tests.default_workers(None))
        self.module("test_a", PASSING)
        result = self.run_runner()
        self.assertIn(f"on {min(os.cpu_count() or 1, 6)} workers", result.stdout)

    def test_a_module_that_cannot_be_started_fails_and_says_so(self):
        """A module whose process cannot be started is a failure carrying the reason, never a pass."""
        # SOL-TOOL-TESTS-RUN-SIDE-BY-SIDE.C2: The tooling test run fails when it finds nothing to run or any module does not pass
        with mock.patch.object(run_tool_tests.subprocess, "run", side_effect=OSError("no interpreter")):
            result = run_tool_tests.run_module("test_a", self.directory.name)
        self.assertNotEqual(0, result["status"])
        self.assertEqual(0, result["tests"])
        self.assertIn("could not start: no interpreter", result["output"])
        self.assertFalse(run_tool_tests.passed(result))

    def test_the_task_passes_the_callers_arguments_to_the_runner(self):
        """The Taskfile's test task hands its command-line arguments to the runner, so the worker count is settable through it."""
        # SOL-TOOL-TESTS-RUN-SIDE-BY-SIDE.C1: The task running the firmware tooling's tests runs each test module in a process of its own, side by side
        with open(os.path.join(REPOSITORY, "Taskfile.yml"), encoding="utf-8") as handle:
            lines = handle.read().splitlines()
        start = lines.index("  fw:test:")
        commands = []
        for line in lines[start + 1:]:
            if line.strip() and (len(line) - len(line.lstrip(" "))) <= 2:
                break
            if line.startswith("      - "):
                commands.append(line[len("      - "):].strip())
        (runner,) = [command for command in commands if "tools/run_tool_tests.py" in command]
        self.assertTrue(runner.endswith("{{.CLI_ARGS}}"), runner)


if __name__ == "__main__":
    unittest.main()
