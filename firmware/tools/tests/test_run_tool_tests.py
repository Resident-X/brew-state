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
        self.assertRegex(together.stdout, r"PASSED: .*, \d+\.\d+s on 2 workers")

    def test_the_worker_count_asked_for_is_the_one_reported(self):
        """The closing line states the number of workers the run used."""
        # SOL-BOARD-TIER-TESTS-RUN-SIDE-BY-SIDE.C1: Over a synthetic directory of test files, the stage runs each file in a process of its own from the serial run's working directory, with the serial run's environment and test selection, several at once, at most four unless asked for more; reports each file's result as it finishes; and exits non-zero naming every file that fails, a file that crashes or cannot be imported included. A directory holding no test file fails the stage rather than passing. A file that cannot run because a tool it needs is missing makes the stage report that tool by name on its error output in the form the round reads as a failure to look, once however many files report it, so the round stops naming the tool rather than reporting a finding. The stage gives the same verdict run side by side as run one file after another, and two synthetic files that each need the one installed CAD tool both pass when run side by side. The on-demand full run of the board tooling's tests runs its files the same way. A test file divided to shorten the stage keeps every test it held, each in exactly one of the files it is divided into: the stage runs the same tests before and after the division, and the tests that need the seeded-fault proof stay outside the stage and inside the on-demand full run, as before. Tests of one class that only read a copy of a proof design and the result of checking it share one copy and one check made for the class, and a test that changes its copy has a copy of its own, so a test that changed a shared copy would be caught and no test sees another's change. Every test process the stage starts makes its git commits unsigned, whatever signing the user's own git configuration asks for, so scratch commits neither queue on one signing agent across the files run at once nor wait on a passphrase. The stage states its wall time and how many files it ran at once when it finishes. Out of scope: selecting tiers by changed path and the seeded-fault proof.
        # SOL-TOOL-TESTS-RUN-SIDE-BY-SIDE.C1: The task running the firmware tooling's tests runs each test module in a process of its own, side by side
        self.module("test_a", PASSING)
        self.assertRegex(self.run_runner("--workers", "3").stdout, r", \d+\.\d+s on 3 workers")

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


CANNOT_RUN = """
import sys, unittest
def setUpModule():
    print("CANNOT RUN | the tool named {name} was not found", file=sys.stderr, flush=True)
    raise unittest.SkipTest("tool missing")
class Needs(unittest.TestCase):
    def test_needs(self):
        pass
"""


class TheRunnerRunsFilesFromTheSerialRunsDirectoryAndForwardsAMissingTool(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = tempfile.TemporaryDirectory()
        self.addCleanup(self.root.cleanup)
        self.tests = os.path.join(self.directory.name, "tests")
        os.mkdir(self.tests)

    def module(self, name: str, source: str) -> None:
        with open(os.path.join(self.tests, name + ".py"), "w", encoding="utf-8") as handle:
            handle.write(textwrap.dedent(source))

    def run_runner(self, *extra: str, env: dict | None = None) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, os.path.join(TOOLS, "run_tool_tests.py"), "--tests", self.tests,
             "--cwd", self.root.name, *extra],
            capture_output=True, text=True, check=False, env=env,
        )

    def test_each_file_runs_from_the_named_directory_with_the_runners_environment(self):
        """Every file sees the working directory it was told to and the environment the runner was given."""
        # SOL-BOARD-TIER-TESTS-RUN-SIDE-BY-SIDE.C1: Over a synthetic directory of test files, the stage runs each file in a process of its own from the serial run's working directory, with the serial run's environment and test selection, several at once, at most four unless asked for more; reports each file's result as it finishes; and exits non-zero naming every file that fails, a file that crashes or cannot be imported included. A directory holding no test file fails the stage rather than passing. A file that cannot run because a tool it needs is missing makes the stage report that tool by name on its error output in the form the round reads as a failure to look, once however many files report it, so the round stops naming the tool rather than reporting a finding. The stage gives the same verdict run side by side as run one file after another, and two synthetic files that each need the one installed CAD tool both pass when run side by side. The on-demand full run of the board tooling's tests runs its files the same way. A test file divided to shorten the stage keeps every test it held, each in exactly one of the files it is divided into: the stage runs the same tests before and after the division, and the tests that need the seeded-fault proof stay outside the stage and inside the on-demand full run, as before. Tests of one class that only read a copy of a proof design and the result of checking it share one copy and one check made for the class, and a test that changes its copy has a copy of its own, so a test that changed a shared copy would be caught and no test sees another's change. Every test process the stage starts makes its git commits unsigned, whatever signing the user's own git configuration asks for, so scratch commits neither queue on one signing agent across the files run at once nor wait on a passphrase. The stage states its wall time and how many files it ran at once when it finishes. Out of scope: selecting tiers by changed path and the seeded-fault proof.
        self.module("test_where", f"""
            import os, unittest
            class Where(unittest.TestCase):
                def test_where(self):
                    self.assertEqual(os.path.realpath({self.root.name!r}), os.path.realpath(os.getcwd()))
                    self.assertEqual("kept", os.environ.get("RUN_TOOL_TESTS_MARK"))
            """)
        self.module("test_where_too", f"""
            import os, unittest
            class WhereToo(unittest.TestCase):
                def test_where(self):
                    self.assertEqual(os.path.realpath({self.root.name!r}), os.path.realpath(os.getcwd()))
            """)
        result = self.run_runner(env={**os.environ, "RUN_TOOL_TESTS_MARK": "kept"})
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("PASSED: 2 modules, 2 tests", result.stdout)

    def test_a_file_commits_unsigned_though_signing_is_on_in_the_runners_environment(self):
        """Side by side files do not queue on a signing agent: git is told not to sign, and the count already set is kept."""
        # SOL-BOARD-TIER-TESTS-RUN-SIDE-BY-SIDE.C1: Over a synthetic directory of test files, the stage runs each file in a process of its own from the serial run's working directory, with the serial run's environment and test selection, several at once, at most four unless asked for more; reports each file's result as it finishes; and exits non-zero naming every file that fails, a file that crashes or cannot be imported included. A directory holding no test file fails the stage rather than passing. A file that cannot run because a tool it needs is missing makes the stage report that tool by name on its error output in the form the round reads as a failure to look, once however many files report it, so the round stops naming the tool rather than reporting a finding. The stage gives the same verdict run side by side as run one file after another, and two synthetic files that each need the one installed CAD tool both pass when run side by side. The on-demand full run of the board tooling's tests runs its files the same way. A test file divided to shorten the stage keeps every test it held, each in exactly one of the files it is divided into: the stage runs the same tests before and after the division, and the tests that need the seeded-fault proof stay outside the stage and inside the on-demand full run, as before. Tests of one class that only read a copy of a proof design and the result of checking it share one copy and one check made for the class, and a test that changes its copy has a copy of its own, so a test that changed a shared copy would be caught and no test sees another's change. Every test process the stage starts makes its git commits unsigned, whatever signing the user's own git configuration asks for, so scratch commits neither queue on one signing agent across the files run at once nor wait on a passphrase. The stage states its wall time and how many files it ran at once when it finishes. Out of scope: selecting tiers by changed path and the seeded-fault proof.
        self.module("test_commit", f"""
            import os, subprocess, tempfile, unittest
            class Commits(unittest.TestCase):
                def test_commit(self):
                    with tempfile.TemporaryDirectory() as repo:
                        run = lambda *a: subprocess.run(["git", *a], cwd=repo, capture_output=True, text=True)
                        self.assertEqual(0, run("init").returncode)
                        done = run("-c", "user.name=t", "-c", "user.email=t@t", "commit", "--allow-empty", "-m", "x")
                        self.assertEqual(0, done.returncode, done.stderr)
                        self.assertEqual("a", os.environ.get("GIT_CONFIG_VALUE_0"))
            """)
        env = {**os.environ, "GIT_CONFIG_COUNT": "2", "GIT_CONFIG_KEY_0": "user.note", "GIT_CONFIG_VALUE_0": "a",
               "GIT_CONFIG_KEY_1": "commit.gpgsign", "GIT_CONFIG_VALUE_1": "true"}
        env["GIT_CONFIG_COUNT"] = "3"
        env.update({"GIT_CONFIG_KEY_2": "gpg.program", "GIT_CONFIG_VALUE_2": "/nonexistent/gpg"})
        result = self.run_runner(env=env)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)

    def test_every_failing_crashing_or_unimportable_file_is_named_and_the_stage_fails(self):
        """A failing file, a file that cannot be imported and a file that crashes the interpreter are all named."""
        # SOL-BOARD-TIER-TESTS-RUN-SIDE-BY-SIDE.C1: Over a synthetic directory of test files, the stage runs each file in a process of its own from the serial run's working directory, with the serial run's environment and test selection, several at once, at most four unless asked for more; reports each file's result as it finishes; and exits non-zero naming every file that fails, a file that crashes or cannot be imported included. A directory holding no test file fails the stage rather than passing. A file that cannot run because a tool it needs is missing makes the stage report that tool by name on its error output in the form the round reads as a failure to look, once however many files report it, so the round stops naming the tool rather than reporting a finding. The stage gives the same verdict run side by side as run one file after another, and two synthetic files that each need the one installed CAD tool both pass when run side by side. The on-demand full run of the board tooling's tests runs its files the same way. A test file divided to shorten the stage keeps every test it held, each in exactly one of the files it is divided into: the stage runs the same tests before and after the division, and the tests that need the seeded-fault proof stay outside the stage and inside the on-demand full run, as before. Tests of one class that only read a copy of a proof design and the result of checking it share one copy and one check made for the class, and a test that changes its copy has a copy of its own, so a test that changed a shared copy would be caught and no test sees another's change. Every test process the stage starts makes its git commits unsigned, whatever signing the user's own git configuration asks for, so scratch commits neither queue on one signing agent across the files run at once nor wait on a passphrase. The stage states its wall time and how many files it ran at once when it finishes. Out of scope: selecting tiers by changed path and the seeded-fault proof.
        self.module("test_good", PASSING)
        self.module("test_bad", FAILING)
        self.module("test_unimportable", UNIMPORTABLE)
        self.module("test_crashes", """
            import os, unittest
            class Crashes(unittest.TestCase):
                def test_crashes(self):
                    os._exit(7)
            """)
        result = self.run_runner()
        self.assertEqual(1, result.returncode)
        for name in ("test_bad", "test_unimportable", "test_crashes"):
            self.assertIn(f"FAILED {name}", result.stdout)
        self.assertNotIn("FAILED test_good", result.stdout)
        self.assertTrue(result.stdout.rstrip().endswith("test_bad, test_crashes, test_unimportable"), result.stdout)

    def test_each_result_is_reported_as_the_file_finishes(self):
        """A quick file's line is out before a slow file has finished."""
        # SOL-BOARD-TIER-TESTS-RUN-SIDE-BY-SIDE.C1: Over a synthetic directory of test files, the stage runs each file in a process of its own from the serial run's working directory, with the serial run's environment and test selection, several at once, at most four unless asked for more; reports each file's result as it finishes; and exits non-zero naming every file that fails, a file that crashes or cannot be imported included. A directory holding no test file fails the stage rather than passing. A file that cannot run because a tool it needs is missing makes the stage report that tool by name on its error output in the form the round reads as a failure to look, once however many files report it, so the round stops naming the tool rather than reporting a finding. The stage gives the same verdict run side by side as run one file after another, and two synthetic files that each need the one installed CAD tool both pass when run side by side. The on-demand full run of the board tooling's tests runs its files the same way. A test file divided to shorten the stage keeps every test it held, each in exactly one of the files it is divided into: the stage runs the same tests before and after the division, and the tests that need the seeded-fault proof stay outside the stage and inside the on-demand full run, as before. Tests of one class that only read a copy of a proof design and the result of checking it share one copy and one check made for the class, and a test that changes its copy has a copy of its own, so a test that changed a shared copy would be caught and no test sees another's change. Every test process the stage starts makes its git commits unsigned, whatever signing the user's own git configuration asks for, so scratch commits neither queue on one signing agent across the files run at once nor wait on a passphrase. The stage states its wall time and how many files it ran at once when it finishes. Out of scope: selecting tiers by changed path and the seeded-fault proof.
        marker = os.path.join(self.root.name, "quick-done")
        self.module("test_slow", f"""
            import os, time, unittest
            class Slow(unittest.TestCase):
                def test_waits_for_the_quick_report(self):
                    for _ in range(300):
                        if os.path.exists({marker!r}):
                            return
                        time.sleep(0.1)
                    self.fail("the quick file was not reported while this one ran")
            """)
        self.module("test_quick", PASSING)
        process = subprocess.Popen(
            [sys.executable, os.path.join(TOOLS, "run_tool_tests.py"), "--tests", self.tests,
             "--cwd", self.root.name, "--workers", "2"],
            stdout=subprocess.PIPE, text=True,
        )
        first = process.stdout.readline()
        open(marker, "w").close()
        rest = process.stdout.read()
        process.wait()
        self.assertIn("ok     test_quick", first)
        self.assertEqual(0, process.returncode, first + rest)

    def test_an_empty_directory_fails_when_run_from_a_directory(self):
        """A directory with no test file fails the stage in this form too."""
        # SOL-BOARD-TIER-TESTS-RUN-SIDE-BY-SIDE.C1: Over a synthetic directory of test files, the stage runs each file in a process of its own from the serial run's working directory, with the serial run's environment and test selection, several at once, at most four unless asked for more; reports each file's result as it finishes; and exits non-zero naming every file that fails, a file that crashes or cannot be imported included. A directory holding no test file fails the stage rather than passing. A file that cannot run because a tool it needs is missing makes the stage report that tool by name on its error output in the form the round reads as a failure to look, once however many files report it, so the round stops naming the tool rather than reporting a finding. The stage gives the same verdict run side by side as run one file after another, and two synthetic files that each need the one installed CAD tool both pass when run side by side. The on-demand full run of the board tooling's tests runs its files the same way. A test file divided to shorten the stage keeps every test it held, each in exactly one of the files it is divided into: the stage runs the same tests before and after the division, and the tests that need the seeded-fault proof stay outside the stage and inside the on-demand full run, as before. Tests of one class that only read a copy of a proof design and the result of checking it share one copy and one check made for the class, and a test that changes its copy has a copy of its own, so a test that changed a shared copy would be caught and no test sees another's change. Every test process the stage starts makes its git commits unsigned, whatever signing the user's own git configuration asks for, so scratch commits neither queue on one signing agent across the files run at once nor wait on a passphrase. The stage states its wall time and how many files it ran at once when it finishes. Out of scope: selecting tiers by changed path and the seeded-fault proof.
        result = self.run_runner()
        self.assertEqual(1, result.returncode)
        self.assertIn("no test module found", result.stderr)

    def test_the_same_verdict_side_by_side_as_one_after_another(self):
        """A mixed directory and an all-passing one each give the verdict and the named files on one worker as on several."""
        # SOL-BOARD-TIER-TESTS-RUN-SIDE-BY-SIDE.C1: Over a synthetic directory of test files, the stage runs each file in a process of its own from the serial run's working directory, with the serial run's environment and test selection, several at once, at most four unless asked for more; reports each file's result as it finishes; and exits non-zero naming every file that fails, a file that crashes or cannot be imported included. A directory holding no test file fails the stage rather than passing. A file that cannot run because a tool it needs is missing makes the stage report that tool by name on its error output in the form the round reads as a failure to look, once however many files report it, so the round stops naming the tool rather than reporting a finding. The stage gives the same verdict run side by side as run one file after another, and two synthetic files that each need the one installed CAD tool both pass when run side by side. The on-demand full run of the board tooling's tests runs its files the same way. A test file divided to shorten the stage keeps every test it held, each in exactly one of the files it is divided into: the stage runs the same tests before and after the division, and the tests that need the seeded-fault proof stay outside the stage and inside the on-demand full run, as before. Tests of one class that only read a copy of a proof design and the result of checking it share one copy and one check made for the class, and a test that changes its copy has a copy of its own, so a test that changed a shared copy would be caught and no test sees another's change. Every test process the stage starts makes its git commits unsigned, whatever signing the user's own git configuration asks for, so scratch commits neither queue on one signing agent across the files run at once nor wait on a passphrase. The stage states its wall time and how many files it ran at once when it finishes. Out of scope: selecting tiers by changed path and the seeded-fault proof.
        self.module("test_a", PASSING)
        self.module("test_b", PASSING)
        for workers in ("1", "4"):
            self.assertEqual(0, self.run_runner("--workers", workers).returncode)
        self.module("test_bad", FAILING)
        self.module("test_unimportable", UNIMPORTABLE)
        closings = []
        for workers in ("1", "4"):
            result = self.run_runner("--workers", workers)
            self.assertEqual(1, result.returncode)
            closings.append(result.stdout.rstrip().splitlines()[-1].rsplit(": ", 1)[1])
        self.assertEqual(["test_bad, test_unimportable"] * 2, closings)

    def test_a_missing_tool_is_reported_once_on_the_error_output_at_the_start_of_a_line(self):
        """Three files that each report the same missing tool put one CANNOT RUN line on stderr, and the stage fails."""
        # SOL-BOARD-TIER-TESTS-RUN-SIDE-BY-SIDE.C1: Over a synthetic directory of test files, the stage runs each file in a process of its own from the serial run's working directory, with the serial run's environment and test selection, several at once, at most four unless asked for more; reports each file's result as it finishes; and exits non-zero naming every file that fails, a file that crashes or cannot be imported included. A directory holding no test file fails the stage rather than passing. A file that cannot run because a tool it needs is missing makes the stage report that tool by name on its error output in the form the round reads as a failure to look, once however many files report it, so the round stops naming the tool rather than reporting a finding. The stage gives the same verdict run side by side as run one file after another, and two synthetic files that each need the one installed CAD tool both pass when run side by side. The on-demand full run of the board tooling's tests runs its files the same way. A test file divided to shorten the stage keeps every test it held, each in exactly one of the files it is divided into: the stage runs the same tests before and after the division, and the tests that need the seeded-fault proof stay outside the stage and inside the on-demand full run, as before. Tests of one class that only read a copy of a proof design and the result of checking it share one copy and one check made for the class, and a test that changes its copy has a copy of its own, so a test that changed a shared copy would be caught and no test sees another's change. Every test process the stage starts makes its git commits unsigned, whatever signing the user's own git configuration asks for, so scratch commits neither queue on one signing agent across the files run at once nor wait on a passphrase. The stage states its wall time and how many files it ran at once when it finishes. Out of scope: selecting tiers by changed path and the seeded-fault proof.
        for name in ("test_one", "test_two", "test_three"):
            self.module(name, CANNOT_RUN.format(name="kicad-cli"))
        self.module("test_other", CANNOT_RUN.format(name="resvg"))
        result = self.run_runner()
        self.assertEqual(1, result.returncode)
        lines = result.stderr.splitlines()
        self.assertEqual(1, lines.count("CANNOT RUN | the tool named kicad-cli was not found"), result.stderr)
        self.assertEqual(1, lines.count("CANNOT RUN | the tool named resvg was not found"), result.stderr)
        self.assertEqual(2, len([line for line in lines if line.startswith("CANNOT RUN |")]))
        self.assertNotIn("PASSED", result.stdout)

    def test_the_round_reads_the_runners_missing_tool_line_as_a_failure_to_look(self):
        """The round's own reader of a task's error output notes the one line the real runner forwards."""
        # SOL-BOARD-TIER-TESTS-RUN-SIDE-BY-SIDE.C1: Over a synthetic directory of test files, the stage runs each file in a process of its own from the serial run's working directory, with the serial run's environment and test selection, several at once, at most four unless asked for more; reports each file's result as it finishes; and exits non-zero naming every file that fails, a file that crashes or cannot be imported included. A directory holding no test file fails the stage rather than passing. A file that cannot run because a tool it needs is missing makes the stage report that tool by name on its error output in the form the round reads as a failure to look, once however many files report it, so the round stops naming the tool rather than reporting a finding. The stage gives the same verdict run side by side as run one file after another, and two synthetic files that each need the one installed CAD tool both pass when run side by side. The on-demand full run of the board tooling's tests runs its files the same way. A test file divided to shorten the stage keeps every test it held, each in exactly one of the files it is divided into: the stage runs the same tests before and after the division, and the tests that need the seeded-fault proof stay outside the stage and inside the on-demand full run, as before. Tests of one class that only read a copy of a proof design and the result of checking it share one copy and one check made for the class, and a test that changes its copy has a copy of its own, so a test that changed a shared copy would be caught and no test sees another's change. Every test process the stage starts makes its git commits unsigned, whatever signing the user's own git configuration asks for, so scratch commits neither queue on one signing agent across the files run at once nor wait on a passphrase. The stage states its wall time and how many files it ran at once when it finishes. Out of scope: selecting tiers by changed path and the seeded-fault proof.
        import task_gate
        for name in ("test_one", "test_two"):
            self.module(name, CANNOT_RUN.format(name="kicad-cli"))
        stub = os.path.join(self.root.name, "task")
        with open(stub, "w", encoding="utf-8") as handle:
            handle.write(f"#!/bin/sh\nexec {sys.executable} {os.path.join(TOOLS, 'run_tool_tests.py')} "
                         f"--tests {self.tests} --cwd {self.root.name}\n")
        os.chmod(stub, 0o755)
        with open(os.devnull, "w") as quiet, mock.patch.object(task_gate, "say"), \
                mock.patch.object(sys, "stderr", new=quiet):
            status, noted = task_gate.run_noting(
                stub, "hw:test:round", REPOSITORY, "round", "tests", "CANNOT RUN |")
        self.assertEqual(1, status)
        self.assertEqual(["CANNOT RUN | the tool named kicad-cli was not found"], noted)

    def test_the_worker_cap_bounds_the_default_and_a_request_overrides_it(self):
        """Unasked, a suite's own cap bounds the worker count; asked, the request is used whatever the cap."""
        # SOL-BOARD-TIER-TESTS-RUN-SIDE-BY-SIDE.C1: Over a synthetic directory of test files, the stage runs each file in a process of its own from the serial run's working directory, with the serial run's environment and test selection, several at once, at most four unless asked for more; reports each file's result as it finishes; and exits non-zero naming every file that fails, a file that crashes or cannot be imported included. A directory holding no test file fails the stage rather than passing. A file that cannot run because a tool it needs is missing makes the stage report that tool by name on its error output in the form the round reads as a failure to look, once however many files report it, so the round stops naming the tool rather than reporting a finding. The stage gives the same verdict run side by side as run one file after another, and two synthetic files that each need the one installed CAD tool both pass when run side by side. The on-demand full run of the board tooling's tests runs its files the same way. A test file divided to shorten the stage keeps every test it held, each in exactly one of the files it is divided into: the stage runs the same tests before and after the division, and the tests that need the seeded-fault proof stay outside the stage and inside the on-demand full run, as before. Tests of one class that only read a copy of a proof design and the result of checking it share one copy and one check made for the class, and a test that changes its copy has a copy of its own, so a test that changed a shared copy would be caught and no test sees another's change. Every test process the stage starts makes its git commits unsigned, whatever signing the user's own git configuration asks for, so scratch commits neither queue on one signing agent across the files run at once nor wait on a passphrase. The stage states its wall time and how many files it ran at once when it finishes. Out of scope: selecting tiers by changed path and the seeded-fault proof.
        self.assertEqual(8, run_tool_tests.default_workers(10, 8))
        self.assertEqual(3, run_tool_tests.default_workers(3, 8))
        self.assertEqual(2, run_tool_tests.default_workers(10, 2))
        self.module("test_a", PASSING)
        self.assertIn("on 2 workers", self.run_runner("--worker-cap", "2").stdout)
        self.assertIn("on 4 workers", self.run_runner("--worker-cap", "2", "--workers", "4").stdout)
        refused = self.run_runner("--worker-cap", "0")
        self.assertEqual(2, refused.returncode)
        self.assertIn("--worker-cap must be at least 1", refused.stderr)


if __name__ == "__main__":
    unittest.main()
