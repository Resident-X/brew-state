#!/usr/bin/env python3
"""The build round's gate decides what to run from what the branch changed.

Every case is driven against a synthetic repository: a handful of files laid out
where the firmware tree, the analysis records, the task runner's declaration
and a board design sit, a remote-tracking main pointed at the main they were
committed to, and a branch changed from that main.
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
import re
import shlex
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
BOARD = ["hw:verify", "hw:test:round"]
BOARD_READS = "hw:reads"
#: What the gate asks the task runner for before anything else when no changed path is
#: one the board tier reads by its name: which files the board designs read.
READS_ASKED = [BOARD_READS]
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
    "hardware/tools/board_check.py": "print('check')\n",
    "hardware/m/board/board.kicad_pro": "{}\n",
    "hardware/m/board/board.kicad_sch": "(kicad_sch)\n",
    "hardware/m/board/board.kicad_pcb": "(kicad_pcb)\n",
    "hardware/m/separation-basis.yaml": "standard: synthetic\n",
    "shared/lib/part.kicad_sym": "(kicad_symbol_lib)\n",
    "shared/lib/part.pretty/license.txt": "licence\n",
    "shared/parts/notes.txt": "a note\n",
    "firmware/tools/round_gate.py": "print('gate')\n",
    "firmware/tools/task_gate.py": "print('task')\n",
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

    #: What the board tooling lists a design as reading in the synthetic repository.
    READS = ["hardware/m/board/", "hardware/m/board/board.kicad_pro", "boards/x/",
             "shared/lib/part.pretty/", "shared/lib/part.kicad_sym"]

    def __init__(
        self,
        directory: str,
        failing: tuple[str, ...] = (),
        sweep_status: int = 0,
        sweep_account: dict | None = SKIPPED,
        reads: list[str] | None = None,
        missing_tool: dict[str, str] | None = None,
    ):
        self.directory = directory
        self.log = os.path.join(directory, "asked.log")
        failures = os.path.join(directory, "failing")
        with open(failures, "w", encoding="utf-8") as handle:
            handle.write("".join(f"{name}\n" for name in failing))
        listing = os.path.join(directory, "reads.txt")
        with open(listing, "w", encoding="utf-8") as handle:
            handle.write("".join(f"{entry}\n" for entry in (self.READS if reads is None else reads)))
        # A board task that cannot find a tool says so as the board tools do, on
        # standard error, and fails.
        said = "".join(
            f'if [ "$1" = "{name}" ]; then echo {shlex.quote("CANNOT RUN | " + message)} >&2; exit 3; fi\n'
            for name, message in (missing_tool or {}).items()
        )
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
                f"{said}"
                f'if grep -qx "$1" "{failures}"; then exit 3; fi\n'
                f'if [ "$1" = "{BOARD_READS}" ]; then cat "{listing}"; fi\n'
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
    for name in BOARD:
        arguments += ["--board", name]
    arguments += ["--board-reads", BOARD_READS, "--sweep", SWEEP]
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
        self.assertEqual(READS_ASKED + HOST + [SWEEP], asked)
        self.assertIn("ROUND GATE PASSED", result.stdout)
        self.assertIn("emulation tier was correctly SKIPPED", result.stdout)
        # The skip names the paths it was judged by, so the reader can check it.
        self.assertIn("docs/machine/notes.md", result.stdout.split("ROUND GATE PASSED")[1])

    def test_a_firmware_change_runs_the_host_tier_then_emulation_and_names_the_path(self):
        # SOL-VERIFY-ROUND-GATE-TARGETED.C1: The round gate runs the host tier in full and the emulation tier only for changes it exercises
        self.repository.change_and_commit("firmware/src/control/loop.c")
        result, asked = run_gate(self.repository)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertEqual(READS_ASKED + HOST + EMULATION + [SWEEP], asked)
        self.assertIn("emulation tier WILL RUN", result.stdout)
        self.assertIn("    firmware/src/control/loop.c", result.stdout)
        self.assertIn("both ran and passed", result.stdout)

    def test_a_host_failure_stops_the_gate_and_says_emulation_was_not_reached(self):
        # SOL-VERIFY-ROUND-GATE-TARGETED.C1: The round gate runs the host tier in full and the emulation tier only for changes it exercises
        self.repository.change_and_commit("firmware/src/control/loop.c")
        result, asked = run_gate(self.repository, failing=("fw:check",))
        self.assertNotEqual(0, result.returncode)
        self.assertEqual(READS_ASKED + ["fw:build", "fw:check"], asked)
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
        self.assertEqual(READS_ASKED + HOST, asked)
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
        self.assertEqual(READS_ASKED + HOST + EMULATION, asked)
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
        self.assertEqual(HOST + EMULATION + BOARD, asked)
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

    def test_the_diff_settings_and_environment_that_shape_hunks_are_pinned(self):
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

    def test_a_content_filter_the_repository_declares_is_applied(self):
        # SOL-SWEEP-CHANGED-PLANT-LINES-IN-ROUND.C1: The round gate sweeps the mutants drawn from the plant lines the branch changes
        # A clean filter is the repository's statement of what its content is,
        # not a way of showing a diff, so the measure is of the filtered
        # content: the filter drops the first line, and the change on line 5
        # is measured where the filtered file has it, on line 4.
        self.repository.write(PLANT, "one\ntwo\nthree\nfour\nFIVE\n")
        self.assertEqual({PLANT: [5]}, self.lines())
        self.assertEqual(
            {PLANT: [4]},
            self.measured_under({"filter.drop.clean": "sed 1d"}, f"/{PLANT} filter=drop\n"),
        )

    def test_this_repository_declares_no_content_filter_for_the_sweeps_sources(self):
        # SOL-SWEEP-CHANGED-PLANT-LINES-IN-ROUND.C1: The round gate sweeps the mutants drawn from the plant lines the branch changes
        # The measure applies a declared filter, so a filter on a C source or
        # header here would move the lines the round charges a branch with.
        # Every tracked one under the firmware is checked, which takes in all
        # the sweep can draw from.
        listed = subprocess.run(
            ["git", "-C", REPOSITORY, "ls-files", "-z", "--", "firmware/*.c", "firmware/*.h"],
            capture_output=True, text=True, check=True,
        )
        sources = [path for path in listed.stdout.split("\0") if path]
        self.assertTrue(sources)
        attributes = subprocess.run(
            ["git", "-C", REPOSITORY, "check-attr", "-z", "--stdin", "filter"],
            input="\0".join(sources) + "\0", capture_output=True, text=True, check=True,
        )
        fields = attributes.stdout.split("\0")
        declared = {
            fields[index]: fields[index + 2]
            for index in range(0, len(fields) - 2, 3)
            if fields[index + 2] != "unspecified"
        }
        self.assertEqual({}, declared)

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
        self.assertEqual(READS_ASKED + HOST + EMULATION + [SWEEP], asked)
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
        self.assertEqual(READS_ASKED + HOST + [SWEEP], asked)
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
        self.assertEqual(READS_ASKED + HOST + EMULATION + [SWEEP], asked)
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
        self.assertEqual(READS_ASKED + ["fw:build", "fw:check", "fw:test"], asked)
        self.assertIsNone(runner.handed_lines())
        self.assertIn("The mutation sweep was NOT REACHED", self.closing(result))

    def test_an_emulation_failure_leaves_the_sweep_not_reached(self):
        # SOL-SWEEP-CHANGED-PLANT-LINES-IN-ROUND.C1: The round gate sweeps the mutants drawn from the plant lines the branch changes
        self.repository.write(PLANT, "one\nTWO\nthree\nfour\nfive\n")
        result, asked, runner = self.gate(failing=("fw:emulate",))
        self.assertEqual(1, result.returncode)
        self.assertEqual(READS_ASKED + HOST + EMULATION, asked)
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
        self.assertEqual(HOST + EMULATION + BOARD, asked)
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
        self.assertIn("all ran and passed", closing)

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
        locked = "tools/locked.c"
        self.repository.write(locked, "a\n")
        self.lock(locked)
        result, asked, runner = self.gate(sweep_status=TASK_FAILED, sweep_account=account(
            "could-not-run", "could-not-look", lines_unknown=True,
            detail="the round could not tell which lines 1 population file(s) change. Make each "
            "of those files one git can read and diff, and run the round again.",
        ))
        self.assertEqual(1, result.returncode, result.stdout)
        self.assertEqual(READS_ASKED + HOST + EMULATION + [SWEEP], asked)
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
        self.assertEqual(READS_ASKED + HOST + [SWEEP], asked)
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


# --- The board tier ------------------------------------------------------------


#: Paths that reach a board by their name or place alone, each as the branch changes it.
RUNS_BY_NAME = (
    ("a design's layout", "hardware/m/board/board.kicad_pcb"),
    ("the board tooling", "hardware/tools/board_check.py"),
    ("a new file anywhere under the hardware tree", "hardware/notes/new.md"),
    ("a project file outside the hardware tree", "elsewhere/other.kicad_pro"),
    ("a schematic outside the hardware tree", "elsewhere/other.kicad_sch"),
    ("a rules file outside the hardware tree", "elsewhere/other.kicad_dru"),
    ("a symbol library outside the hardware tree", "shared/lib/part.kicad_sym"),
    ("a footprint outside the hardware tree", "elsewhere/lib.pretty/foot.kicad_mod"),
    ("a symbol library table", "elsewhere/sym-lib-table"),
    ("a footprint library table", "elsewhere/fp-lib-table"),
    ("a separation basis record outside the hardware tree", "elsewhere/separation-basis.yaml"),
    ("the round gate's own code", "firmware/tools/round_gate.py"),
    ("the code the round gate shares with the complete verification", "firmware/tools/task_gate.py"),
    ("the task runner's definition file", "Taskfile.yml"),
)

#: Paths a design reads that carry no KiCad name and sit outside the hardware tree: they reach a
#: board only because the board tooling lists them.
RUNS_BY_LISTING = (
    ("a file in a design's folder outside the hardware tree", "boards/x/layout-plan.md"),
    ("a file in a library folder a table names", "shared/lib/part.pretty/license.txt"),
)

#: Paths no board reads, which the round does not need KiCad for.
SKIPPED = (
    ("a document", "docs/machine/notes.md"),
    ("firmware source", "firmware/src/control/loop.c"),
    ("a firmware tool", "firmware/tools/check_example.py"),
    ("a requirement node", "specs/example.req.yaml"),
    ("a file beside a library but not in one a design reads", "shared/parts/notes.txt"),
    ("a tree whose name only starts like the hardware tree's", "hardware-notes/readme.md"),
    ("a file whose name only starts like the round gate's", "firmware/tools/round_gate.py.orig"),
    ("a file whose name only starts like the task definition file's", "Taskfile.yml.orig"),
    ("a KiCad backup, which KiCad does not read", "elsewhere/other.kicad_pcb-bak"),
)


class TheBoardTierIsJudgedOnChangedPathsAlone(unittest.TestCase):
    def setUp(self):
        self.repository = SyntheticRepository()
        self.addCleanup(self.repository.cleanup)

    def scope(self, listed=FakeTaskRunner.READS, problem: str = "") -> round_gate.BoardScope:
        """The board tier's decision for the branch as it stands, the listing being what the tooling prints."""
        return round_gate.board_scope(
            round_gate.changed(self.repository.root),
            lambda: (None if problem else listed, problem),
        )

    def restore(self) -> None:
        """Put the branch back to main, working tree and index included."""
        self.repository.git("reset", "-q", "--hard", "origin/main")
        self.repository.git("clean", "-fdq")

    def test_a_path_that_reaches_a_board_by_its_name_runs_the_tier_and_is_named(self):
        # SOL-HW-GATE-IN-ROUND-AND-NIGHTLY.C1: The build round runs the board check when the branch changes a board design, anything it reads, or the check
        for what, path in RUNS_BY_NAME:
            with self.subTest(change=what):
                self.repository.write(path, "changed\n")
                self.repository.git("add", "-A")
                chosen = self.scope()
                self.assertTrue(chosen.run, chosen.reason)
                self.assertEqual([path], chosen.judged)
                self.assertEqual([], chosen.untracked)
                self.restore()

    def test_a_committed_change_to_a_path_a_board_reads_runs_the_tier(self):
        # SOL-HW-GATE-IN-ROUND-AND-NIGHTLY.C1: The build round runs the board check when the branch changes a board design, anything it reads, or the check
        for what, path in RUNS_BY_NAME:
            if path not in BASELINE:
                continue
            with self.subTest(change=what):
                self.repository.change_and_commit(path)
                chosen = self.scope()
                self.assertTrue(chosen.run, chosen.reason)
                self.assertIn(path, chosen.judged)
                self.restore()

    def test_a_path_only_the_board_tooling_lists_as_read_runs_the_tier(self):
        # SOL-HW-GATE-IN-ROUND-AND-NIGHTLY.C1: The build round runs the board check when the branch changes a board design, anything it reads, or the check
        for what, path in RUNS_BY_LISTING:
            with self.subTest(change=what):
                self.repository.write(path, "changed\n")
                chosen = self.scope()
                self.assertTrue(chosen.run, chosen.reason)
                self.assertEqual([path], chosen.judged)
                self.assertIn("a board design reads", chosen.reason)
                # Without the listing the same path is not one the tier reads.
                self.assertFalse(self.scope(listed=[]).run)
                self.restore()

    def test_a_design_folder_listed_as_read_whole_covers_a_file_deleted_from_it(self):
        # SOL-HW-GATE-IN-ROUND-AND-NIGHTLY.C1: The build round runs the board check when the branch changes a board design, anything it reads, or the check
        self.repository.git("rm", "-q", "shared/lib/part.pretty/license.txt")
        chosen = self.scope(listed=["shared/lib/part.pretty/"])
        self.assertTrue(chosen.run, chosen.reason)
        self.assertEqual(["shared/lib/part.pretty/license.txt"], chosen.judged)

    def test_a_design_in_the_top_folder_makes_every_changed_path_one_a_board_reads(self):
        # SOL-HW-GATE-IN-ROUND-AND-NIGHTLY.C1: The build round runs the board check when the branch changes a board design, anything it reads, or the check
        self.repository.write("docs/machine/notes.md", "changed\n")
        self.assertTrue(self.scope(listed=["./"]).run)
        self.assertFalse(self.scope(listed=[]).run)

    def test_a_deleted_or_moved_file_counts_by_the_name_it_had(self):
        # SOL-HW-GATE-IN-ROUND-AND-NIGHTLY.C1: The build round runs the board check when the branch changes a board design, anything it reads, or the check
        self.repository.git("rm", "-q", "hardware/m/board/board.kicad_sch")
        self.assertTrue(self.scope().run)
        self.restore()
        self.repository.git("mv", "shared/lib/part.kicad_sym", "elsewhere-moved.txt")
        chosen = self.scope(listed=[])
        self.assertTrue(chosen.run, chosen.reason)
        self.assertIn("shared/lib/part.kicad_sym", chosen.judged)
        self.restore()
        os.makedirs(os.path.join(self.repository.root, "tools"))
        self.repository.git("mv", "hardware/tools/board_check.py", "tools/board_check.py")
        self.assertIn("hardware/tools/board_check.py", self.scope().judged)

    def test_a_branch_changing_none_of_these_skips_the_tier_and_names_what_it_judged(self):
        # SOL-HW-GATE-IN-ROUND-AND-NIGHTLY.C1: The build round runs the board check when the branch changes a board design, anything it reads, or the check
        for what, path in SKIPPED:
            with self.subTest(change=what):
                self.repository.write(path, "changed\n")
                chosen = self.scope()
                self.assertFalse(chosen.run, chosen.reason)
                self.assertEqual([path], chosen.judged)
                self.assertIn("none of the 1 changed path(s) is one the board tier reads", chosen.reason)
                self.assertIn(f"merge-base {self.repository.head()} with origin/main", chosen.reason)
                self.restore()

    def test_an_empty_change_skips_the_tier_without_listing_anything(self):
        # SOL-HW-GATE-IN-ROUND-AND-NIGHTLY.C1: The build round runs the board check when the branch changes a board design, anything it reads, or the check
        listed = []
        chosen = round_gate.board_scope(
            round_gate.changed(self.repository.root), lambda: listed.append("asked") or ([], "")
        )
        self.assertFalse(chosen.run)
        self.assertIn("the branch changes nothing", chosen.reason)
        self.assertEqual([], listed)

    def test_the_listing_is_not_asked_for_when_a_changed_path_already_runs_the_tier(self):
        # SOL-HW-GATE-IN-ROUND-AND-NIGHTLY.C1: The build round runs the board check when the branch changes a board design, anything it reads, or the check
        self.repository.write("hardware/m/board/board.kicad_pcb", "changed\n")
        asked = []
        chosen = round_gate.board_scope(
            round_gate.changed(self.repository.root), lambda: asked.append("asked") or ([], "")
        )
        self.assertTrue(chosen.run)
        self.assertEqual([], asked)

    def test_paths_that_cannot_be_told_run_the_tier_and_say_why(self):
        # SOL-HW-GATE-IN-ROUND-AND-NIGHTLY.C1: The build round runs the board check when the branch changes a board design, anything it reads, or the check
        repository = SyntheticRepository(with_tracking=False)
        self.addCleanup(repository.cleanup)
        repository.write("docs/machine/notes.md", "changed\n")
        chosen = round_gate.board_scope(round_gate.changed(repository.root), lambda: ([], ""))
        self.assertTrue(chosen.run)
        self.assertIn("could not tell what changed", chosen.reason)
        self.assertIn("there is no remote-tracking origin/main", chosen.reason)
        self.assertIn("Running the board tier rather than skipping it", chosen.reason)

    def test_changed_lines_that_cannot_be_told_do_not_run_the_tier_though_they_run_emulation(self):
        # SOL-HW-GATE-IN-ROUND-AND-NIGHTLY.C1: The build round runs the board check when the branch changes a board design, anything it reads, or the check
        # The paths are known and none is one a board reads; only the lines are not known.
        change = round_gate.Change(
            "head", "base", ["docs/machine/notes.md"], lines=None, lines_problem="the diff failed"
        )
        self.assertTrue(round_gate.scope(change).run_emulation)
        chosen = round_gate.board_scope(change, lambda: ([], ""))
        self.assertFalse(chosen.run, chosen.reason)

    def test_a_listing_that_cannot_be_read_runs_the_tier_and_says_so(self):
        # SOL-HW-GATE-IN-ROUND-AND-NIGHTLY.C1: The build round runs the board check when the branch changes a board design, anything it reads, or the check
        self.repository.write("docs/machine/notes.md", "changed\n")
        chosen = self.scope(problem="hw:reads exited with status 3")
        self.assertTrue(chosen.run)
        self.assertIn("could not list the files the board designs read", chosen.reason)
        self.assertIn("hw:reads exited with status 3", chosen.reason)
        self.assertIn("Running the board tier rather than skipping it", chosen.reason)

    def test_the_listing_is_read_as_one_entry_a_line_ignoring_blank_lines(self):
        # SOL-HW-GATE-IN-ROUND-AND-NIGHTLY.C1: The build round runs the board check when the branch changes a board design, anything it reads, or the check
        with tempfile.TemporaryDirectory() as directory:
            runner = FakeTaskRunner(directory, reads=["", "  boards/x/  ", "", "shared/lib/part.kicad_sym"])
            self.assertEqual(
                (["boards/x/", "shared/lib/part.kicad_sym"], ""),
                round_gate.list_reads(runner.path, BOARD_READS, self.repository.root),
            )
            failing = FakeTaskRunner(directory, failing=(BOARD_READS,))
            listed, problem = round_gate.list_reads(failing.path, BOARD_READS, self.repository.root)
            self.assertIsNone(listed)
            self.assertIn("hw:reads exited with status 3", problem)
        listed, problem = round_gate.list_reads(
            os.path.join(self.repository.root, "no-such-task-runner"), BOARD_READS, self.repository.root
        )
        self.assertIsNone(listed)
        self.assertIn("exited with status 127", problem)


class TheBoardTierRunsAfterTheOtherTiersAndBeforeTheSweep(unittest.TestCase):
    def setUp(self):
        self.repository = SyntheticRepository()
        self.addCleanup(self.repository.cleanup)
        self.scratch = tempfile.TemporaryDirectory()
        self.addCleanup(self.scratch.cleanup)

    def gate(self, failing=(), **runner_options):
        directory = tempfile.mkdtemp(dir=self.scratch.name)
        runner = FakeTaskRunner(directory, failing, **runner_options)
        result, asked = run_gate(self.repository, runner=runner)
        return result, asked, runner

    def closing(self, result) -> str:
        """Everything from the verdict line on, which must be the last thing printed."""
        verdicts = [line for line in result.stdout.splitlines() if line.startswith("ROUND GATE ")]
        self.assertEqual(1, len(verdicts), result.stdout)
        return result.stdout[result.stdout.index(verdicts[0]):]

    def test_a_board_change_runs_the_board_tasks_in_order_after_the_host_tier_and_before_the_sweep(self):
        # SOL-HW-GATE-IN-ROUND-AND-NIGHTLY.C1: The build round runs the board check when the branch changes a board design, anything it reads, or the check
        self.repository.change_and_commit("hardware/m/board/board.kicad_pcb")
        result, asked, _ = self.gate()
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertEqual(HOST + BOARD + [SWEEP], asked)
        closing = self.closing(result)
        self.assertIn(
            "ROUND GATE PASSED: the host tier (fw:build, fw:check, fw:test, fw:run) and the board "
            "tier (hw:verify, hw:test:round) both ran and passed",
            closing,
        )
        self.assertIn("The board tier ran because the branch changes 1 path(s) the board tier reads", closing)
        self.assertIn("    hardware/m/board/board.kicad_pcb", closing)
        self.assertIn(f"merge-base {self.repository.git('rev-parse', 'origin/main').strip()}", closing)
        self.assertIn("The emulation tier was correctly SKIPPED", closing)

    def test_a_change_both_tiers_read_runs_the_host_emulation_board_tiers_then_the_sweep(self):
        # SOL-HW-GATE-IN-ROUND-AND-NIGHTLY.C1: The build round runs the board check when the branch changes a board design, anything it reads, or the check
        self.repository.change_and_commit("firmware/src/control/loop.c")
        self.repository.change_and_commit("hardware/tools/board_check.py")
        result, asked, _ = self.gate()
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertEqual(HOST + EMULATION + BOARD + [SWEEP], asked)
        self.assertIn(
            "the host tier (fw:build, fw:check, fw:test, fw:run), the emulation tier (fw:emulate) "
            "and the board tier (hw:verify, hw:test:round) all ran and passed",
            self.closing(result),
        )

    def test_a_firmware_only_branch_skips_the_tier_says_why_and_needs_no_board_tool(self):
        # SOL-HW-GATE-IN-ROUND-AND-NIGHTLY.C1: The build round runs the board check when the branch changes a board design, anything it reads, or the check
        self.repository.change_and_commit("firmware/src/control/loop.c")
        # Every board tool is missing; a tier that is skipped never asks for one.
        result, asked, _ = self.gate(missing_tool={
            "hw:verify": "kicad-cli was not found", "hw:test:round": "resvg was not found",
        })
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertEqual(READS_ASKED + HOST + EMULATION + [SWEEP], asked)
        closing = self.closing(result)
        self.assertIn("ROUND GATE PASSED", closing)
        self.assertIn("The board tier was correctly SKIPPED, because none of the 1 changed path(s) "
                      "is one the board tier reads", closing)
        self.assertIn("    firmware/src/control/loop.c", closing.split("The board tier was correctly SKIPPED")[1])
        self.assertNotIn("CANNOT RUN", result.stdout + result.stderr)
        # The opening statement says so too, before any tier runs.
        self.assertIn("board tier WILL BE SKIPPED, because", result.stdout.split("running fw:build")[0])

    def test_a_firmware_branch_editing_the_task_definition_file_runs_the_tier(self):
        # SOL-HW-GATE-IN-ROUND-AND-NIGHTLY.C1: The build round runs the board check when the branch changes a board design, anything it reads, or the check
        self.repository.change_and_commit("firmware/src/control/loop.c")
        self.repository.change_and_commit("Taskfile.yml")
        result, asked, _ = self.gate()
        self.assertEqual(HOST + EMULATION + BOARD + [SWEEP], asked)
        self.assertIn("    Taskfile.yml", self.closing(result).split("The board tier ran because")[1])

    def test_a_change_to_the_round_gate_itself_runs_the_tier(self):
        # SOL-HW-GATE-IN-ROUND-AND-NIGHTLY.C1: The build round runs the board check when the branch changes a board design, anything it reads, or the check
        self.repository.change_and_commit("firmware/tools/round_gate.py")
        result, asked, _ = self.gate()
        self.assertEqual(HOST + EMULATION + BOARD + [SWEEP], asked)
        self.assertEqual(0, result.returncode, result.stdout)

    def test_a_listed_read_runs_the_tier_after_the_listing_is_asked_for(self):
        # SOL-HW-GATE-IN-ROUND-AND-NIGHTLY.C1: The build round runs the board check when the branch changes a board design, anything it reads, or the check
        self.repository.change_and_commit("boards/x/layout-plan.md")
        result, asked, _ = self.gate()
        self.assertEqual(READS_ASKED + HOST + BOARD + [SWEEP], asked)
        self.assertIn("board tier WILL RUN, because the branch changes 1 path(s) a board design reads",
                      result.stdout)

    def test_paths_that_cannot_be_told_run_every_tier_and_the_closing_lines_say_why(self):
        # SOL-HW-GATE-IN-ROUND-AND-NIGHTLY.C1: The build round runs the board check when the branch changes a board design, anything it reads, or the check
        repository = SyntheticRepository(with_tracking=False)
        self.addCleanup(repository.cleanup)
        repository.write("docs/machine/notes.md", "changed\n")
        result, asked = run_gate(repository, runner=FakeTaskRunner(self.scratch.name))
        # The sweep step then fails the round for the same cause, after the tiers have run.
        self.assertEqual(1, result.returncode)
        self.assertEqual(HOST + EMULATION + BOARD, asked)
        closing = self.closing(result)
        self.assertIn("The board tier ran because could not tell what changed", closing)
        self.assertIn("there is no remote-tracking origin/main", closing)

    def test_a_listing_that_fails_runs_the_tier_rather_than_skipping_it(self):
        # SOL-HW-GATE-IN-ROUND-AND-NIGHTLY.C1: The build round runs the board check when the branch changes a board design, anything it reads, or the check
        self.repository.change_and_commit("docs/machine/notes.md")
        result, asked, _ = self.gate(failing=(BOARD_READS,))
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertEqual(READS_ASKED + HOST + BOARD + [SWEEP], asked)
        self.assertIn("The board tier ran because could not list the files the board designs read",
                      self.closing(result))

    def test_a_failing_board_check_stops_the_round_and_the_sweep_is_not_reached(self):
        # SOL-HW-GATE-IN-ROUND-AND-NIGHTLY.C1: The build round runs the board check when the branch changes a board design, anything it reads, or the check
        self.repository.write("hardware/m/board/board.kicad_pcb", "changed\n")
        result, asked, runner = self.gate(failing=("hw:verify",))
        self.assertEqual(1, result.returncode)
        self.assertEqual(HOST + ["hw:verify"], asked)
        self.assertIsNone(runner.handed_lines())
        closing = self.closing(result)
        self.assertIn("ROUND GATE FAILED: the board tier failed at hw:verify (exit status 3)", closing)
        self.assertIn("This is a finding, not a failure to look", closing)
        self.assertIn("The host tier ran and passed (fw:build, fw:check, fw:test, fw:run).", closing)
        self.assertIn("The emulation tier was correctly SKIPPED", closing)
        self.assertIn("The board tier ran because", closing)
        self.assertIn("The mutation sweep was NOT REACHED", closing)
        self.assertNotIn("PASSED", result.stdout)

    def test_failing_tooling_tests_stop_the_round_after_the_check_passed(self):
        # SOL-HW-GATE-IN-ROUND-AND-NIGHTLY.C1: The build round runs the board check when the branch changes a board design, anything it reads, or the check
        self.repository.write("hardware/tools/board_check.py", "changed\n")
        result, asked, runner = self.gate(failing=("hw:test:round",))
        self.assertEqual(1, result.returncode)
        self.assertEqual(HOST + BOARD, asked)
        self.assertIsNone(runner.handed_lines())
        self.assertIn("the board tier failed at hw:test:round (exit status 3)", self.closing(result))
        self.assertIn("hw:verify passed", result.stdout)

    def test_a_missing_kicad_stops_the_round_naming_it_rather_than_skipping_the_tier(self):
        # SOL-HW-GATE-IN-ROUND-AND-NIGHTLY.C1: The build round runs the board check when the branch changes a board design, anything it reads, or the check
        self.repository.write("hardware/m/board/board.kicad_pcb", "changed\n")
        message = "kicad-cli was not found or could not be run at 'kicad-cli'. Install KiCad 10.0 or newer"
        result, asked, runner = self.gate(missing_tool={"hw:verify": message})
        self.assertEqual(1, result.returncode)
        self.assertEqual(HOST + ["hw:verify"], asked)
        self.assertIsNone(runner.handed_lines())
        closing = self.closing(result)
        self.assertIn("ROUND GATE FAILED: the board tier COULD NOT RUN at hw:verify (exit status 3), "
                      "because a tool it needs is missing or too old", closing)
        self.assertIn(f"    CANNOT RUN | {message}", closing)
        self.assertIn("Install the tool named above, then run the round again.", closing)
        self.assertIn("the tier neither passed nor found a problem", closing)
        self.assertNotIn("finding, not a failure to look", closing)
        self.assertNotIn("board tier was correctly SKIPPED", closing)
        self.assertNotIn("PASSED", result.stdout)
        # The task's own account reaches the reader as it was written.
        self.assertIn(f"CANNOT RUN | {message}", result.stderr)

    def test_a_missing_rasteriser_or_font_stops_the_round_after_the_check_passed(self):
        # SOL-HW-GATE-IN-ROUND-AND-NIGHTLY.C1: The build round runs the board check when the branch changes a board design, anything it reads, or the check
        self.repository.write("hardware/m/board/board.kicad_pcb", "changed\n")
        message = "resvg at 'resvg' found no font to draw the captions with. Install a monospaced font"
        result, asked, _ = self.gate(missing_tool={"hw:test:round": message})
        self.assertEqual(1, result.returncode)
        self.assertEqual(HOST + BOARD, asked)
        closing = self.closing(result)
        self.assertIn("the board tier COULD NOT RUN at hw:test:round", closing)
        self.assertIn(f"    CANNOT RUN | {message}", closing)
        self.assertIn("The mutation sweep was NOT REACHED", closing)

    def test_a_host_failure_says_the_board_tier_was_not_reached_and_what_it_would_have_done(self):
        # SOL-HW-GATE-IN-ROUND-AND-NIGHTLY.C1: The build round runs the board check when the branch changes a board design, anything it reads, or the check
        for change, would in (
            ("hardware/m/board/board.kicad_pcb", "it would have run, because"),
            ("docs/machine/notes.md", "it would have been skipped, because"),
        ):
            with self.subTest(change=change):
                self.repository.write(change, "changed\n")
                result, asked, _ = self.gate(failing=("fw:check",))
                self.assertEqual(1, result.returncode)
                self.assertNotIn("hw:verify", asked)
                closing = self.closing(result)
                self.assertIn("The board tier was NOT REACHED, so it neither passed nor failed", closing)
                self.assertIn(would, closing.split("The board tier was NOT REACHED")[1])
                self.assertIn(f"    {change}", closing.split("The board tier was NOT REACHED")[1])
                self.repository.git("clean", "-fdq")
                self.repository.git("checkout", "-q", "--", ".")

    def test_an_emulation_failure_says_the_board_tier_was_not_reached(self):
        # SOL-HW-GATE-IN-ROUND-AND-NIGHTLY.C1: The build round runs the board check when the branch changes a board design, anything it reads, or the check
        self.repository.write("firmware/src/control/loop.c", "changed\n")
        self.repository.write("hardware/tools/board_check.py", "changed\n")
        result, asked, _ = self.gate(failing=("fw:emulate",))
        self.assertEqual(HOST + EMULATION, asked)
        closing = self.closing(result)
        self.assertIn("the emulation tier failed at fw:emulate", closing)
        self.assertIn("The board tier was NOT REACHED, so it neither passed nor failed", closing)
        self.assertIn("it would have run, because", closing)

    def test_a_sweep_finding_still_names_the_board_tier_that_ran(self):
        # SOL-HW-GATE-IN-ROUND-AND-NIGHTLY.C1: The build round runs the board check when the branch changes a board design, anything it reads, or the check
        self.repository.write("hardware/tools/board_check.py", "changed\n")
        result, asked, _ = self.gate(
            sweep_status=1,
            sweep_account=account("ran", "found-a-problem", files=1, lines=2, detail="a survivor."),
        )
        self.assertEqual(1, result.returncode)
        self.assertEqual(HOST + BOARD + [SWEEP], asked)
        closing = self.closing(result)
        self.assertIn("FOUND A PROBLEM", closing)
        self.assertIn("the board tier (hw:verify, hw:test:round) both ran and passed", closing)


class AKiCadDesignGitDoesNotTrackFailsTheRound(unittest.TestCase):
    def setUp(self):
        self.repository = SyntheticRepository()
        self.addCleanup(self.repository.cleanup)
        self.scratch = tempfile.TemporaryDirectory()
        self.addCleanup(self.scratch.cleanup)

    def gate(self, failing=()):
        runner = FakeTaskRunner(tempfile.mkdtemp(dir=self.scratch.name), failing)
        result, asked = run_gate(self.repository, runner=runner)
        return result, asked, runner

    def test_each_kind_of_design_file_untracked_anywhere_fails_the_round_naming_it(self):
        # SOL-HW-GATE-IN-ROUND-AND-NIGHTLY.C1: The build round runs the board check when the branch changes a board design, anything it reads, or the check
        for path in ("hardware/m/new/new.kicad_pcb", "elsewhere/new.kicad_pro", "deep/er/new.kicad_sch"):
            with self.subTest(path=path):
                self.repository.write(path, "new\n")
                result, asked, runner = self.gate()
                self.assertEqual(1, result.returncode)
                # The host tier ran as it always does; no board task ran, and the sweep was not reached.
                self.assertEqual(HOST, asked)
                self.assertNotIn("hw:verify", asked)
                self.assertNotIn("hw:test:round", asked)
                self.assertIsNone(runner.handed_lines())
                self.assertIn("board tier WILL FAIL THE ROUND, because", result.stdout)
                closing = result.stdout[result.stdout.index("ROUND GATE FAILED"):]
                self.assertIn("ROUND GATE FAILED: the board tier did not run the board check, because "
                              "the working tree holds 1 KiCad design file(s) that git does not track", closing)
                self.assertIn(f"    {path}", closing)
                self.assertIn("Track each file named below with git add, then run the round again", closing)
                self.assertIn("The mutation sweep was NOT REACHED", closing)
                self.assertNotIn("PASSED", result.stdout)
                self.repository.git("clean", "-fdq")

    def test_every_untracked_design_file_is_named_and_the_others_are_not(self):
        # SOL-HW-GATE-IN-ROUND-AND-NIGHTLY.C1: The build round runs the board check when the branch changes a board design, anything it reads, or the check
        self.repository.write("hardware/m/new/new.kicad_pcb", "new\n")
        self.repository.write("hardware/m/new/new.kicad_pro", "new\n")
        self.repository.write("hardware/m/new/new.kicad_dru", "new\n")
        result, _, _ = self.gate()
        closing = result.stdout[result.stdout.index("ROUND GATE FAILED"):]
        self.assertIn("holds 2 KiCad design file(s)", closing)
        self.assertIn("    hardware/m/new/new.kicad_pcb", closing)
        self.assertIn("    hardware/m/new/new.kicad_pro", closing)
        self.assertNotIn("new.kicad_dru", closing)

    def test_the_failure_comes_after_the_host_and_emulation_tiers_and_names_what_passed(self):
        # SOL-HW-GATE-IN-ROUND-AND-NIGHTLY.C1: The build round runs the board check when the branch changes a board design, anything it reads, or the check
        self.repository.write("firmware/src/control/loop.c", "changed\n")
        self.repository.write("hardware/m/new/new.kicad_pcb", "new\n")
        result, asked, _ = self.gate()
        self.assertEqual(HOST + EMULATION, asked)
        closing = result.stdout[result.stdout.index("ROUND GATE FAILED"):]
        self.assertIn("The host tier (fw:build, fw:check, fw:test, fw:run) and the emulation tier "
                      "(fw:emulate) both ran and passed.", closing)

    def test_a_host_failure_comes_first_and_says_the_board_tier_would_have_failed_the_round(self):
        # SOL-HW-GATE-IN-ROUND-AND-NIGHTLY.C1: The build round runs the board check when the branch changes a board design, anything it reads, or the check
        self.repository.write("hardware/m/new/new.kicad_pcb", "new\n")
        result, asked, _ = self.gate(failing=("fw:build",))
        self.assertEqual(["fw:build"], asked)
        self.assertIn("it would have failed the round, because", result.stdout)
        self.assertIn("    hardware/m/new/new.kicad_pcb", result.stdout)

    def test_a_design_that_is_staged_is_tracked_and_the_tier_runs(self):
        # SOL-HW-GATE-IN-ROUND-AND-NIGHTLY.C1: The build round runs the board check when the branch changes a board design, anything it reads, or the check
        for kind in ("pro", "sch", "pcb"):
            self.repository.write(f"hardware/m/new/new.kicad_{kind}", "new\n")
        self.repository.git("add", "-A")
        result, asked, _ = self.gate()
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertEqual(HOST + BOARD + [SWEEP], asked)

    def test_an_untracked_kicad_file_that_is_not_a_design_runs_the_tier_without_failing_the_round(self):
        # SOL-HW-GATE-IN-ROUND-AND-NIGHTLY.C1: The build round runs the board check when the branch changes a board design, anything it reads, or the check
        self.repository.write("hardware/m/board/board.kicad_prl", "{}\n")
        result, asked, _ = self.gate()
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertEqual(HOST + BOARD + [SWEEP], asked)

    def test_an_untracked_design_file_the_repository_ignores_is_not_a_change(self):
        # SOL-HW-GATE-IN-ROUND-AND-NIGHTLY.C1: The build round runs the board check when the branch changes a board design, anything it reads, or the check
        self.repository.write(".gitignore", "firmware/.pio/\nscratch/\n")
        self.repository.commit("ignore scratch")
        self.repository.track("HEAD")
        self.repository.write("scratch/new.kicad_pcb", "new\n")
        result, asked, _ = self.gate()
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertNotIn("hw:verify", asked)


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


def declared_gates(taskfile: str) -> list[str]:
    """The gates the complete verification declares, in order: what it hands its driver."""
    (command,) = task_commands(taskfile, "fw:verify")
    words = command.split()
    return [words[i + 1] for i, word in enumerate(words) if word == "--gate"]


class TheTaskRunnerDeclaresTheRound(unittest.TestCase):
    def setUp(self):
        with open(os.path.join(REPOSITORY, "Taskfile.yml"), encoding="utf-8") as handle:
            taskfile = handle.read()
        self.round = task_commands(taskfile, "check:round")
        self.verify = declared_gates(taskfile)

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
            [name for name in self.verify if name not in ("fw:emulate", "fw:sweep") + tuple(BOARD)],
            self.tasks_given("--host"),
        )
        self.assertEqual(["fw:emulate"], self.tasks_given("--emulation"))

    def test_the_round_hands_over_the_board_gates_the_complete_verification_declares(self):
        # SOL-HW-GATE-IN-ROUND-AND-NIGHTLY.C1: The build round runs the board check when the branch changes a board design, anything it reads, or the check
        # The same two tasks, in the same order, and the tooling tests are the
        # ones without the seeded-fault proof, which neither hands over.
        self.assertEqual(BOARD, self.tasks_given("--board"))
        self.assertEqual([name for name in self.verify if name.startswith("hw:")], self.tasks_given("--board"))
        self.assertEqual([BOARD_READS], self.tasks_given("--board-reads"))
        self.assertNotIn("hw:prove", self.round_arguments() + self.verify)
        self.assertNotIn("hw:test", self.round_arguments() + self.verify)
        self.assertEqual(self.verify.index("fw:emulate") + 1, self.verify.index(BOARD[0]))
        self.assertEqual(self.verify.index(SWEEP) - 1, self.verify.index(BOARD[-1]))
        self.assertNotIn(BOARD_READS, self.verify)

    def test_the_task_descriptions_say_when_the_board_tier_runs(self):
        # SOL-HW-GATE-IN-ROUND-AND-NIGHTLY.C3: The project instructions and the hardware notes say when the board check runs
        with open(os.path.join(REPOSITORY, "Taskfile.yml"), encoding="utf-8") as handle:
            lines = handle.read().splitlines()

        def description(name: str) -> str:
            start = lines.index(f"  {name}:")
            return next(line for line in lines[start + 1:] if line.strip().startswith("desc:"))

        round_description = description("check:round")
        for words in (
            "board tier (hw:verify", "hw:test:round", "tracked KiCad file anywhere", "hardware tree",
            "this task definition file", "judged on the changed paths alone",
            "a KiCad design file git does not track fails the round naming it",
            "a missing or too-old tool stops the round naming it rather than skipping the tier",
        ):
            self.assertIn(words, round_description)
        verify_description = description("fw:verify")
        for words in ("every board design", "without those that run the seeded-fault proof", "stays on demand"):
            self.assertIn(words, verify_description)
        self.assertIn("on demand", description("hw:prove"))
        self.assertIn("hw:test:round", description("hw:test"))

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
            ["fw:build", "fw:check", "fw:test", "fw:run", "fw:emulate", "hw:verify", "hw:test:round", "fw:sweep"],
            self.verify,
        )


class TheDocumentsSayWhenTheBoardCheckRuns(unittest.TestCase):
    """The project instructions, the hardware notes and the firmware documentation each
    state the board check's cadences, so a reader of any of them is not left to find the
    gate's code to learn them."""

    #: What each document must say, as patterns over its text with whitespace collapsed.
    EVERY_DOCUMENT = (
        ("the check runs in the round", r"board (tier|check)"),
        ("for a board design", r"board design"),
        ("for what a design reads", r"(anything|any file|files?) a board design reads"),
        ("for the board tooling", r"board (check's )?tooling"),
        ("for the round gate's own code", r"round gate's own code"),
        ("for the task definition file", r"Taskfile\.yml"),
        ("judged on changed paths", r"changed paths alone"),
        ("nightly", r"nightly"),
        ("the proof on demand", r"seeded-fault proof[^.]*(on demand|stays on demand)|on demand[^.]*seeded-fault proof"),
    )

    DOCUMENTS = (
        "CLAUDE.md",
        "hardware/README.md",
        "firmware/README.md",
        "firmware/emulation/README.md",
    )

    def read(self, path: str) -> str:
        with open(os.path.join(REPOSITORY, path), encoding="utf-8") as handle:
            return " ".join(handle.read().split())

    def test_each_document_states_when_the_board_check_runs_and_that_its_proof_is_on_demand(self):
        # SOL-HW-GATE-IN-ROUND-AND-NIGHTLY.C3: The project instructions and the hardware notes say when the board check runs
        for path in self.DOCUMENTS:
            text = self.read(path)
            for what, pattern in self.EVERY_DOCUMENT:
                with self.subTest(document=path, says=what):
                    self.assertRegex(text, pattern)

    def test_the_project_instructions_name_the_gates_the_tier_runs_and_the_nightly_declares(self):
        # SOL-HW-GATE-IN-ROUND-AND-NIGHTLY.C3: The project instructions and the hardware notes say when the board check runs
        text = self.read("CLAUDE.md")
        gates = text[text.index("**Gates.**"): text.index("**Generated records pin their inputs.**")]
        round_part, nightly_part = gates.split("**Nightly.**")
        for name in ("hw:verify", "hw:test:round", "BOARD_READS", "task hw:reads"):
            self.assertIn(name, round_part)
        for name in ("hw:verify", "hw:test:round", "task hw:prove", "on demand"):
            self.assertIn(name, nightly_part)
        for words in (
            "anything under `hardware/`", "a tracked KiCad file anywhere", "or `Taskfile.yml`",
            "firmware-only branch that leaves `Taskfile.yml` alone", "fails the round, naming it",
            "stops the round naming the tool rather than skipping the tier",
            "when the changed paths cannot be told", "not on unknown changed lines alone",
        ):
            self.assertIn(words, round_part)

    def test_the_hardware_notes_say_the_rasteriser_and_font_are_needed_by_the_tests_the_round_runs(self):
        # SOL-HW-GATE-IN-ROUND-AND-NIGHTLY.C3: The project instructions and the hardware notes say when the board check runs
        text = self.read("hardware/README.md")
        needs = text[text.index("## What you need"): text.index("## The commands")]
        for tool in ("resvg", "A monospaced font"):
            row = next(row for row in needs.split("| ") if row.startswith(tool))
            self.assertIn("for the layout review views and for the tooling tests the build round runs", row)
        self.assertNotIn("for the layout review views only", needs)
        self.assertNotIn("The pre-order check does not need it", needs)
        section = text[text.index("## When the board check runs"): text.index("## The locked-copper check")]
        for words in (
            "tooling tests", "the rasteriser", "monospaced font", "`task hw:test:round`", "`task hw:verify`",
            "`BOARD_TESTS_WITHOUT_PROOF`", "`Proved`", "test_board_check_kicad.py", "`task hw:reads`",
            "first nightly run demonstrates",
        ):
            self.assertIn(words, section)

    def test_the_hardware_notes_name_the_variable_and_base_class_the_split_is_made_with(self):
        # SOL-HW-GATE-IN-ROUND-AND-NIGHTLY.C3: The project instructions and the hardware notes say when the board check runs
        # What the notes say names what the code has, so a rename in one is seen in the other.
        notes = self.read("hardware/README.md")
        with open(os.path.join(REPOSITORY, "hardware", "tools", "tests", "test_board_check_kicad.py"), encoding="utf-8") as handle:
            tests = handle.read()
        variable = re.search(r'(?m)^WITHOUT_PROOF = "([A-Z_]+)"', tests).group(1)
        self.assertIn(f"`{variable}`", notes)
        self.assertRegex(tests, r"(?m)^class Proved\(unittest\.TestCase\):")
        self.assertIn("derives from `Proved`", notes)


class TheRoundNeedsOnlyTheStandardLibrary(unittest.TestCase):
    """The host tier discovers these tests and the round runs the gate, so a
    third-party import in either fails the round on a machine that lacks it."""

    def test_the_gate_and_its_tests_import_only_the_standard_library(self):
        # SOL-VERIFY-ROUND-GATE-TARGETED.C1: The round gate runs the host tier in full and the emulation tier only for changes it exercises
        for path in (
            os.path.join(TOOLS, "round_gate.py"), os.path.join(TOOLS, "task_gate.py"),
            os.path.abspath(__file__),
        ):
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
                if name not in sys.stdlib_module_names and name not in ("__future__", "round_gate", "task_gate")
            )
            with self.subTest(path=os.path.basename(path)):
                self.assertIn("subprocess", imported)
                self.assertEqual([], foreign)


if __name__ == "__main__":
    unittest.main()
