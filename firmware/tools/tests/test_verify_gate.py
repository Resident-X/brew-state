#!/usr/bin/env python3
"""The complete verification runs every declared gate and names every failure.

The task runner is a shell script that records which tasks it was asked for and
fails the ones it is told to, so the order, the running on after a failure, the
leaving out of a gate and the closing account are observed without a build
behind them. The declaration itself, and the hosted workflow that runs it
nightly, are read from the repository as text, so these need nothing beyond the
standard library.
"""

from __future__ import annotations

import ast
import os
import re
import shlex
import stat
import subprocess
import sys
import tempfile
import unittest

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPOSITORY = os.path.dirname(os.path.dirname(TOOLS))
FIRMWARE = os.path.dirname(TOOLS)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)

import build_environments  # noqa: E402
from test_round_gate import declared_gates, task_commands  # noqa: E402
import workflow_declarations  # noqa: E402

GATES = ["fw:build", "fw:check", "fw:test", "fw:run", "fw:emulate", "fw:sweep"]


class FakeTaskRunner:
    """Logs each task it is asked for and exits with the status it is told to for each."""

    def __init__(self, directory: str, statuses: dict[str, int] | None = None):
        self.log = os.path.join(directory, "asked.log")
        self.path = os.path.join(directory, "task")
        cases = "".join(
            f'  "{name}") exit {status} ;;\n' for name, status in (statuses or {}).items()
        )
        with open(self.path, "w", encoding="utf-8") as handle:
            handle.write(
                "#!/bin/sh\n"
                f'echo "$1" >> "{self.log}"\n'
                'case "$1" in\n'
                f"{cases}"
                "esac\n"
                "exit 0\n"
            )
        os.chmod(self.path, os.stat(self.path).st_mode | stat.S_IEXEC)

    def asked(self) -> list[str]:
        if not os.path.exists(self.log):
            return []
        with open(self.log, encoding="utf-8") as handle:
            return handle.read().split()


def run_verification(
    statuses: dict[str, int] | None = None,
    leave_out: tuple[str, ...] = (),
    gates: list[str] = GATES,
    task: str | None = None,
):
    with tempfile.TemporaryDirectory() as directory:
        runner = FakeTaskRunner(directory, statuses)
        arguments = [sys.executable, os.path.join(TOOLS, "verify_gate.py"),
                     "--task", task or runner.path, "--repo", directory]
        for name in gates:
            arguments += ["--gate", name]
        arguments.append("--")
        for name in leave_out:
            arguments += ["--leave-out", name]
        result = subprocess.run(arguments, capture_output=True, text=True, check=False)
        return result, runner.asked()


def closing(result: subprocess.CompletedProcess) -> str:
    """The account after the last gate's own output."""
    return result.stdout.rstrip("\n").split("\n\n")[-1]


class EveryGateRunsToCompletion(unittest.TestCase):
    def test_every_gate_passing_runs_each_in_order_and_reads_as_the_complete_verification(self):
        # SOL-VERIFY-NIGHTLY-FULL-ON-MAIN.C1: The daily verification runs every gate to completion and reports every failure
        result, asked = run_verification()
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertEqual(GATES, asked)
        account = closing(result)
        self.assertIn("COMPLETE VERIFICATION PASSED", account)
        self.assertIn("Gates that ran: " + ", ".join(f"{g} (passed)" for g in GATES), account)
        self.assertIn("Gates left out: none.", account)

    def test_an_early_failure_does_not_stop_the_gates_after_it(self):
        # SOL-VERIFY-NIGHTLY-FULL-ON-MAIN.C1: The daily verification runs every gate to completion and reports every failure
        result, asked = run_verification({"fw:build": 1})
        self.assertNotEqual(0, result.returncode)
        self.assertEqual(GATES, asked)
        account = closing(result)
        self.assertIn("VERIFICATION FAILED: 1 of the 6 gate(s) that ran failed: fw:build "
                      "(exit status 1).", account)
        self.assertIn("fw:build (FAILED), fw:check (passed)", account)
        self.assertNotIn("PASSED", account)

    def test_every_failure_is_named_with_its_own_status(self):
        # SOL-VERIFY-NIGHTLY-FULL-ON-MAIN.C1: The daily verification runs every gate to completion and reports every failure
        result, asked = run_verification({"fw:check": 3, "fw:emulate": 2, "fw:sweep": 1})
        self.assertNotEqual(0, result.returncode)
        self.assertEqual(GATES, asked)
        account = closing(result)
        self.assertIn(
            "3 of the 6 gate(s) that ran failed: fw:check (exit status 3), "
            "fw:emulate (exit status 2), fw:sweep (exit status 1).",
            account,
        )

    def test_only_the_last_gate_failing_still_fails_the_run(self):
        # SOL-VERIFY-NIGHTLY-FULL-ON-MAIN.C1: The daily verification runs every gate to completion and reports every failure
        result, asked = run_verification({"fw:sweep": 1})
        self.assertNotEqual(0, result.returncode)
        self.assertEqual(GATES, asked)
        self.assertIn("failed: fw:sweep (exit status 1).", closing(result))

    def test_a_task_runner_that_cannot_start_fails_every_gate_and_names_each(self):
        # SOL-VERIFY-NIGHTLY-FULL-ON-MAIN.C1: The daily verification runs every gate to completion and reports every failure
        with tempfile.TemporaryDirectory() as directory:
            missing = os.path.join(directory, "no-such-task-runner")
            result, _ = run_verification(task=missing)
        self.assertNotEqual(0, result.returncode)
        for name in GATES:
            self.assertIn(f"{name} could not be started", result.stdout)
            self.assertIn(f"{name} (exit status 127)", closing(result))
        self.assertNotIn("PASSED", closing(result))


class AGateCanBeLeftOutByName(unittest.TestCase):
    def test_a_gate_left_out_is_not_run_and_the_pass_says_it_is_not_complete(self):
        # SOL-VERIFY-NIGHTLY-FULL-ON-MAIN.C1: The daily verification runs every gate to completion and reports every failure
        result, asked = run_verification(leave_out=("fw:sweep",))
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertEqual(GATES[:-1], asked)
        account = closing(result)
        self.assertIn("VERIFICATION PASSED WITH GATES LEFT OUT", account)
        self.assertIn("NOT the complete verification passing", account)
        self.assertNotIn("COMPLETE VERIFICATION PASSED", result.stdout)
        self.assertIn("Gates left out: fw:sweep.", account)
        self.assertNotIn("fw:sweep (", account)

    def test_a_failure_with_a_gate_left_out_names_both(self):
        # SOL-VERIFY-NIGHTLY-FULL-ON-MAIN.C1: The daily verification runs every gate to completion and reports every failure
        result, asked = run_verification({"fw:test": 1}, leave_out=("fw:emulate", "fw:sweep"))
        self.assertNotEqual(0, result.returncode)
        self.assertEqual(["fw:build", "fw:check", "fw:test", "fw:run"], asked)
        account = closing(result)
        self.assertIn("1 of the 4 gate(s) that ran failed: fw:test (exit status 1).", account)
        self.assertIn("Gates left out: fw:emulate, fw:sweep.", account)

    def test_a_name_that_is_not_a_declared_gate_is_refused_before_anything_runs(self):
        # SOL-VERIFY-NIGHTLY-FULL-ON-MAIN.C1: The daily verification runs every gate to completion and reports every failure
        result, asked = run_verification(leave_out=("fw:swep",))
        self.assertEqual(2, result.returncode)
        self.assertEqual([], asked)
        self.assertIn("--leave-out names no declared gate: fw:swep", result.stderr)
        self.assertIn("fw:sweep", result.stderr)
        self.assertNotIn("PASSED", result.stdout)

    def test_one_unknown_name_among_known_ones_is_still_refused(self):
        # SOL-VERIFY-NIGHTLY-FULL-ON-MAIN.C1: The daily verification runs every gate to completion and reports every failure
        result, asked = run_verification(leave_out=("fw:sweep", "hw:verify"))
        self.assertEqual(2, result.returncode)
        self.assertEqual([], asked)
        self.assertIn("no declared gate: hw:verify ", result.stderr)

    def test_leaving_out_every_gate_is_refused(self):
        # SOL-VERIFY-NIGHTLY-FULL-ON-MAIN.C1: The daily verification runs every gate to completion and reports every failure
        result, asked = run_verification(leave_out=tuple(GATES))
        self.assertEqual(2, result.returncode)
        self.assertEqual([], asked)
        self.assertIn("leaves out every declared gate", result.stderr)

    def test_a_gate_declared_twice_is_refused(self):
        # SOL-VERIFY-NIGHTLY-FULL-ON-MAIN.C1: The daily verification runs every gate to completion and reports every failure
        result, asked = run_verification(gates=GATES + ["fw:test"])
        self.assertEqual(2, result.returncode)
        self.assertEqual([], asked)
        self.assertIn("declared more than once: fw:test", result.stderr)

    def test_a_gate_left_out_twice_is_refused(self):
        # SOL-VERIFY-NIGHTLY-FULL-ON-MAIN.C1: The daily verification runs every gate to completion and reports every failure
        result, asked = run_verification(leave_out=("fw:sweep", "fw:emulate", "fw:sweep"))
        self.assertEqual(2, result.returncode)
        self.assertEqual([], asked)
        self.assertIn("--leave-out names a gate more than once: fw:sweep", result.stderr)


class OnlyAGateLeftOutMayBePassedOn(unittest.TestCase):
    """The task hands its own command line on to the driver after the
    declaration. Those words are a different source from the declaration and
    are read apart from it: the task runner and the gates come from the
    Taskfile, and what is passed on can only leave a declared gate out. These
    run the Taskfile's own command, rendered as the task runner renders it, so
    a declaration that let passed-on words reach the driver's other options is
    caught here and not only a driver that did."""

    def run_declared(self, forwarded: list[str], statuses: dict[str, int] | None = None):
        (command,) = task_commands(read("Taskfile.yml"), "fw:verify")
        with tempfile.TemporaryDirectory() as directory:
            declared = FakeTaskRunner(directory, statuses)
            substitute = os.path.join(directory, "substitute")
            substituted = os.path.join(directory, "substitute.log")
            with open(substitute, "w", encoding="utf-8") as handle:
                handle.write(f'#!/bin/sh\necho "$1" >> "{substituted}"\nexit 0\n')
            os.chmod(substitute, os.stat(substitute).st_mode | stat.S_IEXEC)
            forwarded = [substitute if word == "SUBSTITUTE" else word for word in forwarded]
            rendered = (
                command.replace("{{.FW_DIR}}", os.path.join(REPOSITORY, "firmware"))
                .replace("{{.TASK_EXE}}", declared.path)
                .replace("{{.CLI_ARGS}}", shlex.join(forwarded))
            )
            self.assertNotIn("{{", rendered, "the declaration uses a variable this does not render")
            words = shlex.split(rendered)
            self.assertEqual("python3", words[0])
            result = subprocess.run(
                [sys.executable, *words[1:]], cwd=directory,
                capture_output=True, text=True, check=False,
            )
            ran_substitute = os.path.exists(substituted)
            return result, declared.asked(), ran_substitute

    def test_a_task_runner_or_gate_passed_on_is_refused_and_nothing_runs(self):
        # SOL-VERIFY-NIGHTLY-FULL-ON-MAIN.C1: The daily verification runs every gate to completion and reports every failure
        for forwarded in (
            ["--task", "SUBSTITUTE"],
            ["--task=SUBSTITUTE"],
            ["--leave-out", "fw:sweep", "--task", "SUBSTITUTE"],
            ["--gate", "fw:extra"],
            ["--gate", "fw:build"],
            ["--repo", "/"],
            ["--", "--task", "SUBSTITUTE"],
            ["--ta", "SUBSTITUTE"],
        ):
            with self.subTest(forwarded=forwarded):
                result, asked, ran_substitute = self.run_declared(forwarded)
                self.assertEqual(2, result.returncode, result.stdout + result.stderr)
                self.assertEqual([], asked)
                self.assertFalse(ran_substitute, "a task runner passed on was run")
                self.assertIn("only --leave-out GATE may follow the declaration", result.stderr)
                self.assertNotIn("PASSED", result.stdout)

    def test_a_gate_left_out_through_the_declaration_runs_the_rest(self):
        # SOL-VERIFY-NIGHTLY-FULL-ON-MAIN.C1: The daily verification runs every gate to completion and reports every failure
        result, asked, _ = self.run_declared(["--leave-out", "fw:sweep"], {"fw:check": 1})
        self.assertEqual(1, result.returncode, result.stdout + result.stderr)
        self.assertEqual(GATES[:-1], asked)
        account = closing(result)
        self.assertIn("failed: fw:check (exit status 1).", account)
        self.assertIn("Gates left out: fw:sweep.", account)

    def test_nothing_passed_on_runs_every_declared_gate(self):
        # SOL-VERIFY-NIGHTLY-FULL-ON-MAIN.C1: The daily verification runs every gate to completion and reports every failure
        result, asked, _ = self.run_declared([])
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertEqual(GATES, asked)
        self.assertIn("COMPLETE VERIFICATION PASSED", closing(result))

    def test_an_undeclared_name_left_out_through_the_declaration_is_refused(self):
        # SOL-VERIFY-NIGHTLY-FULL-ON-MAIN.C1: The daily verification runs every gate to completion and reports every failure
        result, asked, _ = self.run_declared(["--leave-out", "fw:swep"])
        self.assertEqual(2, result.returncode)
        self.assertEqual([], asked)
        self.assertIn("--leave-out names no declared gate: fw:swep", result.stderr)

    def test_an_invocation_with_no_end_to_its_declaration_is_refused(self):
        # SOL-VERIFY-NIGHTLY-FULL-ON-MAIN.C1: The daily verification runs every gate to completion and reports every failure
        # Without the separator nothing tells the declaration from what was
        # passed on, so the driver will not guess.
        with tempfile.TemporaryDirectory() as directory:
            runner = FakeTaskRunner(directory)
            result = subprocess.run(
                [sys.executable, os.path.join(TOOLS, "verify_gate.py"), "--task", runner.path,
                 "--gate", "fw:build", "--gate", "fw:test"],
                cwd=directory, capture_output=True, text=True, check=False,
            )
            self.assertEqual(2, result.returncode)
            self.assertEqual([], runner.asked())
        self.assertIn("the declaration must end with '--'", result.stderr)


def read(path: str) -> str:
    with open(os.path.join(REPOSITORY, path), encoding="utf-8") as handle:
        return handle.read()


class TheTaskRunnerDeclaresTheCompleteVerification(unittest.TestCase):
    def setUp(self):
        self.taskfile = read("Taskfile.yml")

    def test_the_declaration_is_one_driver_call_over_every_gate_in_order(self):
        # SOL-VERIFY-NIGHTLY-FULL-ON-MAIN.C1: The daily verification runs every gate to completion and reports every failure
        (command,) = task_commands(self.taskfile, "fw:verify")
        self.assertIn("tools/verify_gate.py", command)
        # What is passed on comes after the end of the declaration and nowhere
        # else, so it cannot reach the driver's other options.
        self.assertTrue(command.endswith(" -- {{.CLI_ARGS}}"), command)
        self.assertEqual(1, command.count("{{.CLI_ARGS}}"), command)
        self.assertEqual(GATES, declared_gates(self.taskfile))

    def test_every_declared_gate_is_a_task_that_always_runs_afresh(self):
        # SOL-VERIFY-NIGHTLY-FULL-ON-MAIN.C1: The daily verification runs every gate to completion and reports every failure
        # A gate the task runner could judge up to date would hand back an
        # earlier run's verdict rather than run.
        lines = self.taskfile.splitlines()
        for name in declared_gates(self.taskfile):
            self.assertIn(f"  {name}:", lines, f"{name} is not a task")
            start = lines.index(f"  {name}:")
            body = []
            for line in lines[start + 1:]:
                if line.strip() and (len(line) - len(line.lstrip(" "))) <= 2:
                    break
                body.append(line)
            for key in ("sources:", "status:", "method:"):
                self.assertFalse(
                    any(line.strip().startswith(key) for line in body),
                    f"{name} declares {key} and could be skipped as up to date",
                )


class TheNightlyRunsTheSameDeclaration(unittest.TestCase):
    def setUp(self):
        self.nightly = read(".github/workflows/nightly-verify.yml")
        self.sweep = read(".github/workflows/mutation-sweep.yml")

    def test_the_nightly_runs_the_declaration_leaving_out_only_the_sweep_and_calls_the_shards(self):
        # SOL-VERIFY-NIGHTLY-FULL-ON-MAIN.C2: A scheduled workflow runs the daily verification against main on hosted runners
        # The invocation is the last thing its step runs and nothing follows it
        # on its line, so the step's result is the declaration's result: an
        # `|| true`, a `; exit 0` or a later command would turn a failed gate
        # into a passed step.
        steps = [
            script for script in workflow_declarations.scripts(self.nightly)
            if any("fw:verify" in line for line in script)
        ]
        self.assertEqual(1, len(steps), steps)
        script = [line for line in steps[0] if line.strip()]
        self.assertEqual(1, sum("fw:verify" in line for line in script), script)
        invocation = re.fullmatch(r"task fw:verify --((?: --leave-out [\w:.-]+)+)", script[-1])
        self.assertIsNotNone(invocation, f"the step does not end on the bare invocation: {script[-1]!r}")
        left_out = invocation.group(1).split()[1::2]
        self.assertEqual(["fw:sweep"], left_out)
        self.assertIn("fw:sweep", declared_gates(read("Taskfile.yml")))
        self.assertIn(
            "$/.github/workflows/mutation-sweep.yml", list(workflow_declarations.uses(self.nightly))
        )
        self.assertRegex(self.sweep, r"(?m)^  workflow_call:")
        self.assertRegex(self.sweep, r"(?m)^  workflow_dispatch:")

    def test_the_nightly_is_scheduled_and_dispatchable_and_never_cancels_a_run(self):
        # SOL-VERIFY-NIGHTLY-FULL-ON-MAIN.C2: A scheduled workflow runs the daily verification against main on hosted runners
        self.assertRegex(self.nightly, r'(?m)^name: Nightly verification$')
        self.assertRegex(self.nightly, r"(?m)^  schedule:\n(?:\s*#.*\n)*    - cron: ")
        self.assertRegex(self.nightly, r"(?m)^  workflow_dispatch:")
        self.assertNotRegex(self.nightly, r"cancel-in-progress:\s*true")

    def night(self, run_id: str, event: str) -> dict[str, str]:
        """What a nightly run, and the sweep it calls, see: in a called
        workflow the run, the ref and the workflow's name are the caller's."""
        name, _ = workflow_declarations.find(self.nightly, "name")
        return {"github.workflow": name, "github.ref": "refs/heads/main",
                "github.run_id": run_id, "github.event_name": event}

    def held(self, context: dict[str, str]) -> list[tuple[str, bool]]:
        """Every concurrency group one night's run joins, its own and its sweep's."""
        return (workflow_declarations.concurrency(self.nightly, context)
                + workflow_declarations.concurrency(self.sweep, context))

    def test_no_night_waits_on_or_cancels_another_night_or_its_own_sweep(self):
        # SOL-VERIFY-NIGHTLY-FULL-ON-MAIN.C2: A scheduled workflow runs the daily verification against main on hosted runners
        # Two runs sharing a group do not both run: the later one waits, and a
        # pending run is displaced by a newer one even when nothing cancels in
        # progress. So a night keeps its result only if no group it joins --
        # its own, or the called sweep's, which is evaluated in the caller's
        # context -- is one another night joins too, and none of them is
        # cancelled by a newer run.
        nights = [self.night("1001", "schedule"), self.night("1002", "schedule"),
                  self.night("1003", "workflow_dispatch")]
        groups = []
        for context in nights:
            held = self.held(context)
            self.assertTrue(held, "a night joins no concurrency group to check")
            names = [group for group, _ in held]
            with self.subTest(run=context["github.run_id"]):
                self.assertEqual(len(names), len(set(names)),
                                 f"the night and the sweep it calls share a group: {names}")
                for group, cancels in held:
                    self.assertFalse(cancels, f"a newer run cancels the group {group}")
            groups.append(set(names))
        for earlier, later in ((0, 1), (0, 2), (1, 2)):
            self.assertEqual(set(), groups[earlier] & groups[later],
                             "two nights join the same concurrency group")

    def test_no_gate_or_shard_in_the_night_can_fail_or_be_skipped_without_failing_it(self):
        # SOL-VERIFY-NIGHTLY-FULL-ON-MAIN.C2: A scheduled workflow runs the daily verification against main on hosted runners
        # A job or step allowed to fail reports success when it fails, and one
        # with a condition can be skipped, which also reads as success. Neither
        # has a place in a run whose result is the night's verdict, in the
        # nightly or in the sweep it calls.
        for workflow, declared in (("nightly", self.nightly), ("sweep", self.sweep)):
            for _, key, value in workflow_declarations.entries(declared):
                with self.subTest(workflow=workflow, key=key):
                    self.assertNotIn(key, ("continue-on-error", "if"),
                                     f"{workflow} declares {key}: {value}")
        self.assertEqual(
            ["gates", "host-build-macos", "sweep"], workflow_declarations.keys(self.nightly, "jobs")
        )

    def job_text(self, name: str) -> str:
        """One job's lines of the nightly, from its key to the next job's."""
        match = re.search(rf"(?ms)^  {re.escape(name)}:\n(.*?)(?=^  [\w-]+:\n|\Z)", self.nightly)
        self.assertIsNotNone(match, f"the nightly declares no job {name}")
        return match.group(1)

    def test_the_nightly_builds_the_host_tier_on_a_linux_host_and_a_macos_arm64_host(self):
        # SOL-PLANT-FIXTURES-BUILD-CLEAN-UNDER-GCC.C2: A verification run builds the host tier with each supported host's default compiler
        # Which compiler a job builds with is which host it runs on, so the
        # hosts are what has to be right: Ubuntu for GCC and an arm64 macOS
        # image for Apple clang. A floating label, or an Intel image, would
        # change which compiler the job builds with without a line changing.
        gates, _ = workflow_declarations.find(self.nightly, "jobs", "gates", "runs-on")
        self.assertRegex(gates, r"ubuntu-\d+\.\d+$")
        macos, _ = workflow_declarations.find(self.nightly, "jobs", "host-build-macos", "runs-on")
        match = re.fullmatch(r"macos-(\d+)", macos)
        self.assertIsNotNone(match, f"the macOS job's runner is not a fixed, plain image: {macos!r}")
        self.assertGreaterEqual(int(match.group(1)), 14, "the first macOS image on arm64 is 14")

    def test_the_macos_job_ends_on_the_bare_build_task_that_builds_every_host_environment(self):
        # SOL-PLANT-FIXTURES-BUILD-CLEAN-UNDER-GCC.C2: A verification run builds the host tier with each supported host's default compiler
        # The step's result is the build task's result: nothing follows the
        # invocation on its line or after it. And the task is the declaration
        # of the host builds, so an environment added later is built here
        # without a line here changing.
        scripts = [
            [line for line in script if line.strip()]
            for script in workflow_declarations.scripts(self.job_text("host-build-macos"))
            if any("fw:build" in line for line in script)
        ]
        self.assertEqual(1, len(scripts), scripts)
        self.assertEqual("task fw:build", scripts[0][-1])
        self.assertEqual(1, sum("fw:build" in line for line in scripts[0]))
        built = {
            name
            for line in task_commands(read("Taskfile.yml"), "fw:build")
            for name in re.findall(r"run -e (\w+)", line)
        }
        environments = build_environments.load(FIRMWARE)
        host = {e.name for e in build_environments.artefact_environments(environments)}
        machine = {e.name for e in build_environments.machine_environments(environments)}
        self.assertTrue(host)
        self.assertEqual(host | machine, built)

    def test_neither_host_job_selects_a_compiler_or_installs_one(self):
        # SOL-PLANT-FIXTURES-BUILD-CLEAN-UNDER-GCC.C2: A verification run builds the host tier with each supported host's default compiler
        # Each job builds with what its host defaults to. A compiler injected
        # through a setting, or installed beside the default, would be a
        # compiler a contributor on that platform does not run.
        selecting = re.compile(
            r"\b(CC|CXX|CFLAGS|CPPFLAGS|DEVELOPER_DIR|PLATFORMIO_BUILD_FLAGS|PLATFORMIO_BUILD_SRC_FLAGS)\b"
            r"|apt(-get)? +install|brew +install|update-alternatives|xcode-select|--toolchain"
        )
        for job in ("gates", "host-build-macos"):
            text = "\n".join(
                line for line in self.job_text(job).splitlines() if not line.lstrip().startswith("#")
            )
            with self.subTest(job=job):
                self.assertTrue(text.strip())
                self.assertIsNone(selecting.search(text), selecting.search(text))
        # The pattern would pass a job selecting a compiler if it never matched.
        self.assertIsNotNone(selecting.search("export CC=clang"))
        self.assertIsNotNone(selecting.search("sudo apt-get install -y clang"))

    def test_the_macos_job_pins_its_tools_as_the_linux_job_does_with_its_own_digest(self):
        # SOL-PLANT-FIXTURES-BUILD-CLEAN-UNDER-GCC.C2: A verification run builds the host tier with each supported host's default compiler
        def declared(job: str, name: str) -> str:
            match = re.search(rf'(?m)^\s+{name}: "([^"]+)"', self.job_text(job))
            self.assertIsNotNone(match, f"{job} does not pin {name}")
            return match.group(1)

        linux_digest = declared("gates", "TASK_SHA256")
        macos_digest = declared("host-build-macos", "TASK_SHA256")
        self.assertRegex(macos_digest, r"[0-9a-f]{64}")
        # An archive for one platform checked against another's digest would
        # fail every night, so the two must be told apart.
        self.assertNotEqual(linux_digest, macos_digest)
        for name in ("TASK_VERSION", "PLATFORMIO_VERSION"):
            self.assertEqual(declared("gates", name), declared("host-build-macos", name))
        job = self.job_text("host-build-macos")
        self.assertIn("task_darwin_arm64.tar.gz", job)
        self.assertNotIn("task_linux", job)
        self.assertIn('shasum -a 256 -c -', job)
        for script in workflow_declarations.scripts(job):
            self.assertEqual("set -euo pipefail", script[0].strip())

    def test_the_header_and_the_firmware_documentation_say_which_compiler_each_job_builds_with(self):
        # SOL-PLANT-FIXTURES-BUILD-CLEAN-UNDER-GCC.C2: A verification run builds the host tier with each supported host's default compiler
        header = re.sub(r"\s*\n#\s*", " ", self.nightly.split("\nname:", 1)[0])
        self.assertRegex(header, r"(?s)Ubuntu.*GCC")
        self.assertRegex(header, r"(?s)macOS.*Apple\s+clang")
        readme = read("firmware/README.md")
        readme = re.sub(r"\s+", " ", readme)
        self.assertRegex(readme, r"nightly.{0,600}GCC.{0,600}Apple clang|nightly.{0,600}Apple clang.{0,600}GCC")

    def test_a_step_in_a_form_the_workflow_reader_cannot_read_is_refused(self):
        # SOL-VERIFY-NIGHTLY-FULL-ON-MAIN.C2: A scheduled workflow runs the daily verification against main on hosted runners
        # Each check over the workflows reads them through one reader; a step
        # written in a form it skipped would carry an unpinned action or a
        # condition past every check at once.
        for declared in (
            "jobs:\n  a:\n    steps:\n      - {uses: actions/checkout@v4}\n",
            'jobs:\n  a:\n    steps:\n      - "uses": actions/checkout@v4\n',
            "jobs:\n  a: {continue-on-error: true}\n",
        ):
            with self.subTest(declared=declared):
                with self.assertRaises(ValueError):
                    list(workflow_declarations.entries(declared))

    def test_every_action_is_pinned_to_a_full_commit_and_permissions_are_read_only(self):
        # SOL-VERIFY-NIGHTLY-FULL-ON-MAIN.C2: A scheduled workflow runs the daily verification against main on hosted runners
        for text in (self.nightly, self.sweep):
            for used in workflow_declarations.uses(text):
                with self.subTest(used=used):
                    self.assertIsNone(workflow_declarations.unpinned(used))
            # Every grant, at the top and on every job, is read access to the
            # contents and nothing else; a one-line grant such as write-all
            # reads as the broad grant it is.
            workflow_declarations.find(text, "permissions")
            grants = workflow_declarations.permissions(text)
            self.assertTrue(grants)
            self.assertEqual({("contents", "read")}, set(grants))

    def test_a_broad_or_writing_grant_anywhere_is_seen(self):
        # SOL-VERIFY-NIGHTLY-FULL-ON-MAIN.C2: A scheduled workflow runs the daily verification against main on hosted runners
        top = "permissions:\n  contents: read\njobs:\n  a:\n    runs-on: x\n"
        for job_grant, seen in (
            ("    permissions: write-all\n", ("*", "write-all")),
            ("    permissions:\n      contents: write\n", ("contents", "write")),
            ("    permissions:\n      id-token: write\n", ("id-token", "write")),
        ):
            with self.subTest(job_grant=job_grant):
                self.assertIn(seen, workflow_declarations.permissions(top + job_grant))


class TheVerificationNeedsOnlyTheStandardLibrary(unittest.TestCase):
    """The host tier discovers these tests and the nightly runs the driver, so a
    third-party import in either fails it on a machine that lacks it."""

    def test_the_driver_and_its_tests_import_only_the_standard_library(self):
        # SOL-VERIFY-NIGHTLY-FULL-ON-MAIN.C1: The daily verification runs every gate to completion and reports every failure
        local = (
            "__future__", "build_environments", "task_gate", "test_round_gate", "workflow_declarations"
        )
        for path in (
            os.path.join(TOOLS, "verify_gate.py"), os.path.join(TOOLS, "task_gate.py"),
            os.path.abspath(__file__), os.path.abspath(workflow_declarations.__file__),
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
                if name not in sys.stdlib_module_names and name not in local
            )
            with self.subTest(path=os.path.basename(path)):
                self.assertTrue(imported)
                self.assertEqual([], foreign)


if __name__ == "__main__":
    unittest.main()
