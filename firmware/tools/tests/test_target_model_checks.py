"""The gates that keep a machine from being built carrying the wrong model.

Two questions are asked here that the host tier never has to ask. A host build
that names a structure describing nothing is a legitimate analysis build; a
build that will be energised carrying those equations is a machine predicting
nothing about itself. And a host build opens the description it is exercised
against, so what it read is answerable afterwards; a target carries the bytes
compiled in, where the one thing that cannot be read back off the running
machine is which description they were.

Both failures are silent on the machine. Predictions that stop matching
observation look exactly like a machine that has drifted, which is the state
the estimator exists to tell apart -- so these are driven against trees that
are wrong in each way rather than reasoned about.

Run with: python3 -m unittest discover -s firmware/tools/tests
"""

from __future__ import annotations

import os
import stat
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

import embedded_description  # noqa: E402
from test_plant_checks import (  # noqa: E402
    TOOLS,
    ClaimTree,
    declare_environments,
    run_check,
    write,
)

#: A description in the language the loader accepts. Its content is never
#: parsed here -- these gates compare bytes -- but a description that reads like
#: one keeps the fixtures honest about what is being carried.
DESCRIPTION = (
    "# A synthetic description.\n"
    "alpha.coefficient = 1.5 ~ 0.1 @estimated From nothing in particular.\n"
)

#: A second description of the same structure, of the kind a tree acquires when
#: a variant is added beside the one the design was established against.
VARIANT = (
    "# A synthetic variant description.\n"
    "alpha.coefficient = 2.5 ~ 0.1 @estimated From nothing in particular either.\n"
)

#: The declaration that travels beside the description: what a reading off the
#: machine may plausibly be. Its content is no more parsed here than the
#: description's is, and it reads like one for the same reason.
LIMITS = (
    "# A synthetic limits declaration.\n"
    "some-channel = -1000 .. 250000 @estimated From nothing in particular.\n"
)

#: A second declaration, for the tree that has acquired one beside the intended
#: one.
LIMITS_VARIANT = (
    "# A synthetic variant limits declaration.\n"
    "some-channel = -2000 .. 300000 @estimated From nothing in particular either.\n"
)


def target_environment(structure: str | None = None, **options):
    """One environment building for a board, as the build file would declare it."""
    terms = ["+<control/>", "+<plant/common/>", "+<hw/board/>", "+<app/board/>"]
    if structure is not None:
        terms.append(f"+<plant/{structure}/>")
    declared = {"platform": "ststm32", "build_src_filter": " ".join(terms)}
    declared.update(options)
    return declared


def carrying_environment(structure: str | None = None, **options):
    """A board environment declaring both of the things an artefact carries.

    The pair is what a build is entitled to declare, so the fixture declares the
    pair. A test about one of them overrides that one, which is what makes the
    tests that leave one out visibly about leaving it out.
    """
    declared = {
        "custom_embedded_description": "params/thermoblock.params",
        "custom_embedded_limits": "params/thermoblock.limits",
    }
    declared.update(options)
    return target_environment(structure, **declared)


def host_test_environment(
    structure: str,
    description: str,
    limits: str = "params/thermoblock.limits",
    **options,
):
    """The host environment that pins the tier to a description, as the build file has it.

    It pins the limits declaration on the same terms and in the same place,
    because that is where the build states it: the two are named separately so
    that a build pinning one and forgetting the other is a state a gate can see.
    """
    declared = {
        "platform": "native",
        "build_src_filter": f"+<control/> +<plant/common/> +<plant/{structure}/> +<app/native/>",
        "build_flags": f"-O1 -D REFERENCE_DESCRIPTION_PATH='\"$PROJECT_DIR/{description}\"'"
        + (f" -D REFERENCE_LIMITS_PATH='\"$PROJECT_DIR/{limits}\"'" if limits else ""),
        "test_build_src": "yes",
    }
    declared.update(options)
    return declared


class TargetModelTree:
    """A tree with structures, descriptions, and a build file naming environments."""

    def __init__(self):
        self.tree = ClaimTree(structures=("thermoblock",))
        self.tree.structure("fixture", "PLANT_DESCRIBES_NO_MACHINE")
        self.root = self.tree.root.name
        self.params = os.path.join(self.root, "params")
        os.makedirs(self.params, exist_ok=True)
        self.describe("thermoblock.params", DESCRIPTION)
        self.describe("thermoblock.limits", LIMITS)
        # The directory every structure shares. It carries no structure header,
        # which is what makes it shared rather than a structure, and the real
        # tree keeps the parameter loader in it.
        os.makedirs(os.path.join(self.tree.plant, "common"), exist_ok=True)
        write(os.path.join(self.tree.plant, "common", "plant_parameters.c"), "/* shared */\n")

    def describe(self, name: str, content: str) -> str:
        path = os.path.join(self.params, name)
        write(path, content)
        return path

    def declare(self, environments) -> str:
        return declare_environments(self.root, environments)

    def generated(self, environment: str) -> str:
        """The directory this environment's build renders into."""
        directory = os.path.join(self.root, ".pio", "build", environment, "generated")
        os.makedirs(directory, exist_ok=True)
        return directory

    def render(
        self,
        environment: str,
        embedding: embedded_description.Embedding,
        source: str,
        data: bytes | None = None,
    ) -> str:
        """Render one embedding the way the build's own script renders it.

        `data` overrides what is carried, so an embedding that has fallen out of
        step with the file it names can be written as one would be found rather
        than described.
        """
        path = os.path.join(self.generated(environment), embedding.generated_name)
        if data is None:
            with open(os.path.join(self.root, source), "rb") as handle:
                data = handle.read()
        write(path, embedded_description.render(source, data, embedding))
        return path

    def generate(
        self,
        environment: str,
        source: str = "params/thermoblock.params",
        data: bytes | None = None,
        limits_source: str = "params/thermoblock.limits",
        limits_data: bytes | None = None,
    ) -> str:
        """Render both embeddings and answer the directory they went into.

        Both, because a build renders both and a fixture rendering one would be
        exercising the gate against a state no build produces. The directory is
        what the gate is offered, so it is what this hands back.
        """
        self.render(environment, embedded_description.DESCRIPTION, source, data)
        self.render(environment, embedded_description.LIMITS, limits_source, limits_data)
        return self.generated(environment)

    def cleanup(self) -> None:
        self.tree.cleanup()


class TargetModelCase(unittest.TestCase):
    def setUp(self):
        self.tree = TargetModelTree()
        self.addCleanup(self.tree.cleanup)


# --- a machine build required to be refused ---------------------------------


class AMachineBuildIsDrivenToBeRefused(TargetModelCase):
    """SOL-ONBOARD-PLANT-MODEL-IDENTITY.C2: a target build naming no plant structure, or more than one, fails rather than choosing.

    The host environments already drive this refusal, and this is not a second
    copy of it. What is established here is that an environment building for a
    machine is in scope on the same terms -- picked up because it declares
    itself refused and not because of what it is called -- and that one nothing
    drives fails the gate rather than sitting there declared and unexercised.
    """

    def fake_pio(self, body: str) -> str:
        path = os.path.join(self.tree.root, "pio")
        write(path, "#!/bin/sh\n" + body)
        os.chmod(path, os.stat(path).st_mode | stat.S_IEXEC)
        return path

    def declare(self, *refused: str):
        self.tree.declare(
            [("board", target_environment("thermoblock"))]
            + [
                (name, target_environment(custom_must_not_build="it names no structure"))
                for name in refused
            ]
        )

    def check(self, pio: str, *envs: str):
        arguments = ["--project", self.tree.root, "--pio", pio]
        for env in envs:
            arguments.extend(["--env", env])
        return run_check("check_selection_refused.py", *arguments)

    def test_a_machine_build_stopping_on_the_selection_check_passes(self):
        self.declare("board_no_structure")
        result = self.check(
            self.fake_pio('echo "check_structure_selection: names no structure"\nexit 1\n'),
            "board_no_structure",
        )
        self.assertEqual(0, result.returncode, result.stderr)

    def test_a_machine_build_that_succeeds_fails_the_check(self):
        """A target that builds carrying no model is the case with no symptom."""
        self.declare("board_no_structure")
        result = self.check(
            self.fake_pio('echo "check_structure_selection: ok"\nexit 0\n'), "board_no_structure"
        )
        self.assertEqual(1, result.returncode)
        self.assertIn("succeeded rather than refusing", result.stderr)

    def test_a_machine_build_stopping_for_another_reason_fails_the_check(self):
        self.declare("board_no_structure")
        result = self.check(
            self.fake_pio('echo "error: something else entirely"\nexit 1\n'), "board_no_structure"
        )
        self.assertEqual(1, result.returncode)

    def test_a_declared_machine_refusal_nobody_drives_fails_the_check(self):
        """Declared and unexercised is the state this gate exists to end."""
        self.declare("board_no_structure", "board_two_structures")
        result = self.check(
            self.fake_pio('echo "check_structure_selection: names no structure"\nexit 1\n'),
            "board_no_structure",
        )
        self.assertEqual(1, result.returncode)
        self.assertIn("board_two_structures", result.stderr)


# --- check_machine_build_settings -------------------------------------------


class AMachineBuildKeepsItsSettings(TargetModelCase):
    """SOL-ONBOARD-PLANT-MODEL-IDENTITY.C6: the plant sources added to a machine build are compiled under that build's own settings.

    The gate that asks this of the host builds covers only those, by design --
    it is about an analysis the host tier runs. Without this the one artefact
    that gets energised is the one nothing asks it of, and the relaxation would
    be a line in a build file nobody reads twice.
    """

    def check(self):
        return run_check(
            "check_machine_build_settings.py",
            "--project",
            self.tree.root,
            "--plant-root",
            self.tree.tree.plant,
        )

    def declare(self, options=None):
        declared = target_environment("thermoblock", build_src_flags="-Werror")
        declared.update(options or {})
        self.tree.declare([("board", declared)])

    def test_a_machine_build_compiling_the_shared_sources_under_settings_passes(self):
        self.declare()
        result = self.check()
        self.assertEqual(0, result.returncode, result.stderr)

    def test_a_machine_build_with_no_settings_for_our_own_sources_fails(self):
        self.declare({"build_src_flags": ""})
        result = self.check()
        self.assertEqual(1, result.returncode)
        self.assertIn("applies no settings", result.stderr)

    def test_a_machine_build_declaring_no_settings_at_all_fails(self):
        declared = target_environment("thermoblock")
        self.tree.declare([("board", declared)])
        result = self.check()
        self.assertEqual(1, result.returncode)
        self.assertIn("applies no settings", result.stderr)

    def test_a_machine_build_claiming_the_host_exemption_fails(self):
        """The exemption is for a build compiling sources that are not ours."""
        self.declare({"custom_strict_flags_exemption": "it would be convenient"})
        result = self.check()
        self.assertEqual(1, result.returncode)
        self.assertIn("turning the settings off", result.stderr)

    def test_a_machine_build_not_compiling_the_shared_sources_fails(self):
        declared = target_environment("thermoblock", build_src_flags="-Werror")
        declared["build_src_filter"] = declared["build_src_filter"].replace(
            "+<plant/common/> ", ""
        )
        self.tree.declare([("board", declared)])
        result = self.check()
        self.assertEqual(1, result.returncode)
        self.assertIn("plant/common", result.stderr)

    def test_shared_sources_taken_back_out_by_a_later_term_fails(self):
        """A filter is what every term leaves, not what one of them adds."""
        declared = target_environment("thermoblock", build_src_flags="-Werror")
        declared["build_src_filter"] += " -<plant/common/>"
        self.tree.declare([("board", declared)])
        result = self.check()
        self.assertEqual(1, result.returncode)
        self.assertIn("plant/common", result.stderr)

    def test_a_shared_directory_named_from_outside_the_root_is_not_read_as_inside_it(self):
        """SOL-FILTER-TERM-READ-IN-ONE-PLACE.C1: this gate reads a term like every other reader does.

        `../plant/common/` is a different directory from `plant/common/`. Read
        as the same one, a machine build compiling none of the shared sources
        is reported as compiling them under its settings. This gate arrived
        carrying its own reading, and this is what holds it to the shared one.
        """
        self.declare(
            {
                "build_src_filter": target_environment("thermoblock")[
                    "build_src_filter"
                ].replace("+<plant/common/>", "+<../plant/common/>")
            }
        )
        result = self.check()
        self.assertEqual(1, result.returncode)
        self.assertIn("plant/common", result.stderr)

    def test_a_host_build_is_not_asked(self):
        """Host environments have their own gate, and one of them holds an exemption."""
        self.tree.declare(
            [
                ("board", target_environment("thermoblock", build_src_flags="-Werror")),
                (
                    "native_test",
                    dict(
                        host_test_environment("thermoblock", "params/thermoblock.params"),
                        build_src_flags="",
                        custom_strict_flags_exemption="the runner's generated support file",
                    ),
                ),
            ]
        )
        result = self.check()
        self.assertEqual(0, result.returncode, result.stderr)

    def test_a_machine_build_required_to_be_refused_is_not_asked(self):
        self.tree.declare(
            [
                ("board", target_environment("thermoblock", build_src_flags="-Werror")),
                (
                    "board_no_structure",
                    target_environment(custom_must_not_build="it names no structure"),
                ),
            ]
        )
        result = self.check()
        self.assertEqual(0, result.returncode, result.stderr)

    def test_a_second_board_is_covered_without_the_invocation_changing(self):
        self.tree.declare(
            [
                ("board", target_environment("thermoblock", build_src_flags="-Werror")),
                ("second_board", target_environment("thermoblock")),
            ]
        )
        result = self.check()
        self.assertEqual(1, result.returncode)
        self.assertIn("second_board", result.stderr)

    def test_a_tree_with_no_machine_build_fails_rather_than_passing_vacuously(self):
        self.tree.declare(
            [("native_test", host_test_environment("thermoblock", "params/thermoblock.params"))]
        )
        result = self.check()
        self.assertEqual(1, result.returncode)
        self.assertIn("nothing to cover", result.stderr)


# --- check_machine_structure_selected ---------------------------------------


class ABuildForAMachineCarriesAMachinesEquations(TargetModelCase):
    """SOL-ONBOARD-PLANT-MODEL-IDENTITY.C1: a machine build compiles one structure, and one describing a machine.

    The count of structures is not the whole question a machine build faces."""

    def check(self):
        return run_check(
            "check_machine_structure_selected.py",
            "--project",
            self.tree.root,
            "--plant-root",
            self.tree.tree.plant,
            "--include-dir",
            self.tree.tree.include,
        )

    def test_a_machine_describing_structure_passes(self):
        self.tree.declare([("board", target_environment("thermoblock"))])
        result = self.check()
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("board", result.stdout)

    def test_a_structure_describing_no_machine_fails_the_count_it_would_satisfy(self):
        self.tree.declare([("board", target_environment("fixture"))])
        result = self.check()
        self.assertEqual(1, result.returncode)
        self.assertIn("fixture", result.stderr)
        self.assertIn("PLANT_DESCRIBES_A_MACHINE", result.stderr)

    def test_a_machine_build_naming_no_structure_fails(self):
        self.tree.declare([("board", target_environment())])
        result = self.check()
        self.assertEqual(1, result.returncode)
        self.assertIn("no single plant structure", result.stderr)

    def test_a_machine_build_naming_two_structures_fails(self):
        both = target_environment("thermoblock")
        both["build_src_filter"] += " +<plant/fixture/>"
        self.tree.declare([("board", both)])
        result = self.check()
        self.assertEqual(1, result.returncode)
        self.assertIn("no single plant structure", result.stderr)

    def test_a_host_build_against_a_structure_describing_no_machine_is_not_asked(self):
        """The fixture exists to be built on the host; only a machine is refused it."""
        self.tree.declare(
            [
                ("board", target_environment("thermoblock")),
                (
                    "native_fixture",
                    {
                        "platform": "native",
                        "build_src_filter": "+<control/> +<plant/fixture/> +<app/native/>",
                    },
                ),
            ]
        )
        result = self.check()
        self.assertEqual(0, result.returncode, result.stderr)

    def test_a_machine_build_required_to_be_refused_is_not_asked(self):
        """A build that must fail is not an artefact anybody is energising."""
        self.tree.declare(
            [
                ("board", target_environment("thermoblock")),
                (
                    "board_no_structure",
                    target_environment(custom_must_not_build="it names no structure"),
                ),
            ]
        )
        result = self.check()
        self.assertEqual(0, result.returncode, result.stderr)

    def test_a_second_board_is_covered_without_the_invocation_changing(self):
        self.tree.declare(
            [
                ("board", target_environment("thermoblock")),
                ("second_board", target_environment("fixture")),
            ]
        )
        result = self.check()
        self.assertEqual(1, result.returncode)
        self.assertIn("second_board", result.stderr)

    def test_a_tree_with_no_machine_build_fails_rather_than_passing_vacuously(self):
        self.tree.declare(
            [
                (
                    "native",
                    {
                        "platform": "native",
                        "build_src_filter": "+<control/> +<plant/thermoblock/> +<app/native/>",
                    },
                )
            ]
        )
        result = self.check()
        self.assertEqual(1, result.returncode)
        self.assertIn("nothing to cover", result.stderr)

    def test_a_structure_whose_claim_is_unreadable_fails_rather_than_being_left_out(self):
        """An unreadable claim must not read as a structure describing nothing."""
        self.tree.tree.structure("thermoblock", None)
        self.tree.declare([("board", target_environment("thermoblock"))])
        result = self.check()
        self.assertEqual(1, result.returncode)
        self.assertIn("PLANT_STRUCTURE_MACHINE_CLAIM", result.stderr)


# --- check_embedded_description ---------------------------------------------


class AMachineCarriesTheVerifiedDescription(TargetModelCase):
    """SOL-ONBOARD-PLANT-MODEL-IDENTITY.C5: a target build embedding a description other than the verified one fails.

    SOL-ONBOARD-PLANT-MODEL-IDENTITY.C3: the description travels in the artefact rather than being read from a path.

    Each way an artefact's bytes can diverge from what the tier verified, asked
    of both of the things an artefact carries. The two are the same mechanism
    twice, and the reason each refusal is driven for each of them is that the
    second one acquiring fewer refusals than the first is exactly what a shared
    implementation is supposed to prevent and would not announce.
    """

    def setUp(self):
        super().setUp()
        self.pinned = host_test_environment("thermoblock", "params/thermoblock.params")

    def check(self, *generated: str):
        arguments = ["--project", self.tree.root]
        for entry in generated:
            arguments.extend(["--generated", entry])
        return run_check("check_embedded_description.py", *arguments)

    def declare(self, board_options=None):
        options = carrying_environment("thermoblock")
        options.update(board_options or {})
        self.tree.declare([("board", options), ("native_test", self.pinned)])

    def test_both_embeddings_matching_what_is_pinned_pass(self):
        self.declare()
        generated = self.tree.generate("board")
        result = self.check(f"board={generated}")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("byte for byte", result.stdout)

    def test_the_success_line_names_both_of_the_things_it_inspected(self):
        """A line naming one while having compared two would misreport its own coverage."""
        self.declare()
        generated = self.tree.generate("board")
        result = self.check(f"board={generated}")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("board's parameter description", result.stdout)
        self.assertIn("board's limits declaration", result.stdout)

    def test_a_build_declaring_a_different_description_fails(self):
        """The first divergence: a build naming a description the tier never saw."""
        self.tree.describe("thermoblock-variant.params", VARIANT)
        self.declare({"custom_embedded_description": "params/thermoblock-variant.params"})
        generated = self.tree.generate("board", source="params/thermoblock-variant.params")
        result = self.check(f"board={generated}")
        self.assertEqual(1, result.returncode)
        self.assertIn("thermoblock-variant.params", result.stderr)
        self.assertIn("parameter description the tier never verified", result.stderr)

    def test_a_build_declaring_a_different_limits_declaration_fails(self):
        self.tree.describe("thermoblock-variant.limits", LIMITS_VARIANT)
        self.declare({"custom_embedded_limits": "params/thermoblock-variant.limits"})
        generated = self.tree.generate(
            "board", limits_source="params/thermoblock-variant.limits"
        )
        result = self.check(f"board={generated}")
        self.assertEqual(1, result.returncode)
        self.assertIn("thermoblock-variant.limits", result.stderr)
        self.assertIn("limits declaration the tier never verified", result.stderr)

    def test_an_embedding_left_stale_by_an_incremental_build_fails(self):
        """The second: the description moved on and the rendered bytes did not."""
        self.declare()
        generated = self.tree.generate("board", data=DESCRIPTION.encode("utf-8"))
        self.tree.describe("thermoblock.params", DESCRIPTION + "alpha.extra = 3.0\n")
        result = self.check(f"board={generated}")
        self.assertEqual(1, result.returncode)
        self.assertIn("bytes of parameter description", result.stderr)
        self.assertIn("disagree about what the machine is", result.stderr)

    def test_limits_left_stale_by_an_incremental_build_fail(self):
        """The same divergence on the other file, which has no symptom either."""
        self.declare()
        generated = self.tree.generate("board", limits_data=LIMITS.encode("utf-8"))
        self.tree.describe("thermoblock.limits", LIMITS + "other-channel = 0 .. 1\n")
        result = self.check(f"board={generated}")
        self.assertEqual(1, result.returncode)
        self.assertIn("bytes of limits declaration", result.stderr)
        self.assertIn("disagree about what the machine is", result.stderr)

    def test_an_embedding_rendered_from_a_second_description_fails(self):
        """The third: a variant sitting beside the intended one is what got carried."""
        self.tree.describe("thermoblock-variant.params", VARIANT)
        self.declare()
        generated = self.tree.generate("board", source="params/thermoblock-variant.params")
        result = self.check(f"board={generated}")
        self.assertEqual(1, result.returncode)
        self.assertIn("generated from params/thermoblock-variant.params", result.stderr)

    def test_limits_rendered_from_a_second_declaration_fail(self):
        self.tree.describe("thermoblock-variant.limits", LIMITS_VARIANT)
        self.declare()
        generated = self.tree.generate(
            "board", limits_source="params/thermoblock-variant.limits"
        )
        result = self.check(f"board={generated}")
        self.assertEqual(1, result.returncode)
        self.assertIn("generated from params/thermoblock-variant.limits", result.stderr)
        self.assertIn("pinned limits declaration", result.stderr)

    def test_an_embedding_carrying_two_descriptions_fails(self):
        """Two definitions leave which one the machine carries to the compiler."""
        self.declare()
        generated = self.tree.generate("board")
        rendered = os.path.join(
            generated, embedded_description.DESCRIPTION.generated_name
        )
        with open(rendered, "a", encoding="utf-8") as handle:
            handle.write(
                embedded_description.render("params/thermoblock.params", b"other")
            )
        result = self.check(f"board={generated}")
        self.assertEqual(1, result.returncode)
        self.assertIn("defined more than once", result.stderr)

    def test_a_machine_build_declaring_no_description_fails(self):
        self.tree.declare(
            [
                (
                    "board",
                    target_environment(
                        "thermoblock", custom_embedded_limits="params/thermoblock.limits"
                    ),
                ),
                ("native_test", self.pinned),
            ]
        )
        generated = self.tree.generate("board")
        result = self.check(f"board={generated}")
        self.assertEqual(1, result.returncode)
        self.assertIn("custom_embedded_description", result.stderr)

    def test_a_machine_build_declaring_no_limits_fails(self):
        """A machine believing every reading is as unstated as one with no model."""
        self.tree.declare(
            [
                (
                    "board",
                    target_environment(
                        "thermoblock",
                        custom_embedded_description="params/thermoblock.params",
                    ),
                ),
                ("native_test", self.pinned),
            ]
        )
        generated = self.tree.generate("board")
        result = self.check(f"board={generated}")
        self.assertEqual(1, result.returncode)
        self.assertIn("custom_embedded_limits", result.stderr)
        self.assertIn("limits declaration its artefact carries", result.stderr)

    def test_a_build_pinning_no_description_fails(self):
        """A tier pinned to nothing has verified against nothing in particular."""
        self.tree.declare([("board", carrying_environment("thermoblock"))])
        generated = self.tree.generate("board")
        result = self.check(f"board={generated}")
        self.assertEqual(1, result.returncode)
        self.assertIn("REFERENCE_DESCRIPTION_PATH", result.stderr)

    def test_a_build_pinning_no_limits_fails(self):
        """The same omission on the other file, which is why it is read separately."""
        self.tree.declare(
            [
                ("board", carrying_environment("thermoblock")),
                (
                    "native_test",
                    host_test_environment(
                        "thermoblock", "params/thermoblock.params", limits=""
                    ),
                ),
            ]
        )
        generated = self.tree.generate("board")
        result = self.check(f"board={generated}")
        self.assertEqual(1, result.returncode)
        self.assertIn("REFERENCE_LIMITS_PATH", result.stderr)
        self.assertIn("no limits declaration the verification tier is pinned to", result.stderr)

    def test_a_build_pinning_two_descriptions_fails(self):
        self.tree.describe("thermoblock-variant.params", VARIANT)
        self.tree.declare(
            [
                ("board", carrying_environment("thermoblock")),
                ("native_test", self.pinned),
                (
                    "other_test",
                    host_test_environment(
                        "thermoblock", "params/thermoblock-variant.params"
                    ),
                ),
            ]
        )
        generated = self.tree.generate("board")
        result = self.check(f"board={generated}")
        self.assertEqual(1, result.returncode)
        self.assertIn("more than one description is named", result.stderr)
        self.assertIn("not settled", result.stderr)

    def test_a_build_pinning_two_limits_declarations_fails(self):
        """Two answers to what a reading may be is no answer at all."""
        self.tree.describe("thermoblock-variant.limits", LIMITS_VARIANT)
        self.tree.declare(
            [
                ("board", carrying_environment("thermoblock")),
                ("native_test", self.pinned),
                (
                    "other_test",
                    host_test_environment(
                        "thermoblock",
                        "params/thermoblock.params",
                        limits="params/thermoblock-variant.limits",
                    ),
                ),
            ]
        )
        generated = self.tree.generate("board")
        result = self.check(f"board={generated}")
        self.assertEqual(1, result.returncode)
        self.assertIn("more than one limits declaration is named", result.stderr)
        self.assertIn("thermoblock-variant.limits by other_test", result.stderr)

    def test_a_pinned_description_that_is_not_there_fails(self):
        self.declare()
        generated = self.tree.generate("board")
        os.remove(os.path.join(self.tree.root, "params", "thermoblock.params"))
        result = self.check(f"board={generated}")
        self.assertEqual(1, result.returncode)
        self.assertIn("nothing for an artefact to be compared against", result.stderr)

    def test_a_pinned_limits_declaration_that_is_not_there_fails(self):
        self.declare()
        generated = self.tree.generate("board")
        os.remove(os.path.join(self.tree.root, "params", "thermoblock.limits"))
        result = self.check(f"board={generated}")
        self.assertEqual(1, result.returncode)
        self.assertIn("pinned to the limits declaration", result.stderr)
        self.assertIn("nothing for an artefact to be compared against", result.stderr)

    def test_an_embedding_offered_for_something_that_is_not_a_machine_build_fails(self):
        self.declare()
        generated = self.tree.generate("native_test")
        result = self.check(f"native_test={generated}")
        self.assertEqual(1, result.returncode)
        self.assertIn("does not build an artefact for a machine", result.stderr)

    def test_offering_nothing_reads_every_machine_build_from_its_own_build_directory(self):
        """Naming none is how the gate outside the build covers a board nobody named."""
        self.declare()
        self.tree.generate("board")
        result = self.check()
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("board", result.stdout)

    def test_a_machine_build_whose_embedding_was_never_rendered_fails(self):
        """Comparing no bytes must not report that the bytes compared."""
        self.declare()
        result = self.check()
        self.assertEqual(1, result.returncode)
        self.assertIn("no generated embedding of the parameter description", result.stderr)
        self.assertIn("no generated embedding of the limits declaration", result.stderr)

    def test_a_machine_build_whose_limits_alone_were_never_rendered_fails(self):
        """Half a rendering is the state an added embedding arrives through."""
        self.declare()
        self.tree.generate("board")
        os.remove(
            os.path.join(
                self.tree.generated("board"), embedded_description.LIMITS.generated_name
            )
        )
        result = self.check()
        self.assertEqual(1, result.returncode)
        self.assertIn("no generated embedding of the limits declaration", result.stderr)

    def test_a_generated_directory_inside_the_source_tree_is_refused(self):
        """A rendered file kept in the tree is the second copy this exists to prevent."""
        self.declare()
        inside = os.path.join(self.tree.root, "src", "generated")
        os.makedirs(inside, exist_ok=True)
        for embedding in embedded_description.EMBEDDINGS:
            write(
                os.path.join(inside, embedding.generated_name),
                embedded_description.render(
                    "params/thermoblock.params", b"whatever", embedding
                ),
            )
        result = self.check(f"board={inside}")
        self.assertEqual(1, result.returncode)
        self.assertIn("is inside the source tree", result.stderr)

    def test_a_second_board_is_compared_without_being_named(self):
        self.tree.declare(
            [
                ("board", carrying_environment("thermoblock")),
                ("second_board", carrying_environment("thermoblock")),
                ("native_test", self.pinned),
            ]
        )
        self.tree.generate("board")
        self.tree.generate("second_board", data=b"# something else entirely\n")
        result = self.check()
        self.assertEqual(1, result.returncode)
        self.assertIn("second_board", result.stderr)

    def test_a_generated_file_that_is_not_an_embedding_fails(self):
        self.declare()
        generated = self.tree.generate("board")
        write(
            os.path.join(generated, embedded_description.DESCRIPTION.generated_name),
            "const char reference_description[] = { 0x00 };\n",
        )
        result = self.check(f"board={generated}")
        self.assertEqual(1, result.returncode)
        self.assertIn("description-source:", result.stderr)
        self.assertIn("parameter description", result.stderr)

    def test_a_generated_limits_file_that_is_not_an_embedding_fails(self):
        self.declare()
        generated = self.tree.generate("board")
        write(
            os.path.join(generated, embedded_description.LIMITS.generated_name),
            "const char reference_limits[] = { 0x00 };\n",
        )
        result = self.check(f"board={generated}")
        self.assertEqual(1, result.returncode)
        self.assertIn("limits declaration", result.stderr)
        self.assertIn("description-source:", result.stderr)

    def test_a_second_board_declaring_the_wrong_description_is_caught(self):
        self.tree.describe("thermoblock-variant.params", VARIANT)
        self.tree.declare(
            [
                ("board", carrying_environment("thermoblock")),
                (
                    "second_board",
                    carrying_environment(
                        "thermoblock",
                        custom_embedded_description="params/thermoblock-variant.params",
                    ),
                ),
                ("native_test", self.pinned),
            ]
        )
        generated = self.tree.generate("board")
        result = self.check(f"board={generated}")
        self.assertEqual(1, result.returncode)
        self.assertIn("second_board", result.stderr)

    def test_the_generated_argument_wants_a_directory_and_says_so(self):
        self.declare()
        result = self.check("board")
        self.assertEqual(2, result.returncode)
        self.assertIn("--generated wants ENV=DIR", result.stderr)


# --- check_target_carries_model ---------------------------------------------


class TheArtefactCarriesTheModel(TargetModelCase):
    """SOL-ONBOARD-PLANT-MODEL-IDENTITY.C8: the artefact a machine would run retains the plant model's operations.

    SOL-ONBOARD-PLANT-MODEL-IDENTITY.C3: the description travels in the artefact, read back out of the artefact itself.

    SOL-ONBOARD-PLANT-MODEL-IDENTITY.C7: the target build links the maths the plant sources call into. That criterion is
    established by the build itself, as its own text says -- but only while the
    equations calling into the maths are still in what gets linked. This is what
    keeps that from becoming a question nobody asks: an artefact they were
    dropped from links cleanly whether the maths could be resolved or not.

    What survives the linker, asked of the artefact rather than of the build.

    Everything else here is established before an artefact exists. The linker
    discards what nothing reaches, and nothing on the machine drives the model
    yet, so an artefact that dropped the equations is the state every earlier
    check passes on.
    """

    @classmethod
    def setUpClass(cls):
        cls.compiler = os.environ.get("CC", "clang")
        if subprocess.run(
            [cls.compiler, "--version"], capture_output=True, check=False
        ).returncode:
            raise unittest.SkipTest(f"{cls.compiler} is not available on this host")

    def check(self):
        return run_check(
            "check_target_carries_model.py",
            "--project",
            self.tree.root,
            "--include-dir",
            self.tree.tree.include,
            "--params-dir",
            "params",
        )

    def declare(self, *names: str):
        environments = [(name, carrying_environment("thermoblock")) for name in names]
        environments.append(("native_test", host_test_environment("thermoblock", "params/thermoblock.params")))
        self.tree.declare(environments)

    def link(self, environment: str, *, operations=("plant_model_init", "plant_model_step"),
             descriptions=("params/thermoblock.params",)):
        """Link an artefact defining the given operations and carrying the given bytes.

        The description goes in through the same rendering the build uses, so
        what a real artefact would carry is what is compiled here rather than a
        restatement of it.
        """
        directory = os.path.join(self.tree.root, ".pio", "build", environment)
        os.makedirs(directory, exist_ok=True)
        artefact = os.path.join(directory, "firmware.elf")

        parts = []
        for index, description in enumerate(descriptions):
            with open(os.path.join(self.tree.root, description), "rb") as handle:
                rendered = embedded_description.render(description, handle.read())
            parts.append(
                rendered.replace(
                    f"const char {embedded_description.DESCRIPTION.symbol}[]",
                    f"const char {embedded_description.DESCRIPTION.symbol}_{index}[]",
                )
            )
        parts.extend(f"int {name}(void) {{ return 0; }}\n" for name in operations)
        used = "".join(f"    total += {name}();\n" for name in operations)
        used += "".join(
            f"    total += {embedded_description.DESCRIPTION.symbol}_{index}[0];\n"
            for index in range(len(descriptions))
        )
        parts.append(f"int main(void) {{\n    int total = 0;\n{used}    return total;\n}}\n")

        source = os.path.join(self.tree.root, f"{environment}.c")
        write(source, "\n".join(parts))
        subprocess.run([self.compiler, "-o", artefact, source], check=True)
        return artefact

    def test_an_artefact_carrying_the_model_and_the_description_passes(self):
        self.declare("board")
        self.link("board")
        result = self.check()
        self.assertEqual(0, result.returncode, result.stderr)

    def test_an_artefact_the_model_was_discarded_from_fails(self):
        """The regression with no symptom: the build succeeds, the model is gone."""
        self.declare("board")
        self.link("board", operations=("plant_model_init",))
        result = self.check()
        self.assertEqual(1, result.returncode)
        self.assertIn("plant_model_step", result.stderr)
        self.assertIn("discarded", result.stderr)

    def test_an_artefact_carrying_no_description_fails(self):
        self.declare("board")
        self.link("board", descriptions=())
        result = self.check()
        self.assertEqual(1, result.returncode)
        self.assertIn("0 time(s)", result.stderr)

    def test_an_artefact_carrying_a_second_description_fails(self):
        """Two descriptions in one image leaves the machine's numbers unsettled."""
        self.tree.describe("thermoblock-variant.params", VARIANT)
        self.declare("board")
        self.link(
            "board",
            descriptions=("params/thermoblock.params", "params/thermoblock-variant.params"),
        )
        result = self.check()
        self.assertEqual(1, result.returncode)
        self.assertIn("thermoblock-variant.params", result.stderr)

    def test_an_artefact_that_has_not_been_built_fails(self):
        self.declare("board")
        result = self.check()
        self.assertEqual(1, result.returncode)
        self.assertIn("no artefact at", result.stderr)

    def test_a_second_board_is_covered_without_the_invocation_changing(self):
        self.declare("board", "second_board")
        self.link("board")
        self.link("second_board", operations=("plant_model_init",))
        result = self.check()
        self.assertEqual(1, result.returncode)
        self.assertIn("second_board", result.stderr)

    def test_a_tree_with_no_machine_build_fails_rather_than_passing_vacuously(self):
        self.tree.declare(
            [("native_test", host_test_environment("thermoblock", "params/thermoblock.params"))]
        )
        result = self.check()
        self.assertEqual(1, result.returncode)
        self.assertIn("nothing to cover", result.stderr)

    def test_a_seam_declaring_no_operations_is_an_error_rather_than_a_pass(self):
        """An empty list would look for nothing and find it."""
        self.declare("board")
        self.link("board")
        write(os.path.join(self.tree.tree.include, "plant_model.h"), "/* nothing here */\n")
        result = self.check()
        self.assertEqual(2, result.returncode)
        self.assertIn("declares no operations", result.stderr)


# --- pio_embed_description --------------------------------------------------


#: A stand-in for the build system, so the script that renders into an artefact
#: can be driven on a host that has no PlatformIO installed.
#:
#: It answers the three substitutions the script makes and turns Exit into the
#: process exit SCons's own Exit is, which is what makes a refusal observable
#: here as an exit status rather than as a description of one. Anything the
#: script does beyond that -- what it puts on the include path -- is printed, so
#: a test can assert on it rather than reach into the script's variables.
PIO_DRIVER = '''import sys

project_dir, build_dir, environment_name, script = sys.argv[1:5]


class BuildEnvironment:
    def subst(self, token):
        return {
            "$PROJECT_DIR": project_dir,
            "$BUILD_DIR": build_dir,
            "$PIOENV": environment_name,
        }[token]

    def Exit(self, code):
        sys.exit(code)

    def Prepend(self, **values):
        for name, entries in values.items():
            for entry in entries:
                print(f"prepend {name} {entry}")


namespace = {"__name__": "__main__", "Import": lambda *names: None, "env": BuildEnvironment()}
with open(script, "r", encoding="utf-8") as handle:
    exec(compile(handle.read(), script, "exec"), namespace)
'''


class TheArtefactIsGivenWhatItCarries(TargetModelCase):
    """SOL-ONBOARD-PLANT-MODEL-IDENTITY.C3: what an artefact carries is rendered into it by the build rather than read from a path.

    The renderer is driven rather than reasoned about, because the state it
    exists to refuse -- an artefact carrying a description of a machine and no
    statement of what a reading off it may plausibly be -- compiles cleanly and
    reports nothing on the running machine.
    """

    def setUp(self):
        super().setUp()
        self.pinned = host_test_environment("thermoblock", "params/thermoblock.params")

    def declare(self, board_options=None):
        options = carrying_environment("thermoblock")
        options.update(board_options or {})
        self.tree.declare([("board", options), ("native_test", self.pinned)])

    def embed(self, environment: str = "board"):
        # The script resolves its own imports and the check it runs from
        # PROJECT_DIR, because the working directory a build runs it from is not
        # guaranteed. A synthetic project therefore has to have those tools where
        # the script looks for them, and linking rather than copying keeps this
        # driving the scripts as they are rather than a snapshot of them.
        linked = os.path.join(self.tree.root, "tools")
        if not os.path.exists(linked):
            os.symlink(TOOLS, linked)

        driver = os.path.join(self.tree.root, "drive_extra_script.py")
        write(driver, PIO_DRIVER)
        return subprocess.run(
            [
                sys.executable,
                driver,
                self.tree.root,
                os.path.join(self.tree.root, ".pio", "build", environment),
                environment,
                os.path.join(TOOLS, "pio_embed_description.py"),
            ],
            capture_output=True,
            text=True,
            check=False,
        )

    def rendered(self, embedding, environment: str = "board") -> str:
        return os.path.join(
            self.tree.root, ".pio", "build", environment, "generated", embedding.generated_name
        )

    def test_both_embeddings_are_rendered(self):
        self.declare()
        result = self.embed()
        self.assertEqual(0, result.returncode, result.stderr)
        for embedding, content in (
            (embedded_description.DESCRIPTION, DESCRIPTION),
            (embedded_description.LIMITS, LIMITS),
        ):
            with open(self.rendered(embedding), "r", encoding="utf-8") as handle:
                source, carried = embedded_description.decode(handle.read(), embedding)
            self.assertEqual(content.encode("utf-8"), carried)
            self.assertIn("params/thermoblock", source)

    def test_the_generated_directory_goes_on_the_include_path_once(self):
        """Twice would be the same answer on the path twice, and one of them
        could later be a different one."""
        self.declare()
        result = self.embed()
        self.assertEqual(0, result.returncode, result.stderr)
        prepends = [line for line in result.stdout.splitlines() if line.startswith("prepend ")]
        self.assertEqual(1, len(prepends), result.stdout)
        self.assertTrue(prepends[0].endswith("generated"), prepends[0])

    def test_a_build_declaring_a_description_and_no_limits_is_refused(self):
        """Half a declaration: the artefact would believe every reading."""
        self.tree.declare(
            [
                (
                    "board",
                    target_environment(
                        "thermoblock",
                        custom_embedded_description="params/thermoblock.params",
                    ),
                ),
                ("native_test", self.pinned),
            ]
        )
        result = self.embed()
        self.assertEqual(2, result.returncode)
        self.assertIn("custom_embedded_limits", result.stderr)
        self.assertIn("believe every reading or believe none", result.stderr)
        self.assertFalse(os.path.exists(self.rendered(embedded_description.DESCRIPTION)))

    def test_a_build_declaring_limits_and_no_description_is_refused(self):
        self.tree.declare(
            [
                (
                    "board",
                    target_environment(
                        "thermoblock", custom_embedded_limits="params/thermoblock.limits"
                    ),
                ),
                ("native_test", self.pinned),
            ]
        )
        result = self.embed()
        self.assertEqual(2, result.returncode)
        self.assertIn("custom_embedded_description", result.stderr)

    def test_a_build_declaring_neither_is_refused(self):
        self.tree.declare(
            [("board", target_environment("thermoblock")), ("native_test", self.pinned)]
        )
        result = self.embed()
        self.assertEqual(2, result.returncode)
        self.assertIn("declares neither", result.stderr)

    def test_a_declared_limits_file_that_is_not_there_is_refused(self):
        self.declare({"custom_embedded_limits": "params/nowhere.limits"})
        result = self.embed()
        self.assertEqual(2, result.returncode)
        self.assertIn("no limits declaration at", result.stderr)

    def test_an_unchanged_declaration_is_not_rewritten(self):
        """Restamping the rendered file would rebuild the translation unit that
        includes it on every build."""
        self.declare()
        self.assertEqual(0, self.embed().returncode)
        stamps = {
            embedding.generated_name: os.stat(self.rendered(embedding)).st_mtime_ns
            for embedding in embedded_description.EMBEDDINGS
        }
        self.assertEqual(0, self.embed().returncode)
        for embedding in embedded_description.EMBEDDINGS:
            self.assertEqual(
                stamps[embedding.generated_name],
                os.stat(self.rendered(embedding)).st_mtime_ns,
            )

    def test_what_was_rendered_is_compared_before_anything_is_compiled(self):
        """The renderer is not on its own an argument that the bytes are right."""
        self.tree.describe("thermoblock-variant.limits", LIMITS_VARIANT)
        self.declare({"custom_embedded_limits": "params/thermoblock-variant.limits"})
        result = self.embed()
        self.assertEqual(1, result.returncode)
        self.assertIn("thermoblock-variant.limits", result.stderr)


# --- the form the description travels in ------------------------------------


class TheEmbeddedFormSurvivesBeingReadBack(unittest.TestCase):
    """SOL-ONBOARD-PLANT-MODEL-IDENTITY.C3: the bytes rendered into the artefact are the description's own, whatever they are.

    Rendering and reading are two halves of one format, so they are driven together.
    """

    def test_every_byte_value_round_trips(self):
        data = bytes(range(256))
        source, carried = embedded_description.decode(
            embedded_description.render("params/x.params", data)
        )
        self.assertEqual("params/x.params", source)
        self.assertEqual(data, carried)

    def test_every_embedding_round_trips_under_its_own_symbol(self):
        """Two embeddings, one format. A second symbol reading back through the
        first would decode whichever file happened to be looked at."""
        data = bytes(range(256))
        for embedding in embedded_description.EMBEDDINGS:
            rendered = embedded_description.render("params/x", data, embedding)
            self.assertIn(f"const char {embedding.symbol}[]", rendered)
            source, carried = embedded_description.decode(rendered, embedding)
            self.assertEqual("params/x", source)
            self.assertEqual(data, carried)

    def test_one_embedding_is_not_read_back_as_another(self):
        """Reading the limits file through the description's symbol would find no
        definition, which is the refusal that keeps the two from being swapped."""
        rendered = embedded_description.render(
            "params/x.limits", b"data", embedded_description.LIMITS
        )
        with self.assertRaises(embedded_description.MalformedEmbedding) as raised:
            embedded_description.decode(rendered, embedded_description.DESCRIPTION)
        self.assertIn(embedded_description.DESCRIPTION.symbol, str(raised.exception))

    def test_an_empty_description_is_refused_rather_than_rendered(self):
        """An empty initialiser is not C every compiler accepts, and an empty
        description is not a smaller description of the machine."""
        with self.assertRaises(embedded_description.MalformedEmbedding):
            embedded_description.render("params/x.params", b"")

    def test_the_bytes_are_an_initialiser_rather_than_a_string_literal(self):
        """A literal would put the description under C11's 4095-character limit."""
        rendered = embedded_description.render("params/x.params", b"# a description\n")
        definition = rendered[rendered.index(f"const char {embedded_description.DESCRIPTION.symbol}") :]
        self.assertNotIn('"', definition)
        self.assertIn("(char)0x23u", definition)

    def test_no_line_is_long_enough_to_trouble_a_compiler(self):
        rendered = embedded_description.render("params/x.params", bytes(4096))
        self.assertLess(max(len(line) for line in rendered.splitlines()), 4095)

    def test_a_file_recording_no_source_is_refused(self):
        rendered = embedded_description.render("params/x.params", b"data")
        without = rendered.replace(embedded_description.SOURCE_MARKER, "made-from:")
        with self.assertRaises(embedded_description.MalformedEmbedding):
            embedded_description.decode(without)

    def test_a_file_defining_nothing_is_refused(self):
        with self.assertRaises(embedded_description.MalformedEmbedding):
            embedded_description.decode(f"/* {embedded_description.SOURCE_MARKER} params/x */\n")

    def test_a_definition_that_is_not_terminated_is_refused(self):
        rendered = embedded_description.render("params/x.params", b"data")
        with self.assertRaises(embedded_description.MalformedEmbedding):
            embedded_description.decode(rendered.replace("};", ""))

    def test_something_other_than_bytes_in_the_definition_is_refused(self):
        """A name in the initialiser would carry a value this cannot read."""
        rendered = embedded_description.render("params/x.params", b"data")
        tampered = rendered.replace("(char)0x64u,", "(char)0x64u, SOME_MACRO,")
        with self.assertRaises(embedded_description.MalformedEmbedding) as raised:
            embedded_description.decode(tampered)
        self.assertIn("SOME_MACRO", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
