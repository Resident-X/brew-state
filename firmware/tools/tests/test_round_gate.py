#!/usr/bin/env python3
"""The build round's gate decides what to run from what the branch changed.

Every case is driven against a synthetic repository: a handful of files laid out
where the firmware tree, the analysis records and the task runner's declaration
sit, a remote-tracking main pointed at the main they were committed to, and a
branch changed from that main.
The task runner is a shell script that records which tasks it was asked for and
fails the ones it is told to, so the gate's ordering, stopping and verdict are
observed without a build behind them. Asked for the sweep, it keeps the changed
lines the gate handed over and writes back whatever account of the sweep it is
told to, so what the gate says about each outcome is observed without the
mutation toolchain; the sweep's own side of that exchange is driven in the
sweep's tests.
"""

from __future__ import annotations

import ast
import json
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
SWEEP = "fw:sweep"

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
    "firmware/src/plant/common/plant_step.c": "one\ntwo\nthree\nfour\nfive\n",
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
    """Stands in for the task runner: logs each task it is asked for, fails some.

    Asked for the sweep, it keeps a copy of the changed lines it was handed and
    of every argument, writes the account it was given where the gate asked for
    one, and exits with the status it was given -- by default an account of a
    sweep that found no changed line in its population.
    """

    SKIPPED = {"state": "skipped", "outcome": "skipped", "files": 0, "lines": 0,
               "detail": "none of the changed path(s) is a source the sweep draws mutants from."}

    def __init__(
        self,
        directory: str,
        failing: tuple[str, ...] = (),
        sweep_status: int = 0,
        sweep_account: dict | None = SKIPPED,
    ):
        self.directory = directory
        self.log = os.path.join(directory, "asked.log")
        failures = os.path.join(directory, "failing")
        with open(failures, "w", encoding="utf-8") as handle:
            handle.write("".join(f"{name}\n" for name in failing))
        account = os.path.join(directory, "account.json")
        if sweep_account is not None:
            with open(account, "w", encoding="utf-8") as handle:
                json.dump(sweep_account, handle)
        self.handed = os.path.join(directory, "handed.json")
        self.arguments = os.path.join(directory, "sweep-arguments")
        self.marker = os.path.join(directory, "sweep-marker")
        self.path = os.path.join(directory, "task")
        with open(self.path, "w", encoding="utf-8") as handle:
            handle.write(
                "#!/bin/sh\n"
                f'echo "$1" >> "{self.log}"\n'
                f'if [ "$1" = "{SWEEP}" ]; then\n'
                f'  printf "%s" "${round_gate.ROUND_ACCOUNT_VARIABLE}" > "{self.marker}"\n'
                f'  printf "%s\\n" "$@" > "{self.arguments}"\n'
                '  shift\n'
                '  lines=""; result=""\n'
                '  while [ $# -gt 0 ]; do\n'
                '    case "$1" in\n'
                '      --changed-lines) lines="$2"; shift ;;\n'
                '      --changed-lines-result) result="$2"; shift ;;\n'
                '    esac\n'
                '    shift\n'
                '  done\n'
                f'  [ -n "$lines" ] && cp "$lines" "{self.handed}"\n'
                f'  [ -n "$result" ] && [ -f "{account}" ] && cp "{account}" "$result"\n'
                '  echo "the sweep reporting on its own"\n'
                f'  exit {sweep_status}\n'
                'fi\n'
                f'if grep -qx "$1" "{failures}"; then exit 3; fi\n'
                "exit 0\n"
            )
        os.chmod(self.path, os.stat(self.path).st_mode | stat.S_IEXEC)

    def asked(self) -> list[str]:
        if not os.path.exists(self.log):
            return []
        with open(self.log, encoding="utf-8") as handle:
            return handle.read().split()

    def handed_lines(self) -> dict | None:
        """The changed lines the gate handed the sweep, or None if it handed none."""
        if not os.path.exists(self.handed):
            return None
        with open(self.handed, encoding="utf-8") as handle:
            return json.load(handle)

    def sweep_arguments(self) -> list[str]:
        with open(self.arguments, encoding="utf-8") as handle:
            return handle.read().splitlines()

    def sweep_marker(self) -> str:
        """What the sweep found in the environment naming the round's account."""
        with open(self.marker, encoding="utf-8") as handle:
            return handle.read()


def run_gate(
    repository: SyntheticRepository,
    failing: tuple[str, ...] = (),
    task: str | None = None,
    runner: FakeTaskRunner | None = None,
):
    if runner is None:
        runner_directory = tempfile.TemporaryDirectory()
        runner = FakeTaskRunner(runner_directory.name, failing)
    else:
        runner_directory = None
    arguments = [
        sys.executable, os.path.join(TOOLS, "round_gate.py"), "--task", task or runner.path
    ]
    for name in HOST:
        arguments += ["--host", name]
    for name in EMULATION:
        arguments += ["--emulation", name]
    arguments += ["--sweep", SWEEP]
    result = subprocess.run(
        arguments, cwd=repository.root, capture_output=True, text=True, check=False,
        env=GIT_ENVIRONMENT,
    )
    asked = runner.asked()
    if runner_directory is not None:
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
        self.assertEqual(HOST + [SWEEP], asked)
        self.assertIn("ROUND GATE PASSED", result.stdout)
        self.assertIn("emulation tier was correctly SKIPPED", result.stdout)
        # The skip names the paths it was judged by, so the reader can check it.
        self.assertIn("docs/machine/notes.md", result.stdout.split("ROUND GATE PASSED")[1])

    def test_a_firmware_change_runs_the_host_tier_then_emulation_and_names_the_path(self):
        # SOL-VERIFY-ROUND-GATE-TARGETED.C1: The round gate runs the host tier in full and the emulation tier only for changes it exercises
        self.repository.change_and_commit("firmware/src/control/loop.c")
        result, asked = run_gate(self.repository)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertEqual(HOST + EMULATION + [SWEEP], asked)
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
        # Emulation runs; the round then fails at the sweep step, which cannot
        # clear an unmeasured change as touching no plant line.
        self.assertEqual(1, result.returncode, result.stdout + result.stderr)
        self.assertEqual(HOST + EMULATION, asked)
        self.assertIn("could not tell what changed", result.stdout)
        self.assertIn("there is no remote-tracking origin/main", result.stdout)
        self.assertIn(f"HEAD {repository.head()}", result.stdout)


# --- The base is guarded against unusual git state, not against tampering -----


class TheBaseIsTheRemoteTrackingMain(unittest.TestCase):
    """The selection is a cost measure: it guards against git state that is
    unusually configured, not against a producer rewriting the tree."""

    def setUp(self):
        self.repository = SyntheticRepository()
        self.addCleanup(self.repository.cleanup)
        self.repository.change_and_commit("firmware/src/control/loop.c")

    def test_a_stale_remote_tracking_main_charges_mains_later_change_to_the_branch(self):
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


# --- The lines the branch changes ------------------------------------------

PLANT = "firmware/src/plant/common/plant_step.c"


class TheChangedLinesAreMeasuredTheWayThePathsAre(unittest.TestCase):
    """The lines come from the same merge-base and working tree as the paths,
    so the sweep is handed exactly the change the tiers were chosen by."""

    def setUp(self):
        self.repository = SyntheticRepository()
        self.addCleanup(self.repository.cleanup)

    def lines(self) -> dict:
        change = round_gate.changed(self.repository.root)
        self.assertIsNotNone(change.lines, change.lines_problem)
        return change.lines

    def test_a_modified_line_is_a_changed_line_and_its_neighbours_are_not(self):
        # SOL-SWEEP-CHANGED-PLANT-LINES-IN-ROUND.C1: The round gate sweeps the mutants drawn from the plant lines the branch changes
        self.repository.write(PLANT, "one\ntwo\nTHREE\nfour\nfive\n")
        self.assertEqual({PLANT: [3]}, self.lines())

    def test_separate_hunks_each_contribute_their_new_side_lines(self):
        # SOL-SWEEP-CHANGED-PLANT-LINES-IN-ROUND.C1: The round gate sweeps the mutants drawn from the plant lines the branch changes
        self.repository.write(PLANT, "ONE\ntwo\nthree\nfour\nFIVE\nsix\n")
        self.assertEqual({PLANT: [1, 5, 6]}, self.lines())

    def test_inserted_lines_are_changed_lines_on_the_new_side(self):
        # SOL-SWEEP-CHANGED-PLANT-LINES-IN-ROUND.C1: The round gate sweeps the mutants drawn from the plant lines the branch changes
        self.repository.write(PLANT, "one\ntwo\nnew a\nnew b\nthree\nfour\nfive\n")
        self.assertEqual({PLANT: [3, 4]}, self.lines())

    def test_a_hunk_that_only_deletes_still_counts_the_file_as_changed(self):
        # SOL-SWEEP-CHANGED-PLANT-LINES-IN-ROUND.C1: The round gate sweeps the mutants drawn from the plant lines the branch changes
        self.repository.write(PLANT, "one\nthree\nfour\nfive\n")
        self.assertEqual({PLANT: []}, self.lines())

    def test_a_deleted_file_counts_as_changed_with_no_line_left(self):
        # SOL-SWEEP-CHANGED-PLANT-LINES-IN-ROUND.C1: The round gate sweeps the mutants drawn from the plant lines the branch changes
        self.repository.git("rm", "-q", PLANT)
        self.repository.commit("delete")
        self.assertEqual({PLANT: []}, self.lines())

    def test_every_line_of_a_new_file_not_yet_committed_is_a_changed_line(self):
        # SOL-SWEEP-CHANGED-PLANT-LINES-IN-ROUND.C1: The round gate sweeps the mutants drawn from the plant lines the branch changes
        self.repository.write("firmware/src/plant/common/added.c", "a\nb\nc\n")
        self.repository.write("firmware/src/plant/common/unterminated.c", "a\nb")
        self.repository.write("firmware/src/plant/common/empty.c", "")
        self.assertEqual(
            {
                "firmware/src/plant/common/added.c": [1, 2, 3],
                "firmware/src/plant/common/unterminated.c": [1, 2],
                "firmware/src/plant/common/empty.c": [],
            },
            self.lines(),
        )

    def test_committed_and_uncommitted_lines_are_both_counted(self):
        # SOL-SWEEP-CHANGED-PLANT-LINES-IN-ROUND.C1: The round gate sweeps the mutants drawn from the plant lines the branch changes
        self.repository.write(PLANT, "ONE\ntwo\nthree\nfour\nfive\n")
        self.repository.commit("first line")
        self.repository.write(PLANT, "ONE\ntwo\nthree\nFOUR\nfive\n")
        self.assertEqual({PLANT: [1, 4]}, self.lines())

    def test_lines_main_changed_after_the_branch_left_it_are_not_charged_to_the_branch(self):
        # SOL-SWEEP-CHANGED-PLANT-LINES-IN-ROUND.C1: The round gate sweeps the mutants drawn from the plant lines the branch changes
        self.repository.git("checkout", "-q", "main")
        self.repository.write(PLANT, "ONE\ntwo\nthree\nfour\nfive\n")
        self.repository.commit("main's own change")
        self.repository.track("main")
        self.repository.git("checkout", "-q", "feature")
        self.repository.write(PLANT, "one\ntwo\nthree\nfour\nFIVE\n")
        self.assertEqual({PLANT: [5]}, self.lines())

    def test_every_changed_path_is_handed_over_with_its_lines(self):
        # SOL-SWEEP-CHANGED-PLANT-LINES-IN-ROUND.C1: The round gate sweeps the mutants drawn from the plant lines the branch changes
        # Which of them are in the sweep's population is the sweep's to say.
        self.repository.change_and_commit("docs/machine/notes.md")
        self.repository.write(PLANT, "one\nTWO\nthree\nfour\nfive\n")
        self.assertEqual({"docs/machine/notes.md": [2], PLANT: [2]}, self.lines())

    def test_a_path_with_pattern_characters_is_read_as_the_path_it_is(self):
        # SOL-SWEEP-CHANGED-PLANT-LINES-IN-ROUND.C1: The round gate sweeps the mutants drawn from the plant lines the branch changes
        odd = "firmware/src/plant/common/odd name [1]*.c"
        self.repository.write(odd, "a\nb\n")
        self.repository.commit("odd")
        self.repository.track("HEAD")
        self.repository.write(odd, "a\nB\n")
        self.assertEqual({odd: [2]}, self.lines())

    def test_content_in_no_particular_encoding_is_measured(self):
        # SOL-SWEEP-CHANGED-PLANT-LINES-IN-ROUND.C1: The round gate sweeps the mutants drawn from the plant lines the branch changes
        with open(os.path.join(self.repository.root, PLANT), "wb") as handle:
            handle.write(b"one\n\xff\xfe two\nthree\nfour\nfive\n")
        self.assertEqual({PLANT: [2]}, self.lines())

    def test_the_lines_are_relative_to_the_top_level_when_started_below_it(self):
        # SOL-SWEEP-CHANGED-PLANT-LINES-IN-ROUND.C1: The round gate sweeps the mutants drawn from the plant lines the branch changes
        self.repository.write(PLANT, "one\ntwo\nthree\nfour\nFIVE\n")
        change = round_gate.changed(os.path.join(self.repository.root, "docs"))
        self.assertEqual(self.repository.root, os.path.realpath(change.root))
        self.assertEqual({PLANT: [5]}, change.lines)

    def measured_under(self, settings: dict[str, str], attributes: str = "",
                       environment: dict[str, str] | None = None) -> dict:
        """The lines measured with the repository configured and the environment set as given."""
        for key, value in settings.items():
            self.repository.git("config", key, value)
        if attributes:
            self.repository.write(".git/info/attributes", attributes)
        with mock.patch.dict(os.environ, environment or {}):
            return self.lines()

    def test_no_setting_of_the_repository_or_environment_reshapes_the_hunks(self):
        # SOL-SWEEP-CHANGED-PLANT-LINES-IN-ROUND.C1: The round gate sweeps the mutants drawn from the plant lines the branch changes
        # Lines 2 and 5 change and lines 3 and 4 between them do not. Each
        # setting below, left to itself, joins the two hunks, widens them with
        # context, hides them or shifts them, and would charge the branch with
        # lines it never changed or drop the ones it did.
        cases = {
            "diff.interHunkContext": ({"diff.interHunkContext": "5"}, "", None),
            "GIT_DIFF_OPTS": ({}, "", {"GIT_DIFF_OPTS": "-u3"}),
            "a -diff attribute": ({}, "*.c -diff\n", None),
            "a textconv driver": (
                {"diff.shift.textconv": "sed 1d"}, "*.c diff=shift\n", None
            ),
            "color.ui": ({"color.ui": "always"}, "", None),
            "diff.external": ({"diff.external": "true"}, "", None),
            "GIT_EXTERNAL_DIFF": ({}, "", {"GIT_EXTERNAL_DIFF": "true"}),
            "diff.relative": ({"diff.relative": "true"}, "", None),
            "diff.context": ({"diff.context": "4"}, "", None),
        }
        for name, (settings, attributes, environment) in cases.items():
            with self.subTest(setting=name):
                repository = SyntheticRepository()
                self.addCleanup(repository.cleanup)
                self.repository = repository
                repository.write(PLANT, "one\nTWO\nthree\nfour\nFIVE\n")
                self.assertEqual({PLANT: [2, 5]}, self.measured_under(settings, attributes, environment))

    def test_the_diff_algorithm_and_hunk_placement_are_gits_defaults_whatever_is_configured(self):
        # SOL-SWEEP-CHANGED-PLANT-LINES-IN-ROUND.C1: The round gate sweeps the mutants drawn from the plant lines the branch changes
        # Each pair is an edit two diffs of the same change attribute to
        # different lines: the configured one would charge the branch with
        # lines git's default does not.
        cases = {
            "diff.algorithm": (
                {"diff.algorithm": "histogram"},
                "b\n{\nb\n{\nb\n", "{\nb\n{\nb\na\nb\n{\nb\n", [1, 5, 6],
            ),
            "diff.indentHeuristic": (
                {"diff.indentHeuristic": "false"},
                "}\n}\n  b\n\nf {\n  a\n\n", "}\n}\n}\n  b\n\nf {\n  a\n\n", [2],
            ),
        }
        for name, (settings, old, new, expected) in cases.items():
            with self.subTest(setting=name):
                repository = SyntheticRepository()
                self.addCleanup(repository.cleanup)
                self.repository = repository
                repository.write(PLANT, old)
                repository.commit("old")
                repository.track("HEAD")
                repository.write(PLANT, new)
                self.assertEqual({PLANT: expected}, self.lines())
                self.assertEqual({PLANT: expected}, self.measured_under(settings))

    def test_no_remote_tracking_main_leaves_the_lines_unknown_and_says_why(self):
        # SOL-SWEEP-CHANGED-PLANT-LINES-IN-ROUND.C1: The round gate sweeps the mutants drawn from the plant lines the branch changes
        repository = SyntheticRepository(with_tracking=False)
        self.addCleanup(repository.cleanup)
        change = round_gate.changed(repository.root)
        self.assertIsNone(change.lines)
        self.assertIn("no remote-tracking origin/main", change.lines_unknown_because)

    def test_lines_that_cannot_be_told_run_emulation_whatever_the_paths(self):
        # SOL-SWEEP-CHANGED-PLANT-LINES-IN-ROUND.C1: The round gate sweeps the mutants drawn from the plant lines the branch changes
        change = round_gate.Change(
            "head", "base", ["docs/machine/notes.md"], lines=None, lines_problem="unreadable"
        )
        chosen = round_gate.scope(change)
        self.assertTrue(chosen.run_emulation)
        self.assertIn("could not tell what changed at HEAD head: unreadable", chosen.reason)

    def lock(self, path: str) -> None:
        """Leave a file in the working tree that nothing can read."""
        if os.geteuid() == 0:
            self.skipTest("a superuser reads a file whatever its mode")
        full = os.path.join(self.repository.root, path)
        os.chmod(full, 0)
        self.addCleanup(os.chmod, full, 0o644)

    def test_an_unreadable_new_file_is_set_apart_while_every_other_line_is_told(self):
        # SOL-SWEEP-CHANGED-PLANT-LINES-IN-ROUND.C1: The round gate sweeps the mutants drawn from the plant lines the branch changes
        locked = "firmware/src/plant/common/locked.c"
        self.repository.write(locked, "a\n")
        self.lock(locked)
        self.repository.write(PLANT, "one\nTWO\nthree\nfour\nfive\n")
        change = round_gate.changed(self.repository.root)
        self.assertEqual(sorted([locked, PLANT]), change.paths)
        self.assertEqual({PLANT: [2]}, change.lines)
        self.assertEqual([locked], list(change.unreadable))
        self.assertIn("could not be read", change.unreadable[locked])
        self.assertEqual("", change.lines_unknown_because)

    def test_an_unreadable_source_runs_emulation_and_says_whose_lines_are_untold(self):
        # SOL-SWEEP-CHANGED-PLANT-LINES-IN-ROUND.C1: The round gate sweeps the mutants drawn from the plant lines the branch changes
        # Whether the source is in the sweep's population is the sweep's to
        # say; until it does, a line of the population may be untold, and the
        # gate runs emulation as for any change it cannot tell.
        change = round_gate.Change(
            "head", "base", ["hardware/tools/locked.c"], lines={},
            unreadable={"hardware/tools/locked.c": "permission denied"},
        )
        chosen = round_gate.scope(change)
        self.assertTrue(chosen.run_emulation)
        self.assertIn("could not tell which lines 1 changed source(s) change", chosen.reason)
        self.assertEqual(["hardware/tools/locked.c: permission denied"], chosen.judged)

    def test_an_unreadable_document_leaves_emulation_chosen_by_its_path(self):
        # SOL-SWEEP-CHANGED-PLANT-LINES-IN-ROUND.C1: The round gate sweeps the mutants drawn from the plant lines the branch changes
        # The sweep draws from no document, so a document going unread leaves no
        # line of its population untold.
        locked = "docs/machine/locked.md"
        self.repository.write(locked, "a\n")
        self.lock(locked)
        chosen = self.repository.scope()
        self.assertFalse(chosen.run_emulation, chosen.reason)

    def test_the_gate_and_the_sweep_agree_on_what_kind_of_file_is_swept(self):
        # SOL-SWEEP-CHANGED-PLANT-LINES-IN-ROUND.C1: The round gate sweeps the mutants drawn from the plant lines the branch changes
        self.assertTrue(round_gate.could_be_swept("firmware/src/plant/common/plant_step.c"))
        self.assertTrue(round_gate.could_be_swept("firmware/src/plant/common/plant_step.h"))
        self.assertFalse(round_gate.could_be_swept("firmware/src/plant/common/notes.md"))
        self.assertFalse(round_gate.could_be_swept("firmware/src/plant/common/plant_step.cpp"))


def account(state: str, outcome: str, **fields) -> dict:
    return {"state": state, "outcome": outcome, **fields}


#: What the task runner this project uses exits with when a task's command
#: fails, whatever status the command itself exited with.
TASK_FAILED = 201


class TheRoundSweepsTheChangedLinesAfterTheTiers(unittest.TestCase):
    def setUp(self):
        self.repository = SyntheticRepository()
        self.addCleanup(self.repository.cleanup)
        self.scratch = tempfile.TemporaryDirectory()
        self.addCleanup(self.scratch.cleanup)

    def gate(self, failing=(), sweep_status=0, sweep_account=FakeTaskRunner.SKIPPED):
        runner = FakeTaskRunner(self.scratch.name, failing, sweep_status, sweep_account)
        result, asked = run_gate(self.repository, runner=runner)
        return result, asked, runner

    def closing(self, result) -> str:
        """Everything from the verdict line on, which must be the last thing printed."""
        verdicts = [line for line in result.stdout.splitlines() if line.startswith("ROUND GATE ")]
        self.assertEqual(1, len(verdicts), result.stdout)
        return result.stdout[result.stdout.index(verdicts[0]):]

    def test_the_sweep_runs_after_host_and_emulation_and_is_handed_the_changed_lines(self):
        # SOL-SWEEP-CHANGED-PLANT-LINES-IN-ROUND.C1: The round gate sweeps the mutants drawn from the plant lines the branch changes
        self.repository.write(PLANT, "one\nTWO\nthree\nfour\nfive\n")
        base = self.repository.head()
        result, asked, runner = self.gate()
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertEqual(HOST + EMULATION + [SWEEP], asked)
        handed = runner.handed_lines()
        self.assertEqual({PLANT: [2]}, handed["files"])
        self.assertEqual(self.repository.root, os.path.realpath(handed["root"]))
        self.assertEqual(base, handed["base"])
        # The sweep is always handed the restriction; the round never asks for
        # it unrestricted.
        arguments = runner.sweep_arguments()
        self.assertEqual(SWEEP, arguments[0])
        self.assertIn("--changed-lines", arguments)
        self.assertIn("--changed-lines-result", arguments)

    def test_the_sweep_runs_after_the_host_tier_when_emulation_is_skipped(self):
        # SOL-SWEEP-CHANGED-PLANT-LINES-IN-ROUND.C1: The round gate sweeps the mutants drawn from the plant lines the branch changes
        self.repository.change_and_commit("docs/machine/notes.md")
        result, asked, runner = self.gate()
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertEqual(HOST + [SWEEP], asked)
        self.assertEqual({"docs/machine/notes.md": [2]}, runner.handed_lines()["files"])

    def test_a_branch_changing_no_population_line_passes_and_says_the_sweep_was_skipped(self):
        # SOL-SWEEP-CHANGED-PLANT-LINES-IN-ROUND.C1: The round gate sweeps the mutants drawn from the plant lines the branch changes
        self.repository.change_and_commit("docs/machine/notes.md")
        result, _, _ = self.gate()
        closing = self.closing(result)
        self.assertIn("ROUND GATE PASSED", closing)
        self.assertIn(
            "the mutation sweep was correctly SKIPPED, because the branch changes no line in the "
            "sweep's population",
            closing,
        )
        self.assertNotIn("sweep of the", closing.splitlines()[0])

    def test_a_sweep_that_ran_and_passed_is_stated_with_the_lines_it_covered(self):
        # SOL-SWEEP-CHANGED-PLANT-LINES-IN-ROUND.C1: The round gate sweeps the mutants drawn from the plant lines the branch changes
        self.repository.write(PLANT, "one\nTWO\nTHREE\nFOUR\nfive\n")
        result, _, _ = self.gate(sweep_account=account(
            "ran", "passed", files=1, lines=3, mutants=4,
            detail="4 mutant(s) lie on the changed lines.",
        ))
        self.assertEqual(0, result.returncode, result.stdout)
        verdict = self.closing(result).splitlines()[0]
        self.assertTrue(verdict.startswith("ROUND GATE PASSED"), verdict)
        self.assertIn("both ran and passed", verdict)
        self.assertIn(
            "the mutation sweep of the 3 changed plant line(s) in 1 file(s) ran and passed", verdict
        )

    def test_a_seeded_surviving_mutant_reported_by_the_sweep_fails_the_round_as_a_finding(self):
        # SOL-SWEEP-CHANGED-PLANT-LINES-IN-ROUND.C1: The round gate sweeps the mutants drawn from the plant lines the branch changes
        # The task runner reports the sweep's failure as its own status, not the
        # sweep's; the account the sweep wrote says it found a problem.
        self.repository.write(PLANT, "one\nTWO\nthree\nfour\nfive\n")
        result, asked, _ = self.gate(sweep_status=TASK_FAILED, sweep_account=account(
            "ran", "found-a-problem", files=1, lines=1, mutants=1,
            detail="1 unreviewed survivor(s).",
        ))
        self.assertEqual(1, result.returncode, result.stdout)
        self.assertEqual(HOST + EMULATION + [SWEEP], asked)
        closing = self.closing(result)
        self.assertIn(
            "ROUND GATE FAILED: the mutation sweep of the 1 changed plant line(s) in 1 file(s) "
            "FOUND A PROBLEM",
            closing,
        )
        self.assertIn("This is a finding, not a failure to look", closing)
        self.assertNotIn("COULD NOT", closing)
        self.assertNotIn("PASSED", result.stdout)
        # The verdict comes after the sweep's own output, never before it.
        self.assertLess(
            result.stdout.index("the sweep reporting on its own"),
            result.stdout.index("ROUND GATE FAILED"),
        )

    def test_a_sweep_that_could_not_look_fails_the_round_and_is_not_called_a_finding(self):
        # SOL-SWEEP-CHANGED-PLANT-LINES-IN-ROUND.C1: The round gate sweeps the mutants drawn from the plant lines the branch changes
        self.repository.write(PLANT, "one\nTWO\nthree\nfour\nfive\n")
        result, _, _ = self.gate(sweep_status=TASK_FAILED, sweep_account=account(
            "could-not-run", "could-not-look", files=1, lines=1,
            detail="the triage record cannot be read.",
        ))
        self.assertEqual(1, result.returncode, result.stdout)
        closing = self.closing(result)
        self.assertIn(
            f"ROUND GATE FAILED: the mutation sweep COULD NOT LOOK (exit status {TASK_FAILED})",
            closing,
        )
        self.assertIn("neither passed nor found a problem", closing)
        self.assertIn("the triage record cannot be read.", closing)
        self.assertNotIn("FOUND A PROBLEM", closing)

    def test_a_missing_toolchain_fails_the_round_and_says_it_is_missing(self):
        # SOL-SWEEP-CHANGED-PLANT-LINES-IN-ROUND.C1: The round gate sweeps the mutants drawn from the plant lines the branch changes
        self.repository.write(PLANT, "one\nTWO\nthree\nfour\nfive\n")
        result, _, _ = self.gate(sweep_status=TASK_FAILED, sweep_account=account(
            "could-not-run", "could-not-look", files=1, lines=1, toolchain_missing=True,
            detail="no clang-19 was found.",
        ))
        self.assertEqual(1, result.returncode, result.stdout)
        closing = self.closing(result)
        self.assertIn("ROUND GATE FAILED", closing)
        self.assertIn("the mutation toolchain the sweep needs is MISSING on this host", closing)
        self.assertIn("no clang-19 was found.", closing)
        self.assertNotIn("FOUND A PROBLEM", closing)

    def test_a_sweep_leaving_no_account_fails_the_round_rather_than_passing(self):
        # SOL-SWEEP-CHANGED-PLANT-LINES-IN-ROUND.C1: The round gate sweeps the mutants drawn from the plant lines the branch changes
        self.repository.write(PLANT, "one\nTWO\nthree\nfour\nfive\n")
        result, _, _ = self.gate(sweep_status=0, sweep_account=None)
        self.assertEqual(1, result.returncode, result.stdout)
        self.assertIn(
            "ROUND GATE FAILED: the mutation sweep COULD NOT RUN: it exited with status 0 and left "
            "no account",
            self.closing(result),
        )
        self.assertNotIn("PASSED", result.stdout)

    def test_an_account_the_exit_status_contradicts_fails_the_round(self):
        # SOL-SWEEP-CHANGED-PLANT-LINES-IN-ROUND.C1: The round gate sweeps the mutants drawn from the plant lines the branch changes
        self.repository.write(PLANT, "one\nTWO\nthree\nfour\nfive\n")
        for status, outcome in ((0, "found-a-problem"), (0, "could-not-look"), (1, "passed"),
                                (TASK_FAILED, "skipped")):
            with self.subTest(status=status, outcome=outcome):
                result, _, _ = self.gate(
                    sweep_status=status, sweep_account=account("ran", outcome, files=1, lines=1)
                )
                self.assertEqual(1, result.returncode, result.stdout)
                self.assertIn("left no account the round can read", self.closing(result))
                self.assertNotIn("PASSED", result.stdout)

    def test_a_problem_found_before_any_mutant_is_drawn_is_still_a_finding(self):
        # SOL-SWEEP-CHANGED-PLANT-LINES-IN-ROUND.C1: The round gate sweeps the mutants drawn from the plant lines the branch changes
        self.repository.write(PLANT, "one\nTWO\nthree\nfour\nfive\n")
        result, _, _ = self.gate(
            sweep_status=TASK_FAILED, sweep_account=account("could-not-run", "found-a-problem")
        )
        self.assertEqual(1, result.returncode, result.stdout)
        closing = self.closing(result)
        self.assertIn("FOUND A PROBLEM before drawing any mutant", closing)
        self.assertNotIn("COULD NOT", closing)

    def test_a_host_failure_leaves_the_sweep_not_reached(self):
        # SOL-SWEEP-CHANGED-PLANT-LINES-IN-ROUND.C1: The round gate sweeps the mutants drawn from the plant lines the branch changes
        self.repository.write(PLANT, "one\nTWO\nthree\nfour\nfive\n")
        result, asked, runner = self.gate(failing=("fw:test",))
        self.assertEqual(1, result.returncode)
        self.assertEqual(["fw:build", "fw:check", "fw:test"], asked)
        self.assertIsNone(runner.handed_lines())
        self.assertIn("The mutation sweep was NOT REACHED", self.closing(result))

    def test_an_emulation_failure_leaves_the_sweep_not_reached(self):
        # SOL-SWEEP-CHANGED-PLANT-LINES-IN-ROUND.C1: The round gate sweeps the mutants drawn from the plant lines the branch changes
        self.repository.write(PLANT, "one\nTWO\nthree\nfour\nfive\n")
        result, asked, runner = self.gate(failing=("fw:emulate",))
        self.assertEqual(1, result.returncode)
        self.assertEqual(HOST + EMULATION, asked)
        self.assertIsNone(runner.handed_lines())
        closing = self.closing(result)
        self.assertIn("the emulation tier failed at fw:emulate", closing)
        self.assertIn("The mutation sweep was NOT REACHED", closing)

    def test_an_unmeasurable_change_runs_both_tiers_then_fails_naming_the_cause_and_remedy(self):
        # SOL-SWEEP-CHANGED-PLANT-LINES-IN-ROUND.C1: The round gate sweeps the mutants drawn from the plant lines the branch changes
        repository = SyntheticRepository(with_tracking=False)
        self.addCleanup(repository.cleanup)
        repository.write(PLANT, "one\nTWO\nthree\nfour\nfive\n")
        runner = FakeTaskRunner(self.scratch.name)
        result, asked = run_gate(repository, runner=runner)
        self.assertEqual(1, result.returncode, result.stdout)
        # Host and emulation run as they do for any change the gate cannot
        # measure; the sweep runs neither restricted nor in full.
        self.assertEqual(HOST + EMULATION, asked)
        self.assertIsNone(runner.handed_lines())
        closing = self.closing(result)
        self.assertIn(
            "ROUND GATE FAILED: the mutation sweep COULD NOT RUN, because the round could not "
            "tell which plant lines the branch changes",
            closing,
        )
        self.assertIn("there is no remote-tracking origin/main", closing)
        self.assertIn("git fetch origin main", closing)
        self.assertIn("neither a restricted nor the full sweep", closing)
        self.assertIn("both ran and passed", closing)

    def lock(self, path: str) -> None:
        if os.geteuid() == 0:
            self.skipTest("a superuser reads a file whatever its mode")
        full = os.path.join(self.repository.root, path)
        os.chmod(full, 0)
        self.addCleanup(os.chmod, full, 0o644)

    def test_lines_of_a_source_that_cannot_be_read_run_both_tiers_then_hand_it_to_the_sweep(self):
        # SOL-SWEEP-CHANGED-PLANT-LINES-IN-ROUND.C1: The round gate sweeps the mutants drawn from the plant lines the branch changes
        # The paths are known and touch nothing emulation reads, but a source
        # whose lines are untold may be in the population, so emulation runs as
        # it does for any change the gate cannot tell; the sweep, whose
        # population it is, is handed the source as unread and fails the round.
        locked = "hardware/tools/locked.c"
        self.repository.write(locked, "a\n")
        self.lock(locked)
        result, asked, runner = self.gate(sweep_status=TASK_FAILED, sweep_account=account(
            "could-not-run", "could-not-look", lines_unknown=True,
            detail="the round could not tell which lines 1 population file(s) change. Make each "
            "of those files one git can read and diff, and run the round again.",
        ))
        self.assertEqual(1, result.returncode, result.stdout)
        self.assertEqual(HOST + EMULATION + [SWEEP], asked)
        handed = runner.handed_lines()
        self.assertEqual({}, handed["files"])
        self.assertEqual([locked], list(handed["unreadable"]))
        self.assertIn("emulation tier WILL RUN, because could not tell which lines", result.stdout)
        closing = self.closing(result)
        self.assertIn(
            "ROUND GATE FAILED: the mutation sweep COULD NOT RUN (exit status "
            f"{TASK_FAILED}), because the round could not tell which plant lines the branch "
            "changes",
            closing,
        )
        self.assertIn("run the round again", closing)
        self.assertIn("both ran and passed", closing)
        self.assertNotIn("FOUND A PROBLEM", closing)

    def test_a_document_that_cannot_be_read_neither_runs_emulation_nor_fails_the_round(self):
        # SOL-SWEEP-CHANGED-PLANT-LINES-IN-ROUND.C1: The round gate sweeps the mutants drawn from the plant lines the branch changes
        # No sweep draws from a document, so its lines going unread leaves no
        # line of the population untold.
        locked = "docs/machine/locked.md"
        self.repository.write(locked, "a\n")
        self.lock(locked)
        result, asked, runner = self.gate()
        self.assertEqual(0, result.returncode, result.stdout)
        self.assertEqual(HOST + [SWEEP], asked)
        self.assertEqual([locked], list(runner.handed_lines()["unreadable"]))
        self.assertIn("ROUND GATE PASSED", self.closing(result))

    def test_the_sweep_is_told_through_the_environment_that_the_round_asked_for_it(self):
        # SOL-SWEEP-CHANGED-PLANT-LINES-IN-ROUND.C1: The round gate sweeps the mutants drawn from the plant lines the branch changes
        self.repository.write(PLANT, "one\nTWO\nthree\nfour\nfive\n")
        result, _, runner = self.gate()
        self.assertEqual(0, result.returncode, result.stdout)
        arguments = runner.sweep_arguments()
        result_path = arguments[arguments.index("--changed-lines-result") + 1]
        self.assertEqual(result_path, runner.sweep_marker())

    def test_a_task_dropping_the_restriction_fails_the_round_without_sweeping(self):
        # SOL-SWEEP-CHANGED-PLANT-LINES-IN-ROUND.C1: The round gate sweeps the mutants drawn from the plant lines the branch changes
        # The sweep's task is stood in for by one that runs the real sweep
        # without forwarding the arguments the gate hands it. The sweep refuses
        # before deriving anything, and the round reads that refusal as a sweep
        # that could not look.
        self.repository.write(PLANT, "one\nTWO\nthree\nfour\nfive\n")
        dropping = os.path.join(self.scratch.name, "dropping-task")
        missing = os.path.join(self.scratch.name, "no-project-here")
        with open(dropping, "w", encoding="utf-8") as handle:
            handle.write(
                "#!/bin/sh\n"
                f'if [ "$1" = "{SWEEP}" ]; then\n'
                f'  exec "{sys.executable}" "{os.path.join(TOOLS, "mull_sweep.py")}" '
                f'--project "{missing}"\n'
                "fi\n"
                "exit 0\n"
            )
        os.chmod(dropping, os.stat(dropping).st_mode | stat.S_IEXEC)
        result, _ = run_gate(self.repository, task=dropping, runner=FakeTaskRunner(self.scratch.name))
        self.assertEqual(1, result.returncode, result.stdout + result.stderr)
        self.assertFalse(os.path.exists(missing))
        closing = self.closing(result)
        self.assertIn("ROUND GATE FAILED: the mutation sweep COULD NOT LOOK", closing)
        self.assertIn("did not forward --changed-lines", closing)
        self.assertNotIn("FOUND A PROBLEM", closing)
        self.assertIn("did not forward --changed-lines", result.stderr)


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

    def test_the_round_hands_over_the_sweep_only_as_its_sweep_step(self):
        # SOL-SWEEP-CHANGED-PLANT-LINES-IN-ROUND.C1: The round gate sweeps the mutants drawn from the plant lines the branch changes
        # The sweep reaches the round only as the gate's sweep step, which
        # always restricts it, and never as a tier run as it stands.
        self.assertEqual([SWEEP], self.tasks_given("--sweep"))
        self.assertNotIn(SWEEP, self.tasks_given("--host") + self.tasks_given("--emulation"))
        self.assertNotIn("mull_sweep", " ".join(self.round_arguments()))

    def test_the_task_descriptions_say_the_round_runs_the_changed_lines_sweep_and_never_the_full(self):
        # SOL-SWEEP-CHANGED-PLANT-LINES-IN-ROUND.C1: The round gate sweeps the mutants drawn from the plant lines the branch changes
        with open(os.path.join(REPOSITORY, "Taskfile.yml"), encoding="utf-8") as handle:
            lines = handle.read().splitlines()

        def description(name: str) -> str:
            start = lines.index(f"  {name}:")
            return next(line for line in lines[start + 1:] if line.strip().startswith("desc:"))

        round_description = description("check:round")
        self.assertIn("changed-lines mutation sweep", round_description)
        self.assertIn("never the full one", round_description)
        sweep_description = description("fw:sweep")
        self.assertIn("restricted to the lines the branch changes", sweep_description)
        self.assertNotIn("never part of a build round", sweep_description)

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
