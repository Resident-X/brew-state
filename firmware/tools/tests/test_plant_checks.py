"""The plant-model seam's build-time checks, against synthetic subjects.

Every check here exists to fail on something. A check is only worth having if
it fails when the property it names is broken, so each one is tested from both
sides: the clean subject passes, and a subject with the specific violation the
check exists for is caught with the file, line and symbol that make it
actionable. The vacuous cases -- nothing to inspect, nothing to exclude, a
subject the check cannot see -- are tested too, because those are the states in
which a check reports success without having established anything.

Nothing here is run against this project's own sources or its real structures.
The structures are synthetic and live in a temporary directory, so a legitimate
change to the machine-describing structure does not break these tests.
"""

from __future__ import annotations


import os
import stat
import subprocess
import sys
import tempfile
import unittest

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)

import structure_symbols  # noqa: E402
from structure_symbols import discover, exclusive_declarations, owned_names  # noqa: E402

# --- Synthetic subjects -----------------------------------------------------

NEUTRAL_TYPES = """
#ifndef PLANT_TYPES_H
#define PLANT_TYPES_H
#include <stdbool.h>
#include <stddef.h>
typedef struct {
    const char *name;
    double minimum;
    double maximum;
    size_t offset;
} plant_parameter_spec_t;
#endif
"""

NEUTRAL_MODEL = """
#ifndef PLANT_MODEL_H
#define PLANT_MODEL_H
#include "plant_types.h"
#include "plant_structure.h"
bool plant_model_init(plant_model_t *model, const plant_parameters_t *parameters);
bool plant_model_step(plant_model_t *model, double seconds);
#endif
"""


def structure_header(prefix: str) -> str:
    """A synthetic structure header owning names prefixed with `prefix`."""
    return f"""
#ifndef PLANT_STRUCTURE_H
#define PLANT_STRUCTURE_H
#include "plant_types.h"
typedef struct {{
    double {prefix}_coefficient;
}} plant_parameters_t;
typedef struct {{
    bool ready_flag;
    plant_parameters_t coefficients;
    double {prefix}_state;
}} plant_model_t;
const plant_parameter_spec_t *plant_structure_parameter_specs(size_t *count);
void {prefix}_advance(plant_model_t *model, double seconds);
#endif
"""


class SyntheticTree:
    """A temporary project with an include directory and two structures."""

    def __init__(self, structures=("alpha", "beta")):
        self.root = tempfile.TemporaryDirectory()
        self.include = os.path.join(self.root.name, "include")
        self.plant = os.path.join(self.root.name, "src", "plant")
        self.source = os.path.join(self.root.name, "src")
        os.makedirs(self.include)
        os.makedirs(self.plant)
        self._write(os.path.join(self.include, "plant_types.h"), NEUTRAL_TYPES)
        self._write(os.path.join(self.include, "plant_model.h"), NEUTRAL_MODEL)
        for name in structures:
            directory = os.path.join(self.plant, name)
            os.makedirs(directory)
            self._write(os.path.join(directory, "plant_structure.h"), structure_header(name))

    @staticmethod
    def _write(path: str, content: str) -> None:
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(content)

    def consumer(self, name: str, content: str) -> str:
        directory = os.path.join(self.source, "app")
        os.makedirs(directory, exist_ok=True)
        path = os.path.join(directory, name)
        self._write(path, content)
        return path

    def cleanup(self) -> None:
        self.root.cleanup()


def run_check(script: str, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, os.path.join(TOOLS, script), *args],
        capture_output=True,
        text=True,
        check=False,
    )


# --- structure_symbols ------------------------------------------------------


class StructureSymbolDetection(unittest.TestCase):
    """SOL-PLANT-STRUCTURE-SEAM-FIRST-STRUCTURE.C5: what counts as naming a structure."""

    def setUp(self):
        self.tree = SyntheticTree()
        self.addCleanup(self.tree.cleanup)
        self.structures = discover(self.tree.plant, self.tree.include)

    def test_both_structures_are_discovered(self):
        self.assertEqual(["alpha", "beta"], [s.name for s in self.structures])

    def test_a_directory_without_a_structure_header_is_not_a_structure(self):
        os.makedirs(os.path.join(self.tree.plant, "common"))
        with open(os.path.join(self.tree.plant, "common", "loader.c"), "w") as handle:
            handle.write("/* shared, not a structure */\n")
        self.assertEqual(
            ["alpha", "beta"],
            [s.name for s in discover(self.tree.plant, self.tree.include)],
        )

    def test_record_fields_are_members_and_functions_are_declarations(self):
        neutral = structure_symbols.neutral_names(self.tree.include)
        declarations, members = owned_names(structure_header("alpha"), neutral)
        self.assertIn("alpha_advance", declarations)
        self.assertIn("plant_structure_parameter_specs", declarations)
        self.assertIn("alpha_coefficient", members)
        self.assertIn("alpha_state", members)
        self.assertIn("ready_flag", members)

    def test_names_the_seam_already_carries_are_not_a_structures_to_own(self):
        neutral = structure_symbols.neutral_names(self.tree.include)
        declarations, members = owned_names(structure_header("alpha"), neutral)
        # Both are declared in the structure header, but the seam's own headers
        # name them, so they belong to the interface rather than the structure.
        self.assertNotIn("plant_parameters_t", declarations | members)
        self.assertNotIn("plant_model_t", declarations | members)
        # A field named after the seam's own vocabulary is excluded too. That
        # exclusion is what the encapsulation check refuses outright, since it
        # would blind the check for that field in every consumer at once.
        shadowing = structure_header("alpha").replace("double alpha_state;", "double minimum;")
        _, shadowed = owned_names(shadowing, neutral)
        self.assertNotIn("minimum", shadowed)

    def test_a_member_access_is_a_violation(self):
        source = "void f(void) { extern double x; x = record.alpha_coefficient; }\n"
        found = structure_symbols.find_violations("c.c", source, self.structures)
        self.assertEqual(1, len(found))
        self.assertEqual("alpha_coefficient", found[0].symbol)
        self.assertEqual(1, found[0].line)
        self.assertIn("alpha", found[0].kind)

    def test_an_arrow_access_is_a_violation_too(self):
        source = "double g(void) { return model->beta_state; }\n"
        found = structure_symbols.find_violations("c.c", source, self.structures)
        self.assertEqual(["beta_state"], [v.symbol for v in found])

    def test_a_local_sharing_a_field_name_is_not_a_violation(self):
        source = "void f(void) { double alpha_coefficient = 1.0; (void)alpha_coefficient; }\n"
        self.assertEqual([], structure_symbols.find_violations("c.c", source, self.structures))

    def test_naming_a_structures_function_is_a_violation_anywhere(self):
        source = "void f(void) { alpha_advance(0, 1.0); }\n"
        found = structure_symbols.find_violations("c.c", source, self.structures)
        self.assertEqual(["alpha_advance"], [v.symbol for v in found])

    def test_including_a_structures_own_header_is_a_violation(self):
        source = '#include "plant_structure.h"\n'
        found = structure_symbols.find_violations("c.c", source, self.structures)
        self.assertEqual("structure header include", found[0].kind)

    def test_including_a_path_inside_a_structure_is_a_violation(self):
        source = '#include "plant/alpha/equations.h"\n'
        found = structure_symbols.find_violations("c.c", source, self.structures)
        self.assertEqual("structure directory include", found[0].kind)

    def test_including_the_seam_header_is_not_a_violation(self):
        source = '#include "plant_model.h"\n'
        self.assertEqual([], structure_symbols.find_violations("c.c", source, self.structures))

    def test_an_include_named_by_a_macro_is_a_violation(self):
        source = "#include WHICHEVER_HEADER\n"
        found = structure_symbols.find_violations("c.c", source, self.structures)
        self.assertEqual("include the check cannot resolve", found[0].kind)

    def test_a_structure_name_in_a_comment_or_string_is_not_a_violation(self):
        source = '/* alpha_advance is the one */\nconst char *s = "alpha_coefficient";\n'
        self.assertEqual([], structure_symbols.find_violations("c.c", source, self.structures))

    def test_line_numbers_survive_comment_stripping(self):
        source = "/* a\n   multi-line\n   comment */\nvoid f(void) { alpha_advance(0, 1.0); }\n"
        found = structure_symbols.find_violations("c.c", source, self.structures)
        self.assertEqual(4, found[0].line)

    def test_a_tree_with_no_structures_is_an_error_not_an_empty_answer(self):
        with self.assertRaises(SystemExit):
            structure_symbols.find_violations("c.c", "int x;\n", [])

    def test_only_names_unique_to_a_structure_can_witness_it(self):
        exclusive = exclusive_declarations(self.structures)
        # Shared by both, so it cannot tell two artefacts apart.
        self.assertNotIn("plant_structure_parameter_specs", exclusive["alpha"])
        self.assertNotIn("PLANT_STRUCTURE_H", exclusive["alpha"])
        self.assertEqual({"alpha_advance"}, set(exclusive["alpha"]))
        self.assertEqual({"beta_advance"}, set(exclusive["beta"]))


# --- check_plant_encapsulation ----------------------------------------------


class PlantEncapsulationCheck(unittest.TestCase):
    """SOL-PLANT-STRUCTURE-SEAM-FIRST-STRUCTURE.C5: the build fails on a direct reference."""

    def setUp(self):
        self.tree = SyntheticTree()
        self.addCleanup(self.tree.cleanup)

    def check(self, *extra):
        return run_check(
            "check_plant_encapsulation.py",
            self.tree.source,
            *extra,
            "--plant-root",
            self.tree.plant,
            "--include-dir",
            self.tree.include,
        )

    def test_a_clean_consumer_passes(self):
        self.tree.consumer("main.c", '#include "plant_model.h"\nint main(void) { return 0; }\n')
        result = self.check()
        self.assertEqual(0, result.returncode, result.stderr)

    def test_a_direct_reference_fails_and_names_file_line_and_symbol(self):
        path = self.tree.consumer(
            "main.c",
            '#include "plant_model.h"\n'
            "int main(void) { return (int)model.alpha_coefficient; }\n",
        )
        result = self.check()
        self.assertEqual(1, result.returncode)
        self.assertIn(os.path.basename(path), result.stderr)
        self.assertIn(":2:", result.stderr)
        self.assertIn("alpha_coefficient", result.stderr)

    def test_the_structures_themselves_are_exempt(self):
        # A structure's own source names its own symbols; that is its job.
        with open(os.path.join(self.tree.plant, "alpha", "plant_structure.c"), "w") as handle:
            handle.write('#include "plant_model.h"\nvoid alpha_advance(void) {}\n')
        self.tree.consumer("main.c", "int main(void) { return 0; }\n")
        result = self.check()
        self.assertEqual(0, result.returncode, result.stderr)

    def test_no_structures_fails_rather_than_passing_vacuously(self):
        empty = tempfile.mkdtemp()
        self.tree.consumer("main.c", "int main(void) { return 0; }\n")
        result = run_check(
            "check_plant_encapsulation.py",
            self.tree.source,
            "--plant-root",
            empty,
            "--include-dir",
            self.tree.include,
        )
        self.assertEqual(2, result.returncode)
        self.assertIn("no structures", result.stderr)

    def test_no_consumer_sources_fails_rather_than_passing_vacuously(self):
        # Only the structures exist, so there is nothing to inspect.
        result = run_check(
            "check_plant_encapsulation.py",
            self.tree.plant,
            "--plant-root",
            self.tree.plant,
            "--include-dir",
            self.tree.include,
        )
        self.assertEqual(2, result.returncode)
        self.assertIn("no consumer sources", result.stderr)

    def test_a_missing_path_is_an_error_not_a_pass(self):
        result = self.check(os.path.join(self.tree.root.name, "nowhere"))
        self.assertEqual(2, result.returncode)

    def test_a_field_named_after_the_seams_vocabulary_is_refused(self):
        # `offset` is a field of the seam's own parameter-spec type, so a
        # structure field of that name is dropped from the structure's members
        # to protect consumers' locals -- and reaching it then goes undetected
        # everywhere at once. The structure has to rename it instead.
        path = os.path.join(self.tree.plant, "alpha", "plant_structure.h")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(structure_header("alpha").replace("double alpha_state;", "double offset;"))
        self.tree.consumer("main.c", "int main(void) { return 0; }\n")
        result = self.check()
        self.assertEqual(2, result.returncode)
        self.assertIn("share a name with the seam's own vocabulary", result.stderr)
        self.assertIn("offset", result.stderr)

    def test_a_field_reached_through_that_shadowing_would_otherwise_be_invisible(self):
        # The same subject, showing what the guard above is buying: without it
        # the check reports the consumer clean while it reads the field.
        path = os.path.join(self.tree.plant, "alpha", "plant_structure.h")
        source = structure_header("alpha").replace("double alpha_state;", "double offset;")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(source)
        structures = discover(self.tree.plant, self.tree.include)
        reaching = "double g(void) { return model->offset; }\n"
        self.assertEqual([], structure_symbols.find_violations("c.c", reaching, structures))
        neutral = structure_symbols.neutral_names(self.tree.include)
        self.assertIn("offset", structure_symbols.shadowed_members(source, neutral))


# --- check_structure_selection ----------------------------------------------


class StructureSelectionCheck(unittest.TestCase):
    """SOL-PLANT-STRUCTURE-SEAM-FIRST-STRUCTURE.C7: exactly one structure, or the build stops."""

    def setUp(self):
        self.tree = SyntheticTree()
        self.addCleanup(self.tree.cleanup)

    def check(self, source_filter: str):
        return run_check(
            "check_structure_selection.py",
            "--filter",
            source_filter,
            "--plant-root",
            self.tree.plant,
        )

    def test_exactly_one_structure_passes(self):
        result = self.check("+<control/> +<plant/common/> +<plant/alpha/> +<app/>")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("alpha", result.stdout)

    def test_naming_none_while_compiling_the_model_fails(self):
        result = self.check("+<control/> +<plant/common/> +<app/>")
        self.assertEqual(1, result.returncode)
        self.assertIn("names no structure", result.stderr)
        self.assertIn("alpha", result.stderr)

    def test_naming_two_fails(self):
        result = self.check("+<plant/common/> +<plant/alpha/> +<plant/beta/>")
        self.assertEqual(1, result.returncode)
        self.assertIn("names 2 structures", result.stderr)

    def test_naming_the_whole_plant_directory_is_the_two_structure_case(self):
        result = self.check("+<control/> +<plant/>")
        self.assertEqual(1, result.returncode)
        self.assertIn("names 2 structures", result.stderr)

    def test_a_build_compiling_no_plant_source_is_not_a_model_build(self):
        result = self.check("+<control/> +<hw/stm32/> +<app/stm32/>")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("not a model build", result.stdout)

    def test_an_excluded_structure_is_not_counted(self):
        result = self.check("+<plant/> -<plant/beta/>")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("alpha", result.stdout)

    def test_an_empty_filter_is_an_error_not_a_pass(self):
        # An unresolvable filter must not read as "compiles no plant source".
        result = self.check("   ")
        self.assertEqual(2, result.returncode)
        self.assertIn("cannot be established", result.stderr)


# --- check_plant_header -----------------------------------------------------


class PlantHeaderCheck(unittest.TestCase):
    """SOL-PLANT-STRUCTURE-SEAM-FIRST-STRUCTURE.C1: the seam header names no structure."""

    def setUp(self):
        self.tree = SyntheticTree()
        self.addCleanup(self.tree.cleanup)
        self.header = os.path.join(self.tree.include, "plant_model.h")

    def check(self, plant_root: str | None = None):
        return run_check(
            "check_plant_header.py",
            self.header,
            "--plant-root",
            plant_root or self.tree.plant,
            "--include-dir",
            self.tree.include,
        )

    def rewrite(self, content: str) -> None:
        with open(self.header, "w", encoding="utf-8") as handle:
            handle.write(content)

    def test_a_neutral_header_passes_against_every_structure(self):
        result = self.check()
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("alpha", result.stdout)
        self.assertIn("beta", result.stdout)

    def test_a_header_naming_a_structure_fails(self):
        self.rewrite(NEUTRAL_MODEL.replace("bool plant_model_step", "/**/\nint alpha;\nbool plant_model_step"))
        result = self.check()
        self.assertEqual(1, result.returncode)
        self.assertIn("names a structure", result.stderr)

    def test_a_header_reaching_into_a_structure_directory_fails(self):
        self.rewrite(NEUTRAL_MODEL.replace('#include "plant_structure.h"', '#include "alpha/plant_structure.h"'))
        result = self.check()
        self.assertEqual(1, result.returncode)
        self.assertIn("names a structure", result.stderr)

    def test_a_header_carrying_a_function_definition_fails(self):
        self.rewrite(NEUTRAL_MODEL.replace("bool plant_model_step(plant_model_t *model, double seconds);",
                                           "static double square(double x) { return x * x; }"))
        result = self.check()
        self.assertEqual(1, result.returncode)
        self.assertIn("function definition", result.stderr)

    def test_a_header_declaring_no_operation_fails(self):
        self.rewrite('#ifndef PLANT_MODEL_H\n#define PLANT_MODEL_H\n#include "plant_types.h"\n#include "plant_structure.h"\n#endif\n')
        result = self.check()
        self.assertEqual(1, result.returncode)
        self.assertIn("declares no operation", result.stderr)

    def test_a_header_reaching_into_a_structures_record_fails(self):
        # A field only one structure has is exactly the dependency the seam
        # exists to prevent, and it hides from the directory-name check: the
        # name does not contain the structure's own, and a macro body is never
        # expanded, so the standalone compile succeeds either way.
        self.rewrite(
            NEUTRAL_MODEL.replace(
                "bool plant_model_step(plant_model_t *model, double seconds);",
                "double plant_model_first(const plant_parameters_t *p);\n"
                "#define PLANT_FIRST(p) ((p)->alpha_coefficient)",
            )
        )
        result = self.check()
        self.assertEqual(1, result.returncode)
        self.assertIn("reaches into a structure", result.stderr)
        self.assertIn("alpha_coefficient", result.stderr)

    def test_a_header_naming_a_structures_function_fails(self):
        self.rewrite(
            NEUTRAL_MODEL.replace(
                "bool plant_model_step(plant_model_t *model, double seconds);",
                "void alpha_advance(plant_model_t *model, double seconds);",
            )
        )
        result = self.check()
        self.assertEqual(1, result.returncode)
        self.assertIn("alpha_advance", result.stderr)

    def test_naming_the_types_a_structure_supplies_is_not_a_violation(self):
        # plant_model_t and plant_parameters_t are defined by whichever
        # structure the build compiles. Declaring operations in terms of them
        # is what the seam is for, so it must not read as reaching into one.
        result = self.check()
        self.assertEqual(0, result.returncode, result.stderr)


    def check_vocabulary_only(self):
        return run_check(
            "check_plant_header.py",
            self.header,
            "--plant-root",
            self.tree.plant,
            "--include-dir",
            self.tree.include,
            "--vocabulary-only",
        )

    def test_vocabulary_only_accepts_a_header_that_declares_no_operation(self):
        # This is the one condition the flag exists to drop.
        self.rewrite(
            '#ifndef PLANT_MODEL_H\n#define PLANT_MODEL_H\n#include "plant_types.h"\n'
            '#include "plant_structure.h"\n#endif\n'
        )
        self.assertEqual(1, self.check().returncode)
        result = self.check_vocabulary_only()
        self.assertEqual(0, result.returncode, result.stderr)

    def test_vocabulary_only_still_refuses_a_function_definition(self):
        # Widening the flag to skip this too would restore the hole it closed:
        # an equation could then live in the header nothing inspects.
        self.rewrite(
            '#ifndef PLANT_MODEL_H\n#define PLANT_MODEL_H\n#include "plant_types.h"\n'
            '#include "plant_structure.h"\n'
            "static float square(float x) { return x * x; }\n#endif\n"
        )
        result = self.check_vocabulary_only()
        self.assertEqual(1, result.returncode)
        self.assertIn("function definition", result.stderr)

    def test_vocabulary_only_still_refuses_reaching_into_a_structure(self):
        self.rewrite(
            '#ifndef PLANT_MODEL_H\n#define PLANT_MODEL_H\n#include "plant_types.h"\n'
            '#include "plant_structure.h"\n'
            "#define PLANT_FIRST(p) ((p)->alpha_coefficient)\n#endif\n"
        )
        result = self.check_vocabulary_only()
        self.assertEqual(1, result.returncode)
        self.assertIn("alpha_coefficient", result.stderr)

    def test_vocabulary_only_still_refuses_a_named_structure(self):
        self.rewrite(
            '#ifndef PLANT_MODEL_H\n#define PLANT_MODEL_H\n#include "plant_types.h"\n'
            '#include "alpha/plant_structure.h"\n#endif\n'
        )
        result = self.check_vocabulary_only()
        self.assertEqual(1, result.returncode)
        self.assertIn("names a structure", result.stderr)

    def test_one_structure_is_not_enough_to_establish_neutrality(self):
        single = SyntheticTree(structures=("alpha",))
        self.addCleanup(single.cleanup)
        result = self.check(plant_root=single.plant)
        self.assertEqual(2, result.returncode)
        self.assertIn("fewer than two", result.stderr)


# --- check_structure_exclusive ----------------------------------------------


class StructureExclusiveCheck(unittest.TestCase):
    """SOL-PLANT-STRUCTURE-SEAM-FIRST-STRUCTURE.C6: one structure's symbols, and no other's."""

    @classmethod
    def setUpClass(cls):
        cls.compiler = os.environ.get("CC", "clang")
        if subprocess.run([cls.compiler, "--version"], capture_output=True, check=False).returncode:
            raise unittest.SkipTest(f"{cls.compiler} is not available on this host")

    def setUp(self):
        self.tree = SyntheticTree()
        self.addCleanup(self.tree.cleanup)

    def build(self, prefix: str) -> str:
        """Link a tiny executable defining one structure's unique symbol."""
        source = os.path.join(self.tree.root.name, f"{prefix}.c")
        binary = os.path.join(self.tree.root.name, f"{prefix}.out")
        with open(source, "w", encoding="utf-8") as handle:
            handle.write(
                f"void {prefix}_advance(void) {{}}\n"
                f"int main(void) {{ {prefix}_advance(); return 0; }}\n"
            )
        subprocess.run([self.compiler, "-o", binary, source], check=True)
        return binary

    def check(self, binary: str, structure: str, plant_root: str | None = None):
        return run_check(
            "check_structure_exclusive.py",
            binary,
            "--structure",
            structure,
            "--plant-root",
            plant_root or self.tree.plant,
            "--include-dir",
            self.tree.include,
        )

    def test_an_artefact_carrying_only_its_own_structure_passes(self):
        result = self.check(self.build("alpha"), "alpha")
        self.assertEqual(0, result.returncode, result.stderr)

    def test_the_check_reverses_for_the_other_structure(self):
        result = self.check(self.build("beta"), "beta")
        self.assertEqual(0, result.returncode, result.stderr)

    def test_an_artefact_built_for_the_other_structure_fails(self):
        result = self.check(self.build("beta"), "alpha")
        self.assertEqual(1, result.returncode)
        self.assertIn("alpha_advance", result.stderr)
        self.assertIn("is not in the artefact", result.stderr)

    def test_a_second_structure_surviving_into_the_artefact_fails(self):
        source = os.path.join(self.tree.root.name, "both.c")
        binary = os.path.join(self.tree.root.name, "both.out")
        with open(source, "w", encoding="utf-8") as handle:
            handle.write(
                "void alpha_advance(void) {}\n"
                "void beta_advance(void) {}\n"
                "int main(void) { alpha_advance(); beta_advance(); return 0; }\n"
            )
        subprocess.run([self.compiler, "-o", binary, source], check=True)
        result = self.check(binary, "alpha")
        self.assertEqual(1, result.returncode)
        self.assertIn("beta_advance", result.stderr)
        self.assertIn("survived into the artefact", result.stderr)

    def test_one_structure_leaves_nothing_to_exclude(self):
        single = SyntheticTree(structures=("alpha",))
        self.addCleanup(single.cleanup)
        result = self.check(self.build("alpha"), "alpha", plant_root=single.plant)
        self.assertEqual(2, result.returncode)
        self.assertIn("nothing to exclude", result.stderr)

    def test_a_structure_with_no_unique_symbol_is_reported_rather_than_passed(self):
        # Two structures whose headers declare exactly the same names cannot be
        # told apart in an artefact, which is the state that would make this
        # check pass unconditionally.
        for name in ("alpha", "beta"):
            path = os.path.join(self.tree.plant, name, "plant_structure.h")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(structure_header("shared"))
        result = self.check(self.build("alpha"), "alpha")
        self.assertEqual(2, result.returncode)
        self.assertIn("no symbol unique to them", result.stderr)

    def test_a_structure_that_is_not_in_the_tree_is_an_error(self):
        result = self.check(self.build("alpha"), "gamma")
        self.assertEqual(2, result.returncode)

    def test_a_missing_executable_is_an_error_not_a_pass(self):
        result = self.check(os.path.join(self.tree.root.name, "nothing.out"), "alpha")
        self.assertEqual(2, result.returncode)


# --- check_parameters_are_data ----------------------------------------------


class ParametersAreDataCheck(unittest.TestCase):
    """SOL-PLANT-STRUCTURE-SEAM-FIRST-STRUCTURE.C3: one artefact, two descriptions, two runs."""

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.a = self.write("a.params", "gain = 1.0\n")
        self.b = self.write("b.params", "gain = 2.0\n")

    def write(self, name: str, content: str) -> str:
        path = os.path.join(self.dir.name, name)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(content)
        return path

    def executable(self, body: str) -> str:
        path = os.path.join(self.dir.name, "program")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("#!/bin/sh\n" + body)
        os.chmod(path, os.stat(path).st_mode | stat.S_IEXEC)
        return path

    def check(self, executable: str):
        return run_check(
            "check_parameters_are_data.py", executable, "--params", self.a, "--params", self.b
        )

    def test_two_descriptions_giving_two_trajectories_passes(self):
        result = self.check(self.executable('cat "$1"\n'))
        self.assertEqual(0, result.returncode, result.stderr)

    def test_a_coefficient_compiled_in_gives_the_same_trajectory_twice_and_fails(self):
        result = self.check(self.executable('echo "gain = 1.0"\n'))
        self.assertEqual(1, result.returncode)
        self.assertIn("same trajectory", result.stderr)

    def test_a_run_that_fails_is_reported(self):
        result = self.check(self.executable('cat "$1"\nexit 3\n'))
        self.assertEqual(1, result.returncode)
        self.assertIn("the run failed", result.stderr)

    def test_an_artefact_rebuilt_between_the_runs_establishes_nothing(self):
        # The "executable" rewrites itself, standing in for a rebuild.
        path = self.executable('cat "$1"\nprintf "#\\n" >> "$0"\n')
        result = self.check(path)
        self.assertEqual(1, result.returncode)
        self.assertIn("changed between the runs", result.stderr)

    def test_one_description_cannot_establish_anything(self):
        result = run_check(
            "check_parameters_are_data.py",
            self.executable('cat "$1"\n'),
            "--params",
            self.a,
        )
        self.assertEqual(2, result.returncode)
        self.assertIn("two descriptions are needed", result.stderr)

    def test_a_missing_description_is_an_error_not_a_pass(self):
        result = run_check(
            "check_parameters_are_data.py",
            self.executable('cat "$1"\n'),
            "--params",
            self.a,
            "--params",
            os.path.join(self.dir.name, "absent.params"),
        )
        self.assertEqual(2, result.returncode)


# --- check_selection_refused ------------------------------------------------


class SelectionRefusedCheck(unittest.TestCase):
    """SOL-PLANT-STRUCTURE-SEAM-FIRST-STRUCTURE.C7: the refusal itself is exercised."""

    def setUp(self):
        self.project = tempfile.TemporaryDirectory()
        self.addCleanup(self.project.cleanup)

    def fake_pio(self, body: str) -> str:
        path = os.path.join(self.project.name, "pio")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("#!/bin/sh\n" + body)
        os.chmod(path, os.stat(path).st_mode | stat.S_IEXEC)
        return path

    def check(self, pio: str, env: str = "native_no_structure"):
        return run_check(
            "check_selection_refused.py", "--project", self.project.name, "--env", env, "--pio", pio
        )

    def test_a_build_that_stops_on_the_selection_check_passes(self):
        result = self.check(self.fake_pio('echo "check_structure_selection: names no structure"\nexit 1\n'))
        self.assertEqual(0, result.returncode, result.stderr)

    def test_a_build_that_succeeds_fails_the_check(self):
        result = self.check(self.fake_pio('echo "check_structure_selection: ok"\nexit 0\n'))
        self.assertEqual(1, result.returncode)
        self.assertIn("succeeded rather than refusing", result.stderr)

    def test_stopping_for_some_other_reason_fails_the_check(self):
        # A build that fails to compile is not a build that refused to select.
        result = self.check(self.fake_pio('echo "undefined reference to plant_model_init"\nexit 1\n'))
        self.assertEqual(1, result.returncode)
        self.assertIn("some reason other than structure selection", result.stderr)

    def test_an_artefact_left_behind_fails_the_check(self):
        build_dir = os.path.join(self.project.name, ".pio", "build", "native_no_structure")
        os.makedirs(build_dir)
        result = self.check(
            self.fake_pio(
                'echo "check_structure_selection: names no structure"\n'
                f'touch "{build_dir}/program"\n'
                "exit 1\n"
            )
        )
        self.assertEqual(1, result.returncode)
        self.assertIn("left an artefact behind", result.stderr)




# --- The plant seam's share of the checks it did not have to reimplement -----


class PlantSeamDirectCalls(unittest.TestCase):
    """SOL-PLANT-STRUCTURE-SEAM-FIRST-STRUCTURE.C8: calls through the plant seam are direct.

    The check itself is the hardware seam's and is not reimplemented here. What
    is established is that it applies to *this* seam: that its declarations are
    read out of plant_model.h, that a direct call through them passes, and that
    routing one through a function pointer -- which is how a structure would
    come to be bound while the program runs -- fails.
    """

    @classmethod
    def setUpClass(cls):
        cls.compiler = os.environ.get("CC", "clang")
        if subprocess.run([cls.compiler, "--version"], capture_output=True, check=False).returncode:
            raise unittest.SkipTest(f"{cls.compiler} is not available on this host")

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.header = os.path.join(self.dir.name, "plant_model.h")
        with open(self.header, "w", encoding="utf-8") as handle:
            handle.write(
                "#ifndef PLANT_MODEL_H\n#define PLANT_MODEL_H\n"
                "int plant_model_step(int millis);\n"
                "#endif\n"
            )

    def build(self, body: str) -> tuple[str, str]:
        """Link a consumer against a separate implementation of the seam.

        The consuming translation unit must *reference* the operation rather
        than define it -- an object that defines what it calls is not reaching
        through a seam at all, and the check says so rather than passing.
        """
        consumer = os.path.join(self.dir.name, "consumer.c")
        implementation = os.path.join(self.dir.name, "implementation.c")
        obj = os.path.join(self.dir.name, "consumer.o")
        binary = os.path.join(self.dir.name, "program")

        with open(consumer, "w", encoding="utf-8") as handle:
            handle.write('#include "plant_model.h"\n' + body)
        with open(implementation, "w", encoding="utf-8") as handle:
            handle.write('#include "plant_model.h"\nint plant_model_step(int m) { return m; }\n')

        subprocess.run(
            [self.compiler, "-O0", "-c", "-o", obj, "-I", self.dir.name, consumer], check=True
        )
        subprocess.run(
            [self.compiler, "-O0", "-o", binary, "-I", self.dir.name, consumer, implementation],
            check=True,
        )
        return binary, obj

    def check(self, binary: str, obj: str):
        return run_check("check_direct_calls.py", binary, "--header", self.header, "--objects", obj)

    def test_a_direct_call_through_the_plant_seam_passes(self):
        binary, obj = self.build("int main(void) { return plant_model_step(1) - 1; }\n")
        result = self.check(binary, obj)
        self.assertEqual(0, result.returncode, result.stderr)

    def test_binding_the_structure_through_a_pointer_fails(self):
        binary, obj = self.build(
            "static int (*volatile dispatch)(int) = plant_model_step;\n"
            "int main(void) { return dispatch(1) - 1; }\n"
        )
        result = self.check(binary, obj)
        self.assertEqual(1, result.returncode)


class PlantSourcesUnderTheHostTiersAnalysis(unittest.TestCase):
    """SOL-PLANT-STRUCTURE-SEAM-FIRST-STRUCTURE.C9: the new sources are under the same analysis.

    The criterion asks for two things of every source of this project's own:
    the memory and undefined-behaviour analysis, and the strict warning
    settings that make a conversion or a shadowed name a failure. Requiring
    only the first would let the second be dropped from the build file with
    everything still green, so both are asserted here against the check's own
    contract, and the enlargement guard is asserted alongside them -- adding a
    directory of sources must not be able to narrow what is analysed.
    """

    def test_the_required_flags_cover_analysis_and_the_strict_warnings(self):
        sys.path.insert(0, TOOLS)
        import check_sanitizers

        required = set(check_sanitizers.REQUIRED_COMPILE_FLAGS)
        self.assertIn("-fsanitize=address,undefined", required)
        self.assertIn("-fno-sanitize-recover=all", required)
        self.assertIn("-Werror", required)
        self.assertIn("-Wconversion", required)
        self.assertIn("-Wshadow", required)

    def test_a_source_missing_any_required_flag_is_reported(self):
        import check_sanitizers

        project = tempfile.mkdtemp()
        source_dir = os.path.join(project, "src", "plant", "thermoblock")
        os.makedirs(source_dir)
        source = os.path.join(source_dir, "plant_structure.c")
        with open(source, "w", encoding="utf-8") as handle:
            handle.write("int x;\n")

        for dropped in check_sanitizers.REQUIRED_COMPILE_FLAGS:
            kept = [f for f in check_sanitizers.REQUIRED_COMPILE_FLAGS if f != dropped]
            database = [{"directory": project, "file": source, "arguments": ["cc", *kept, source]}]
            problems = check_sanitizers.analysis_problems(database, project, "native")
            self.assertTrue(
                any(dropped in problem for problem in problems),
                f"dropping {dropped} was not reported: {problems}",
            )

    def test_a_build_compiling_no_project_source_has_no_subject(self):
        import check_sanitizers

        project = tempfile.mkdtemp()
        os.makedirs(os.path.join(project, "src"))
        problems = check_sanitizers.analysis_problems([], project, "native")
        self.assertTrue(any("no subject" in problem for problem in problems), problems)

if __name__ == "__main__":
    unittest.main()
