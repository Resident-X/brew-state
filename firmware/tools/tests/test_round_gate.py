#!/usr/bin/env python3
"""The build round's gate decides what to run from what the branch changed.

Every case is driven against a synthetic repository: a handful of files laid out
where the firmware tree, the analysis records and the task runner's declaration
sit, a remote-tracking main pointed at the main they were committed to, and a
branch changed from that main.
The task runner is a shell script that records which tasks it was asked for and
fails the ones it is told to, so the gate's ordering, stopping and verdict are
observed without a build behind them.
"""

from __future__ import annotations

import ast
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPOSITORY = os.path.dirname(os.path.dirname(TOOLS))
sys.path.insert(0, TOOLS)

import round_gate  # noqa: E402

HOST = ["fw:build", "fw:check", "fw:test", "fw:run"]
EMULATION = ["fw:emulate"]

#: Git told nothing about the user running the tests: no global or system
#: configuration, and an identity of its own.
GIT_ENVIRONMENT = {
    **os.environ,
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_AUTHOR_NAME": "Synthetic",
    "GIT_AUTHOR_EMAIL": "synthetic@example.invalid",
    "GIT_COMMITTER_NAME": "Synthetic",
    "GIT_COMMITTER_EMAIL": "synthetic@example.invalid",
}

#: The files the synthetic main starts with, at the places the real ones sit.
BASELINE = {
    "firmware/src/control/loop.c": "int loop(void) { return 0; }\n",
    "firmware/src/control/old.c": "int old(void) { return 0; }\n",
    "firmware/include/hw.h": "#pragma once\n",
    "firmware/params/thermoblock.params": "mass 1.0\n",
    "firmware/platformio.ini": "[env:native]\nplatform = native\n",
    "firmware/tools/check_example.py": "print('check')\n",
    "firmware/emulation/tests/test_example.py": "pass\n",
    "docs/protection-margin.md": "# margin\n",
    "docs/parameter-dominance.md": "# dominance\n",
    "docs/parameter-identifiability.md": "# identifiability\n",
    "docs/parameter-stability.md": "# stability\n",
    "docs/machine/notes.md": "# notes\n",
    "specs/example.req.yaml": "id: REQ-TEST-001\n",
    "Taskfile.yml": "version: '3'\n",
    ".gitignore": "firmware/.pio/\n",
}


class SyntheticRepository:
    """A repository whose remote-tracking main is its main, on a branch off it."""

    def __init__(self, with_tracking: bool = True):
        self.directory = tempfile.TemporaryDirectory()
        self.root = os.path.realpath(self.directory.name)
        self.git("init", "-q", "-b", "main")
        for path, content in BASELINE.items():
            self.write(path, content)
        self.commit("baseline")
        if with_tracking:
            self.track("main")
        self.git("checkout", "-q", "-b", "feature")

    def cleanup(self) -> None:
        self.directory.cleanup()

    def git(self, *arguments: str) -> str:
        return subprocess.run(
            ["git", "-C", self.root, *arguments],
            capture_output=True,
            text=True,
            check=True,
            env=GIT_ENVIRONMENT,
        ).stdout

    def write(self, path: str, content: str = "changed\n") -> None:
        full = os.path.join(self.root, path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as handle:
            handle.write(content)

    def commit(self, message: str) -> None:
        self.git("add", "-A")
        self.git("commit", "-q", "--allow-empty", "-m", message)

    def change_and_commit(self, path: str) -> None:
        self.write(path, BASELINE.get(path, "") + "changed\n")
        self.commit(f"change {path}")

    def head(self) -> str:
        return self.git("rev-parse", "HEAD").strip()

    def track(self, commit: str) -> None:
        """Point the remote-tracking main at a commit, as a fetch would leave it."""
        self.git("update-ref", "refs/remotes/origin/main", commit)

    def scope(self) -> round_gate.Scope:
        return round_gate.scope(round_gate.changed(self.root))


class FakeTaskRunner:
    """Stands in for the task runner: logs each task it is asked for, fails some."""

    def __init__(self, directory: str, failing: tuple[str, ...] = ()):
        self.log = os.path.join(directory, "asked.log")
        failures = os.path.join(directory, "failing")
        with open(failures, "w", encoding="utf-8") as handle:
            handle.write("".join(f"{name}\n" for name in failing))
        self.path = os.path.join(directory, "task")
        with open(self.path, "w", encoding="utf-8") as handle:
            handle.write(
                "#!/bin/sh\n"
                f'echo "$1" >> "{self.log}"\n'
                f'if grep -qx "$1" "{failures}"; then exit 3; fi\n'
                "exit 0\n"
            )
        os.chmod(self.path, os.stat(self.path).st_mode | stat.S_IEXEC)

    def asked(self) -> list[str]:
        if not os.path.exists(self.log):
            return []
        with open(self.log, encoding="utf-8") as handle:
            return handle.read().split()


def run_gate(
    repository: SyntheticRepository, failing: tuple[str, ...] = (), task: str | None = None
):
    runner_directory = tempfile.TemporaryDirectory()
    runner = FakeTaskRunner(runner_directory.name, failing)
    arguments = [
        sys.executable, os.path.join(TOOLS, "round_gate.py"), "--task", task or runner.path
    ]
    for name in HOST:
        arguments += ["--host", name]
    for name in EMULATION:
        arguments += ["--emulation", name]
    result = subprocess.run(
        arguments, cwd=repository.root, capture_output=True, text=True, check=False,
        env=GIT_ENVIRONMENT,
    )
    asked = runner.asked()
    runner_directory.cleanup()
    return result, asked


# --- What the gate runs, and what it says -----------------------------------


class TheGateRunsTheHostTierAlwaysAndEmulationWhenItCanMatter(unittest.TestCase):
    def setUp(self):
        self.repository = SyntheticRepository()
        self.addCleanup(self.repository.cleanup)

    def test_a_change_outside_what_emulation_reads_runs_every_host_task_and_skips_emulation(self):
        # SOL-VERIFY-ROUND-GATE-TARGETED.C1: The round gate runs the host tier in full and the emulation tier only for changes it exercises
        self.repository.change_and_commit("docs/machine/notes.md")
        result, asked = run_gate(self.repository)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertEqual(HOST, asked)
        self.assertIn("ROUND GATE PASSED", result.stdout)
        self.assertIn("emulation tier was correctly SKIPPED", result.stdout)
        # The skip names the paths it was judged by, so the reader can check it.
        self.assertIn("docs/machine/notes.md", result.stdout.split("ROUND GATE PASSED")[1])

    def test_a_firmware_change_runs_the_host_tier_then_emulation_and_names_the_path(self):
        # SOL-VERIFY-ROUND-GATE-TARGETED.C1: The round gate runs the host tier in full and the emulation tier only for changes it exercises
        self.repository.change_and_commit("firmware/src/control/loop.c")
        result, asked = run_gate(self.repository)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertEqual(HOST + EMULATION, asked)
        self.assertIn("emulation tier WILL RUN", result.stdout)
        self.assertIn("    firmware/src/control/loop.c", result.stdout)
        self.assertIn("both ran and passed", result.stdout)

    def test_a_host_failure_stops_the_gate_and_says_emulation_was_not_reached(self):
        # SOL-VERIFY-ROUND-GATE-TARGETED.C1: The round gate runs the host tier in full and the emulation tier only for changes it exercises
        self.repository.change_and_commit("firmware/src/control/loop.c")
        result, asked = run_gate(self.repository, failing=("fw:check",))
        self.assertNotEqual(0, result.returncode)
        self.assertEqual(["fw:build", "fw:check"], asked)
        self.assertIn("ROUND GATE FAILED: the host tier failed at fw:check", result.stdout)
        closing = result.stdout.split("ROUND GATE FAILED")[1]
        self.assertIn("emulation tier was NOT REACHED", closing)
        self.assertIn("it would have run, because", closing)
        self.assertIn("    firmware/src/control/loop.c", closing)
        self.assertNotIn("PASSED", result.stdout)

    def test_the_last_host_task_failing_still_fails_the_gate_when_emulation_would_be_skipped(self):
        # SOL-VERIFY-ROUND-GATE-TARGETED.C1: The round gate runs the host tier in full and the emulation tier only for changes it exercises
        self.repository.change_and_commit("docs/machine/notes.md")
        result, asked = run_gate(self.repository, failing=("fw:run",))
        self.assertNotEqual(0, result.returncode)
        self.assertEqual(HOST, asked)
        self.assertIn("host tier failed at fw:run", result.stdout)
        # Both facts reach the closing lines: emulation was not reached, and it
        # would have been skipped, judged by the paths named.
        closing = result.stdout.split("ROUND GATE FAILED")[1]
        self.assertIn("emulation tier was NOT REACHED", closing)
        self.assertIn("it would have been skipped, because", closing)
        self.assertIn("    docs/machine/notes.md", closing)
        self.assertNotIn("PASSED", result.stdout)

    def test_a_task_runner_that_cannot_start_fails_the_host_tier(self):
        # SOL-VERIFY-ROUND-GATE-TARGETED.C1: The round gate runs the host tier in full and the emulation tier only for changes it exercises
        self.repository.change_and_commit("firmware/src/control/loop.c")
        missing = os.path.join(self.repository.root, "no-such-task-runner")
        result, asked = run_gate(self.repository, task=missing)
        self.assertNotEqual(0, result.returncode)
        self.assertEqual([], asked)
        self.assertIn("fw:build could not be started", result.stdout)
        self.assertIn("ROUND GATE FAILED: the host tier failed at fw:build", result.stdout)
        self.assertIn("emulation tier was NOT REACHED", result.stdout)
        self.assertNotIn("PASSED", result.stdout)

    def test_the_statements_name_the_base_and_head_commits_measured_between(self):
        # SOL-VERIFY-ROUND-GATE-TARGETED.C1: The round gate runs the host tier in full and the emulation tier only for changes it exercises
        base = self.repository.head()
        self.repository.change_and_commit("docs/machine/notes.md")
        head = self.repository.head()
        result, _ = run_gate(self.repository)
        closing = result.stdout.split("ROUND GATE PASSED")[1]
        self.assertIn(f"merge-base {base} with origin/main", closing)
        self.assertIn(f"HEAD {head}", closing)

    def test_an_emulation_failure_fails_the_gate(self):
        # SOL-VERIFY-ROUND-GATE-TARGETED.C1: The round gate runs the host tier in full and the emulation tier only for changes it exercises
        self.repository.change_and_commit("firmware/src/control/loop.c")
        result, asked = run_gate(self.repository, failing=("fw:emulate",))
        self.assertNotEqual(0, result.returncode)
        self.assertEqual(HOST + EMULATION, asked)
        self.assertIn("ROUND GATE FAILED: the emulation tier failed at fw:emulate", result.stdout)

    def test_an_unresolvable_base_runs_emulation_and_says_why(self):
        # SOL-VERIFY-ROUND-GATE-TARGETED.C2: The round gate runs everything when it cannot tell what changed
        repository = SyntheticRepository(with_tracking=False)
        self.addCleanup(repository.cleanup)
        repository.change_and_commit("docs/machine/notes.md")
        result, asked = run_gate(repository)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertEqual(HOST + EMULATION, asked)
        self.assertIn("could not tell what changed", result.stdout)
        self.assertIn("there is no remote-tracking origin/main", result.stdout)
        self.assertIn(f"HEAD {repository.head()}", result.stdout)


# --- The base is guarded against accidental git state, not against tampering --


class TheBaseIsTheRemoteTrackingMain(unittest.TestCase):
    """The selection is a cost measure: it guards against git state that is
    stale or unusually configured, not against a producer rewriting the tree."""

    def setUp(self):
        self.repository = SyntheticRepository()
        self.addCleanup(self.repository.cleanup)
        self.repository.change_and_commit("firmware/src/control/loop.c")

    def test_a_stale_remote_tracking_main_only_widens_the_change(self):
        # SOL-VERIFY-ROUND-GATE-TARGETED.C1: The round gate runs the host tier in full and the emulation tier only for changes it exercises
        # Main gained a firmware change the remote-tracking copy never heard
        # of, and the branch was started from that newer main: the older base
        # charges main's change to the branch, so emulation runs rather than
        # being skipped for a branch that itself touches only documents.
        self.repository.git("checkout", "-q", "main")
        self.repository.change_and_commit("firmware/include/hw.h")
        self.repository.git("checkout", "-q", "-B", "feature", "main")
        self.repository.change_and_commit("docs/machine/notes.md")
        chosen = self.repository.scope()
        self.assertTrue(chosen.run_emulation, chosen.reason)
        self.assertEqual(["firmware/include/hw.h"], chosen.judged)

    def test_a_local_branch_named_like_the_base_does_not_shadow_it(self):
        # SOL-VERIFY-ROUND-GATE-TARGETED.C1: The round gate runs the host tier in full and the emulation tier only for changes it exercises
        self.repository.git("branch", "origin/main", "HEAD")
        chosen = self.repository.scope()
        self.assertTrue(chosen.run_emulation, chosen.reason)
        self.assertEqual(["firmware/src/control/loop.c"], chosen.judged)

    def test_git_that_cannot_be_run_runs_emulation_and_says_why(self):
        # SOL-VERIFY-ROUND-GATE-TARGETED.C2: The round gate runs everything when it cannot tell what changed
        empty = tempfile.TemporaryDirectory()
        self.addCleanup(empty.cleanup)
        with mock.patch.dict(os.environ, {"PATH": empty.name}):
            change = round_gate.changed(self.repository.root)
        self.assertIsNone(change.paths)
        chosen = round_gate.scope(change)
        self.assertTrue(chosen.run_emulation)
        self.assertIn("git could not be run", chosen.reason)


class TheChangeIsMeasuredFromTheMergeBaseAndTheWorkingTree(unittest.TestCase):
    def setUp(self):
        self.repository = SyntheticRepository()
        self.addCleanup(self.repository.cleanup)

    def test_what_main_gained_after_the_branch_left_it_is_not_charged_to_the_branch(self):
        # SOL-VERIFY-ROUND-GATE-TARGETED.C1: The round gate runs the host tier in full and the emulation tier only for changes it exercises
        self.repository.git("checkout", "-q", "main")
        self.repository.change_and_commit("firmware/src/control/loop.c")
        self.repository.track("main")
        self.repository.git("checkout", "-q", "feature")
        self.repository.change_and_commit("docs/machine/notes.md")
        chosen = self.repository.scope()
        self.assertFalse(chosen.run_emulation, chosen.reason)
        self.assertEqual(["docs/machine/notes.md"], chosen.judged)

    def test_an_uncommitted_edit_to_a_firmware_file_counts(self):
        # SOL-VERIFY-ROUND-GATE-TARGETED.C1: The round gate runs the host tier in full and the emulation tier only for changes it exercises
        self.repository.write("firmware/include/hw.h", "#pragma once\nint x;\n")
        chosen = self.repository.scope()
        self.assertTrue(chosen.run_emulation, chosen.reason)
        self.assertEqual(["firmware/include/hw.h"], chosen.judged)

    def test_a_staged_but_uncommitted_edit_counts(self):
        # SOL-VERIFY-ROUND-GATE-TARGETED.C1: The round gate runs the host tier in full and the emulation tier only for changes it exercises
        self.repository.write("firmware/include/hw.h", "#pragma once\nint x;\n")
        self.repository.git("add", "firmware/include/hw.h")
        self.assertTrue(self.repository.scope().run_emulation)

    def test_an_ignored_build_output_is_not_a_new_file_of_the_change(self):
        # SOL-VERIFY-ROUND-GATE-TARGETED.C1: The round gate runs the host tier in full and the emulation tier only for changes it exercises
        self.repository.write("firmware/.pio/build/native/program", "binary\n")
        chosen = self.repository.scope()
        self.assertFalse(chosen.run_emulation, chosen.reason)

    def test_the_change_is_read_from_the_repository_root_when_started_below_it(self):
        # SOL-VERIFY-ROUND-GATE-TARGETED.C1: The round gate runs the host tier in full and the emulation tier only for changes it exercises
        self.repository.write("firmware/src/control/new.c", "int new_one;\n")
        change = round_gate.changed(os.path.join(self.repository.root, "docs"))
        self.assertEqual(["firmware/src/control/new.c"], change.paths)

    def test_a_relative_diff_configuration_does_not_hide_changes_outside_the_start(self):
        # SOL-VERIFY-ROUND-GATE-TARGETED.C1: The round gate runs the host tier in full and the emulation tier only for changes it exercises
        self.repository.git("config", "diff.relative", "true")
        self.repository.change_and_commit("firmware/src/control/loop.c")
        change = round_gate.changed(os.path.join(self.repository.root, "docs"))
        self.assertEqual(["firmware/src/control/loop.c"], change.paths)


# --- The selection, case by case ---------------------------------------------


class ThePathSelection(unittest.TestCase):
    def setUp(self):
        self.repository = SyntheticRepository()
        self.addCleanup(self.repository.cleanup)

    def assertRuns(self, *expected: str):
        chosen = self.repository.scope()
        self.assertTrue(chosen.run_emulation, chosen.reason)
        for path in expected:
            self.assertIn(path, chosen.judged)

    def assertSkips(self):
        chosen = self.repository.scope()
        self.assertFalse(chosen.run_emulation, chosen.reason)
        return chosen

    def test_a_documents_only_change_outside_what_emulation_reads_skips_it(self):
        # SOL-VERIFY-ROUND-GATE-TARGETED.C2: The round gate runs everything when it cannot tell what changed
        self.repository.change_and_commit("docs/machine/notes.md")
        self.repository.change_and_commit("specs/example.req.yaml")
        chosen = self.assertSkips()
        self.assertEqual(["docs/machine/notes.md", "specs/example.req.yaml"], chosen.judged)
        self.assertIn("none of the 2 changed path(s)", chosen.reason)

    def test_a_firmware_source_change_runs_it(self):
        # SOL-VERIFY-ROUND-GATE-TARGETED.C2: The round gate runs everything when it cannot tell what changed
        self.repository.change_and_commit("firmware/src/control/loop.c")
        self.assertRuns("firmware/src/control/loop.c")

    def test_a_parameter_file_change_runs_it(self):
        # SOL-VERIFY-ROUND-GATE-TARGETED.C2: The round gate runs everything when it cannot tell what changed
        self.repository.change_and_commit("firmware/params/thermoblock.params")
        self.assertRuns("firmware/params/thermoblock.params")

    def test_an_emulation_suite_change_runs_it(self):
        # SOL-VERIFY-ROUND-GATE-TARGETED.C2: The round gate runs everything when it cannot tell what changed
        self.repository.change_and_commit("firmware/emulation/tests/test_example.py")
        self.assertRuns("firmware/emulation/tests/test_example.py")

    def test_a_change_to_a_record_the_emulation_suite_checks_runs_it(self):
        # SOL-VERIFY-ROUND-GATE-TARGETED.C2: The round gate runs everything when it cannot tell what changed
        for record in (
            "docs/protection-margin.md",
            "docs/parameter-dominance.md",
            "docs/parameter-identifiability.md",
            "docs/parameter-stability.md",
        ):
            with self.subTest(record=record):
                repository = SyntheticRepository()
                self.addCleanup(repository.cleanup)
                repository.change_and_commit(record)
                chosen = repository.scope()
                self.assertTrue(chosen.run_emulation, chosen.reason)
                self.assertEqual([record], chosen.judged)

    def test_a_new_firmware_file_not_yet_committed_runs_it(self):
        # SOL-VERIFY-ROUND-GATE-TARGETED.C2: The round gate runs everything when it cannot tell what changed
        self.repository.write("firmware/src/control/added.c", "int added;\n")
        self.assertRuns("firmware/src/control/added.c")

    def test_a_deleted_firmware_file_runs_it(self):
        # SOL-VERIFY-ROUND-GATE-TARGETED.C2: The round gate runs everything when it cannot tell what changed
        self.repository.git("rm", "-q", "firmware/src/control/old.c")
        self.repository.commit("delete")
        self.assertRuns("firmware/src/control/old.c")

    def test_a_file_renamed_out_of_the_firmware_tree_runs_it(self):
        # SOL-VERIFY-ROUND-GATE-TARGETED.C2: The round gate runs everything when it cannot tell what changed
        self.repository.git("mv", "firmware/src/control/old.c", "docs/machine/old.c")
        self.repository.commit("move")
        chosen = self.repository.scope()
        self.assertTrue(chosen.run_emulation, chosen.reason)
        self.assertEqual(["firmware/src/control/old.c"], chosen.judged)

    def test_an_empty_change_skips_it_and_says_nothing_changed(self):
        # SOL-VERIFY-ROUND-GATE-TARGETED.C2: The round gate runs everything when it cannot tell what changed
        chosen = self.assertSkips()
        self.assertEqual([], chosen.judged)
        self.assertIn("changes nothing", chosen.reason)

    def test_an_unresolvable_base_runs_it_and_says_why(self):
        # SOL-VERIFY-ROUND-GATE-TARGETED.C2: The round gate runs everything when it cannot tell what changed
        # The remote's main was rewritten to a history the branch shares
        # nothing with: the base resolves, and there is no merge-base with it.
        self.repository.change_and_commit("docs/machine/notes.md")
        self.repository.git("checkout", "-q", "--orphan", "unrelated")
        self.repository.commit("unrelated")
        self.repository.track("unrelated")
        self.repository.git("checkout", "-q", "feature")
        change = round_gate.changed(self.repository.root)
        self.assertIsNone(change.paths)
        chosen = round_gate.scope(change)
        self.assertTrue(chosen.run_emulation)
        self.assertIn("merge-base of HEAD with origin/main could not be resolved", chosen.reason)

    def test_a_repository_with_no_remote_tracking_main_runs_it_and_says_why(self):
        # SOL-VERIFY-ROUND-GATE-TARGETED.C2: The round gate runs everything when it cannot tell what changed
        repository = SyntheticRepository(with_tracking=False)
        self.addCleanup(repository.cleanup)
        repository.change_and_commit("docs/machine/notes.md")
        change = round_gate.changed(repository.root)
        self.assertIsNone(change.paths)
        chosen = round_gate.scope(change)
        self.assertTrue(chosen.run_emulation)
        self.assertIn(
            "there is no remote-tracking origin/main (refs/remotes/origin/main)", chosen.reason
        )

    def test_an_unreadable_list_of_changed_paths_runs_it_and_says_why(self):
        # SOL-VERIFY-ROUND-GATE-TARGETED.C2: The round gate runs everything when it cannot tell what changed
        self.repository.change_and_commit("docs/machine/notes.md")
        with open(os.path.join(self.repository.root, ".git", "index"), "wb") as handle:
            handle.write(b"not an index")
        change = round_gate.changed(self.repository.root)
        self.assertIsNotNone(change.base, "the base resolves; it is the list that cannot be read")
        self.assertIsNone(change.paths)
        chosen = round_gate.scope(change)
        self.assertTrue(chosen.run_emulation)
        self.assertIn("could not tell what changed", chosen.reason)
        self.assertIn("could not be read", chosen.reason)

    def test_a_task_runner_declaration_change_runs_it(self):
        # SOL-VERIFY-ROUND-GATE-TARGETED.C2: The round gate runs everything when it cannot tell what changed
        self.repository.change_and_commit("Taskfile.yml")
        self.assertRuns("Taskfile.yml")

    def test_a_build_configuration_change_runs_it(self):
        # SOL-VERIFY-ROUND-GATE-TARGETED.C2: The round gate runs everything when it cannot tell what changed
        self.repository.change_and_commit("firmware/platformio.ini")
        self.assertRuns("firmware/platformio.ini")

    def test_a_firmware_tooling_change_runs_it(self):
        # SOL-VERIFY-ROUND-GATE-TARGETED.C2: The round gate runs everything when it cannot tell what changed
        self.repository.change_and_commit("firmware/tools/check_example.py")
        self.assertRuns("firmware/tools/check_example.py")

    def test_a_path_that_only_shares_a_prefix_with_a_trigger_does_not_run_it(self):
        # SOL-VERIFY-ROUND-GATE-TARGETED.C2: The round gate runs everything when it cannot tell what changed
        self.assertFalse(round_gate.reads("firmware-notes.md"))
        self.assertFalse(round_gate.reads("docs/protection-margin.md.orig"))
        self.assertFalse(round_gate.reads("docs/machine/Taskfile.yml"))


# --- The declaration the task runner carries --------------------------------


def task_commands(taskfile: str, name: str) -> list[str]:
    """The entries under a task's `cmds`, read from the Taskfile as text.

    Read as text so the host tier, which runs these tests, needs nothing beyond
    the standard library. A task is a key indented two spaces under `tasks:`;
    its commands are the list items indented six.
    """
    lines = taskfile.splitlines()
    start = lines.index(f"  {name}:")
    commands = []
    for line in lines[start + 1:]:
        if line.strip() and (len(line) - len(line.lstrip(" "))) <= 2:
            break
        if line.startswith("      - "):
            commands.append(line[len("      - "):].strip())
    return commands


class TheTaskRunnerDeclaresTheRound(unittest.TestCase):
    def setUp(self):
        with open(os.path.join(REPOSITORY, "Taskfile.yml"), encoding="utf-8") as handle:
            taskfile = handle.read()
        self.round = task_commands(taskfile, "check:round")
        self.verify = [
            command[len("task: "):] for command in task_commands(taskfile, "fw:verify")
        ]

    def round_arguments(self) -> list[str]:
        (command,) = self.round
        return command.split()

    def tasks_given(self, option: str) -> list[str]:
        arguments = self.round_arguments()
        return [arguments[i + 1] for i, word in enumerate(arguments) if word == option]

    def test_the_round_hands_over_every_host_task_the_complete_verification_runs(self):
        # SOL-VERIFY-ROUND-GATE-TARGETED.C1: The round gate runs the host tier in full and the emulation tier only for changes it exercises
        self.assertIn("tools/round_gate.py", " ".join(self.round_arguments()))
        self.assertEqual(
            [name for name in self.verify if name not in ("fw:emulate", "fw:sweep")],
            self.tasks_given("--host"),
        )
        self.assertEqual(["fw:emulate"], self.tasks_given("--emulation"))

    def test_the_round_never_runs_the_full_sweep(self):
        # SOL-VERIFY-ROUND-GATE-TARGETED.C1: The round gate runs the host tier in full and the emulation tier only for changes it exercises
        self.assertNotIn("fw:sweep", self.round_arguments())
        self.assertNotIn("mull_sweep", " ".join(self.round_arguments()))

    def test_the_complete_verification_keeps_its_declaration_of_every_gate(self):
        # SOL-VERIFY-ROUND-GATE-TARGETED.C1: The round gate runs the host tier in full and the emulation tier only for changes it exercises
        self.assertEqual(
            ["fw:build", "fw:check", "fw:test", "fw:run", "fw:emulate", "fw:sweep"], self.verify
        )


class TheRoundNeedsOnlyTheStandardLibrary(unittest.TestCase):
    """The host tier discovers these tests and the round runs the gate, so a
    third-party import in either fails the round on a machine that lacks it."""

    def test_the_gate_and_its_tests_import_only_the_standard_library(self):
        # SOL-VERIFY-ROUND-GATE-TARGETED.C1: The round gate runs the host tier in full and the emulation tier only for changes it exercises
        for path in (os.path.join(TOOLS, "round_gate.py"), os.path.abspath(__file__)):
            with open(path, encoding="utf-8") as handle:
                tree = ast.parse(handle.read())
            imported = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported.update(alias.name.split(".")[0] for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.level == 0:
                    imported.add(node.module.split(".")[0])
            foreign = sorted(
                name for name in imported
                if name not in sys.stdlib_module_names and name not in ("__future__", "round_gate")
            )
            with self.subTest(path=os.path.basename(path)):
                self.assertIn("subprocess", imported)
                self.assertEqual([], foreign)


if __name__ == "__main__":
    unittest.main()
