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

import contextlib
import io
import json
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
import round_gate  # noqa: E402
import mull_toolchain  # noqa: E402
from check_support_status import Uninspectable  # noqa: E402
from structure_symbols import discover  # noqa: E402
from test_plant_checks import ClaimTree, declare_environments, host_environment  # noqa: E402
from test_round_gate import GIT_ENVIRONMENT  # noqa: E402

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


def timing_entry(name: str, build=1.0, unmutated=1.0, runner=1.0, mutants=1) -> dict:
    """One unit's timing, as a shard report carries it."""
    return {
        "identity": {"environment": "native_alpha_mutation", "suite": name},
        "listing": False,
        "seconds": {"build": build, "unmutated": unmutated, "runner": runner},
        "mutants": mutants,
    }


def without_a_summary() -> dict:
    """This process's environment with no hosted job summary in it.

    A test run on a hosted runner inherits the variable naming the job's own
    summary, and a sweep started from a test would append its timing there.
    """
    environment = dict(os.environ)
    environment.pop("GITHUB_STEP_SUMMARY", None)
    return environment


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

    def declare(self, excludes=(), includes=()):
        """Write the sweep's configuration.

        Includes are writable even though the tool now refuses them, because
        refusing them is the behaviour under test: the file is what the toolchain
        reads, so a list reappearing here has to fail rather than be ignored.
        """
        path = os.path.join(self.project.name, mull_toolchain.CONFIG_NAME)
        with open(path, "w", encoding="utf-8") as handle:
            if includes:
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
        self.declare()
        problems = mull_sweep.scope_problems(self.project.name, [".*"], [])
        self.assertEqual(1, len(problems))
        self.assertIn("test sources", problems[0])
        self.assertIn("test/test_plant/test_plant.c", problems[0])

    def test_a_scope_reaching_nothing_is_refused(self):
        self.declare()
        problems = mull_sweep.scope_problems(
            self.project.name, [".*/src/plant/nowhere/.*"], []
        )
        self.assertEqual(1, len(problems))
        self.assertIn("no source under src/", problems[0])

    def test_the_declared_exclusions_are_read_and_a_bad_pattern_is_reported_against_the_file(self):
        self.declare(excludes=[".*/test/.*"])
        self.assertEqual(
            ([".*/test/.*"], []), mull_sweep.declared_excludes(self.project.name)
        )
        self.declare(excludes=["*unclosed["])
        with self.assertRaises(mull_sweep.SweepError) as raised:
            mull_sweep.declared_excludes(self.project.name)
        self.assertIn("excludePaths", str(raised.exception))

    def test_a_configuration_declaring_a_population_of_its_own_is_refused(self):
        # The written-down list is what this replaced, and the toolchain reads
        # this file rather than the derivation -- so a list reappearing here
        # would win silently. It has to fail instead.
        # Reported as a problem found rather than as being unable to look: the
        # file is perfectly readable, and what is wrong is what it says. The two
        # exit statuses are not interchangeable, and mutate.py asks for this one.
        self.declare(excludes=[".*/test/.*"], includes=[".*/src/plant/thermoblock/.*"])
        excludes, problems = mull_sweep.declared_excludes(self.project.name)
        self.assertEqual([".*/test/.*"], excludes)
        self.assertEqual(1, len(problems))
        self.assertIn("includePaths", problems[0])
        self.assertIn("PLANT_STRUCTURE_MACHINE_CLAIM", problems[0])

    def test_the_configuration_this_project_ships_names_no_population(self):
        """SOL-PLANT-RECONSTRUCTABLE-STATE.C7: nothing is widened to take new
        arithmetic into the sweep. The shipped configuration states only what the
        sweep must never mutate; a population written back into it would be the
        written-down list again, and arithmetic added to a structure would then
        join the sweep only if somebody remembered to say so."""
        excludes, problems = mull_sweep.declared_excludes(PROJECT)
        self.assertTrue(excludes)
        self.assertEqual([], problems)


# --- Where the population comes from ----------------------------------------


def mutation_environment(structure: str, suite: str) -> dict:
    """One environment declaring itself built for the sweep, over one structure."""
    options = host_environment(structure, entry_point=False)
    options["custom_mutation_sweep"] = "it is compiled by a mutation toolchain"
    options["test_filter"] = suite
    return options


class PopulationTree:
    """A synthetic project whose structures say what their equations are about.

    Built on the same tree the claim gate is driven against, so a test here
    cannot pass because this file's idea of a declaration has drifted from the
    gate's.
    """

    def __init__(self):
        self.tree = ClaimTree(("alpha", "beta"))
        self.root = self.tree.root.name
        self.plant = self.tree.plant
        self.include = self.tree.include
        self.shared = os.path.join(self.plant, "common")
        os.makedirs(self.shared, exist_ok=True)
        with open(os.path.join(self.shared, "plant_step.c"), "w", encoding="utf-8") as handle:
            handle.write("float advance(float x) { return x * 2.0f; }\n")
        self.describe("beta", "PLANT_DESCRIBES_NO_MACHINE")
        self.config()
        self.declare([("native_alpha_mutation", mutation_environment("alpha", "test_alpha"))])

    def describe(self, name: str, claim: str | None) -> str:
        """Add or restate one structure's claim, as editing the tree would."""
        return self.tree.structure(name, claim)

    def config(self, excludes=(".*/test/.*",), includes=()) -> str:
        path = os.path.join(self.root, mull_toolchain.CONFIG_NAME)
        with open(path, "w", encoding="utf-8") as handle:
            if includes:
                handle.write("includePaths:\n")
                for pattern in includes:
                    handle.write(f'  - "{pattern}"\n')
            handle.write("excludePaths:\n")
            for pattern in excludes:
                handle.write(f'  - "{pattern}"\n')
        return path

    def declare(self, environments) -> str:
        return declare_environments(self.root, environments)

    def structures(self):
        return discover(self.plant, self.include)

    def described(self):
        """The structures the sweep would draw from, and why the tree might not say."""
        return mull_sweep.machine_describing_structures(
            self.structures(), self.plant, self.include
        )

    def directories(self) -> list[str]:
        """The population, as relative paths, the way the sweep assembles it."""
        described, _ = self.described()
        assembled = mull_sweep.shared_directories(self.plant) + [
            structure.directory for structure in described
        ]
        return [os.path.relpath(directory, self.root) for directory in assembled]

    def environments(self):
        return build_environments.mutation_environments(build_environments.load(self.root))

    def cleanup(self) -> None:
        self.tree.cleanup()


class ThePopulationFollowsTheTree(unittest.TestCase):
    """SOL-MUTATION-SWEEP-STRUCTURE-DISCOVERY.C1: the sources the sweep draws
    mutants from are read from the tree, and a machine-describing structure is in
    that population without its name appearing in the sweep's configuration."""

    def setUp(self):
        self.tree = PopulationTree()
        self.addCleanup(self.tree.cleanup)

    def test_a_structure_describing_a_machine_is_in_the_population(self):
        self.assertIn(os.path.join("src", "plant", "alpha"), self.tree.directories())

    def test_a_structure_describing_no_machine_is_not_in_the_population(self):
        self.assertNotIn(os.path.join("src", "plant", "beta"), self.tree.directories())

    def test_the_shared_sources_are_in_the_population_without_being_a_structure(self):
        self.assertIn(os.path.join("src", "plant", "common"), self.tree.directories())

    def test_a_structure_arriving_later_joins_the_population_with_nothing_edited(self):
        # The case the fixed list could not answer. Nothing hand-maintained is
        # touched here: no pattern is written, no name is added to a
        # configuration, and the sweep's own files are left exactly as they were.
        before = self.tree.directories()
        self.tree.describe("gamma", "PLANT_DESCRIBES_A_MACHINE")
        after = self.tree.directories()
        self.assertNotIn(os.path.join("src", "plant", "gamma"), before)
        self.assertIn(os.path.join("src", "plant", "gamma"), after)

    def test_a_structure_arriving_later_describing_no_machine_stays_out(self):
        # The other half of the distinction: the population is drawn on what a
        # structure claims about itself, not on how many structures there are.
        self.tree.describe("gamma", "PLANT_DESCRIBES_NO_MACHINE")
        self.assertNotIn(os.path.join("src", "plant", "gamma"), self.tree.directories())

    def test_a_structure_whose_claim_is_unreadable_is_refused_rather_than_left_out(self):
        self.tree.describe("gamma", None)
        described, problems = self.tree.described()
        self.assertNotIn("gamma", [structure.name for structure in described])
        self.assertTrue(problems, "a structure carrying no claim was silently left out")
        self.assertIn("gamma", " ".join(problems))

    def test_the_derived_patterns_reach_the_sources_and_not_the_tests(self):
        described, _ = self.tree.described()
        directories = mull_sweep.shared_directories(self.tree.plant) + [
            structure.directory for structure in described
        ]
        includes = [mull_sweep.scope_pattern(self.tree.root, d) for d in directories]
        excludes, _ = mull_sweep.declared_excludes(self.tree.root)
        self.assertEqual([], mull_sweep.scope_problems(self.tree.root, includes, excludes))
        self.assertTrue(
            mull_sweep.in_scope("/a/src/plant/alpha/plant_structure.h", includes, excludes)
        )
        self.assertFalse(
            mull_sweep.in_scope("/a/src/plant/beta/plant_structure.h", includes, excludes)
        )

    def test_a_derived_scope_written_out_reads_back_as_the_same_patterns(self):
        # The patterns are regular expressions, so they carry backslashes. A
        # document quoting them the wrong way round is one the toolchain reads as
        # different patterns -- and the sweep would then mutate a different set
        # from the one reported here, which is the failure that would look most
        # like success.
        includes = [".*/src/plant/alpha/.*"]
        excludes = [".*/test/.*", ".*/\\.pio/.*", ".*[Uu]nity.*"]
        with tempfile.TemporaryDirectory() as directory:
            path = mull_sweep.write_scope(directory, includes, excludes)
            written = mull_sweep.load_yaml(path)
        self.assertEqual(includes, written["includePaths"])
        self.assertEqual(excludes, written["excludePaths"])

    def test_a_mutators_restriction_is_written_and_read_back_the_same_way(self):
        with tempfile.TemporaryDirectory() as directory:
            path = mull_sweep.write_scope(
                directory, [".*/a/.*"], [".*/test/.*"], ["cxx_eq_to_ne"]
            )
            written = mull_sweep.load_yaml(path)
        self.assertEqual(["cxx_eq_to_ne"], written["mutators"])

    def test_no_mutators_restriction_leaves_the_key_out_entirely(self):
        # Not written empty: an empty mutators: list is Mull's own way of
        # asking for none of them, the opposite of every operator this sweep
        # means by omitting the key.
        with tempfile.TemporaryDirectory() as directory:
            path = mull_sweep.write_scope(directory, [".*/a/.*"], [".*/test/.*"])
            written = mull_sweep.load_yaml(path)
        self.assertNotIn("mutators", written)

    def test_the_population_this_project_ships_covers_every_structure_that_claims_a_machine(self):
        """SOL-PLANT-RECONSTRUCTABLE-STATE.C7: the population follows the
        structures declaring they describe a machine, so arithmetic added to one
        of them is swept without anything being widened. Whether the mutants that
        arithmetic produces are then killed or judged is the sweep's own run
        against mutation_triage.yaml, which this cannot stand in for."""
        plant = os.path.join(PROJECT, "src", "plant")
        include = os.path.join(PROJECT, "include")
        structures = discover(plant, include)
        described, problems = mull_sweep.machine_describing_structures(
            structures, plant, include
        )
        self.assertEqual([], problems)
        self.assertTrue(described, "the shipped tree claims no machine at all")

        directories = mull_sweep.shared_directories(plant) + [
            structure.directory for structure in described
        ]
        includes = [mull_sweep.scope_pattern(PROJECT, d) for d in directories]
        excludes, _ = mull_sweep.declared_excludes(PROJECT)
        self.assertEqual([], mull_sweep.scope_problems(PROJECT, includes, excludes))

        swept = [
            os.path.relpath(path, PROJECT)
            for path in mull_sweep.sources_under(os.path.join(PROJECT, "src"))
            if mull_sweep.in_scope(path, includes, excludes)
        ]
        self.assertTrue(swept, "the derived scope reaches no source at all")
        # Every structure claiming a machine contributes, and nothing else does.
        for structure in described:
            prefix = os.path.relpath(structure.directory, PROJECT) + os.sep
            self.assertTrue(
                any(path.startswith(prefix) for path in swept),
                f"{structure.name} claims a machine and no source of it is swept",
            )
        allowed = tuple(
            os.path.relpath(directory, PROJECT) + os.sep for directory in directories
        )
        for path in swept:
            self.assertTrue(
                path.startswith(allowed),
                f"{path} is swept but is outside the plant model's arithmetic",
            )


class AnEnvironmentExistsForEveryStructureSwept(unittest.TestCase):
    """SOL-MUTATION-SWEEP-STRUCTURE-DISCOVERY.C1: a structure in the population
    that no mutation build compiles is refused, because it would contribute no
    mutants while the score read as covering it."""

    def setUp(self):
        self.tree = PopulationTree()
        self.addCleanup(self.tree.cleanup)

    def uncovered(self):
        described, problems = self.tree.described()
        self.assertEqual([], problems)
        return mull_sweep.uncovered_structures(
            self.tree.environments(), self.tree.structures(), described
        )

    def test_a_structure_every_environment_covers_passes(self):
        self.assertEqual([], self.uncovered())

    def test_a_machine_describing_structure_with_no_environment_is_named(self):
        self.tree.describe("gamma", "PLANT_DESCRIBES_A_MACHINE")
        self.assertEqual(["gamma"], self.uncovered())

    def test_a_structure_describing_no_machine_needs_no_environment(self):
        self.tree.describe("gamma", "PLANT_DESCRIBES_NO_MACHINE")
        self.assertEqual([], self.uncovered())

    def test_an_environment_added_for_a_structure_is_taken_up_without_being_named(self):
        self.tree.describe("gamma", "PLANT_DESCRIBES_A_MACHINE")
        self.tree.declare(
            [
                ("native_alpha_mutation", mutation_environment("alpha", "test_alpha")),
                ("native_gamma_mutation", mutation_environment("gamma", "test_gamma")),
            ]
        )
        self.assertEqual([], self.uncovered())

    def test_an_environment_not_declared_for_the_sweep_does_not_cover_a_structure(self):
        # An ordinary test environment compiles the structure but carries no
        # mutants, so it is not what makes the structure swept.
        self.tree.describe("gamma", "PLANT_DESCRIBES_A_MACHINE")
        self.tree.declare(
            [
                ("native_alpha_mutation", mutation_environment("alpha", "test_alpha")),
                ("native_gamma_test", host_environment("gamma", entry_point=False)),
            ]
        )
        self.assertEqual(["gamma"], self.uncovered())

    def test_every_structure_this_project_ships_has_an_environment_built_for_it(self):
        plant = os.path.join(PROJECT, "src", "plant")
        include = os.path.join(PROJECT, "include")
        structures = discover(plant, include)
        described, problems = mull_sweep.machine_describing_structures(
            structures, plant, include
        )
        self.assertEqual([], problems)
        environments = build_environments.mutation_environments(
            build_environments.load(PROJECT)
        )
        self.assertEqual(
            [], mull_sweep.uncovered_structures(environments, structures, described)
        )


class OnlyTheDerivedPopulationCountsTowardsTheScore(unittest.TestCase):
    """SOL-MUTATION-SWEEP-STRUCTURE-DISCOVERY.C1: mutants from sources the derived
    population does not take in are refused, so the score cannot be computed over
    more than the plant model's arithmetic.

    What the scope says and what was instrumented are different facts. Since the
    population is no longer written in the file the toolchain reads, a scope that
    fails to reach the plugin yields an unbounded sweep rather than a narrow one --
    the control logic arrives in the report, and if its own tests kill those
    mutants the run passes with an inflated score.
    """

    def setUp(self):
        self.tree = PopulationTree()
        self.addCleanup(self.tree.cleanup)
        described, problems = self.tree.described()
        self.assertEqual([], problems)
        directories = mull_sweep.shared_directories(self.tree.plant) + [
            structure.directory for structure in described
        ]
        self.includes = [mull_sweep.scope_pattern(self.tree.root, d) for d in directories]
        self.excludes, _ = mull_sweep.declared_excludes(self.tree.root)

    def outside(self, *sources):
        found = {
            f"cxx_lt_to_le:{source}:1:1": dict(survivor(source), source=source)
            for source in sources
        }
        return mull_sweep.outside_the_population(
            self.tree.root, found, self.includes, self.excludes
        )

    def test_a_mutant_from_the_population_is_not_reported(self):
        self.assertEqual([], self.outside(os.path.join("src", "plant", "alpha", "x.c")))

    def test_a_mutant_from_the_shared_sources_is_not_reported(self):
        self.assertEqual([], self.outside(os.path.join("src", "plant", "common", "x.c")))

    def test_a_mutant_from_the_control_logic_is_reported(self):
        # The measured consequence of the scope not reaching the compiler.
        source = os.path.join("src", "control", "control.c")
        self.assertEqual([source], self.outside(source))

    def test_a_mutant_from_a_structure_describing_no_machine_is_reported(self):
        source = os.path.join("src", "plant", "beta", "plant_structure.c")
        self.assertEqual([source], self.outside(source))

    def test_an_unbounded_sweep_is_reported_rather_than_averaged_in(self):
        control = os.path.join("src", "control", "control.c")
        hardware = os.path.join("src", "hw", "sim", "hw_sim.c")
        inside = os.path.join("src", "plant", "alpha", "x.c")
        self.assertEqual(sorted([control, hardware]), self.outside(control, hardware, inside))


class TheDerivationCanBeRunWithoutACompiler(unittest.TestCase):
    """SOL-MUTATION-SWEEP-STRUCTURE-DISCOVERY.C1, .C2: the population and the
    checks about it are reachable without the mutation toolchain, and each refusal
    reports through the tool's own exit codes rather than only as a function."""

    def setUp(self):
        self.tree = PopulationTree()
        self.addCleanup(self.tree.cleanup)

    def sweep(self):
        return subprocess.run(
            [
                sys.executable,
                os.path.join(TOOLS, "mull_sweep.py"),
                "--project",
                self.tree.root,
                "--plant-root",
                os.path.relpath(self.tree.plant, self.tree.root),
                "--include-dir",
                os.path.relpath(self.tree.include, self.tree.root),
                "--population-only",
            ],
            capture_output=True,
            text=True,
            check=False,
        )

    def test_the_population_is_reported_and_the_run_succeeds(self):
        result = self.sweep()
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn(os.path.join("src", "plant", "alpha"), result.stdout)
        self.assertIn(os.path.join("src", "plant", "common"), result.stdout)
        self.assertNotIn(os.path.join("src", "plant", "beta"), result.stdout)

    def test_a_structure_carrying_no_claim_stops_the_run(self):
        self.tree.describe("gamma", None)
        result = self.sweep()
        self.assertEqual(1, result.returncode)
        self.assertIn("gamma", result.stderr)

    def test_a_tree_claiming_no_machine_stops_the_run(self):
        self.tree.describe("alpha", "PLANT_DESCRIBES_NO_MACHINE")
        result = self.sweep()
        self.assertEqual(1, result.returncode)
        self.assertIn("no structure declares", result.stderr)

    def test_a_structure_with_no_mutation_environment_stops_the_run(self):
        self.tree.describe("gamma", "PLANT_DESCRIBES_A_MACHINE")
        result = self.sweep()
        self.assertEqual(1, result.returncode)
        self.assertIn("gamma", result.stderr)
        self.assertIn("no environment built for the sweep", result.stderr)

    def test_a_population_written_back_into_the_configuration_stops_the_run(self):
        # Exit 1, not 2: the file is readable and what it says is wrong, which is
        # a problem found rather than an inability to look.
        self.tree.config(includes=[".*/src/plant/beta/.*"])
        result = self.sweep()
        self.assertEqual(1, result.returncode)
        self.assertIn("includePaths", result.stderr)

    def test_a_missing_vocabulary_stops_the_run_as_being_unable_to_look(self):
        os.remove(os.path.join(self.tree.include, "plant_machine_claim.h"))
        result = self.sweep()
        self.assertEqual(2, result.returncode)
        self.assertIn("no vocabulary header", result.stderr)


class TheDerivedScopeReachesTheCompiler(unittest.TestCase):
    """SOL-MUTATION-SWEEP-STRUCTURE-DISCOVERY.C1: the build is told which sources
    to instrument, because the plugin decides that while the compiler runs.

    A scope written only for the mutant runner would leave the build instrumenting
    whatever it liked and the report describing something narrower, which is the
    one failure that would look exactly like success.
    """

    def test_the_build_is_handed_the_derived_configuration(self):
        # Both calls, now that building and running the unmutated suite are two:
        # the build is where the scope decides what is instrumented, and the run
        # that follows it is made under the same environment.
        recorded = []

        def fake_run(command, cwd=None, env=None, check=False):
            recorded.append((command, env))
            return subprocess.CompletedProcess(command, 0)

        original = mull_sweep.subprocess.run
        mull_sweep.subprocess.run = fake_run
        self.addCleanup(setattr, mull_sweep.subprocess, "run", original)
        mull_sweep.build("/project", "pio", "native_mutation", "suite", "/derived/mull.yml")
        mull_sweep.run_unmutated("/project", "pio", "native_mutation", "suite", "/derived/mull.yml")
        self.assertEqual(2, len(recorded))
        for command, env in recorded:
            self.assertEqual("/derived/mull.yml", env["MULL_CONFIG"], command)

    def test_the_build_script_prefers_an_inherited_configuration_over_the_tracked_one(self):
        # pio_mutation.py runs inside SCons and cannot be imported here, so the
        # one line that decides this is asserted against its source. Without it
        # the build would instrument the tracked file's scope -- which, now that
        # the file names no population, means everything.
        with open(os.path.join(TOOLS, "pio_mutation.py"), encoding="utf-8") as handle:
            source = handle.read()
        self.assertIn('CONFIG = os.environ.get("MULL_CONFIG") or os.path.join(', source)


class AnEmptyScopeIsAResultNotAFailure(unittest.TestCase):
    """SOL-MUTATION-SWEEP-CI-TIMEOUT-HEADROOM.C1: a scope with no mutant in it is a report of nothing, not a crash.

    A --shard-directory whose scope an environment's build does not reach --
    every directory sharded against every suite, deliberately, rather than
    worked out in advance -- draws no mutant at all. mull-runner writes no
    report file for that and exits clean, which the run_mull that used to
    assume any missing report meant a broken run could not tell apart from the
    runner having actually failed.
    """

    def fake_run(self, returncode: int):
        def run(command, cwd=None, env=None, capture_output=None, text=None, check=None):
            return subprocess.CompletedProcess(command, returncode, stdout="", stderr="")

        return run

    def test_no_report_and_a_clean_exit_is_an_empty_population(self):
        original = mull_sweep.subprocess.run
        mull_sweep.subprocess.run = self.fake_run(0)
        self.addCleanup(setattr, mull_sweep.subprocess, "run", original)
        report = mull_sweep.run_mull("mull-runner", "/program", "/mull.yml", "/project")
        self.assertEqual({"files": {}}, report)

    def test_no_report_and_a_failing_exit_is_still_refused(self):
        original = mull_sweep.subprocess.run
        mull_sweep.subprocess.run = self.fake_run(1)
        self.addCleanup(setattr, mull_sweep.subprocess, "run", original)
        with self.assertRaises(mull_sweep.SweepError):
            mull_sweep.run_mull("mull-runner", "/program", "/mull.yml", "/project")


class TheClaimIsCheckedInsideEveryBuild(unittest.TestCase):
    """SOL-MUTATION-SWEEP-STRUCTURE-DISCOVERY.C3: the build refuses a structure
    that declares nothing, and not only the check task.

    Every peer declaration gate runs inside the build for the same reason: a
    structure that reached a compiler unanswered would be one whose arithmetic is
    swept or not according to nothing the tree states.
    """

    def test_the_in_build_checks_include_the_claim_gate_and_its_vocabulary(self):
        with open(os.path.join(TOOLS, "pio_seam_checks.py"), encoding="utf-8") as handle:
            source = handle.read()
        self.assertIn("check_machine_claim.py", source)
        self.assertIn("plant_machine_claim.h", source)

    def test_every_gate_the_check_task_runs_over_the_claim_also_runs_in_the_build(self):
        # The check task and the build must not disagree about which declarations
        # a structure owes, so the pairing is asserted rather than assumed.
        with open(os.path.join(TOOLS, "pio_seam_checks.py"), encoding="utf-8") as handle:
            in_build = handle.read()
        with open(
            os.path.join(os.path.dirname(PROJECT), "Taskfile.yml"), encoding="utf-8"
        ) as handle:
            tasks = handle.read()
        for gate in ("check_machine_claim.py", "check_support_status.py"):
            self.assertIn(gate, tasks)
            self.assertIn(gate, in_build)


class TheDiscoveryStepRefusesAnEmptyPopulation(unittest.TestCase):
    """SOL-MUTATION-SWEEP-STRUCTURE-DISCOVERY.C2: a discovery step that finds no
    machine-describing structure stops with an error rather than reporting a clean
    result over an empty population."""

    def setUp(self):
        self.tree = PopulationTree()
        self.addCleanup(self.tree.cleanup)

    def test_a_tree_where_no_structure_describes_a_machine_is_refused(self):
        # The state a mis-drawn declaration produces. It yields no survivors, so
        # it reads exactly like a suite that killed everything -- and none of the
        # sweep's other emptiness guards fires, because the tree is full of
        # structures and an environment is declared.
        self.tree.describe("alpha", "PLANT_DESCRIBES_NO_MACHINE")
        described, problems = self.tree.described()
        self.assertEqual([], described)
        self.assertTrue(problems, "an empty population was reported as fine")
        self.assertIn("no structure declares", " ".join(problems))

    def test_a_tree_with_no_structures_at_all_is_refused(self):
        empty = os.path.join(self.tree.root, "src", "nothing")
        os.makedirs(empty, exist_ok=True)
        described, problems = mull_sweep.machine_describing_structures(
            [], empty, self.tree.include
        )
        self.assertEqual([], described)
        self.assertIn("no structures under", " ".join(problems))

    def test_a_missing_vocabulary_is_refused_rather_than_read_as_no_machines(self):
        with self.assertRaises(Uninspectable):
            mull_sweep.machine_describing_structures(
                self.tree.structures(),
                self.tree.plant,
                os.path.join(self.tree.root, "nowhere"),
            )

    def test_a_vocabulary_that_stopped_drawing_the_line_is_refused(self):
        self.tree.tree.vocabulary(
            "typedef enum { PLANT_DESCRIBES_A_MACHINE = 0 } plant_machine_claim_t;\n"
        )
        _, problems = self.tree.described()
        self.assertIn("PLANT_DESCRIBES_NO_MACHINE", " ".join(problems))


class AStructureThatProducedNoMutantIsRefused(unittest.TestCase):
    """SOL-MUTATION-SWEEP-STRUCTURE-DISCOVERY.C1: a structure the scope named and
    a build compiled, which produced no mutant at all, is reported rather than
    counted as swept -- the only one of the three checks that is evidence rather
    than a statement about configuration."""

    def setUp(self):
        self.tree = PopulationTree()
        self.addCleanup(self.tree.cleanup)

    def described(self):
        described, problems = self.tree.described()
        self.assertEqual([], problems)
        return described

    def found(self, *sources):
        return {
            f"cxx_lt_to_le:{source}:1:1": dict(survivor(f"m:{source}"), source=source)
            for source in sources
        }

    def test_a_structure_that_contributed_a_mutant_is_not_named(self):
        found = self.found(os.path.join("src", "plant", "alpha", "plant_structure.h"))
        self.assertEqual([], mull_sweep.unswept(self.tree.root, found, self.described()))

    def test_a_structure_that_contributed_nothing_is_named(self):
        found = self.found(os.path.join("src", "plant", "common", "plant_step.c"))
        self.assertEqual(
            ["alpha"], mull_sweep.unswept(self.tree.root, found, self.described())
        )

    def test_a_report_carrying_nothing_names_every_structure_in_the_population(self):
        self.assertEqual(
            ["alpha"], mull_sweep.unswept(self.tree.root, {}, self.described())
        )

    def test_a_structure_describing_no_machine_is_never_expected_to_contribute(self):
        found = self.found(os.path.join("src", "plant", "alpha", "plant_structure.h"))
        described = self.described()
        self.assertEqual(["alpha"], [structure.name for structure in described])
        self.assertEqual([], mull_sweep.unswept(self.tree.root, found, described))


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


class TheMutatorAxisIsReadFromADryRunNotFromADocumentedList(unittest.TestCase):
    """SOL-MUTATION-SWEEP-CI-TIMEOUT-HEADROOM.C1: which operators a shard can split by is read from what the compiler produced.

    A fixed list of group names typed from Mull's own documentation was tried
    first and reverted: it dropped every mutant whose operator the list left
    out, silently, because a scope restricted to named operators draws nothing
    from an operator not named. discovered_mutators reads the operators a
    dry-run actually reported instead, so the axis can never leave one out
    that the population it is splitting really has.
    """

    def report(self, *entries: tuple[str, str]) -> dict:
        """A dry-run report naming one mutator per (source, mutator) pair."""
        files: dict = {}
        for source, mutator in entries:
            files.setdefault(source, {"mutants": []})["mutants"].append(
                {
                    "id": "x",
                    "mutatorName": mutator,
                    "replacement": "",
                    "location": {"start": {"line": 1, "column": 1}},
                }
            )
        return {"files": files}

    def test_every_distinct_operator_present_is_returned(self):
        report = self.report(
            ("/p/a.c", "cxx_eq_to_ne"), ("/p/a.c", "cxx_lt_to_le"), ("/p/b.c", "cxx_add_to_sub")
        )
        self.assertEqual(
            ["cxx_add_to_sub", "cxx_eq_to_ne", "cxx_lt_to_le"],
            mull_sweep.discovered_mutators(report),
        )

    def test_the_same_operator_from_two_files_is_reported_once(self):
        report = self.report(("/p/a.c", "cxx_eq_to_ne"), ("/p/b.c", "cxx_eq_to_ne"))
        self.assertEqual(["cxx_eq_to_ne"], mull_sweep.discovered_mutators(report))

    def test_an_empty_report_names_no_operators(self):
        self.assertEqual([], mull_sweep.discovered_mutators({"files": {}}))


class ADryRunDiscoversMutantsWithoutRunningAnyOfThem(unittest.TestCase):
    """SOL-MUTATION-SWEEP-CI-TIMEOUT-HEADROOM.C1: run_mull's dry-run path asks the runner to discover rather than execute -- but still makes the warmup run --timeout was sized for.

    --dry-run skips a mutant's own execution, but the runner still makes its
    warmup run against the unmutated program first, on the same reasoning an
    ordinary sweep does -- discovering what a scope draws presupposes the
    thing being discovered from is testable at all. Omitting --timeout there
    reintroduces exactly the failure BASELINE_TIMEOUT_MS exists to prevent:
    the runner's own undocumented three-second default, too short for a suite
    whose baseline already runs close to it, reports "Original test failed"
    for a suite that never actually failed. Only --workers is dry-run-specific
    -- there is nothing to parallelise when nothing is being executed.
    """

    def fake_run(self, recorded: list):
        def run(command, cwd=None, env=None, capture_output=None, text=None, check=None):
            recorded.append(command)
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        return run

    def test_dry_run_passes_the_flag_and_the_timeout_but_not_the_worker_count(self):
        recorded: list = []
        original = mull_sweep.subprocess.run
        mull_sweep.subprocess.run = self.fake_run(recorded)
        self.addCleanup(setattr, mull_sweep.subprocess, "run", original)
        mull_sweep.run_mull("mull-runner", "/program", "/mull.yml", "/project", dry_run=True)
        command = recorded[0]
        self.assertIn("--dry-run", command)
        self.assertIn("--timeout", command)
        self.assertNotIn("--workers", command)

    def test_an_ordinary_run_carries_both_the_timeout_and_the_worker_count_and_not_the_flag(self):
        recorded: list = []
        original = mull_sweep.subprocess.run
        mull_sweep.subprocess.run = self.fake_run(recorded)
        self.addCleanup(setattr, mull_sweep.subprocess, "run", original)
        mull_sweep.run_mull("mull-runner", "/program", "/mull.yml", "/project")
        command = recorded[0]
        self.assertNotIn("--dry-run", command)
        self.assertIn("--timeout", command)
        self.assertIn("--workers", command)


# --- Matrixing the sweep across shards ---------------------------------------


class AShardIsFoldedTheSameWayASuiteIs(unittest.TestCase):
    """SOL-MUTATION-SWEEP-CI-TIMEOUT-HEADROOM.C1: folding one shard's raw findings into the combined population is the same merge collect() makes within one process.

    Matrixing the sweep across CI jobs moves where a suite's report is folded
    in -- one process per shard instead of one process for all of them -- but
    what "caught" means cannot move with it. A mutant killed by any shard has
    to stay killed regardless of the order the shards happen to finish or the
    order their reports happen to be read back in, the same way collect()
    already guarantees within one process.
    """

    def mutant(self, name: str, killed: bool) -> dict:
        return {
            "id": name,
            "source": "src/plant/common/x.c",
            "line": 1,
            "column": 7,
            "mutator": "cxx_lt_to_le",
            "replacement": "<=",
            "status": "Killed" if killed else "Survived",
            "killed": killed,
        }

    def test_a_mutant_killed_by_a_later_shard_is_caught(self):
        found: dict = {}
        mull_sweep.fold(found, {"x": self.mutant("x", False)})
        mull_sweep.fold(found, {"x": self.mutant("x", True)})
        self.assertTrue(found["x"]["killed"])

    def test_a_mutant_killed_by_an_earlier_shard_stays_caught(self):
        found: dict = {}
        mull_sweep.fold(found, {"x": self.mutant("x", True)})
        mull_sweep.fold(found, {"x": self.mutant("x", False)})
        self.assertTrue(found["x"]["killed"])

    def test_a_mutant_no_shard_kills_survives(self):
        found: dict = {}
        mull_sweep.fold(found, {"x": self.mutant("x", False)})
        mull_sweep.fold(found, {"x": self.mutant("x", False)})
        self.assertFalse(found["x"]["killed"])

    def test_mutants_at_different_places_from_different_shards_are_both_kept(self):
        found: dict = {}
        mull_sweep.fold(found, {"x": self.mutant("x", True)})
        mull_sweep.fold(found, {"y": self.mutant("y", False)})
        self.assertEqual(2, len(found))
        self.assertTrue(found["x"]["killed"])
        self.assertFalse(found["y"]["killed"])


class TheShardsAreDerivedFromTheSameTreeEveryOtherModeReads(unittest.TestCase):
    """SOL-MUTATION-SWEEP-CI-TIMEOUT-HEADROOM.C1: --list-shards names every environment:suite pair the tree declares, without a compiler.

    A matrix built from a list written in the workflow file would go stale the
    same way the scope patterns this file used to carry already did once --
    a suite added later would sweep nothing until somebody remembered to add a
    line for it. --list-shards is read by the workflow instead so the matrix is
    exactly what --population-only already proves is decided before a compiler
    is needed.
    """

    def setUp(self):
        self.tree = PopulationTree()
        self.addCleanup(self.tree.cleanup)

    def sweep(self, *extra):
        return subprocess.run(
            [
                sys.executable,
                os.path.join(TOOLS, "mull_sweep.py"),
                "--project",
                self.tree.root,
                "--plant-root",
                os.path.relpath(self.tree.plant, self.tree.root),
                "--include-dir",
                os.path.relpath(self.tree.include, self.tree.root),
                *extra,
            ],
            capture_output=True,
            text=True,
            check=False,
        )

    def test_the_one_declared_pair_is_split_by_every_directory_in_the_population(self):
        result = self.sweep("--list-shards")
        self.assertEqual(0, result.returncode, result.stderr)
        shards = json.loads(result.stdout)
        self.assertEqual(
            [
                {
                    "environment": "native_alpha_mutation",
                    "suite": "test_alpha",
                    "directory": "src/plant/common",
                },
                {
                    "environment": "native_alpha_mutation",
                    "suite": "test_alpha",
                    "directory": "src/plant/alpha",
                },
            ],
            shards,
        )

    def test_a_second_declared_suite_is_also_split_by_directory(self):
        options = mutation_environment("alpha", "test_alpha")
        options["test_filter"] = "test_alpha,test_alpha_again"
        self.tree.declare([("native_alpha_mutation", options)])
        result = self.sweep("--list-shards")
        self.assertEqual(0, result.returncode, result.stderr)
        shards = json.loads(result.stdout)
        self.assertEqual(4, len(shards))
        self.assertEqual(
            {"test_alpha", "test_alpha_again"}, {shard["suite"] for shard in shards}
        )
        self.assertEqual(
            {"src/plant/common", "src/plant/alpha"},
            {shard["directory"] for shard in shards},
        )

    def test_a_missing_shard_report_flag_refuses_without_a_compiler(self):
        result = self.sweep("--shard", "native_alpha_mutation:test_alpha")
        self.assertEqual(mull_sweep.COULD_NOT_LOOK, result.returncode)
        self.assertIn("--shard-report", result.stderr)

    def test_a_shard_naming_an_undeclared_pair_is_refused_without_a_compiler(self):
        result = self.sweep(
            "--shard", "native_alpha_mutation:test_nobody_declared", "--shard-report", "/dev/null"
        )
        self.assertEqual(mull_sweep.COULD_NOT_LOOK, result.returncode)
        self.assertIn("native_alpha_mutation:test_nobody_declared", result.stderr)

    def test_a_shard_naming_an_undeclared_environment_is_refused_without_a_compiler(self):
        result = self.sweep(
            "--shard", "nobody_declared_this_environment:test_alpha", "--shard-report", "/dev/null"
        )
        self.assertEqual(mull_sweep.COULD_NOT_LOOK, result.returncode)
        self.assertIn("nobody_declared_this_environment:test_alpha", result.stderr)

    def test_a_shard_directory_not_in_the_population_is_refused_without_a_compiler(self):
        result = self.sweep(
            "--shard",
            "native_alpha_mutation:test_alpha",
            "--shard-report",
            "/dev/null",
            "--shard-directory",
            "src/plant/nowhere",
        )
        self.assertEqual(mull_sweep.COULD_NOT_LOOK, result.returncode)
        self.assertIn("src/plant/nowhere", result.stderr)

    def test_list_mutators_in_wants_environment_colon_directory(self):
        result = self.sweep("--list-mutators-in", "native_alpha_mutation")
        self.assertEqual(mull_sweep.COULD_NOT_LOOK, result.returncode)
        self.assertIn("ENVIRONMENT:DIRECTORY", result.stderr)

    def test_list_mutators_in_an_undeclared_environment_is_refused_without_a_compiler(self):
        result = self.sweep("--list-mutators-in", "nobody_declared_this:src/plant/common")
        self.assertEqual(mull_sweep.COULD_NOT_LOOK, result.returncode)
        self.assertIn("nobody_declared_this:src/plant/common", result.stderr)

    def test_list_mutators_in_a_directory_not_in_the_population_is_refused_without_a_compiler(self):
        result = self.sweep("--list-mutators-in", "native_alpha_mutation:src/plant/nowhere")
        self.assertEqual(mull_sweep.COULD_NOT_LOOK, result.returncode)
        self.assertIn("native_alpha_mutation:src/plant/nowhere", result.stderr)

    def test_every_pair_list_shards_names_is_accepted_by_list_mutators_in(self):
        # A second round trip: --list-shards' environment and directory fields
        # have to be exactly what --list-mutators-in accepts, since that is how
        # the discover-mutators job is meant to be driven from the same list.
        listed = json.loads(self.sweep("--list-shards").stdout)
        pairs = {(shard["environment"], shard["directory"]) for shard in listed}
        for environment, directory in pairs:
            result = self.sweep("--list-mutators-in", f"{environment}:{directory}")
            self.assertNotIn("names no environment or no directory", result.stderr, (environment, directory))

    def test_list_mutators_out_is_still_refused_the_same_way_without_a_compiler(self):
        # The refusal paths run before a build is ever started, so routing the
        # eventual result to a file instead of stdout changes nothing about
        # them -- this is the same check as the two refusal tests above, aimed
        # at the flag combination the workflow actually uses.
        result = self.sweep(
            "--list-mutators-in",
            "native_alpha_mutation:src/plant/nowhere",
            "--list-mutators-out",
            "/dev/null",
        )
        self.assertEqual(mull_sweep.COULD_NOT_LOOK, result.returncode)
        self.assertIn("native_alpha_mutation:src/plant/nowhere", result.stderr)

    def test_every_directory_list_shards_names_is_accepted_by_shard_directory(self):
        # A round trip: whatever --list-shards prints in a shard's "directory"
        # field has to be exactly what --shard-directory accepts back, since
        # that is how the workflow carries one to the other. Refused past the
        # directory check (no real toolchain here) is still evidence the
        # refusal above is not this test's failure mode.
        listed = json.loads(self.sweep("--list-shards").stdout)
        for shard in listed:
            result = self.sweep(
                "--shard",
                f"{shard['environment']}:{shard['suite']}",
                "--shard-report",
                "/dev/null",
                "--shard-directory",
                shard["directory"],
            )
            self.assertNotIn("names no directory", result.stderr, shard)


class TheCombinedShardListCrossesDiscoveredMutatorsWithTheOriginalTriples(unittest.TestCase):
    """SOL-MUTATION-SWEEP-CI-TIMEOUT-HEADROOM.C1: --combine-shards folds a discover-mutators job's output back into --list-shards' own triples.

    A discover-mutators shard runs once per environment:directory pair and
    reports which operators it found there; --combine-shards is the step that
    turns those separate small reports back into one shard list, without a
    compiler, the same way --merge-reports turns several sweep shards back
    into one population.
    """

    def setUp(self):
        self.tree = PopulationTree()
        self.addCleanup(self.tree.cleanup)
        self.discovered = tempfile.TemporaryDirectory()
        self.addCleanup(self.discovered.cleanup)

    def write_discovery(self, environment: str, directory: str, mutators: list) -> None:
        path = os.path.join(self.discovered.name, f"{environment}-{directory.replace('/', '-')}.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump({"environment": environment, "directory": directory, "mutators": mutators}, handle)

    def combine(self):
        return subprocess.run(
            [
                sys.executable,
                os.path.join(TOOLS, "mull_sweep.py"),
                "--project",
                self.tree.root,
                "--plant-root",
                os.path.relpath(self.tree.plant, self.tree.root),
                "--include-dir",
                os.path.relpath(self.tree.include, self.tree.root),
                "--combine-shards",
                self.discovered.name,
            ],
            capture_output=True,
            text=True,
            check=False,
        )

    def test_one_directorys_discovered_operators_become_one_shard_each(self):
        self.write_discovery(
            "native_alpha_mutation", "src/plant/alpha", ["cxx_eq_to_ne", "cxx_lt_to_le"]
        )
        result = self.combine()
        self.assertEqual(0, result.returncode, result.stderr)
        shards = json.loads(result.stdout)
        self.assertEqual(
            [
                {
                    "environment": "native_alpha_mutation",
                    "suite": "test_alpha",
                    "directory": "src/plant/alpha",
                    "mutators": "cxx_eq_to_ne",
                },
                {
                    "environment": "native_alpha_mutation",
                    "suite": "test_alpha",
                    "directory": "src/plant/alpha",
                    "mutators": "cxx_lt_to_le",
                },
            ],
            shards,
        )

    def test_a_directory_with_no_discovered_operators_contributes_no_shard(self):
        # common was never written a discovery file for at all here -- the
        # same state as an environment whose build never reaches it.
        self.write_discovery("native_alpha_mutation", "src/plant/alpha", ["cxx_eq_to_ne"])
        result = self.combine()
        self.assertEqual(0, result.returncode, result.stderr)
        shards = json.loads(result.stdout)
        self.assertFalse(any(shard["directory"] == "src/plant/common" for shard in shards))

    def test_no_discovery_files_at_all_produces_no_shards_rather_than_an_error(self):
        # Not a refusal: nothing discovered anywhere is a fact this step folds
        # in as-is, the same way an empty --shard result is not an error.
        result = self.combine()
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual([], json.loads(result.stdout))

    def test_a_discovery_file_that_is_not_valid_json_is_refused_rather_than_crashing(self):
        # A shard that failed to upload whole -- an interrupted artefact
        # rather than a failed job, which the matrix's fail-fast: false
        # already surfaces on its own.
        path = os.path.join(self.discovered.name, "truncated.json")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write('{"environment": "native_alpha_mutation", "director')
        result = self.combine()
        self.assertEqual(mull_sweep.COULD_NOT_LOOK, result.returncode)
        self.assertIn("truncated.json", result.stderr)

    def test_a_discovery_file_missing_a_required_field_is_refused_rather_than_crashing(self):
        path = os.path.join(self.discovered.name, "incomplete.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump({"environment": "native_alpha_mutation"}, handle)
        result = self.combine()
        self.assertEqual(mull_sweep.COULD_NOT_LOOK, result.returncode)
        self.assertIn("incomplete.json", result.stderr)


class TheMergedShardsAreJudgedExactlyAsOneRunWouldBe(unittest.TestCase):
    """SOL-MUTATION-SWEEP-CI-TIMEOUT-HEADROOM.C1: --merge-reports reaches the same checks and the same verdict a single-process run reaches.

    The population, scope and triage checks main() runs inline after sweeping
    everything itself are the same checks judge() runs after --merge-reports
    folds several shards' files together -- the same function, reached by a
    different path. What is under test here is that the path change is
    invisible to the verdict: a shard set standing in for what one process
    would have found reports the same unswept/intruder/triage failures a
    monolithic run would have, and the same clean pass when nothing is wrong.
    """

    def setUp(self):
        self.tree = PopulationTree()
        self.addCleanup(self.tree.cleanup)
        self.reports = tempfile.TemporaryDirectory()
        self.addCleanup(self.reports.cleanup)

    def write_shard(self, name: str, found: dict) -> None:
        path = os.path.join(self.reports.name, f"{name}.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump({"mutants": found, "timing": timing_entry(name)}, handle)

    def killed_mutant(self, source: str, line: int = 1) -> dict:
        return {
            "id": f"cxx_lt_to_le:{source}:{line}:7",
            "source": source,
            "line": line,
            "column": 7,
            "mutator": "cxx_lt_to_le",
            "replacement": "<=",
            "status": "Killed",
            "killed": True,
        }

    def merge(self):
        return subprocess.run(
            [
                sys.executable,
                os.path.join(TOOLS, "mull_sweep.py"),
                "--project",
                self.tree.root,
                "--plant-root",
                os.path.relpath(self.tree.plant, self.tree.root),
                "--include-dir",
                os.path.relpath(self.tree.include, self.tree.root),
                "--merge-reports",
                self.reports.name,
            ],
            capture_output=True,
            text=True,
            check=False,
            env=without_a_summary(),
        )

    def test_a_clean_population_folded_from_two_shards_passes(self):
        self.write_shard("common", {"a": self.killed_mutant("src/plant/common/plant_step.c")})
        self.write_shard("alpha", {"b": self.killed_mutant("src/plant/alpha/plant_structure.c")})
        result = self.merge()
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("2 mutants, 2 killed", result.stdout)

    def test_a_survivor_in_one_shard_is_reported_unreviewed(self):
        self.write_shard("common", {"a": self.killed_mutant("src/plant/common/plant_step.c")})
        survivor_mutant = self.killed_mutant("src/plant/alpha/plant_structure.c")
        survivor_mutant["killed"] = False
        survivor_mutant["status"] = "Survived"
        self.write_shard("alpha", {"b": survivor_mutant})
        result = self.merge()
        self.assertEqual(mull_sweep.FOUND_THE_PROBLEM, result.returncode)
        self.assertIn("have not been reviewed", result.stderr)

    def test_a_structure_missing_from_every_shard_is_reported_unswept(self):
        # Only "common" reported -- "alpha", the one machine-describing
        # structure this fixture declares, contributed nothing.
        self.write_shard("common", {"a": self.killed_mutant("src/plant/common/plant_step.c")})
        result = self.merge()
        self.assertEqual(mull_sweep.FOUND_THE_PROBLEM, result.returncode)
        self.assertIn("no mutant came back from alpha", result.stderr)

    def test_no_shard_reports_at_all_is_refused_without_reading_the_tree_as_empty(self):
        result = self.merge()
        self.assertEqual(mull_sweep.COULD_NOT_LOOK, result.returncode)
        self.assertIn("no shard reports found", result.stderr)

    def test_a_shard_report_that_is_not_valid_json_is_refused_rather_than_crashing(self):
        self.write_shard("common", {"a": self.killed_mutant("src/plant/common/plant_step.c")})
        path = os.path.join(self.reports.name, "truncated.json")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write('{"a": {"id": "a", "kille')
        result = self.merge()
        self.assertEqual(mull_sweep.COULD_NOT_LOOK, result.returncode)
        self.assertIn("truncated.json", result.stderr)


# --- Where the sweep's time goes ---------------------------------------------


class FakeTools:
    """PlatformIO and the mutation runner, and a clock only they move.

    Each call moves the clock on by an amount particular to the phase and the
    suite it was made for, and no two of those amounts are alike -- so a figure
    booked against the wrong phase, or the wrong unit, comes out as a different
    number rather than as the right one by coincidence.
    """

    BUILD = {"test_alpha": 7.0, "test_alpha_again": 11.0}
    UNMUTATED = {"test_alpha": 3.0, "test_alpha_again": 2.0}
    RUNNER = {"test_alpha": 50.0, "test_alpha_again": 130.0}

    def __init__(self, project: str):
        self.project = project
        self.now = 1000.0
        self.suite = ""
        #: How many mutant results the runner reports per suite. The same
        #: places in both, so the runs outnumber the population.
        self.mutants = {"test_alpha": 2, "test_alpha_again": 3}
        self.status = "Killed"
        self.failing: set[tuple[str, str]] = set()
        #: Suites whose runner report is cut off part-way, and suites whose
        #: report lists a mutant with no location: the shapes a report takes
        #: when something nothing here anticipated goes wrong.
        self.truncated: set[str] = set()
        self.malformed: set[str] = set()
        self.observers: list = []
        self.commands: list[list[str]] = []

    def clock(self) -> float:
        return self.now

    def run(self, command, cwd=None, env=None, check=False, capture_output=False, text=False):
        for observe in self.observers:
            observe(command)
        self.commands.append(command)
        if command[0] == "pio":
            environment = command[command.index("-e") + 1]
            self.suite = command[command.index("-f") + 1]
            if "--without-testing" in command:
                self.now += self.BUILD[self.suite]
                program = os.path.join(
                    self.project, build_environments.BUILD_ROOT, environment, "program"
                )
                os.makedirs(os.path.dirname(program), exist_ok=True)
                with open(program, "w", encoding="utf-8") as handle:
                    handle.write("")
                return subprocess.CompletedProcess(
                    command, int(("build", self.suite) in self.failing)
                )
            self.now += self.UNMUTATED[self.suite]
            return subprocess.CompletedProcess(
                command, int(("unmutated", self.suite) in self.failing)
            )
        if command[0] != "mull-runner":
            raise AssertionError(f"the sweep ran something nothing here stands in for: {command}")
        self.now += self.RUNNER[self.suite]
        source = os.path.join(self.project, "src", "plant", "alpha", "plant_structure.c")
        mutants = [
            {
                "id": str(line),
                "mutatorName": "cxx_add_to_sub",
                "replacement": "-",
                "location": {"start": {"line": line, "column": 1}},
                "status": self.status,
            }
            for line in range(1, self.mutants[self.suite] + 1)
        ]
        if self.suite in self.malformed:
            del mutants[0]["location"]
        reports = command[command.index("--report-dir") + 1]
        with open(os.path.join(reports, "sweep.json"), "w", encoding="utf-8") as handle:
            text = json.dumps({"files": {source: {"mutants": mutants}}})
            handle.write(text[: len(text) // 2] if self.suite in self.truncated else text)
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    def pio_calls(self) -> list[list[str]]:
        return [command for command in self.commands if command[0] == "pio"]

    def runner_calls(self) -> list[list[str]]:
        return [command for command in self.commands if command[0] == "mull-runner"]


def figures(output: str, label: str) -> list[float]:
    """The figures on the one plain-text line a unit, or the total, is printed on."""
    lines = [line.strip() for line in output.splitlines() if line.strip().startswith(label + " ")]
    if len(lines) != 1:
        raise AssertionError(f"{len(lines)} plain-text line(s) for '{label}' in:\n{output}")
    return [float(cell) for cell in lines[0][len(label):].split()]


def summary_figures(summary: str, label: str) -> list[float]:
    """The figures on the one summary table row a unit, or the total, is written on."""
    lines = [
        line
        for line in summary.splitlines()
        if line.startswith(f"| `{label}` |") or line.startswith(f"| **{label}** |")
    ]
    if len(lines) != 1:
        raise AssertionError(f"{len(lines)} summary row(s) for '{label}' in:\n{summary}")
    return [float(cell) for cell in lines[0].strip("|").split("|")[1:]]


ALPHA = "native_alpha_mutation:test_alpha"
ALPHA_AGAIN = "native_alpha_mutation:test_alpha_again"


class SweepHarness(unittest.TestCase):
    """A synthetic tree with two suites, swept in this process against FakeTools.

    In this process rather than as a child so the clock can be handed in. The
    path driven is `main` itself -- the one the task runner and the hosted
    workflow invoke -- with only the programs it calls out to stood in for.
    """

    def setUp(self):
        self.tree = PopulationTree()
        self.addCleanup(self.tree.cleanup)
        options = mutation_environment("alpha", "test_alpha")
        options["test_filter"] = "test_alpha,test_alpha_again"
        self.tree.declare([("native_alpha_mutation", options)])
        self.project = os.path.realpath(self.tree.root)
        self.tools = FakeTools(self.project)

        original_run = mull_sweep.subprocess.run
        mull_sweep.subprocess.run = self.tools.run
        self.addCleanup(setattr, mull_sweep.subprocess, "run", original_run)
        original_resolved = mull_sweep.mull_toolchain.resolved
        mull_sweep.mull_toolchain.resolved = lambda warn=None: {"runner": "mull-runner"}
        self.addCleanup(setattr, mull_sweep.mull_toolchain, "resolved", original_resolved)

        inherited = os.environ.pop("GITHUB_STEP_SUMMARY", None)
        if inherited is not None:
            self.addCleanup(os.environ.__setitem__, "GITHUB_STEP_SUMMARY", inherited)
        self.addCleanup(os.environ.pop, "GITHUB_STEP_SUMMARY", None)

        self.scratch = tempfile.TemporaryDirectory()
        self.addCleanup(self.scratch.cleanup)
        self.summary = os.path.join(self.scratch.name, "summary.md")

    def sweep(
        self, *extra: str, summary: str | None = None, output: io.StringIO | None = None
    ) -> tuple[int, str]:
        """Run the sweep, returning its exit status and its output and errors interleaved."""
        if summary is None:
            os.environ.pop("GITHUB_STEP_SUMMARY", None)
        else:
            os.environ["GITHUB_STEP_SUMMARY"] = summary
        argv = [
            "--project", self.tree.root,
            "--plant-root", os.path.relpath(self.tree.plant, self.tree.root),
            "--include-dir", os.path.relpath(self.tree.include, self.tree.root),
            "--pio", "pio",
            *extra,
        ]
        output = output if output is not None else io.StringIO()
        try:
            with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
                status = mull_sweep.main(argv, clock=self.tools.clock)
        finally:
            os.environ.pop("GITHUB_STEP_SUMMARY", None)
        return status, output.getvalue()

    def sweep_raising(self, *extra: str, summary: str | None = None) -> tuple[BaseException, str]:
        """Run a sweep expected to raise, returning what it raised and what it printed first."""
        output = io.StringIO()
        try:
            self.sweep(*extra, summary=summary, output=output)
        except Exception as error:  # noqa: BLE001 -- whatever escaped is the thing under test
            return error, output.getvalue()
        raise AssertionError(f"the sweep raised nothing:\n{output.getvalue()}")

    def written_summary(self) -> str:
        with open(self.summary, encoding="utf-8") as handle:
            return handle.read()


class TheSweepAccountsForItsTimePerUnit(SweepHarness):
    """SOL-SWEEP-TIME-ACCOUNTED.C1: the sweep reports build and execution time per shard.

    The figures are what the next speed-up is chosen from, so the failure worth
    a test is a figure that is printed and wrong: build time booked as
    execution, one unit's time booked to another, a total that is not the sum
    of its rows. A table that merely appears would pass every one of those.
    """

    def test_each_figure_is_attributed_to_its_own_column(self):
        status, output = self.sweep()
        self.assertEqual(0, status, output)
        self.assertEqual([7.0, 3.0, 50.0, 2.0], figures(output, ALPHA))
        self.assertEqual([11.0, 2.0, 130.0, 3.0], figures(output, ALPHA_AGAIN))

    def test_the_total_is_the_sum_of_the_rows(self):
        _, output = self.sweep()
        rows = [figures(output, ALPHA), figures(output, ALPHA_AGAIN)]
        total = figures(output, mull_sweep.TOTAL)
        self.assertEqual([sum(column) for column in zip(*rows)], total)
        self.assertEqual([18.0, 5.0, 180.0, 5.0], total)

    def test_the_count_is_of_runs_and_is_not_offered_as_the_population(self):
        # Three mutants, each run by both suites but counted once by the
        # verdict: five results against three mutants. A column calling those
        # mutants would be read against the verdict's own count.
        _, output = self.sweep()
        self.assertIn("mull_sweep: 3 mutants", output)
        self.assertEqual(5.0, figures(output, mull_sweep.TOTAL)[3])
        self.assertIn("mutant runs", output)
        self.assertIn("not the population", output)

    def test_every_figure_states_its_unit_and_what_it_leaves_out(self):
        _, output = self.sweep()
        for heading in ("build (s)", "unmutated run (s)", "mutation runner (s)"):
            self.assertIn(heading, output)
        self.assertIn("includes its own warm-up and baseline runs", " ".join(output.split()))
        self.assertIn("toolchain installation and other workflow setup are outside", output)
        self.assertIn("summed, not elapsed", output)

    def test_the_build_and_the_unmutated_run_are_separate_calls_in_that_order(self):
        self.sweep()
        calls = self.tools.pio_calls()
        self.assertEqual(4, len(calls))
        for build, run in (calls[0:2], calls[2:4]):
            self.assertIn("--without-testing", build)
            self.assertNotIn("--without-building", build)
            self.assertIn("--without-building", run)
            self.assertNotIn("--without-testing", run)
            self.assertEqual(build[build.index("-f") + 1], run[run.index("-f") + 1])

    def test_a_suite_failing_unmutated_stops_the_sweep_before_its_mutants_run(self):
        self.tools.failing.add(("unmutated", "test_alpha"))
        status, output = self.sweep()
        self.assertEqual(mull_sweep.COULD_NOT_LOOK, status)
        self.assertIn("does not pass under the mutation build before anything is mutated", output)
        self.assertEqual([], self.tools.runner_calls())

    def test_a_suite_that_does_not_build_is_never_run(self):
        self.tools.failing.add(("build", "test_alpha"))
        status, output = self.sweep()
        self.assertEqual(mull_sweep.COULD_NOT_LOOK, status)
        self.assertIn("'test_alpha' does not build", output)
        self.assertEqual(1, len(self.tools.pio_calls()))
        self.assertEqual([], self.tools.runner_calls())

    def test_the_timing_is_printed_before_the_verdict(self):
        status, output = self.sweep()
        self.assertEqual(0, status, output)
        self.assertLess(
            output.index("mull_sweep: time per unit"), output.index("mull_sweep: 3 mutants")
        )

    def test_the_timing_is_printed_before_a_failing_verdict(self):
        self.tools.status = "Survived"
        status, output = self.sweep()
        self.assertEqual(mull_sweep.FOUND_THE_PROBLEM, status)
        self.assertLess(
            output.index("mull_sweep: time per unit"), output.index("have not been reviewed")
        )

    def test_completed_units_are_printed_before_the_error_when_a_later_unit_fails(self):
        self.tools.failing.add(("unmutated", "test_alpha_again"))
        status, output = self.sweep()
        self.assertEqual(mull_sweep.COULD_NOT_LOOK, status)
        self.assertEqual([7.0, 3.0, 50.0, 2.0], figures(output, ALPHA))
        # The failed unit is not a completed one, and is not offered as one.
        self.assertFalse(
            [line for line in output.splitlines() if line.strip().startswith(ALPHA_AGAIN + " ")]
        )
        self.assertLess(
            output.index("mull_sweep: time per unit"),
            output.index("'test_alpha_again' does not pass"),
        )

    def test_completed_units_are_printed_when_a_later_unit_fails_in_a_way_nothing_anticipated(self):
        # A runner report cut off part-way is not refused by name anywhere: it
        # escapes as the error reading it raised. The unit that finished before
        # it still has its timing printed, ahead of that error, and the error is
        # what it was rather than one the timing turned it into.
        self.tools.truncated.add("test_alpha_again")
        error, output = self.sweep_raising(summary=self.summary)
        self.assertIsInstance(error, json.JSONDecodeError)
        self.assertEqual([7.0, 3.0, 50.0, 2.0], figures(output, ALPHA))
        self.assertEqual([7.0, 3.0, 50.0, 2.0], summary_figures(self.written_summary(), ALPHA))

    def test_the_summary_is_written_when_the_hosted_environment_provides_one(self):
        status, output = self.sweep(summary=self.summary)
        self.assertEqual(0, status, output)
        written = self.written_summary()
        self.assertEqual([7.0, 3.0, 50.0, 2.0], summary_figures(written, ALPHA))
        self.assertEqual([11.0, 2.0, 130.0, 3.0], summary_figures(written, ALPHA_AGAIN))
        self.assertEqual([18.0, 5.0, 180.0, 5.0], summary_figures(written, mull_sweep.TOTAL))

    def test_no_summary_is_written_when_the_hosted_environment_provides_none(self):
        # Run from an empty directory, so a summary written to some default
        # path of its own instead of to none would land where it shows.
        elsewhere = os.path.join(self.scratch.name, "elsewhere")
        os.makedirs(elsewhere)
        self.addCleanup(os.chdir, os.getcwd())
        os.chdir(elsewhere)
        status, output = self.sweep()
        self.assertEqual(0, status, output)
        self.assertEqual(["elsewhere"], os.listdir(self.scratch.name))
        self.assertEqual([], os.listdir(elsewhere))
        self.assertNotIn("job summary", output)

    def test_an_empty_summary_variable_is_no_summary_rather_than_a_failed_write(self):
        status, output = self.sweep(summary="")
        self.assertEqual(0, status, output)
        self.assertNotIn("job summary", output)

    def test_a_phases_figure_is_in_the_summary_before_the_next_phase_starts(self):
        seen: dict[str, str] = {}

        def snapshot(command):
            text = open(self.summary, encoding="utf-8").read() if os.path.exists(self.summary) else ""
            if command[0] == "pio" and "--without-building" in command:
                seen.setdefault("unmutated starts", text)
            elif command[0] == "mull-runner":
                seen.setdefault("runner starts", text)

        self.tools.observers.append(snapshot)
        status, output = self.sweep(summary=self.summary)
        self.assertEqual(0, status, output)
        self.assertIn(f"`{ALPHA}` build: 7.0 s", seen["unmutated starts"])
        self.assertNotIn("unmutated run:", seen["unmutated starts"])
        self.assertIn(f"`{ALPHA}` unmutated run: 3.0 s", seen["runner starts"])
        self.assertNotIn("mutation runner:", seen["runner starts"])
        self.assertIn(f"`{ALPHA}` mutation runner: 50.0 s", self.written_summary())

    def test_a_unit_stopped_part_way_leaves_its_finished_phases_in_the_summary(self):
        # What a job its time limit stops looks like from the summary: the
        # phases that finished are there, though the unit never completed.
        self.tools.failing.add(("unmutated", "test_alpha_again"))
        self.sweep(summary=self.summary)
        self.assertIn(f"`{ALPHA_AGAIN}` build: 11.0 s", self.written_summary())

    def test_an_unwritable_summary_leaves_the_exit_status_unchanged(self):
        for outcome in ("Killed", "Survived"):
            self.tools.status = outcome
            expected, _ = self.sweep()
            # A directory where the summary file should be: opened for
            # appending, it refuses.
            status, output = self.sweep(summary=self.scratch.name)
            self.assertEqual(expected, status, outcome)
            # Said once and then left alone, not retried and warned about at
            # every phase and again at the table.
            self.assertEqual(1, output.count("cannot be written"), output)
            self.assertEqual([7.0, 3.0, 50.0, 2.0], figures(output, ALPHA))

    def verdict(self, output: str) -> str:
        """What the sweep printed after its timing table: its verdict, and nothing of the timing."""
        flat = " ".join(output.split())
        return flat[flat.index(mull_sweep.RUNNING_NOTE) + len(mull_sweep.RUNNING_NOTE):]

    def test_a_suite_listed_twice_reaches_the_verdict_it_reaches_listed_once_with_both_runs_timed(self):
        # Both copies are built and run, as they always were, and their results
        # folded and judged. The timing takes in both runs as they happened; a
        # record refusing the second would turn a judged run into one the sweep
        # could not look at.
        for outcome in ("Killed", "Survived"):
            self.tools.status = outcome
            options = mutation_environment("alpha", "test_alpha")
            self.tree.declare([("native_alpha_mutation", options)])
            once_status, once = self.sweep()
            options["test_filter"] = "test_alpha,test_alpha"
            self.tree.declare([("native_alpha_mutation", options)])
            twice_status, twice = self.sweep()
            self.assertEqual(once_status, twice_status, twice)
            self.assertNotEqual(mull_sweep.COULD_NOT_LOOK, twice_status, twice)
            self.assertEqual(self.verdict(once), self.verdict(twice))
            rows = [
                [float(cell) for cell in line.split()[1:]]
                for line in twice.splitlines()
                if line.strip().startswith(ALPHA + " ")
            ]
            self.assertEqual([[7.0, 3.0, 50.0, 2.0]] * 2, rows)
            self.assertEqual([14.0, 6.0, 100.0, 4.0], figures(twice, mull_sweep.TOTAL))

    def test_only_a_run_stopped_by_an_error_labels_its_table_partial(self):
        status, output = self.sweep(summary=self.summary)
        self.assertEqual(0, status, output)
        self.assertNotIn(mull_sweep.PARTIAL, output)
        self.assertNotIn(mull_sweep.PARTIAL, self.written_summary())
        os.remove(self.summary)

        self.tools.failing.add(("unmutated", "test_alpha_again"))
        status, output = self.sweep(summary=self.summary)
        self.assertEqual(mull_sweep.COULD_NOT_LOOK, status, output)
        self.assertIn(f"mull_sweep: time per unit ({mull_sweep.PARTIAL})", output)
        self.assertIn(mull_sweep.STOPPED_NOTE, " ".join(output.split()))
        written = self.written_summary()
        self.assertIn(f"### mull_sweep: time per unit ({mull_sweep.PARTIAL})", written)
        self.assertIn(mull_sweep.STOPPED_NOTE, written)

    def test_a_run_stopped_by_an_error_nothing_anticipated_labels_its_table_partial(self):
        self.tools.truncated.add("test_alpha_again")
        error, output = self.sweep_raising(summary=self.summary)
        self.assertIsInstance(error, json.JSONDecodeError)
        self.assertIn(f"mull_sweep: time per unit ({mull_sweep.PARTIAL})", output)
        self.assertIn(mull_sweep.STOPPED_NOTE, self.written_summary())


class AShardReportsItsTimingForTheMerge(SweepHarness):
    """SOL-SWEEP-TIME-ACCOUNTED.C1: each hosted shard times its own unit, and the merge totals every shard's.

    A shard's report carries its mutant results and its timing as two named
    parts, so a report that lost either is refused rather than judged without
    it or totalled without it.
    """

    SHARD = "native_alpha_mutation:test_alpha_again:src/plant/alpha:cxx_add_to_sub"

    def setUp(self):
        super().setUp()
        self.reports = os.path.join(self.scratch.name, "reports")
        os.makedirs(self.reports)

    def shard(self, suite: str, directory: str, name: str, summary: str | None = None):
        return self.sweep(
            "--shard", f"native_alpha_mutation:{suite}",
            "--shard-directory", directory,
            "--shard-mutators", "cxx_add_to_sub",
            "--shard-report", os.path.join(self.reports, f"{name}.json"),
            summary=summary,
        )

    def write(self, name: str, document) -> None:
        with open(os.path.join(self.reports, name), "w", encoding="utf-8") as handle:
            json.dump(document, handle)

    def test_a_shards_report_carries_its_mutants_and_its_timing_as_two_parts(self):
        status, output = self.shard("test_alpha_again", "src/plant/alpha", "one")
        self.assertEqual(0, status, output)
        with open(os.path.join(self.reports, "one.json"), encoding="utf-8") as handle:
            report = json.load(handle)
        self.assertEqual({"mutants", "timing"}, set(report))
        self.assertEqual(3, len(report["mutants"]))
        self.assertEqual(
            {
                "identity": {
                    "environment": "native_alpha_mutation",
                    "suite": "test_alpha_again",
                    "directory": "src/plant/alpha",
                    "operator": "cxx_add_to_sub",
                },
                "listing": False,
                "seconds": {"build": 11.0, "unmutated": 2.0, "runner": 130.0},
                "mutants": 3,
            },
            report["timing"],
        )
        self.assertEqual([11.0, 2.0, 130.0, 3.0], figures(output, self.SHARD))

    def test_a_shard_writes_its_own_row_to_its_job_summary(self):
        status, output = self.shard("test_alpha_again", "src/plant/alpha", "one", self.summary)
        self.assertEqual(0, status, output)
        self.assertEqual(
            [11.0, 2.0, 130.0, 3.0], summary_figures(self.written_summary(), self.SHARD)
        )

    def test_the_merged_table_covers_every_shard_with_their_total(self):
        self.shard("test_alpha", "src/plant/common", "one")
        self.shard("test_alpha_again", "src/plant/alpha", "two")
        status, output = self.sweep("--merge-reports", self.reports, summary=self.summary)
        self.assertEqual(0, status, output)
        first = "native_alpha_mutation:test_alpha:src/plant/common:cxx_add_to_sub"
        self.assertEqual([7.0, 3.0, 50.0, 2.0], figures(output, first))
        self.assertEqual([11.0, 2.0, 130.0, 3.0], figures(output, self.SHARD))
        self.assertEqual([18.0, 5.0, 180.0, 5.0], figures(output, mull_sweep.TOTAL))
        self.assertIn("covers the shard rows only", output)
        written = self.written_summary()
        self.assertEqual([18.0, 5.0, 180.0, 5.0], summary_figures(written, mull_sweep.TOTAL))
        self.assertIn("covers the shard rows only", written)
        self.assertLess(
            output.index("mull_sweep: time per unit"), output.index("mull_sweep: 3 mutants")
        )

    def assertRefused(self, part: str) -> str:
        status, output = self.sweep("--merge-reports", self.reports)
        self.assertEqual(mull_sweep.COULD_NOT_LOOK, status, output)
        self.assertIn("bad.json", output)
        self.assertIn(part, output)
        return output

    def test_a_report_missing_its_timing_is_refused(self):
        self.write("bad.json", {"mutants": {}})
        self.assertRefused("no 'timing' part")

    def test_a_report_missing_its_mutant_results_is_refused(self):
        self.write("bad.json", {"timing": timing_entry("test_alpha")})
        self.assertRefused("no 'mutants' part")

    def test_a_report_in_the_shape_before_timing_is_refused_rather_than_folded(self):
        # A flat mapping of mutant to finding, as every shard wrote before its
        # report carried timing: read as it used to be, its mutants would be
        # judged and its shard left out of the total.
        self.write("bad.json", {"m": survivor("m")})
        self.assertRefused("no 'mutants' part")

    def test_a_report_timing_anything_but_one_row_is_refused(self):
        # A shard times one unit and writes its one row: none, several, or a
        # list holding the one is not what a shard writes.
        for timing in ([], [timing_entry("test_alpha")], [timing_entry("a"), timing_entry("b")]):
            self.write("bad.json", {"mutants": {}, "timing": timing})
            output = self.assertRefused("not the one unit's row a shard writes")
            self.assertNotIn("time per unit", output, repr(timing))

    def test_a_timing_entry_missing_a_figure_is_refused(self):
        entry = timing_entry("test_alpha")
        del entry["seconds"]["runner"]
        self.write("bad.json", {"mutants": {}, "timing": entry})
        self.assertRefused("does not time exactly the phases build, unmutated, runner")

    def test_a_shard_failing_unmutated_cannot_look_and_its_build_is_in_its_summary(self):
        self.tools.failing.add(("unmutated", "test_alpha_again"))
        status, output = self.shard("test_alpha_again", "src/plant/alpha", "one", self.summary)
        self.assertEqual(mull_sweep.COULD_NOT_LOOK, status, output)
        self.assertIn("'test_alpha_again' does not pass", output)
        written = self.written_summary()
        self.assertIn(f"`{self.SHARD}` build: 11.0 s", written)
        self.assertNotIn("unmutated run:", written)
        self.assertFalse(os.path.exists(os.path.join(self.reports, "one.json")))

    def test_a_shard_that_fails_after_its_unit_completed_still_prints_its_row(self):
        # The unit finished, and then its results could not be read: the error
        # escapes as it was, with the row printed ahead of it.
        self.tools.malformed.add("test_alpha_again")
        error, output = self.sweep_raising(
            "--shard", "native_alpha_mutation:test_alpha_again",
            "--shard-directory", "src/plant/alpha",
            "--shard-mutators", "cxx_add_to_sub",
            "--shard-report", os.path.join(self.reports, "one.json"),
        )
        self.assertIsInstance(error, KeyError)
        self.assertEqual([11.0, 2.0, 130.0, 3.0], figures(output, self.SHARD))

    def shard_report(self, **entry) -> dict:
        """A shard's report as the shard path writes it, with its one row changed as given."""
        row = timing_entry("test_alpha")
        row.update(entry)
        return {"mutants": {}, "timing": row}

    def test_a_figure_that_is_not_a_finite_number_is_refused(self):
        # json.load reads NaN and Infinity, and neither is less than zero.
        for bad in (float("nan"), float("inf"), float("-inf")):
            report = self.shard_report()
            report["timing"]["seconds"]["build"] = bad
            self.write("bad.json", report)
            output = self.assertRefused("no usable build figure")
            self.assertNotIn("time per unit", output, repr(bad))

    def test_a_discovery_row_in_a_shard_report_is_refused(self):
        # The merged total covers shard rows only; a listing row folded in
        # would be totalled with them.
        self.write("bad.json", self.shard_report(listing=True))
        self.assertRefused("discovery unit")

    def test_a_row_carrying_a_field_a_shard_does_not_write_is_refused(self):
        self.write("bad.json", self.shard_report(weight=2))
        self.assertRefused("does not carry exactly")

    def test_a_row_timing_a_phase_a_shard_does_not_have_is_refused(self):
        report = self.shard_report()
        report["timing"]["seconds"]["install"] = 40.0
        self.write("bad.json", report)
        self.assertRefused("does not time exactly the phases")

    def test_a_row_not_keyed_by_a_shards_identity_is_refused(self):
        for identity in (
            {"environment": "native_alpha_mutation"},
            {"environment": "native_alpha_mutation", "directory": "src/plant/alpha"},
            {"environment": "native_alpha_mutation", "suite": "test_alpha", "host": "runner-1"},
            {"environment": "native_alpha_mutation", "suite": ""},
        ):
            self.write("bad.json", self.shard_report(identity=identity))
            self.assertRefused("is not keyed by a shard's")

    def test_a_mutant_count_that_is_not_a_whole_number_is_refused(self):
        for bad in (2.0, float("nan"), -1, True, None):
            self.write("bad.json", self.shard_report(mutants=bad))
            self.assertRefused("no usable mutant count")

    def test_a_report_carrying_a_part_a_shard_does_not_write_is_refused(self):
        report = self.shard_report()
        report["population"] = 303
        self.write("bad.json", report)
        self.assertRefused("parts a shard does not write: population")

    def test_two_reports_timing_the_same_unit_are_refused_rather_than_totalled_twice(self):
        # The same shard uploaded under two names. Its identity written in
        # another order is still the same unit.
        self.shard("test_alpha_again", "src/plant/alpha", "a-good")
        with open(os.path.join(self.reports, "a-good.json"), encoding="utf-8") as handle:
            report = json.load(handle)
        report["timing"]["identity"] = dict(reversed(report["timing"]["identity"].items()))
        self.write("bad.json", report)
        output = self.assertRefused("which an earlier report already timed")
        self.assertEqual([11.0, 2.0, 130.0, 3.0], figures(output, self.SHARD))
        self.assertEqual([11.0, 2.0, 130.0, 3.0], figures(output, mull_sweep.TOTAL))

    def test_the_shards_read_before_a_refused_one_are_printed_before_the_refusal(self):
        self.shard("test_alpha_again", "src/plant/alpha", "a-good")
        self.write("bad.json", {"mutants": {}})
        output = self.assertRefused("no 'timing' part")
        self.assertEqual([11.0, 2.0, 130.0, 3.0], figures(output, self.SHARD))
        self.assertLess(output.index("mull_sweep: time per unit"), output.index("bad.json"))

    def test_a_table_cut_short_by_a_refused_report_is_labelled_partial_in_both_renderings(self):
        # Read as the full total, the table of the shards read before the
        # refusal would understate the sweep by every shard after it.
        self.shard("test_alpha_again", "src/plant/alpha", "a-good")
        self.write("bad.json", {"mutants": {}})
        status, output = self.sweep("--merge-reports", self.reports, summary=self.summary)
        self.assertEqual(mull_sweep.COULD_NOT_LOOK, status, output)
        written = self.written_summary()
        self.assertIn(f"mull_sweep: time per unit ({mull_sweep.PARTIAL})", output)
        self.assertIn(f"### mull_sweep: time per unit ({mull_sweep.PARTIAL})", written)
        self.assertIn(mull_sweep.STOPPED_NOTE, " ".join(output.split()))
        self.assertIn(mull_sweep.STOPPED_NOTE, written)
        self.assertEqual([11.0, 2.0, 130.0, 3.0], summary_figures(written, mull_sweep.TOTAL))

    def test_a_merge_that_read_every_report_is_not_labelled_partial(self):
        # The triage record is read after every report has been: its refusal
        # stops the merge, but the table it printed covers every shard.
        self.shard("test_alpha", "src/plant/common", "one")
        self.shard("test_alpha_again", "src/plant/alpha", "two")
        with open(os.path.join(self.project, mull_sweep.TRIAGE_RECORD), "w", encoding="utf-8") as handle:
            handle.write("judgements:\n  a: fine\n")
        status, output = self.sweep("--merge-reports", self.reports, summary=self.summary)
        self.assertEqual(mull_sweep.COULD_NOT_LOOK, status, output)
        self.assertIn("no 'survivors' mapping", output)
        self.assertEqual([18.0, 5.0, 180.0, 5.0], figures(output, mull_sweep.TOTAL))
        self.assertNotIn(mull_sweep.PARTIAL, output)
        self.assertNotIn(mull_sweep.PARTIAL, self.written_summary())
        self.assertLess(output.index("mull_sweep: time per unit"), output.index("no 'survivors'"))


class DiscoveryTimesItsListing(SweepHarness):
    """SOL-SWEEP-TIME-ACCOUNTED.C1: discovering a directory's operators is a timed unit of its own.

    Its third figure is the runner listing mutants rather than running them, and
    its count is of mutants listed. Labelled as a sweep row it would read as a
    shard that ran its mutants in a fraction of the time.
    """

    PAIR = "native_alpha_mutation:src/plant/alpha"

    def discover(self, summary: str | None = None):
        self.tools.mutants["test_alpha"] = 4
        out = os.path.join(self.scratch.name, "mutators.json")
        status, output = self.sweep(
            "--list-mutators-in", self.PAIR, "--list-mutators-out", out, summary=summary
        )
        with open(out, encoding="utf-8") as handle:
            return status, output, json.load(handle)

    def test_a_discovery_row_carries_its_listing_time_and_listed_count(self):
        status, output, mutators = self.discover()
        self.assertEqual(0, status, output)
        self.assertEqual(["cxx_add_to_sub"], mutators)
        self.assertEqual([7.0, 3.0, 50.0, 4.0], figures(output, self.PAIR))
        self.assertIn("listing (s)", output)
        self.assertIn("mutants listed", output)
        self.assertNotIn("mutant runs", output)
        self.assertIn("--dry-run", self.tools.runner_calls()[0])

    def test_a_discovery_failing_unmutated_cannot_look_and_its_build_is_in_its_summary(self):
        self.tools.failing.add(("unmutated", "test_alpha"))
        status, output = self.sweep(
            "--list-mutators-in", self.PAIR,
            "--list-mutators-out", os.path.join(self.scratch.name, "mutators.json"),
            summary=self.summary,
        )
        self.assertEqual(mull_sweep.COULD_NOT_LOOK, status, output)
        self.assertIn("'test_alpha' does not pass", output)
        written = self.written_summary()
        self.assertIn(f"`{self.PAIR}` build: 7.0 s", written)
        self.assertNotIn("unmutated run:", written)

    def test_a_discovery_row_is_written_to_the_discovery_jobs_summary(self):
        status, output, _ = self.discover(self.summary)
        self.assertEqual(0, status, output)
        written = self.written_summary()
        self.assertEqual([7.0, 3.0, 50.0, 4.0], summary_figures(written, self.PAIR))
        self.assertIn("mutants listed", written)
        self.assertIn(f"`{self.PAIR}` listing: 50.0 s", written)


class TheTwoRenderingsCarryTheSameFigures(unittest.TestCase):
    """SOL-SWEEP-TIME-ACCOUNTED.C1: the plain-text table and the summary table are one rendering of the same figures.

    Figures that do not fall on a tenth of a second are used on purpose, so
    rounding done differently in the two would show.
    """

    def units(self):
        running = []
        for suite, seconds, mutants in (
            ("one", (7.24, 3.05, 50.96), 12),
            ("two", (0.04, 0.04, 0.04), 1),
        ):
            unit = mull_sweep.UnitTiming({"environment": "e", "suite": suite})
            unit.seconds = dict(zip(mull_sweep.PHASES, seconds))
            unit.mutants = mutants
            running.append(unit)
        listed = mull_sweep.UnitTiming({"environment": "e", "directory": "d"}, listing=True)
        listed.seconds = dict(zip(mull_sweep.PHASES, (1.0, 2.0, 4.0)))
        listed.mutants = 9
        return running + [listed]

    def test_both_renderings_carry_the_same_figures(self):
        units = self.units()
        text = mull_sweep.timing_table(units)
        markdown = mull_sweep.timing_table(units, markdown=True)
        for label in ("e:one", "e:two", "e:d"):
            self.assertEqual(figures(text, label), summary_figures(markdown, label), label)
        self.assertEqual([7.2, 3.0, 51.0, 12.0], figures(text, "e:one"))

    def test_both_totals_are_the_sum_of_the_rows_as_printed(self):
        # Two units of 0.04 s print as 0.0 each; a total summed before
        # rounding would print 0.1 under them.
        running = self.units()[:2]
        text = mull_sweep.timing_table(running)
        markdown = mull_sweep.timing_table(running, markdown=True)
        expected = [7.2, 3.0, 51.0, 13.0]
        self.assertEqual(expected, figures(text, mull_sweep.TOTAL))
        self.assertEqual(expected, summary_figures(markdown, mull_sweep.TOTAL))

    def test_running_and_listing_units_are_tabled_apart_with_their_own_totals(self):
        text = mull_sweep.timing_table(self.units())
        self.assertIn("mull_sweep: time per unit", text)
        self.assertIn("mull_sweep: time per discovery unit", text)
        self.assertEqual(2, text.count(mull_sweep.TOTAL))

    def test_both_renderings_carry_the_same_notes(self):
        units = self.units()
        text = " ".join(mull_sweep.timing_table(units, note=mull_sweep.MERGED_NOTE).split())
        markdown = " ".join(
            mull_sweep.timing_table(units, markdown=True, note=mull_sweep.MERGED_NOTE).split()
        )
        for note in (mull_sweep.RUNNING_NOTE, mull_sweep.LISTING_NOTE, mull_sweep.MERGED_NOTE):
            self.assertIn(note, text)
            self.assertIn(note, markdown)

    def test_a_unit_survives_the_round_trip_through_a_shard_report(self):
        unit = self.units()[0]
        back = mull_sweep.UnitTiming.from_shard_report(json.loads(json.dumps(unit.as_dict())))
        self.assertEqual(unit.as_dict(), back.as_dict())

    def test_a_timing_entry_with_a_figure_that_is_not_a_usable_time_is_refused(self):
        for bad in (-1.0, True, "7", None, float("nan"), float("inf")):
            entry = timing_entry("one")
            entry["seconds"]["build"] = bad
            with self.assertRaises(mull_sweep.SweepError, msg=repr(bad)):
                mull_sweep.UnitTiming.from_shard_report(entry)


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



# --- The round's sweep: the mutants on the lines a branch changes -------------


class ScopedTools(FakeTools):
    """FakeTools whose runner draws mutants the way the plugin does: from the tree, within the scope.

    Every `+` in a C source the derived scope takes in is one mutant, at its own
    line and column, so a mutant moves when its line does and disappears with
    its file; a line saying `survives` carries a mutant no test kills. With
    `ignore_scope` set the runner reports every source, as a scope that never
    reached the compiler would.
    """

    def __init__(self, project: str):
        super().__init__(project)
        self.ignore_scope = False

    def run(self, command, cwd=None, env=None, check=False, capture_output=False, text=False):
        if command[0] != "mull-runner":
            return super().run(command, cwd, env, check, capture_output, text)
        for observe in self.observers:
            observe(command)
        self.commands.append(command)
        self.now += self.RUNNER[self.suite]
        scope = mull_sweep.load_yaml(env["MULL_CONFIG"])
        includes, excludes = scope["includePaths"] or [], scope["excludePaths"] or []
        files = {}
        for source in mull_sweep.sources_under(os.path.join(self.project, "src")):
            if not self.ignore_scope and not mull_sweep.in_scope(source, includes, excludes):
                continue
            with open(source, encoding="utf-8") as handle:
                lines = handle.read().splitlines()
            mutants = [
                {
                    "id": f"{number}:{column}",
                    "mutatorName": "cxx_add_to_sub",
                    "replacement": "-",
                    "location": {"start": {"line": number, "column": column}},
                    "status": "Survived" if "survives" in line else "Killed",
                }
                for number, line in enumerate(lines, start=1)
                for column in [index + 1 for index, character in enumerate(line) if character == "+"]
            ]
            if mutants:
                files[source] = {"mutants": mutants}
        reports = command[command.index("--report-dir") + 1]
        with open(os.path.join(reports, "sweep.json"), "w", encoding="utf-8") as handle:
            json.dump({"files": files}, handle)
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")


STRUCTURE = "src/plant/alpha/plant_structure.c"
SHARED = "src/plant/common/plant_step.c"

#: The structure's source as main holds it: three mutants killed, one judged
#: survivor on line 3, and one survivor on line 5 nobody has judged -- which the
#: full sweep would fail on, and which a branch not touching line 5 is not asked
#: about.
STRUCTURE_SOURCE = (
    "float a(float x) { return x + 1.0f; }\n"
    "float b(float x) { return x + 2.0f; }\n"
    "float c(float x) { return x + 3.0f; } /* survives */\n"
    "float d(float x) { return x; }\n"
    "float e(float x) { return x + 5.0f; } /* survives */\n"
)
SHARED_SOURCE = (
    "float advance(float x) { return x + x; } /* survives */\n"
    "float other(float x) { return x + 2.0f; }\n"
)


def mutant(source: str, line: int, column: int) -> str:
    return f"cxx_add_to_sub:{source}:{line}:{column}"


#: Where the `+` sits on every one-letter function line written here, and on
#: the shared source's first line.
COLUMN = STRUCTURE_SOURCE.splitlines()[0].index("+") + 1
JUDGED_STRUCTURE = mutant(STRUCTURE, 3, COLUMN)
JUDGED_SHARED = mutant(SHARED, 1, SHARED_SOURCE.splitlines()[0].index("+") + 1)


class ChangedLinesHarness(unittest.TestCase):
    """A synthetic project that is also a repository, on a branch off its main.

    The changed lines are measured by the round gate's own measurement and
    written by its own writer, so the sweep is driven with exactly what the
    round would hand it; only the build and the mutant runner are stood in for.
    """

    def setUp(self):
        self.tree = PopulationTree()
        self.addCleanup(self.tree.cleanup)
        self.project = os.path.realpath(self.tree.root)
        self.write(STRUCTURE, STRUCTURE_SOURCE)
        self.write(SHARED, SHARED_SOURCE)
        self.judge({JUDGED_STRUCTURE: "equivalent", JUDGED_SHARED: "equivalent"})
        self.git("init", "-q", "-b", "main")
        self.commit("baseline")
        self.git("update-ref", "refs/remotes/origin/main", "HEAD")
        self.git("checkout", "-q", "-b", "feature")

        self.tools = ScopedTools(self.project)
        self.resolved = []
        self.toolchain_error: str | None = None

        def resolved(warn=None):
            self.resolved.append(True)
            if self.toolchain_error:
                raise mull_toolchain.ToolchainError(self.toolchain_error)
            return {"runner": "mull-runner"}

        original_resolved = mull_sweep.mull_toolchain.resolved
        mull_sweep.mull_toolchain.resolved = resolved
        self.addCleanup(setattr, mull_sweep.mull_toolchain, "resolved", original_resolved)
        inherited = os.environ.pop("GITHUB_STEP_SUMMARY", None)
        if inherited is not None:
            self.addCleanup(os.environ.__setitem__, "GITHUB_STEP_SUMMARY", inherited)
        self.scratch = tempfile.TemporaryDirectory()
        self.addCleanup(self.scratch.cleanup)
        self.summary = os.path.join(self.scratch.name, "summary.md")

    def git(self, *arguments: str) -> str:
        return subprocess.run(
            ["git", "-C", self.project, *arguments],
            capture_output=True, text=True, check=True, env=GIT_ENVIRONMENT,
        ).stdout

    def commit(self, message: str) -> None:
        self.git("add", "-A")
        self.git("commit", "-q", "--allow-empty", "-m", message)

    def write(self, relative: str, content: str) -> None:
        full = os.path.join(self.project, relative)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as handle:
            handle.write(content)

    def edit(self, relative: str, line: int, text: str) -> None:
        with open(os.path.join(self.project, relative), encoding="utf-8") as handle:
            lines = handle.read().splitlines()
        lines[line - 1] = text
        self.write(relative, "\n".join(lines) + "\n")

    def judge(self, judgements: dict[str, str]) -> None:
        body = "survivors:\n" + "".join(
            f"  '{name}':\n    verdict: {verdict}\n    reason: synthetic\n"
            for name, verdict in judgements.items()
        )
        self.write(mull_sweep.TRIAGE_RECORD, body)

    def changed_lines(self) -> str:
        change = round_gate.changed(self.project)
        self.assertIsNotNone(change.lines, change.lines_problem)
        path = os.path.join(self.scratch.name, "changed-lines.json")
        round_gate.write_changed_lines(path, change)
        return path

    def run_sweep(self, *extra: str, summary: str | None = None) -> tuple[int, str]:
        if summary is None:
            os.environ.pop("GITHUB_STEP_SUMMARY", None)
        else:
            os.environ["GITHUB_STEP_SUMMARY"] = summary
        argv = [
            "--project", self.tree.root,
            "--plant-root", os.path.relpath(self.tree.plant, self.tree.root),
            "--include-dir", os.path.relpath(self.tree.include, self.tree.root),
            "--pio", "pio",
            *extra,
        ]
        output = io.StringIO()
        original_run = mull_sweep.subprocess.run
        mull_sweep.subprocess.run = self.tools.run
        try:
            with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
                status = mull_sweep.main(argv, clock=self.tools.clock)
        finally:
            mull_sweep.subprocess.run = original_run
            os.environ.pop("GITHUB_STEP_SUMMARY", None)
        return status, output.getvalue()

    def restricted(self, summary: str | None = None, *extra: str) -> tuple[int, str, dict]:
        """Sweep the lines the branch changes, returning the status, the output and the account."""
        lines = self.changed_lines()
        account = os.path.join(self.scratch.name, "account.json")
        status, output = self.run_sweep(
            "--changed-lines", lines, "--changed-lines-result", account, *extra, summary=summary
        )
        with open(account, encoding="utf-8") as handle:
            return status, output, json.load(handle)


class TheRoundSweepsTheMutantsOnTheChangedLines(ChangedLinesHarness):
    def test_a_seeded_surviving_mutant_on_a_changed_line_fails_the_round(self):
        # SOL-SWEEP-CHANGED-PLANT-LINES-IN-ROUND.C1: The round gate sweeps the mutants drawn from the plant lines the branch changes
        self.edit(STRUCTURE, 2, "float b(float x) { return x + 2.5f; } /* survives */")
        status, output, account = self.restricted()
        self.assertEqual(mull_sweep.FOUND_THE_PROBLEM, status, output)
        self.assertIn("1 surviving mutant(s) have not been reviewed", output)
        self.assertIn(mutant(STRUCTURE, 2, COLUMN), output)
        self.assertEqual(
            {"state": "ran", "outcome": "found-a-problem", "files": 1, "lines": 1, "mutants": 1},
            {key: account[key] for key in ("state", "outcome", "files", "lines", "mutants")},
        )

    def test_a_killed_mutant_on_a_changed_line_passes(self):
        # SOL-SWEEP-CHANGED-PLANT-LINES-IN-ROUND.C1: The round gate sweeps the mutants drawn from the plant lines the branch changes
        self.edit(STRUCTURE, 2, "float b(float x) { return x + 2.5f; }")
        status, output, account = self.restricted()
        self.assertEqual(0, status, output)
        self.assertEqual(("ran", "passed"), (account["state"], account["outcome"]))
        self.assertIn("1 mutant(s) on the changed lines, 1 killed by the tests, 0 survived", output)

    def test_an_unchanged_lines_mutants_are_not_drawn(self):
        # SOL-SWEEP-CHANGED-PLANT-LINES-IN-ROUND.C1: The round gate sweeps the mutants drawn from the plant lines the branch changes
        # Line 5's survivor nobody has judged would fail the full sweep. The
        # branch changes line 2 only, so it is not drawn -- and the unchanged
        # file's mutants are not even built.
        self.edit(STRUCTURE, 2, "float b(float x) { return x + 2.5f; }")
        status, output, account = self.restricted()
        self.assertEqual(0, status, output)
        self.assertNotIn(mutant(STRUCTURE, 5, COLUMN), output)
        self.assertIn("1 mutant(s) on the changed lines", output)
        self.assertIn("4 mutant(s) in the changed files altogether", output)
        self.assertEqual(1, account["mutants"])

    def test_the_restricted_population_is_the_full_population_filtered_to_the_changed_lines(self):
        # SOL-SWEEP-CHANGED-PLANT-LINES-IN-ROUND.C1: The round gate sweeps the mutants drawn from the plant lines the branch changes
        self.edit(STRUCTURE, 1, "float a(float x) { return x + 1.5f; } /* survives */")
        self.edit(STRUCTURE, 5, "float e(float x) { return x + 5.5f; } /* survives */")
        self.write("src/plant/alpha/added.c", "float f(float x) { return x + 6.0f; } /* survives */\n")
        status, full = self.run_sweep("--survivors-only")
        self.assertEqual(0, status, full)
        changed = {(STRUCTURE, 1), (STRUCTURE, 5), ("src/plant/alpha/added.c", 1)}
        expected = sorted(
            name for name in re.findall(r"\[(\S+)\]", full)
            if (mull_sweep.judged_source(name), int(name.split(":")[-2])) in changed
        )
        status, output, _ = self.restricted(None, "--survivors-only")
        self.assertEqual(0, status, output)
        self.assertEqual(expected, sorted(re.findall(r"\[(\S+)\]", output)))
        self.assertEqual(3, len(expected))

    def test_every_line_of_a_new_file_not_yet_committed_is_drawn(self):
        # SOL-SWEEP-CHANGED-PLANT-LINES-IN-ROUND.C1: The round gate sweeps the mutants drawn from the plant lines the branch changes
        self.write(
            "src/plant/alpha/added.c",
            "float f(float x) { return x + 6.0f; }\nfloat g(float x) { return x + 7.0f; } /* survives */\n",
        )
        status, output, account = self.restricted()
        self.assertEqual(mull_sweep.FOUND_THE_PROBLEM, status, output)
        self.assertIn(mutant("src/plant/alpha/added.c", 2, COLUMN), output)
        self.assertEqual((1, 2, 2), (account["files"], account["lines"], account["mutants"]))

    def test_a_judgement_outside_the_changed_files_is_not_reported_stale(self):
        # SOL-SWEEP-CHANGED-PLANT-LINES-IN-ROUND.C1: The round gate sweeps the mutants drawn from the plant lines the branch changes
        # A judgement about a mutant the shared file no longer carries would be
        # stale to the full sweep; the branch does not touch that file.
        gone = mutant(SHARED, 9, 1)
        self.judge({JUDGED_STRUCTURE: "equivalent", JUDGED_SHARED: "equivalent", gone: "equivalent"})
        self.edit(STRUCTURE, 2, "float b(float x) { return x + 2.5f; }")
        status, output, _ = self.restricted()
        self.assertEqual(0, status, output)
        self.assertNotIn(gone, output)
        self.assertNotIn("judgement(s) in", output)

    def test_a_judgement_stranded_by_lines_moving_in_a_changed_file_fails_the_round(self):
        # SOL-SWEEP-CHANGED-PLANT-LINES-IN-ROUND.C1: The round gate sweeps the mutants drawn from the plant lines the branch changes
        # Deleting the first line moves the judged survivor from line 3 to 2,
        # and leaves line 3 carrying no mutant. The branch changes no line that
        # is left -- the hunk only deletes -- and the judgement no longer names
        # a mutant: it is checked against the file's whole current population.
        self.write(STRUCTURE, "".join(STRUCTURE_SOURCE.splitlines(keepends=True)[1:]))
        status, output, account = self.restricted()
        self.assertEqual(mull_sweep.FOUND_THE_PROBLEM, status, output)
        self.assertIn(
            f"1 judgement(s) in {mull_sweep.TRIAGE_RECORD} {mull_sweep.STALE_IN_CHANGED}", output
        )
        self.assertIn(JUDGED_STRUCTURE, output)
        self.assertIn(f"{STRUCTURE}: lines deleted only", output)
        self.assertNotIn("have not been reviewed", output)
        self.assertEqual((1, 0, 0), (account["files"], account["lines"], account["mutants"]))

    def test_a_judgement_on_an_unchanged_line_of_a_changed_file_still_holds(self):
        # SOL-SWEEP-CHANGED-PLANT-LINES-IN-ROUND.C1: The round gate sweeps the mutants drawn from the plant lines the branch changes
        self.edit(STRUCTURE, 1, "float a(float x) { return x + 1.5f; }")
        status, output, _ = self.restricted()
        self.assertEqual(0, status, output)
        self.assertNotIn(JUDGED_STRUCTURE, output)

    def test_a_deleted_file_strands_every_judgement_about_it_without_building(self):
        # SOL-SWEEP-CHANGED-PLANT-LINES-IN-ROUND.C1: The round gate sweeps the mutants drawn from the plant lines the branch changes
        extra = "src/plant/alpha/extra.c"
        self.write(extra, "float h(float x) { return x + 8.0f; } /* survives */\n")
        self.judge({
            JUDGED_STRUCTURE: "equivalent", JUDGED_SHARED: "equivalent",
            mutant(extra, 1, COLUMN): "equivalent",
        })
        self.commit("extra")
        self.git("update-ref", "refs/remotes/origin/main", "HEAD")
        self.git("rm", "-q", extra)
        self.toolchain_error = "no toolchain on this host"
        status, output, account = self.restricted()
        self.assertEqual(mull_sweep.FOUND_THE_PROBLEM, status, output)
        self.assertIn(mutant(extra, 1, COLUMN), output)
        self.assertIn(mull_sweep.STALE_IN_CHANGED, output)
        self.assertEqual([], self.tools.commands)
        self.assertEqual([], self.resolved)
        self.assertEqual((1, 0), (account["files"], account["lines"]))

    def test_deleting_the_last_source_of_a_shared_directory_strands_its_judgements(self):
        # SOL-SWEEP-CHANGED-PLANT-LINES-IN-ROUND.C1: The round gate sweeps the mutants drawn from the plant lines the branch changes
        # The directory leaves the population with its last source, so the
        # file is no longer one the sweep derives -- and its judgement is still
        # stranded, as the full sweep would find.
        self.git("rm", "-q", SHARED)
        status, output, account = self.restricted()
        self.assertEqual(mull_sweep.FOUND_THE_PROBLEM, status, output)
        self.assertIn(JUDGED_SHARED, output)
        self.assertIn(f"{SHARED}: no longer in the population", output)
        self.assertEqual("ran", account["state"])

    def test_a_branch_changing_no_population_line_runs_no_sweep_and_needs_no_toolchain(self):
        # SOL-SWEEP-CHANGED-PLANT-LINES-IN-ROUND.C1: The round gate sweeps the mutants drawn from the plant lines the branch changes
        self.toolchain_error = "no toolchain on this host"
        self.write("src/control/loop.c", "int loop(void) { return 1 + 1; }\n")
        self.write("README.md", "notes\n")
        self.write("src/plant/alpha/notes.md", "a + b\n")
        status, output, account = self.restricted()
        self.assertEqual(0, status, output)
        self.assertEqual(("skipped", "skipped"), (account["state"], account["outcome"]))
        self.assertIn("the branch changes no line in the population", output)
        self.assertEqual([], self.tools.commands)
        self.assertEqual([], self.resolved)

    def test_a_population_change_without_the_toolchain_fails_saying_it_is_missing(self):
        # SOL-SWEEP-CHANGED-PLANT-LINES-IN-ROUND.C1: The round gate sweeps the mutants drawn from the plant lines the branch changes
        self.toolchain_error = "no clang-19 was found"
        self.edit(STRUCTURE, 2, "float b(float x) { return x + 2.5f; }")
        status, output, account = self.restricted()
        self.assertEqual(mull_sweep.COULD_NOT_LOOK, status, output)
        self.assertIn("the mutation toolchain is missing: no clang-19 was found", output)
        self.assertTrue(account["toolchain_missing"])
        self.assertEqual(("could-not-run", "could-not-look"), (account["state"], account["outcome"]))
        self.assertEqual([], self.tools.commands)

    def test_a_scope_that_did_not_reach_the_compiler_is_refused(self):
        # SOL-SWEEP-CHANGED-PLANT-LINES-IN-ROUND.C1: The round gate sweeps the mutants drawn from the plant lines the branch changes
        self.tools.ignore_scope = True
        self.edit(STRUCTURE, 2, "float b(float x) { return x + 2.5f; }")
        status, output, _ = self.restricted()
        self.assertEqual(mull_sweep.FOUND_THE_PROBLEM, status, output)
        self.assertIn("was not restricted to them", output)
        self.assertIn(SHARED, output)

    def test_the_build_is_handed_a_scope_naming_only_the_changed_files(self):
        # SOL-SWEEP-CHANGED-PLANT-LINES-IN-ROUND.C1: The round gate sweeps the mutants drawn from the plant lines the branch changes
        scopes = []
        original = self.tools.run

        def capture(command, cwd=None, env=None, **rest):
            if command[0] == "pio" and "--without-testing" in command:
                scopes.append(mull_sweep.load_yaml(env["MULL_CONFIG"]))
            return original(command, cwd, env, **rest)

        self.tools.run = capture
        self.edit(STRUCTURE, 2, "float b(float x) { return x + 2.5f; }")
        status, output, _ = self.restricted()
        self.assertEqual(0, status, output)
        self.assertEqual(1, len(scopes))
        (included,) = scopes[0]["includePaths"]
        self.assertTrue(re.search(included, os.path.join(self.project, STRUCTURE)))
        self.assertFalse(re.search(included, os.path.join(self.project, SHARED)))
        self.assertFalse(re.search(included, os.path.join(self.project, "src/plant/alpha/other.c")))
        self.assertEqual([".*/test/.*"], scopes[0]["excludePaths"])

    def test_the_restricted_run_reports_its_time_through_the_same_record(self):
        # SOL-SWEEP-CHANGED-PLANT-LINES-IN-ROUND.C1: The round gate sweeps the mutants drawn from the plant lines the branch changes
        self.edit(STRUCTURE, 2, "float b(float x) { return x + 2.5f; }")
        status, output, _ = self.restricted(self.summary)
        self.assertEqual(0, status, output)
        # Built 7 s, run unmutated 3 s, runner 50 s, and the four mutants the
        # changed file carries were run.
        self.assertEqual([7.0, 3.0, 50.0, 4.0], figures(output, ALPHA))
        self.assertEqual([7.0, 3.0, 50.0, 4.0], summary_figures(self.written_summary(), ALPHA))
        self.assertIn(mull_sweep.RESTRICTED_NOTE, output)
        self.assertLess(output.index("time per unit"), output.index("mutant(s) on the changed lines"))

    def written_summary(self) -> str:
        with open(self.summary, encoding="utf-8") as handle:
            return handle.read()


class TheChangedLinesAreReadOnlyAsTheGateWritesThem(ChangedLinesHarness):
    def account_after(self, document: object) -> tuple[int, str, dict]:
        path = os.path.join(self.scratch.name, "changed-lines.json")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(document if isinstance(document, str) else json.dumps(document))
        account = os.path.join(self.scratch.name, "account.json")
        status, output = self.run_sweep("--changed-lines", path, "--changed-lines-result", account)
        with open(account, encoding="utf-8") as handle:
            return status, output, json.load(handle)

    def test_a_document_that_is_not_the_gates_cannot_be_looked_at(self):
        # SOL-SWEEP-CHANGED-PLANT-LINES-IN-ROUND.C1: The round gate sweeps the mutants drawn from the plant lines the branch changes
        for document in (
            "not json",
            [1, 2],
            {"files": {}},
            {"root": "relative/root", "files": {}},
            {"root": self.project, "files": []},
            {"root": self.project, "files": {STRUCTURE: [0]}},
            {"root": self.project, "files": {STRUCTURE: [True]}},
            {"root": self.project, "files": {STRUCTURE: "2"}},
        ):
            with self.subTest(document=document):
                status, output, account = self.account_after(document)
                self.assertEqual(mull_sweep.COULD_NOT_LOOK, status, output)
                self.assertEqual("could-not-run", account["state"])
                self.assertEqual("could-not-look", account["outcome"])
                self.assertEqual([], self.tools.commands)

    def test_a_result_path_without_changed_lines_is_refused(self):
        # SOL-SWEEP-CHANGED-PLANT-LINES-IN-ROUND.C1: The round gate sweeps the mutants drawn from the plant lines the branch changes
        status, output = self.run_sweep("--changed-lines-result", os.path.join(self.scratch.name, "x"))
        self.assertEqual(mull_sweep.COULD_NOT_LOOK, status)
        self.assertIn("--changed-lines-result needs --changed-lines", output)

    def test_a_run_unable_to_draw_the_population_leaves_an_account_that_could_not_look(self):
        # SOL-SWEEP-CHANGED-PLANT-LINES-IN-ROUND.C1: The round gate sweeps the mutants drawn from the plant lines the branch changes
        os.remove(os.path.join(self.tree.include, "plant_machine_claim.h"))
        status, output, account = self.account_after({"root": self.project, "files": {STRUCTURE: [2]}})
        self.assertEqual(mull_sweep.COULD_NOT_LOOK, status, output)
        self.assertEqual(("could-not-run", "could-not-look"), (account["state"], account["outcome"]))
        self.assertIn("stopped before it could tell", account["detail"])

    def test_a_population_problem_found_before_sweeping_leaves_an_account_of_a_finding(self):
        # SOL-SWEEP-CHANGED-PLANT-LINES-IN-ROUND.C1: The round gate sweeps the mutants drawn from the plant lines the branch changes
        self.tree.describe("beta", None)
        status, output, account = self.account_after({"root": self.project, "files": {STRUCTURE: [2]}})
        self.assertEqual(mull_sweep.FOUND_THE_PROBLEM, status, output)
        self.assertEqual(("could-not-run", "found-a-problem"), (account["state"], account["outcome"]))

    def test_a_run_ended_by_an_error_nothing_anticipated_leaves_an_account_that_could_not_look(self):
        # SOL-SWEEP-CHANGED-PLANT-LINES-IN-ROUND.C1: The round gate sweeps the mutants drawn from the plant lines the branch changes
        self.edit(STRUCTURE, 2, "float b(float x) { return x + 2.5f; }")
        lines = self.changed_lines()
        account = os.path.join(self.scratch.name, "account.json")
        original = ScopedTools.run

        def unanticipated(tools, command, *rest, **named):
            if command[0] == "mull-runner":
                raise KeyError("location")
            return original(tools, command, *rest, **named)

        ScopedTools.run = unanticipated
        self.addCleanup(setattr, ScopedTools, "run", original)
        with self.assertRaises(KeyError):
            self.run_sweep("--changed-lines", lines, "--changed-lines-result", account)
        with open(account, encoding="utf-8") as handle:
            self.assertEqual("could-not-look", json.load(handle)["outcome"])


class OnlyTheDerivedPopulationsFilesAreChanged(unittest.TestCase):
    def setUp(self):
        self.tree = PopulationTree()
        self.addCleanup(self.tree.cleanup)
        self.project = os.path.realpath(self.tree.root)
        directories = mull_sweep.shared_directories(self.tree.plant) + [
            structure.directory for structure in self.tree.described()[0]
        ]
        self.includes = [
            mull_sweep.scope_pattern(self.project, os.path.realpath(directory))
            for directory in directories
        ]

    def population(self, root: str, files: dict) -> dict:
        return mull_sweep.changed_population(self.project, root, files, self.includes, [".*/test/.*"])

    def test_only_sources_inside_the_project_and_its_population_are_kept(self):
        # SOL-SWEEP-CHANGED-PLANT-LINES-IN-ROUND.C1: The round gate sweeps the mutants drawn from the plant lines the branch changes
        self.assertEqual(
            {"src/plant/alpha/a.c": [1], "src/plant/common/b.h": [2, 3]},
            self.population(self.project, {
                "src/plant/alpha/a.c": [1],
                "src/plant/common/b.h": [3, 2, 3],
                "src/plant/alpha/notes.md": [1],
                "src/plant/beta/c.c": [1],
                "src/control/loop.c": [1],
                "include/plant_model.h": [1],
            }),
        )

    def test_a_like_named_tree_outside_the_project_is_not_the_population(self):
        # SOL-SWEEP-CHANGED-PLANT-LINES-IN-ROUND.C1: The round gate sweeps the mutants drawn from the plant lines the branch changes
        parent = os.path.dirname(self.project)
        name = os.path.basename(self.project)
        self.assertEqual(
            {"src/plant/alpha/a.c": [4]},
            self.population(parent, {
                f"{name}/src/plant/alpha/a.c": [4],
                "elsewhere/src/plant/alpha/a.c": [4],
            }),
        )

    def test_a_triage_key_names_its_source(self):
        # SOL-SWEEP-CHANGED-PLANT-LINES-IN-ROUND.C1: The round gate sweeps the mutants drawn from the plant lines the branch changes
        self.assertEqual(STRUCTURE, mull_sweep.judged_source(mutant(STRUCTURE, 3, COLUMN)))
        self.assertEqual("", mull_sweep.judged_source("not-a-key"))

    def test_line_numbers_are_printed_as_the_runs_they_form(self):
        # SOL-SWEEP-CHANGED-PLANT-LINES-IN-ROUND.C1: The round gate sweeps the mutants drawn from the plant lines the branch changes
        self.assertEqual("1-3, 5, 7-8", mull_sweep.spans([1, 2, 3, 5, 7, 8]))
        self.assertEqual("", mull_sweep.spans([]))

if __name__ == "__main__":
    unittest.main()
