#!/usr/bin/env python3
"""The gates guarding the seams discover their subjects rather than being given them.

Every case here is driven against a synthetic tree: a build file declaring
environments that exist nowhere, structures with no code behind them, and
artefacts that are shell scripts. That is deliberate. A gate that could only be
exercised by starting a real build could not be shown to fail, and these are
the gates whose whole purpose is to fail when something has been forgotten.

The cases fall into three groups: what the build file is read to say, that each
converted gate reaches a subject nobody named, and that each converted gate
stops rather than reporting success when it discovers nothing at all.
"""

from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)

import build_environments  # noqa: E402
import check_sanitizers  # noqa: E402
import run_host_artefacts  # noqa: E402
from test_plant_checks import (  # noqa: E402
    SyntheticTree,
    declare_environments,
    host_environment,
    run_check,
)


def executable_script(path: str, body: str) -> str:
    """A file that runs, standing in for something the build would have produced."""
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("#!/bin/sh\n" + body)
    os.chmod(path, os.stat(path).st_mode | stat.S_IEXEC)
    return path


# --- What the build file is read to say -------------------------------------


class BuildFileResolution(unittest.TestCase):
    """SOL-PLANT-SEAM-GATE-COVERAGE.C2: what an environment declares, resolved as the build resolves it.

    A gate reading the build file has to agree with the build about what an
    environment says, or it covers something other than what is built. The
    inheritance and reference forms the real file uses are what is asserted
    here, along with refusing rather than guessing when a reference names
    something absent.
    """

    def setUp(self):
        self.project = tempfile.TemporaryDirectory()
        self.addCleanup(self.project.cleanup)

    def write(self, content: str) -> str:
        path = os.path.join(self.project.name, "platformio.ini")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(content)
        return self.project.name

    def test_an_environment_inherits_what_it_extends(self):
        self.write(
            "[base]\nplatform = native\nbuild_src_filter = +<control/>\n\n"
            "[env:host]\nextends = base\n"
        )
        (environment,) = build_environments.load(self.project.name)
        self.assertEqual("native", environment.platform)
        self.assertEqual("+<control/>", environment.source_filter)

    def test_an_environments_own_value_wins_over_the_inherited_one(self):
        self.write(
            "[base]\nplatform = native\nbuild_src_filter = +<control/>\nbuild_src_flags = -Wall\n\n"
            "[env:host]\nextends = base\nbuild_src_flags = -Werror\n"
        )
        (environment,) = build_environments.load(self.project.name)
        self.assertEqual("-Werror", environment.source_flags)

    def test_a_reference_to_another_sections_value_is_substituted(self):
        self.write(
            "[common]\nsources = +<control/>\n\n"
            "[base]\nplatform = native\nbuild_src_filter = ${common.sources} +<hw/sim/>\n\n"
            "[env:host]\nextends = base\n"
            "build_src_filter = ${base.build_src_filter} +<plant/alpha/>\n"
        )
        (environment,) = build_environments.load(self.project.name)
        self.assertEqual("+<control/> +<hw/sim/> +<plant/alpha/>", environment.source_filter)

    def test_a_reference_to_the_section_it_is_written_in_is_substituted(self):
        self.write(
            "[env:host]\nplatform = native\nsources = +<control/>\n"
            "build_src_filter = ${this.sources} +<app/native/>\n"
        )
        (environment,) = build_environments.load(self.project.name)
        self.assertEqual("+<control/> +<app/native/>", environment.source_filter)

    def test_a_reference_to_something_absent_is_refused_rather_than_emptied(self):
        # Substituting nothing would silently drop a term of the filter, and a
        # filter missing a term is a build compiling something else. The message
        # is asserted too: one naming an inheritance that does not exist sends
        # the reader to the wrong line.
        self.write("[env:host]\nplatform = native\nbuild_src_filter = ${common.sources}\n")
        with self.assertRaisesRegex(
            build_environments.ConfigurationError, r"\$\{common\.sources\}.*not declared"
        ):
            build_environments.load(self.project.name)

    def test_a_host_environment_leaving_its_filter_to_the_default_is_refused(self):
        # PlatformIO would compile everything under src/. Reading the absence as
        # "compiles nothing" would drop the environment out of every set a gate
        # covers without a word, which is the silence all of this exists against.
        self.write("[env:host]\nplatform = native\n")
        with self.assertRaisesRegex(build_environments.ConfigurationError, "build_src_filter"):
            build_environments.load(self.project.name)

    def test_multiple_parents_are_inherited_in_order(self):
        self.write(
            "[first]\nplatform = native\nbuild_src_filter = +<a/>\nbuild_src_flags = -Wall\n\n"
            "[second]\nbuild_src_filter = +<b/>\n\n"
            "[env:host]\nextends = first, second\n"
        )
        (environment,) = build_environments.load(self.project.name)
        self.assertEqual("+<b/>", environment.source_filter)
        self.assertEqual("-Wall", environment.source_flags)

    def test_a_value_wrapped_over_several_lines_is_read_as_one(self):
        self.write(
            "[env:host]\nplatform = native\n"
            "build_src_filter =\n    +<control/>\n    +<app/native/>\n"
        )
        (environment,) = build_environments.load(self.project.name)
        self.assertEqual("+<control/> +<app/native/>", environment.source_filter)

    def test_extending_something_absent_is_refused(self):
        self.write("[env:host]\nextends = missing\n")
        with self.assertRaises(build_environments.ConfigurationError):
            build_environments.load(self.project.name)

    def test_an_inheritance_cycle_is_reported_rather_than_followed(self):
        self.write("[a]\nextends = b\n\n[b]\nextends = a\n\n[env:host]\nextends = a\n")
        with self.assertRaises(build_environments.ConfigurationError):
            build_environments.load(self.project.name)

    def test_a_missing_build_file_is_reported(self):
        with self.assertRaises(build_environments.ConfigurationError):
            build_environments.load(self.project.name)

    def test_sections_that_are_not_environments_are_not_environments(self):
        self.write(
            "[platformio]\ndefault_envs = host\n\n"
            "[env:host]\nplatform = native\nbuild_src_filter = +<control/>\n"
        )
        self.assertEqual(["host"], [e.name for e in build_environments.load(self.project.name)])


class EnvironmentClassification(unittest.TestCase):
    """SOL-PLANT-SEAM-GATE-COVERAGE.C2: which environments a gate finds, and which it leaves alone.

    Each set a gate covers is defined by a property the environment declares,
    so that adding an environment puts it in the right set without anybody
    editing a gate. The sets are asserted here against one tree carrying every
    shape the real build file carries.
    """

    def setUp(self):
        self.project = tempfile.TemporaryDirectory()
        self.addCleanup(self.project.cleanup)
        declare_environments(
            self.project.name,
            [
                ("host", host_environment("alpha")),
                ("host_second", host_environment("beta")),
                (
                    "host_refused",
                    host_environment(None, custom_must_not_build="it names no structure"),
                ),
                (
                    "host_test",
                    host_environment(
                        "alpha",
                        entry_point=False,
                        test_build_src="yes",
                        custom_strict_flags_exemption="the runner's support file comes through here",
                    ),
                ),
                ("target", {"platform": "ststm32", "build_src_filter": "+<control/>"}),
            ],
        )
        self.environments = build_environments.load(self.project.name)

    def named(self, environments):
        return [environment.name for environment in environments]

    def test_the_target_build_is_not_a_host_environment(self):
        self.assertNotIn("target", self.named(build_environments.host_environments(self.environments)))

    def test_every_host_environment_is_covered_including_the_one_running_tests(self):
        self.assertEqual(
            ["host", "host_second", "host_test"],
            self.named(build_environments.host_environments(self.environments)),
        )

    def test_an_environment_required_to_be_refused_is_left_alone_with_its_reason(self):
        self.assertNotIn(
            "host_refused", self.named(build_environments.host_environments(self.environments))
        )
        (refused,) = build_environments.refused_environments(self.environments)
        self.assertEqual("host_refused", refused.name)
        self.assertIn("names no structure", refused.must_not_build_reason)

    def test_only_environments_linking_the_host_entry_point_produce_an_artefact(self):
        self.assertEqual(
            ["host", "host_second"],
            self.named(build_environments.artefact_environments(self.environments)),
        )

    def test_only_environments_compiling_the_sources_into_the_runner_run_tests(self):
        self.assertEqual(
            ["host_test"], self.named(build_environments.test_environments(self.environments))
        )

    def test_each_environment_reports_the_structure_it_selects(self):
        selected = {
            environment.name: environment.structure(["alpha", "beta"])
            for environment in self.environments
        }
        self.assertEqual("alpha", selected["host"])
        self.assertEqual("beta", selected["host_second"])
        self.assertIsNone(selected["host_refused"])
        self.assertIsNone(selected["target"])

    def test_a_filter_taking_a_directory_wholesale_includes_the_entry_point(self):
        environment = build_environments.Environment(
            name="host", options={"platform": "native", "build_src_filter": "+<app/>"}
        )
        self.assertTrue(environment.links_host_entry_point)

    def test_a_filter_taking_the_entry_point_back_out_does_not_link_it(self):
        # Reading only the additions would report an entry point the artefact
        # does not have, and the run task would then hand it a description it
        # cannot take.
        environment = build_environments.Environment(
            name="host",
            options={"platform": "native", "build_src_filter": "+<app/> -<app/native/>"},
        )
        self.assertFalse(environment.links_host_entry_point)

    def test_the_artefact_and_its_objects_are_where_the_build_puts_them(self):
        (host,) = [e for e in self.environments if e.name == "host"]
        self.assertEqual(
            os.path.join("p", ".pio", "build", "host", "program"), host.artefact("p")
        )
        self.assertEqual(
            os.path.join("p", ".pio", "build", "host", "src", "control"),
            host.objects_under("p", os.path.join("src", "control")),
        )


# --- The analysis gate ------------------------------------------------------


class AnalysisCoversEveryHostEnvironment(unittest.TestCase):
    """SOL-PLANT-SEAM-GATE-COVERAGE.C2: every environment producing a host artefact is verified.

    SOL-PLANT-SEAM-GATE-COVERAGE.C3: the strict warning settings are required where they can be scoped.

    The compilation database each environment would produce is supplied by a
    stand-in for the build system, so the gate's own judgement is exercised
    rather than the host's toolchain: what matters is which environments it
    asks about and what it demands of each.
    """

    def setUp(self):
        self.project = tempfile.TemporaryDirectory()
        self.addCleanup(self.project.cleanup)
        self.source_directory = os.path.join(self.project.name, "src", "control")
        os.makedirs(self.source_directory)
        self.source = os.path.join(self.source_directory, "control.c")
        with open(self.source, "w", encoding="utf-8") as handle:
            handle.write("int control;\n")

        self.databases = os.path.join(self.project.name, "databases")
        os.makedirs(self.databases)
        self.log = os.path.join(self.project.name, "asked.log")
        self.pio = executable_script(
            os.path.join(self.project.name, "pio"),
            f'echo "$3" >> "{self.log}"\n'
            f'cp "{self.databases}/$3.json" compile_commands.json\n',
        )

    def database(self, environment: str, flags) -> None:
        entries = [
            {
                "directory": self.project.name,
                "file": self.source,
                "arguments": ["cc", *flags, "-c", self.source],
            }
        ]
        with open(os.path.join(self.databases, f"{environment}.json"), "w", encoding="utf-8") as h:
            json.dump(entries, h)

    def check(self):
        return run_check(
            "check_sanitizers.py", "--project", self.project.name, "--pio", self.pio
        )

    def asked(self) -> list[str]:
        if not os.path.exists(self.log):
            return []
        with open(self.log, "r", encoding="utf-8") as handle:
            return handle.read().split()

    ANALYSED = check_sanitizers.SANITIZER_FLAGS + check_sanitizers.STRICT_FLAGS

    def test_every_host_environment_is_asked_about_without_being_named(self):
        declare_environments(
            self.project.name,
            [
                ("host", host_environment("alpha", entry_point=False)),
                ("host_second", host_environment("beta", entry_point=False)),
            ],
        )
        self.database("host", self.ANALYSED)
        self.database("host_second", self.ANALYSED)
        result = self.check()
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(["host", "host_second"], self.asked())

    def test_an_environment_added_later_is_covered_with_no_change_to_the_invocation(self):
        # The failure this removes: an environment that drops the analysis
        # after the gate's invocation was written, and nothing notices.
        declare_environments(
            self.project.name,
            [
                ("host", host_environment("alpha", entry_point=False)),
                ("host_added_later", host_environment("beta", entry_point=False)),
            ],
        )
        self.database("host", self.ANALYSED)
        self.database("host_added_later", check_sanitizers.STRICT_FLAGS)
        result = self.check()
        self.assertEqual(1, result.returncode)
        self.assertIn("host_added_later", result.stderr)
        self.assertIn("-fsanitize=address,undefined", result.stderr)

    def test_an_environment_required_to_be_refused_is_not_required_to_build_cleanly(self):
        declare_environments(
            self.project.name,
            [
                ("host", host_environment("alpha", entry_point=False)),
                (
                    "host_refused",
                    host_environment(None, custom_must_not_build="it names no structure"),
                ),
            ],
        )
        self.database("host", self.ANALYSED)
        result = self.check()
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertNotIn("host_refused", self.asked())
        self.assertIn("it names no structure", result.stdout)

    def test_the_strict_settings_are_required_where_nothing_foreign_shares_the_path(self):
        declare_environments(
            self.project.name, [("host", host_environment("alpha", entry_point=False))]
        )
        self.database("host", check_sanitizers.SANITIZER_FLAGS)
        result = self.check()
        self.assertEqual(1, result.returncode)
        self.assertIn("-Werror", result.stderr)

    def test_an_environment_compiling_the_runners_sources_may_drop_them_with_a_reason(self):
        declare_environments(
            self.project.name,
            [
                (
                    "host_test",
                    host_environment(
                        "alpha",
                        entry_point=False,
                        test_build_src="yes",
                        custom_strict_flags_exemption="the runner's generated support file "
                        "is compiled through this path",
                    ),
                )
            ],
        )
        self.database("host_test", check_sanitizers.SANITIZER_FLAGS)
        result = self.check()
        self.assertEqual(0, result.returncode, result.stderr)

    def test_the_exemption_does_not_excuse_the_analysis_itself(self):
        declare_environments(
            self.project.name,
            [
                (
                    "host_test",
                    host_environment(
                        "alpha",
                        entry_point=False,
                        test_build_src="yes",
                        custom_strict_flags_exemption="the runner's support file comes through here",
                    ),
                )
            ],
        )
        self.database("host_test", check_sanitizers.STRICT_FLAGS)
        result = self.check()
        self.assertEqual(1, result.returncode)
        self.assertIn("-fsanitize=address,undefined", result.stderr)

    def test_an_exemption_on_an_environment_that_could_hold_them_is_refused(self):
        # Otherwise the exemption is a way of turning the settings off rather
        # than an admission that they cannot be held.
        declare_environments(
            self.project.name,
            [
                (
                    "host",
                    host_environment(
                        "alpha",
                        entry_point=False,
                        custom_strict_flags_exemption="they are inconvenient",
                    ),
                )
            ],
        )
        self.database("host", check_sanitizers.SANITIZER_FLAGS)
        result = self.check()
        self.assertEqual(1, result.returncode)
        self.assertIn("it can carry them", result.stderr)


class TheArtefactIsInspectedForTheRuntime(unittest.TestCase):
    """SOL-PLANT-SEAM-GATE-COVERAGE.C2: an artefact that links no sanitizer runtime is found.

    Instrumented compilation and a linked runtime are separate conditions and
    either can hold while the other does not, so the artefact of every
    environment that links one is inspected. The environment leaving its entry
    point to the test runner has no artefact of its own here, and is not
    required to produce one -- it is run, under the same analysis, by the task
    that runs the tests.
    """

    @classmethod
    def setUpClass(cls):
        cls.compiler = os.environ.get("CC", "clang")
        if subprocess.run([cls.compiler, "--version"], capture_output=True, check=False).returncode:
            raise unittest.SkipTest(f"{cls.compiler} is not available on this host")

    def setUp(self):
        self.project = tempfile.TemporaryDirectory()
        self.addCleanup(self.project.cleanup)
        self.source_directory = os.path.join(self.project.name, "src", "control")
        os.makedirs(self.source_directory)
        self.source = os.path.join(self.source_directory, "control.c")
        with open(self.source, "w", encoding="utf-8") as handle:
            handle.write("int main(void) { return 0; }\n")

        self.databases = os.path.join(self.project.name, "databases")
        os.makedirs(self.databases)
        self.pio = executable_script(
            os.path.join(self.project.name, "pio"),
            f'cp "{self.databases}/$3.json" compile_commands.json\n',
        )

    def database(self, environment: str) -> None:
        entries = [
            {
                "directory": self.project.name,
                "file": self.source,
                "arguments": [
                    "cc",
                    *check_sanitizers.SANITIZER_FLAGS,
                    *check_sanitizers.STRICT_FLAGS,
                    "-c",
                    self.source,
                ],
            }
        ]
        with open(os.path.join(self.databases, f"{environment}.json"), "w", encoding="utf-8") as h:
            json.dump(entries, h)

    def artefact(self, environment: str, *flags: str) -> str:
        directory = os.path.join(self.project.name, ".pio", "build", environment)
        os.makedirs(directory, exist_ok=True)
        binary = os.path.join(directory, "program")
        subprocess.run([self.compiler, *flags, "-o", binary, self.source], check=True)
        return binary

    def check(self):
        return run_check("check_sanitizers.py", "--project", self.project.name, "--pio", self.pio)

    def test_an_artefact_linking_the_runtime_passes(self):
        declare_environments(self.project.name, [("host", host_environment("alpha"))])
        self.database("host")
        self.artefact("host", "-fsanitize=address,undefined")
        result = self.check()
        self.assertEqual(0, result.returncode, result.stderr)

    def test_an_artefact_linking_no_runtime_is_found(self):
        # Compiled under the analysis and linked without it: the flags read
        # clean and nothing would be reported at run time.
        declare_environments(self.project.name, [("host", host_environment("alpha"))])
        self.database("host")
        self.artefact("host")
        result = self.check()
        self.assertEqual(1, result.returncode)
        self.assertIn("links no sanitizer runtime", result.stderr)

    def test_an_artefact_that_has_not_been_built_is_could_not_look_not_a_pass(self):
        # Distinct from a finding, and distinct from success: the gate has to
        # say it could not look, or a tree with no artefacts reads as clean.
        declare_environments(self.project.name, [("host", host_environment("alpha"))])
        self.database("host")
        result = self.check()
        self.assertEqual(2, result.returncode)
        self.assertIn("has not been built", result.stderr)

    def test_the_environment_leaving_its_entry_point_to_the_runner_needs_no_artefact(self):
        declare_environments(
            self.project.name,
            [("host_test", host_environment("alpha", entry_point=False, test_build_src="yes"))],
        )
        self.database("host_test")
        result = self.check()
        self.assertEqual(0, result.returncode, result.stderr)

    def test_a_build_database_that_cannot_be_produced_is_could_not_look(self):
        declare_environments(self.project.name, [("host", host_environment("alpha"))])
        self.artefact("host", "-fsanitize=address,undefined")
        result = self.check()
        self.assertEqual(2, result.returncode)
        self.assertIn("no compilation database", result.stderr)


# --- Running what was built -------------------------------------------------


class EveryHostArtefactIsExecuted(unittest.TestCase):
    """SOL-PLANT-SEAM-GATE-COVERAGE.C5: an artefact built under the analysis is run under it.

    A sanitizer reports nothing until the code runs, so the environments whose
    artefact takes a parameter description are discovered and each is run
    against every description its own structure ships.
    """

    def setUp(self):
        self.tree = SyntheticTree()
        self.addCleanup(self.tree.cleanup)
        self.params = os.path.join(self.tree.root.name, "params")
        os.makedirs(self.params)
        self.log = os.path.join(self.tree.root.name, "ran.log")

    def description(self, name: str) -> str:
        path = os.path.join(self.params, name)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("coefficient = 1.0\n")
        return path

    def artefact(self, environment: str, body: str = "") -> str:
        return executable_script(
            self.tree.artefact(environment), f'echo "{environment} $1" >> "{self.log}"\n' + body
        )

    def ran(self) -> list[str]:
        if not os.path.exists(self.log):
            return []
        with open(self.log, "r", encoding="utf-8") as handle:
            return [line.strip() for line in handle if line.strip()]

    def run_artefacts(self):
        return run_check(
            "run_host_artefacts.py",
            "--project",
            self.tree.root.name,
            "--plant-root",
            self.tree.plant,
            "--include-dir",
            self.tree.include,
            "--params-dir",
            self.params,
        )

    def test_every_artefact_runs_against_every_description_its_structure_ships(self):
        self.tree.declare(
            [
                ("host_alpha", host_environment("alpha")),
                ("host_beta", host_environment("beta")),
            ]
        )
        self.artefact("host_alpha")
        self.artefact("host_beta")
        nominal = self.description("alpha.params")
        variant = self.description("alpha-variant.params")
        beta = self.description("beta.params")

        result = self.run_artefacts()
        self.assertEqual(0, result.returncode, result.stderr)
        # In name order, which is the order the descriptions are discovered in.
        self.assertEqual(
            [f"host_alpha {variant}", f"host_alpha {nominal}", f"host_beta {beta}"],
            self.ran(),
        )

    def test_an_environment_added_later_is_run_with_no_change_to_the_invocation(self):
        self.tree.structure("gamma")
        self.tree.declare(
            [
                ("host_alpha", host_environment("alpha")),
                ("host_gamma", host_environment("gamma")),
            ]
        )
        self.artefact("host_alpha")
        self.artefact("host_gamma")
        self.description("alpha.params")
        self.description("gamma.params")

        result = self.run_artefacts()
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("host_gamma", " ".join(self.ran()))

    def test_the_environment_leaving_its_entry_point_to_the_runner_is_not_run_here(self):
        # Its artefact takes no description, so there is nothing to hand it. It
        # is run, under the same analysis, by the task that runs the tests.
        self.tree.declare(
            [
                ("host_alpha", host_environment("alpha")),
                ("host_test", host_environment("alpha", entry_point=False, test_build_src="yes")),
            ]
        )
        self.artefact("host_alpha")
        self.artefact("host_test")
        self.description("alpha.params")

        result = self.run_artefacts()
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(1, len(self.ran()))

    def test_a_structure_shipping_no_description_stops_rather_than_skipping_its_artefact(self):
        self.tree.declare([("host_alpha", host_environment("alpha"))])
        self.artefact("host_alpha")
        result = self.run_artefacts()
        self.assertEqual(2, result.returncode)
        self.assertIn("ships no parameter description", result.stderr)

    def test_an_artefact_that_has_not_been_built_stops_rather_than_being_skipped(self):
        self.tree.declare([("host_alpha", host_environment("alpha"))])
        self.description("alpha.params")
        result = self.run_artefacts()
        self.assertEqual(2, result.returncode)
        self.assertIn("has not been built", result.stderr)

    def test_a_run_that_fails_fails_the_task(self):
        self.tree.declare([("host_alpha", host_environment("alpha"))])
        self.artefact("host_alpha", "exit 1\n")
        self.description("alpha.params")
        result = self.run_artefacts()
        self.assertEqual(1, result.returncode)
        self.assertIn("exited 1", result.stderr)

    def test_a_description_no_structure_claims_is_reported_rather_than_left_unrun(self):
        # Renaming a description out of the convention is how one drops out of
        # the analysis: it still looks like part of it and takes no part in it.
        self.tree.declare([("host_alpha", host_environment("alpha"))])
        self.artefact("host_alpha")
        self.description("alpha.params")
        self.description("alpha_variant.params")
        result = self.run_artefacts()
        self.assertEqual(1, result.returncode)
        self.assertIn("alpha_variant.params", result.stderr)
        self.assertIn("belong to no structure", result.stderr)

    def test_a_description_belongs_to_the_whole_of_a_structures_name(self):
        # `thermo` must not inherit `thermoblock`'s descriptions, which is what
        # a bare prefix match would give it.
        for name in ("thermo.params", "thermoblock.params", "thermoblock-variant.params"):
            self.description(name)
        self.assertEqual(
            ["thermo.params"],
            [os.path.basename(p) for p in run_host_artefacts.descriptions_for("thermo", self.params)],
        )
        self.assertEqual(
            ["thermoblock-variant.params", "thermoblock.params"],
            [
                os.path.basename(p)
                for p in run_host_artefacts.descriptions_for("thermoblock", self.params)
            ],
        )


class TheTestTaskDiscoversItsEnvironments(unittest.TestCase):
    """SOL-PLANT-SEAM-GATE-COVERAGE.C6: tests run because they exist, not because a line names them.

    A forgotten test environment leaves nothing behind to notice -- no missing
    artefact, no error, just tests that never ran. So the environments are
    discovered from the property the build file already carries.
    """

    def setUp(self):
        self.project = tempfile.TemporaryDirectory()
        self.addCleanup(self.project.cleanup)
        self.log = os.path.join(self.project.name, "ran.log")
        self.pio = executable_script(
            os.path.join(self.project.name, "pio"), f'echo "$3" >> "{self.log}"\n'
        )

    def ran(self) -> list[str]:
        if not os.path.exists(self.log):
            return []
        with open(self.log, "r", encoding="utf-8") as handle:
            return self.read_names(handle.read())

    @staticmethod
    def read_names(content: str) -> list[str]:
        return [line.strip() for line in content.splitlines() if line.strip()]

    def run_tests(self, pio: str | None = None):
        return run_check(
            "run_host_tests.py", "--project", self.project.name, "--pio", pio or self.pio
        )

    def test_the_environment_carrying_tests_is_run(self):
        declare_environments(
            self.project.name,
            [
                ("host", host_environment("alpha")),
                ("host_test", host_environment("alpha", entry_point=False, test_build_src="yes")),
            ],
        )
        result = self.run_tests()
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(["host_test"], self.ran())

    def test_a_test_environment_added_later_runs_with_no_change_to_the_invocation(self):
        declare_environments(
            self.project.name,
            [
                ("host_test", host_environment("alpha", entry_point=False, test_build_src="yes")),
                (
                    "host_second_test",
                    host_environment("beta", entry_point=False, test_build_src="yes"),
                ),
            ],
        )
        result = self.run_tests()
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(["host_test", "host_second_test"], self.ran())

    def test_a_failing_suite_fails_the_task(self):
        declare_environments(
            self.project.name,
            [("host_test", host_environment("alpha", entry_point=False, test_build_src="yes"))],
        )
        failing = executable_script(os.path.join(self.project.name, "failing_pio"), "exit 1\n")
        result = self.run_tests(pio=failing)
        self.assertEqual(1, result.returncode)
        self.assertIn("host_test", result.stderr)


# --- Nothing to cover is a failure ------------------------------------------


class AGateWithNothingToCoverFails(unittest.TestCase):
    """SOL-PLANT-SEAM-GATE-COVERAGE.C4: a gate that discovers nothing stops rather than passing.

    A gate covering an empty set reports success in exactly the way a gate
    nobody ran does. Each converted gate is driven here against a tree with
    nothing in it for that gate to find, and none of them is allowed to report
    success.
    """

    def setUp(self):
        self.tree = SyntheticTree()
        self.addCleanup(self.tree.cleanup)
        self.params = os.path.join(self.tree.root.name, "params")
        os.makedirs(self.params)

    def declare_nothing(self) -> None:
        self.tree.declare([("target", {"platform": "ststm32", "build_src_filter": "+<control/>"})])

    def test_the_exclusivity_gate_finds_no_artefact_carrying_a_structure(self):
        self.declare_nothing()
        result = run_check(
            "check_structure_exclusive.py",
            "--project",
            self.tree.root.name,
            "--plant-root",
            self.tree.plant,
            "--include-dir",
            self.tree.include,
        )
        self.assertEqual(1, result.returncode)
        self.assertIn("nothing to cover", result.stderr)

    def test_the_direct_call_gate_finds_no_artefact(self):
        self.declare_nothing()
        result = run_check(
            "check_direct_calls.py",
            "--project",
            self.tree.root.name,
            "--header",
            os.path.join(self.tree.include, "plant_model.h"),
            "--objects-in",
            os.path.join("src", "app", "native"),
        )
        self.assertEqual(1, result.returncode)
        self.assertIn("nothing to cover", result.stderr)

    def test_the_analysis_gate_finds_no_host_environment(self):
        self.declare_nothing()
        result = run_check("check_sanitizers.py", "--project", self.tree.root.name)
        self.assertEqual(1, result.returncode)
        self.assertIn("nothing to cover", result.stderr)

    def test_the_run_task_finds_no_artefact_to_run(self):
        self.declare_nothing()
        result = run_check(
            "run_host_artefacts.py",
            "--project",
            self.tree.root.name,
            "--plant-root",
            self.tree.plant,
            "--include-dir",
            self.tree.include,
            "--params-dir",
            self.params,
        )
        self.assertEqual(1, result.returncode)
        self.assertIn("nothing would be run", result.stderr)

    def test_the_test_task_finds_no_environment_carrying_tests(self):
        self.tree.declare([("host", host_environment("alpha"))])
        result = run_check("run_host_tests.py", "--project", self.tree.root.name)
        self.assertEqual(1, result.returncode)
        self.assertIn("no test would run", result.stderr)

    def test_a_tree_with_no_structures_at_all_stops_the_exclusivity_gate(self):
        empty = SyntheticTree(structures=())
        self.addCleanup(empty.cleanup)
        empty.declare([("host", host_environment("alpha"))])
        result = run_check(
            "check_structure_exclusive.py",
            "--project",
            empty.root.name,
            "--plant-root",
            empty.plant,
            "--include-dir",
            empty.include,
        )
        self.assertEqual(2, result.returncode)
        self.assertIn("0 structure(s)", result.stderr)


if __name__ == "__main__":
    unittest.main()
