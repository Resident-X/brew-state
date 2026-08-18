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
from test_plant_checks import ClaimTree, declare_environments, run_check, write  # noqa: E402

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


def target_environment(structure: str | None = None, **options):
    """One environment building for a board, as the build file would declare it."""
    terms = ["+<control/>", "+<plant/common/>", "+<hw/board/>", "+<app/board/>"]
    if structure is not None:
        terms.append(f"+<plant/{structure}/>")
    declared = {"platform": "ststm32", "build_src_filter": " ".join(terms)}
    declared.update(options)
    return declared


def host_test_environment(structure: str, description: str, **options):
    """The host environment that pins the tier to a description, as the build file has it."""
    declared = {
        "platform": "native",
        "build_src_filter": f"+<control/> +<plant/common/> +<plant/{structure}/> +<app/native/>",
        "build_flags": f"-O1 -D REFERENCE_DESCRIPTION_PATH='\"$PROJECT_DIR/{description}\"'",
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

    def generate(self, environment: str, source: str, data: bytes | None = None) -> str:
        """Render an embedding the way the build's own script renders it.

        `data` overrides what is carried, so an embedding that has fallen out of
        step with the description it names can be written as one would be found
        rather than described.
        """
        directory = os.path.join(self.root, ".pio", "build", environment, "generated")
        os.makedirs(directory, exist_ok=True)
        path = os.path.join(directory, "reference_description_bytes.h")
        if data is None:
            with open(os.path.join(self.root, source), "rb") as handle:
                data = handle.read()
        write(path, embedded_description.render(source, data))
        return path

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

    Each way an artefact's bytes can diverge from what the tier verified.
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
        options = target_environment(
            "thermoblock", custom_embedded_description="params/thermoblock.params"
        )
        options.update(board_options or {})
        self.tree.declare([("board", options), ("native_test", self.pinned)])

    def test_an_embedding_matching_the_pinned_description_passes(self):
        self.declare()
        generated = self.tree.generate("board", "params/thermoblock.params")
        result = self.check(f"board={generated}")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("byte for byte", result.stdout)

    def test_a_build_declaring_a_different_description_fails(self):
        """The first divergence: a build naming a description the tier never saw."""
        self.tree.describe("thermoblock-variant.params", VARIANT)
        self.declare({"custom_embedded_description": "params/thermoblock-variant.params"})
        generated = self.tree.generate("board", "params/thermoblock-variant.params")
        result = self.check(f"board={generated}")
        self.assertEqual(1, result.returncode)
        self.assertIn("thermoblock-variant.params", result.stderr)
        self.assertIn("never verified", result.stderr)

    def test_an_embedding_left_stale_by_an_incremental_build_fails(self):
        """The second: the description moved on and the rendered bytes did not."""
        self.declare()
        generated = self.tree.generate(
            "board", "params/thermoblock.params", data=DESCRIPTION.encode("utf-8")
        )
        self.tree.describe("thermoblock.params", DESCRIPTION + "alpha.extra = 3.0\n")
        result = self.check(f"board={generated}")
        self.assertEqual(1, result.returncode)
        self.assertIn("disagree about what the machine is", result.stderr)

    def test_an_embedding_rendered_from_a_second_description_fails(self):
        """The third: a variant sitting beside the intended one is what got carried."""
        self.tree.describe("thermoblock-variant.params", VARIANT)
        self.declare()
        generated = self.tree.generate("board", "params/thermoblock-variant.params")
        result = self.check(f"board={generated}")
        self.assertEqual(1, result.returncode)
        self.assertIn("generated from params/thermoblock-variant.params", result.stderr)

    def test_an_embedding_carrying_two_descriptions_fails(self):
        """Two definitions leave which one the machine carries to the compiler."""
        self.declare()
        generated = self.tree.generate("board", "params/thermoblock.params")
        with open(generated, "a", encoding="utf-8") as handle:
            handle.write(embedded_description.render("params/thermoblock.params", b"other"))
        result = self.check(f"board={generated}")
        self.assertEqual(1, result.returncode)
        self.assertIn("defined more than once", result.stderr)

    def test_a_machine_build_declaring_no_description_fails(self):
        self.tree.declare(
            [("board", target_environment("thermoblock")), ("native_test", self.pinned)]
        )
        generated = self.tree.generate("board", "params/thermoblock.params")
        result = self.check(f"board={generated}")
        self.assertEqual(1, result.returncode)
        self.assertIn("custom_embedded_description", result.stderr)

    def test_a_build_pinning_no_description_fails(self):
        """A tier pinned to nothing has verified against nothing in particular."""
        self.tree.declare(
            [
                (
                    "board",
                    target_environment(
                        "thermoblock",
                        custom_embedded_description="params/thermoblock.params",
                    ),
                )
            ]
        )
        generated = self.tree.generate("board", "params/thermoblock.params")
        result = self.check(f"board={generated}")
        self.assertEqual(1, result.returncode)
        self.assertIn("REFERENCE_DESCRIPTION_PATH", result.stderr)

    def test_a_build_pinning_two_descriptions_fails(self):
        self.tree.describe("thermoblock-variant.params", VARIANT)
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
                (
                    "other_test",
                    host_test_environment("thermoblock", "params/thermoblock-variant.params"),
                ),
            ]
        )
        generated = self.tree.generate("board", "params/thermoblock.params")
        result = self.check(f"board={generated}")
        self.assertEqual(1, result.returncode)
        self.assertIn("not settled", result.stderr)

    def test_a_pinned_description_that_is_not_there_fails(self):
        self.declare()
        generated = self.tree.generate("board", "params/thermoblock.params")
        os.remove(os.path.join(self.tree.root, "params", "thermoblock.params"))
        result = self.check(f"board={generated}")
        self.assertEqual(1, result.returncode)
        self.assertIn("nothing for an artefact to be compared against", result.stderr)

    def test_an_embedding_offered_for_something_that_is_not_a_machine_build_fails(self):
        self.declare()
        generated = self.tree.generate("native_test", "params/thermoblock.params")
        result = self.check(f"native_test={generated}")
        self.assertEqual(1, result.returncode)
        self.assertIn("does not build an artefact for a machine", result.stderr)

    def test_offering_nothing_reads_every_machine_build_from_its_own_build_directory(self):
        """Naming none is how the gate outside the build covers a board nobody named."""
        self.declare()
        self.tree.generate("board", "params/thermoblock.params")
        result = self.check()
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("board", result.stdout)

    def test_a_machine_build_whose_embedding_was_never_rendered_fails(self):
        """Comparing no bytes must not report that the bytes compared."""
        self.declare()
        result = self.check()
        self.assertEqual(1, result.returncode)
        self.assertIn("no generated embedding", result.stderr)

    def test_a_second_board_is_compared_without_being_named(self):
        options = target_environment(
            "thermoblock", custom_embedded_description="params/thermoblock.params"
        )
        self.tree.declare(
            [
                (
                    "board",
                    target_environment(
                        "thermoblock",
                        custom_embedded_description="params/thermoblock.params",
                    ),
                ),
                ("second_board", options),
                ("native_test", self.pinned),
            ]
        )
        self.tree.generate("board", "params/thermoblock.params")
        self.tree.generate(
            "second_board", "params/thermoblock.params", data=b"# something else entirely\n"
        )
        result = self.check()
        self.assertEqual(1, result.returncode)
        self.assertIn("second_board", result.stderr)

    def test_a_generated_file_that_is_not_an_embedding_fails(self):
        self.declare()
        generated = self.tree.generate("board", "params/thermoblock.params")
        write(generated, "const char reference_description[] = { 0x00 };\n")
        result = self.check(f"board={generated}")
        self.assertEqual(1, result.returncode)
        self.assertIn("description-source:", result.stderr)

    def test_a_second_board_declaring_the_wrong_description_is_caught(self):
        self.tree.describe("thermoblock-variant.params", VARIANT)
        options = target_environment(
            "thermoblock", custom_embedded_description="params/thermoblock-variant.params"
        )
        self.tree.declare(
            [
                (
                    "board",
                    target_environment(
                        "thermoblock",
                        custom_embedded_description="params/thermoblock.params",
                    ),
                ),
                ("second_board", options),
                ("native_test", self.pinned),
            ]
        )
        generated = self.tree.generate("board", "params/thermoblock.params")
        result = self.check(f"board={generated}")
        self.assertEqual(1, result.returncode)
        self.assertIn("second_board", result.stderr)


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
        environments = [
            (
                name,
                target_environment(
                    "thermoblock", custom_embedded_description="params/thermoblock.params"
                ),
            )
            for name in names
        ]
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
                    f"const char {embedded_description.SYMBOL}[]",
                    f"const char {embedded_description.SYMBOL}_{index}[]",
                )
            )
        parts.extend(f"int {name}(void) {{ return 0; }}\n" for name in operations)
        used = "".join(f"    total += {name}();\n" for name in operations)
        used += "".join(
            f"    total += {embedded_description.SYMBOL}_{index}[0];\n"
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

    def test_an_empty_description_is_refused_rather_than_rendered(self):
        """An empty initialiser is not C every compiler accepts, and an empty
        description is not a smaller description of the machine."""
        with self.assertRaises(embedded_description.MalformedEmbedding):
            embedded_description.render("params/x.params", b"")

    def test_the_bytes_are_an_initialiser_rather_than_a_string_literal(self):
        """A literal would put the description under C11's 4095-character limit."""
        rendered = embedded_description.render("params/x.params", b"# a description\n")
        definition = rendered[rendered.index(f"const char {embedded_description.SYMBOL}") :]
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
