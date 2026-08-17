#!/usr/bin/env python3
"""The mutation sweep: what it draws mutants from, what it compiles with, and what it does with a survivor.

The sweep itself needs a real LLVM toolchain and several minutes to run, so
nothing here runs one. What is driven instead is every decision it makes around
that: which sources its scope takes in, which compiler it accepts, and what it
concludes from a survivor given what has been judged about it. Those are the
parts that can be wrong while the sweep still finishes and prints a number,
which is the failure worth having tests for -- a sweep that mutated the tests,
or silently compiled with the wrong compiler, would report a score that looked
exactly like a good one.

The toolchains here are shell scripts printing version banners. That is enough,
because what is under test is which candidate is chosen and which is refused,
and both are decided from what the tool says about itself.
"""

from __future__ import annotations

import os
import re
import stat
import subprocess
import sys
import tempfile
import unittest

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)

import build_environments  # noqa: E402
import mull_sweep  # noqa: E402
import mull_toolchain  # noqa: E402
from test_plant_checks import declare_environments, host_environment  # noqa: E402

#: The real project, for the cases asserting that what is shipped is scoped the
#: way it says it is. The tree is the subject there, not a stand-in for one.
PROJECT = os.path.dirname(TOOLS)


def fake_tool(path: str, banner: str) -> str:
    """A program that answers `--version` with the banner given and nothing else."""
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(f'#!/bin/sh\ncat <<\'EOF\'\n{banner}\nEOF\n')
    os.chmod(path, os.stat(path).st_mode | stat.S_IEXEC)
    return path


def survivor(name: str) -> dict:
    """One surviving mutant, as the sweep records it."""
    return {"id": name, "source": "src/plant/common/x.c", "line": 1, "column": 1,
            "mutator": "cxx_lt_to_le", "replacement": "<=", "status": "Survived", "killed": False}


# --- What the sweep draws mutants from --------------------------------------


class TheScopeDecidesWhatIsMutated(unittest.TestCase):
    """SOL-PLANT-MUTATION-SWEEP.C1: the mutant population is the plant model's arithmetic, and not the tests.

    A scope taking in the test sources is the failure that matters most and
    shows least: the suite is the oracle, so mutating it produces a score about
    nothing. A scope taking in nothing at all is the same failure from the other
    side -- a percentage over an empty population reads like a perfect result.
    """

    def setUp(self):
        self.project = tempfile.TemporaryDirectory()
        self.addCleanup(self.project.cleanup)
        for directory in ("src/plant/common", "src/plant/thermoblock", "src/control", "test/test_plant"):
            os.makedirs(os.path.join(self.project.name, directory))
        for path in (
            "src/plant/common/plant_step.c",
            "src/plant/thermoblock/plant_structure.c",
            "src/control/control.c",
            "test/test_plant/test_plant.c",
        ):
            with open(os.path.join(self.project.name, path), "w", encoding="utf-8") as handle:
                handle.write("int main(void) { return 0; }\n")

    def declare(self, includes, excludes=()):
        path = os.path.join(self.project.name, mull_toolchain.CONFIG_NAME)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("includePaths:\n")
            for pattern in includes:
                handle.write(f'  - "{pattern}"\n')
            handle.write("excludePaths:\n")
            for pattern in excludes:
                handle.write(f'  - "{pattern}"\n')
        return path

    def test_the_plant_sources_are_in_scope_and_the_control_logic_is_not(self):
        includes = [".*/src/plant/common/.*", ".*/src/plant/thermoblock/.*"]
        self.assertTrue(mull_sweep.in_scope("/a/src/plant/common/plant_step.c", includes, []))
        self.assertTrue(
            mull_sweep.in_scope("/a/src/plant/thermoblock/plant_structure.c", includes, [])
        )
        self.assertFalse(mull_sweep.in_scope("/a/src/control/control.c", includes, []))

    def test_an_excluded_path_is_out_of_scope_even_when_an_include_takes_it_in(self):
        self.assertFalse(
            mull_sweep.in_scope("/a/test/test_plant.c", [".*"], [".*/test/.*"])
        )

    def test_a_scope_reaching_the_tests_is_refused(self):
        self.declare([".*"])
        includes, excludes = mull_sweep.scope_patterns(self.project.name)
        problems = mull_sweep.scope_problems(self.project.name, includes, excludes)
        self.assertEqual(1, len(problems))
        self.assertIn("test sources", problems[0])
        self.assertIn("test/test_plant/test_plant.c", problems[0])

    def test_a_scope_reaching_nothing_is_refused(self):
        self.declare([".*/src/plant/nowhere/.*"])
        includes, excludes = mull_sweep.scope_patterns(self.project.name)
        problems = mull_sweep.scope_problems(self.project.name, includes, excludes)
        self.assertEqual(1, len(problems))
        self.assertIn("no source under src/", problems[0])

    def test_a_scope_declaring_no_includes_is_refused(self):
        self.declare([])
        with self.assertRaises(mull_sweep.SweepError) as raised:
            mull_sweep.scope_patterns(self.project.name)
        self.assertIn("includePaths", str(raised.exception))

    def test_the_scope_this_project_ships_takes_in_the_plant_model_and_not_the_tests(self):
        includes, excludes = mull_sweep.scope_patterns(PROJECT)
        self.assertEqual([], mull_sweep.scope_problems(PROJECT, includes, excludes))
        swept = [
            os.path.relpath(path, PROJECT)
            for path in mull_sweep.sources_under(os.path.join(PROJECT, "src"))
            if mull_sweep.in_scope(path, includes, excludes)
        ]
        self.assertTrue(swept, "the shipped scope reaches no source at all")
        for path in swept:
            self.assertTrue(
                path.startswith("src/plant/common/")
                or path.startswith("src/plant/thermoblock/"),
                f"{path} is swept but is outside the plant model's arithmetic",
            )


# --- What the sweep compiles with -------------------------------------------


class TheToolchainIsTheOneTheMutantsNeed(unittest.TestCase):
    """SOL-PLANT-MUTATION-SWEEP.C2: the compiler is the matching LLVM release, or the sweep refuses to run.

    The pass plugin is loaded into the compiler's own process and built against
    one release. Loading it into another does not reliably fail -- it
    misbehaves -- so every case here is about refusing the wrong compiler rather
    than about finding the right one. The one that matters most on a Mac is
    Apple's Clang, which is what PATH resolves to and reports a version of its
    own that names no LLVM release.
    """

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.addCleanup(os.environ.pop, mull_toolchain.CLANG_VARIABLE, None)
        os.environ.pop(mull_toolchain.CLANG_VARIABLE, None)

    def tool(self, name: str, banner: str) -> str:
        return fake_tool(os.path.join(self.directory.name, name), banner)

    def test_a_compiler_reporting_the_matching_release_is_chosen(self):
        good = self.tool("good", "Homebrew clang version 19.1.7")
        chosen, version = mull_toolchain.find_clang(candidates=(good,))
        self.assertEqual(good, chosen)
        self.assertEqual((19, 1, 7), version)

    def test_apple_clang_is_passed_over_for_one_naming_the_release(self):
        apple = self.tool("apple", "Apple clang version 17.0.0 (clang-1700.0.13.5)")
        good = self.tool("good", "clang version 19.1.7")
        chosen, _ = mull_toolchain.find_clang(candidates=(apple, good))
        self.assertEqual(good, chosen)

    def test_a_compiler_of_another_release_is_refused_rather_than_used(self):
        wrong = self.tool("wrong", "clang version 18.1.8")
        with self.assertRaises(mull_toolchain.ToolchainError) as raised:
            mull_toolchain.find_clang(candidates=(wrong,))
        self.assertIn(str(mull_toolchain.LLVM_MAJOR), str(raised.exception))

    def test_a_candidate_that_is_not_there_is_stepped_over(self):
        good = self.tool("good", "clang version 19.1.7")
        missing = os.path.join(self.directory.name, "absent")
        chosen, _ = mull_toolchain.find_clang(candidates=(missing, good))
        self.assertEqual(good, chosen)

    def test_the_environment_names_a_compiler_ahead_of_the_defaults(self):
        named = self.tool("named", "clang version 19.1.7")
        other = self.tool("other", "clang version 19.1.7")
        os.environ[mull_toolchain.CLANG_VARIABLE] = named
        chosen, _ = mull_toolchain.find_clang(candidates=(other,))
        self.assertEqual(named, chosen)

    def test_a_compiler_named_outright_is_not_quietly_replaced_by_a_discovered_one(self):
        # Somebody naming a compiler wants that compiler. Falling back to
        # whatever else is installed would build the sweep with a toolchain
        # nobody chose and report a population from it.
        wrong = self.tool("wrong", "clang version 18.1.8")
        os.environ[mull_toolchain.CLANG_VARIABLE] = wrong
        with self.assertRaises(mull_toolchain.ToolchainError) as raised:
            mull_toolchain.find_clang()
        self.assertIn(wrong, str(raised.exception))

    def test_an_absent_pass_plugin_is_refused_naming_what_was_tried(self):
        missing = os.path.join(self.directory.name, "absent")
        with self.assertRaises(mull_toolchain.ToolchainError) as raised:
            mull_toolchain.find_pass_plugin(candidates=(missing,))
        self.assertIn(missing, str(raised.exception))

    def test_the_first_pass_plugin_on_disk_is_taken(self):
        missing = os.path.join(self.directory.name, "absent")
        present = os.path.join(self.directory.name, "mull-ir-frontend")
        with open(present, "w", encoding="utf-8") as handle:
            handle.write("")
        self.assertEqual(present, mull_toolchain.find_pass_plugin(candidates=(missing, present)))

    def plugin(self) -> str:
        path = os.path.join(self.directory.name, "plugin")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("")
        return path

    def test_a_runner_from_another_release_line_than_the_compiler_is_refused(self):
        # The reachable form of the mismatch: a compiler of the wrong release is
        # already refused when it is looked for, so what gets this far is a
        # runner from a different line -- an installation carrying two of them.
        clang = self.tool("clang", "clang version 19.1.7")
        runner = self.tool("runner", "mull-runner 0.34.0\nLLVM: 20.1.8")
        with self.assertRaises(mull_toolchain.ToolchainError) as raised:
            mull_toolchain.resolved(clang=clang, plugin=self.plugin(), runner=runner)
        self.assertIn("19.1.7", str(raised.exception))
        self.assertIn("20.1.8", str(raised.exception))

    def test_a_patch_level_difference_within_the_release_line_is_noted_and_allowed(self):
        # The distributions do not agree on a patch level -- one package names
        # 19.1.1 where another names 19.1.7 -- so refusing here would refuse
        # pairs their own packagers ship together.
        clang = self.tool("clang", "clang version 19.1.1")
        runner = self.tool("runner", "mull-runner 0.34.0\nLLVM: 19.1.7")
        noted = []
        resolved = mull_toolchain.resolved(
            clang=clang, plugin=self.plugin(), runner=runner, warn=noted.append
        )
        self.assertEqual(clang, resolved["clang"])
        self.assertEqual(1, len(noted))
        self.assertIn("19.1.1", noted[0])
        self.assertIn("19.1.7", noted[0])

    def test_an_agreeing_pair_is_not_remarked_on(self):
        clang = self.tool("clang", "clang version 19.1.7")
        runner = self.tool("runner", "mull-runner 0.34.0\nLLVM: 19.1.7")
        noted = []
        mull_toolchain.resolved(
            clang=clang, plugin=self.plugin(), runner=runner, warn=noted.append
        )
        self.assertEqual([], noted)

    def test_a_matching_pair_resolves_with_the_flags_the_mutants_need(self):
        clang = self.tool("clang", "clang version 19.1.7")
        runner = self.tool("runner", "mull-runner 0.34.0\nLLVM: 19.1.7")
        plugin = os.path.join(self.directory.name, "plugin")
        with open(plugin, "w", encoding="utf-8") as handle:
            handle.write("")
        resolved = mull_toolchain.resolved(clang=clang, plugin=plugin, runner=runner)
        self.assertEqual(clang, resolved["clang"])
        self.assertIn(f"-fpass-plugin={plugin}", resolved["compile_flags"])
        # Without this the mutants are in the artefact and the runner cannot
        # account for how each translation unit was built.
        self.assertIn("-grecord-command-line", resolved["compile_flags"])


# --- Where the sweep can run ------------------------------------------------


class TheSweepRunsWhereverTheToolsAre(unittest.TestCase):
    """SOL-PLANT-MUTATION-SWEEP.C3: the sweep is invocable on demand and is not tied to one host.

    A verification tool that only runs on the machine it was written on is one
    nobody else can run, so the candidate paths have to cover more than the
    author's package manager. These assert the shape of that rather than a
    successful run on another operating system, which no test here could stage.
    """

    def test_a_linux_layout_is_among_the_places_looked_in(self):
        self.assertTrue(
            any(candidate.startswith("/usr/") for candidate in mull_toolchain.CLANG_CANDIDATES),
            "no Linux compiler path is tried, so the sweep could not run on a hosted runner",
        )
        self.assertTrue(
            any(candidate.startswith("/usr/") for candidate in mull_toolchain.PLUGIN_CANDIDATES),
            "no Linux plugin path is tried, so the sweep could not run on a hosted runner",
        )

    def test_a_bare_name_is_tried_before_any_packaging_layout(self):
        # A host that has put the right compiler on PATH is believed before any
        # guess about where a package manager put one.
        self.assertFalse(mull_toolchain.CLANG_CANDIDATES[0].startswith("/"))

    def test_every_tool_can_be_named_by_the_environment(self):
        for variable in (
            mull_toolchain.CLANG_VARIABLE,
            mull_toolchain.PLUGIN_VARIABLE,
            mull_toolchain.RUNNER_VARIABLE,
        ):
            self.assertTrue(variable.startswith("MULL_"))

    def test_the_task_runner_declares_a_target_that_invokes_the_sweep(self):
        # The tool existing and nothing invoking it is the same as it not
        # existing, for anybody who does not already know it is there.
        with open(os.path.join(os.path.dirname(PROJECT), "Taskfile.yml"), encoding="utf-8") as handle:
            tasks = handle.read()
        self.assertIn("fw:sweep:", tasks)
        self.assertIn("tools/mull_sweep.py", tasks)

    def test_the_sweep_is_not_wired_into_a_gate_that_runs_on_every_push(self):
        # A stated boundary of this work: the sweep compiles every swept source
        # afresh and runs the suite once per mutant, to answer a question that
        # does not change between commits the way the tests' own results do.
        # Nothing else would notice `on: push` being added to that file.
        workflow = os.path.join(
            os.path.dirname(PROJECT), ".github", "workflows", "mutation-sweep.yml"
        )
        with open(workflow, encoding="utf-8") as handle:
            declared = handle.read()
        triggers = declared.split("on:", 1)[1].split("permissions:", 1)[0]
        self.assertIn("workflow_dispatch", triggers)
        for automatic in ("push:", "pull_request:", "schedule:"):
            self.assertNotIn(automatic, triggers)

    def test_the_sweep_stops_when_no_environment_declares_itself_swept(self):
        # The rule every discovering gate here follows. This one matters twice
        # over, because the declaration is also what excuses an environment from
        # the gates covering every host build.
        project = tempfile.TemporaryDirectory()
        self.addCleanup(project.cleanup)
        declare_environments(project.name, [("host", host_environment("alpha"))])
        result = subprocess.run(
            [sys.executable, os.path.join(TOOLS, "mull_sweep.py"), "--project", project.name],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(mull_sweep.FOUND_THE_PROBLEM, result.returncode)
        self.assertIn("declares itself built for the mutation sweep", result.stderr)


# --- What the hosted run is allowed to pull in ------------------------------


class TheHostedRunPullsInOnlyWhatItNames(unittest.TestCase):
    """SOL-PLANT-MUTATION-SWEEP.C3: the sweep's hosted run is pinned to code somebody chose.

    A workflow step written as `owner/action@v4` runs whatever that tag points
    at on the day it runs, and a tag is a moving reference its owner can
    repoint. This job checks out the repository and installs a package with
    sudo, so what it pulls in is worth naming exactly rather than by a label
    that can be re-aimed.

    The version stays in a trailing comment so the pin still reads as a version
    to a person, and so an updater can bump the digest and the comment together
    -- the shape those tools expect. Asserting both halves is what stops the
    pin degrading back into a tag the next time somebody edits the file.
    """

    #: A pinned reference: a full commit digest, then the version it was.
    PINNED = re.compile(r"^[0-9a-f]{40}$")

    def workflows(self):
        directory = os.path.join(os.path.dirname(PROJECT), ".github", "workflows")
        for name in sorted(os.listdir(directory)):
            if name.endswith((".yml", ".yaml")):
                with open(os.path.join(directory, name), encoding="utf-8") as handle:
                    yield name, handle.read()

    def uses(self):
        for name, declared in self.workflows():
            for line in declared.splitlines():
                stripped = line.strip().lstrip("- ").strip()
                if stripped.startswith("uses:"):
                    yield name, stripped[len("uses:"):].strip()

    def test_there_is_something_to_check(self):
        # A gate over an empty set reports success in exactly the way a gate
        # nobody ran does.
        self.assertTrue(list(self.uses()), "no workflow step uses an action at all")

    def test_every_action_is_pinned_to_a_digest_rather_than_a_tag(self):
        for workflow, used in self.uses():
            reference = used.split("#", 1)[0].strip()
            self.assertIn("@", reference, f"{workflow}: '{used}' names no version at all")
            _, _, version = reference.partition("@")
            self.assertRegex(
                version,
                self.PINNED,
                f"{workflow}: '{used}' is pinned to a moving reference rather than a digest",
            )

    def test_every_pinned_action_still_says_which_version_it_is(self):
        for workflow, used in self.uses():
            _, marker, comment = used.partition("#")
            self.assertTrue(
                marker and comment.strip(),
                f"{workflow}: '{used}' is a digest with nothing saying which release it is",
            )

    def test_the_versions_the_run_installs_are_named_rather_than_taken_as_latest(self):
        # A sweep whose result moved because a build tool was upgraded that
        # morning would be a finding about nothing.
        for workflow, declared in self.workflows():
            for line in declared.splitlines():
                if "pip install" in line:
                    self.assertNotIn("--upgrade", line, f"{workflow}: {line.strip()}")
                    self.assertIn("==", line, f"{workflow}: {line.strip()}")


# --- What every suite together says about one mutant ------------------------


class AMutantIsCaughtWhenAnySuiteKillsIt(unittest.TestCase):
    """SOL-PLANT-MUTATION-SWEEP.C1: a mutant is judged against every suite compiling the source it is in, not one.

    The swept sources are compiled into both structures' test runners, and one
    of them cannot exercise what the other can -- the refusal of a command on an
    unanswered channel has no expression against a structure answering every
    channel. Reading a single suite's report would call that refusal unnoticed
    when what is true is that the suite which notices it was not asked.

    So the folding is the claim, and it is the piece of arithmetic here that
    could silently invert: with the accumulation dropped, whichever suite ran
    last would decide every verdict, and a run would still finish and print a
    plausible number.
    """

    def report(self, source: str, status: str, line: int = 1) -> dict:
        return {
            "files": {
                source: {
                    "mutants": [
                        {
                            "id": "x",
                            "mutatorName": "cxx_lt_to_le",
                            "replacement": "<=",
                            "location": {"start": {"line": line, "column": 7}},
                            "status": status,
                        }
                    ]
                }
            }
        }

    def test_a_mutant_killed_by_a_later_suite_is_caught(self):
        found = {}
        mull_sweep.collect("/p", self.report("/p/src/plant/common/x.c", "Survived"), found)
        mull_sweep.collect("/p", self.report("/p/src/plant/common/x.c", "Killed"), found)
        self.assertEqual(1, len(found))
        self.assertTrue(next(iter(found.values()))["killed"])

    def test_a_mutant_killed_by_an_earlier_suite_stays_caught(self):
        # The accumulation has to survive a later report saying it survived,
        # which is what a suite that does not exercise the line reports.
        found = {}
        mull_sweep.collect("/p", self.report("/p/src/plant/common/x.c", "Killed"), found)
        mull_sweep.collect("/p", self.report("/p/src/plant/common/x.c", "Survived"), found)
        self.assertTrue(next(iter(found.values()))["killed"])

    def test_a_mutant_no_suite_kills_survives(self):
        found = {}
        mull_sweep.collect("/p", self.report("/p/src/plant/common/x.c", "Survived"), found)
        mull_sweep.collect("/p", self.report("/p/src/plant/common/x.c", "Survived"), found)
        self.assertFalse(next(iter(found.values()))["killed"])

    def test_a_mutant_that_timed_out_or_crashed_counts_as_caught(self):
        for status in ("Timeout", "Crashed"):
            found = {}
            mull_sweep.collect("/p", self.report("/p/src/plant/common/x.c", status), found)
            self.assertTrue(next(iter(found.values()))["killed"], status)

    def test_a_mutant_on_a_line_no_test_reaches_is_not_counted_as_caught(self):
        # Not covered is as unnoticed as survived, and folding it into the kills
        # would raise the score for lines nothing runs.
        found = {}
        mull_sweep.collect("/p", self.report("/p/src/plant/common/x.c", "NoCoverage"), found)
        self.assertFalse(next(iter(found.values()))["killed"])

    def test_mutants_at_different_places_are_different_mutants(self):
        found = {}
        mull_sweep.collect("/p", self.report("/p/src/plant/common/x.c", "Killed", line=1), found)
        mull_sweep.collect("/p", self.report("/p/src/plant/common/x.c", "Survived", line=2), found)
        self.assertEqual(2, len(found))

    def test_a_mutant_is_named_relative_to_the_project_so_the_record_travels(self):
        # The runner names the source by absolute path. A judgement written
        # against that would only be valid in the directory it was made in.
        found = {}
        mull_sweep.collect("/p", self.report("/p/src/plant/common/x.c", "Survived"), found)
        name = next(iter(found))
        self.assertEqual("cxx_lt_to_le:src/plant/common/x.c:1:7", name)
        self.assertNotIn("/p/", name)


# --- What the sweep concludes from a survivor -------------------------------


class ASurvivorIsJudgedBeforeItIsAFinding(unittest.TestCase):
    """SOL-PLANT-MUTATION-SWEEP.C4: a surviving mutant is triaged by hand before it is treated as a finding.

    The three outcomes are separated on purpose. An unreviewed survivor is not a
    defect -- nobody has decided whether it could be one -- so the failure it
    causes says that it is unreviewed. A survivor judged equivalent is closed. A
    survivor judged a real gap fails until the gap is closed, which is the whole
    point of having found it.
    """

    def setUp(self):
        self.project = tempfile.TemporaryDirectory()
        self.addCleanup(self.project.cleanup)

    def record(self, body: str) -> None:
        path = os.path.join(self.project.name, mull_sweep.TRIAGE_RECORD)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(body)

    def test_an_unjudged_survivor_is_reported_as_unreviewed(self):
        unreviewed, gaps, stale, retired = mull_sweep.classify({"a": survivor("a")}, {})
        self.assertEqual(["a"], unreviewed)
        self.assertEqual(([], [], []), (gaps, stale, retired))

    def test_a_survivor_judged_equivalent_is_closed(self):
        found = mull_sweep.classify(
            {"a": survivor("a")}, {"a": {"verdict": mull_sweep.EQUIVALENT, "reason": "why"}}
        )
        self.assertEqual(([], [], [], []), found)

    def test_a_survivor_judged_a_real_gap_is_reported_as_one(self):
        unreviewed, gaps, stale, retired = mull_sweep.classify(
            {"a": survivor("a")}, {"a": {"verdict": mull_sweep.GAP, "reason": "no test covers it"}}
        )
        self.assertEqual(["a"], gaps)
        self.assertEqual(([], [], []), (unreviewed, stale, retired))

    def test_a_judgement_about_a_mutant_that_is_gone_is_reported_as_stale(self):
        # The code the judgement was made about has moved or changed, so the
        # decision has to be made again rather than carried forward.
        unreviewed, gaps, stale, retired = mull_sweep.classify(
            {}, {"a": {"verdict": mull_sweep.EQUIVALENT, "reason": "why"}}
        )
        self.assertEqual(["a"], stale)
        self.assertEqual([], retired)

    def test_a_judgement_about_a_mutant_a_test_now_kills_is_retired_not_stale(self):
        # Not a failure. A mutant whose only effect is an out-of-bounds access is
        # killed or not according to how the compiler laid the frame out, so the
        # same judgement is load-bearing on one host and redundant on another.
        # Failing on the redundant one would make the record valid on one
        # machine, which is exactly what it must not be.
        killed = dict(survivor("a"), killed=True)
        unreviewed, gaps, stale, retired = mull_sweep.classify(
            {"a": killed}, {"a": {"verdict": mull_sweep.ANALYSIS, "reason": "why"}}
        )
        self.assertEqual(["a"], retired)
        self.assertEqual(([], [], []), (unreviewed, gaps, stale))

    def test_a_verdict_nobody_recognises_is_refused(self):
        self.record("survivors:\n  a:\n    verdict: probably fine\n    reason: it looks ok\n")
        with self.assertRaises(mull_sweep.SweepError) as raised:
            mull_sweep.read_triage(self.project.name)
        self.assertIn("probably fine", str(raised.exception))

    def test_a_verdict_with_no_reason_is_refused(self):
        # A verdict nobody has to justify is a way of marking a survivor read
        # without reading it.
        self.record(f"survivors:\n  a:\n    verdict: {mull_sweep.EQUIVALENT}\n    reason: ''\n")
        with self.assertRaises(mull_sweep.SweepError) as raised:
            mull_sweep.read_triage(self.project.name)
        self.assertIn("no reason", str(raised.exception))

    def test_a_record_with_no_survivors_mapping_is_refused(self):
        self.record("judgements:\n  a: fine\n")
        with self.assertRaises(mull_sweep.SweepError):
            mull_sweep.read_triage(self.project.name)

    def test_an_absent_record_is_no_judgements_rather_than_an_error(self):
        self.assertEqual({}, mull_sweep.read_triage(self.project.name))

    def test_every_judgement_this_project_ships_carries_a_verdict_and_a_reason(self):
        judgements = mull_sweep.read_triage(PROJECT)
        self.assertTrue(judgements, "the shipped triage record accounts for no survivor at all")
        for name, entry in judgements.items():
            self.assertIn(entry["verdict"], mull_sweep.VERDICTS, name)
            self.assertTrue(entry["reason"], name)

    def test_no_survivor_this_project_ships_is_recorded_as_an_open_gap(self):
        # A gap left standing in the record is work deferred rather than done,
        # and the sweep is red for as long as one is.
        judgements = mull_sweep.read_triage(PROJECT)
        open_gaps = [name for name, entry in judgements.items() if entry["verdict"] == mull_sweep.GAP]
        self.assertEqual([], open_gaps)


# --- What the ordinary gates do with a swept environment --------------------


class ASweptEnvironmentIsExcusedFromTheOrdinaryGates(unittest.TestCase):
    """SOL-PLANT-MUTATION-SWEEP.C2: the environment built by the mutation toolchain is not one the ordinary gates build.

    The gates covering every host build compile what they cover. Covering this
    one would make a mutation toolchain a condition of running them at all, on
    every host, over translation units another environment already covers. The
    declaration in the build file is what keeps them away, and these assert that
    it does -- and that the exclusion is not silent.
    """

    def setUp(self):
        self.project = tempfile.TemporaryDirectory()
        self.addCleanup(self.project.cleanup)
        declare_environments(
            self.project.name,
            [
                ("host", host_environment("alpha")),
                ("host_test", host_environment("alpha", entry_point=False, test_build_src="yes")),
                (
                    "host_mutation",
                    host_environment(
                        "alpha",
                        entry_point=False,
                        test_build_src="yes",
                        custom_mutation_sweep="it is compiled by a mutation toolchain",
                    ),
                ),
            ],
        )
        self.environments = build_environments.load(self.project.name)

    def named(self, environments):
        return [environment.name for environment in environments]

    def test_the_swept_environment_is_the_one_the_sweep_finds(self):
        self.assertEqual(
            ["host_mutation"],
            self.named(build_environments.mutation_environments(self.environments)),
        )

    def test_the_swept_environment_is_not_covered_by_the_gates_over_host_builds(self):
        self.assertNotIn(
            "host_mutation", self.named(build_environments.host_environments(self.environments))
        )

    def test_the_swept_environment_is_not_run_by_the_ordinary_test_task(self):
        # Otherwise the ordinary test task would need the mutation toolchain,
        # and would run every suite a second time under it.
        self.assertEqual(
            ["host_test"], self.named(build_environments.test_environments(self.environments))
        )

    def test_the_environments_the_gates_do_cover_are_untouched(self):
        self.assertEqual(
            ["host", "host_test"],
            self.named(build_environments.host_environments(self.environments)),
        )

    def test_declaring_no_reason_does_not_excuse_an_environment(self):
        # The reason is the content of the declaration. An empty one would be an
        # exclusion nobody stated, so it does not take.
        declare_environments(
            self.project.name,
            [("host_mutation", host_environment("alpha", custom_mutation_sweep=""))],
        )
        environments = build_environments.load(self.project.name)
        self.assertEqual([], self.named(build_environments.mutation_environments(environments)))
        self.assertEqual(
            ["host_mutation"], self.named(build_environments.host_environments(environments))
        )


if __name__ == "__main__":
    unittest.main()
