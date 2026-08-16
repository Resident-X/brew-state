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


def write(path: str, content: str) -> None:
    """Write one synthetic file, creating nothing around it."""
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content)


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
            self.structure(name)

    @staticmethod
    def _write(path: str, content: str) -> None:
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(content)

    def structure(self, name: str) -> str:
        """Add one more structure to the tree, as adding one to the real tree would."""
        directory = os.path.join(self.plant, name)
        os.makedirs(directory, exist_ok=True)
        self._write(os.path.join(directory, "plant_structure.h"), structure_header(name))
        return directory

    def consumer(self, name: str, content: str) -> str:
        directory = os.path.join(self.source, "app")
        os.makedirs(directory, exist_ok=True)
        path = os.path.join(directory, name)
        self._write(path, content)
        return path

    def declare(self, environments) -> str:
        """Write the build file declaring the given environments, and only those.

        The gates read this rather than being told what to cover, so a test
        showing a subject is covered without being named puts it here and
        changes no invocation.
        """
        return declare_environments(self.root.name, environments)

    def build_directory(self, environment: str) -> str:
        directory = os.path.join(self.root.name, ".pio", "build", environment)
        os.makedirs(directory, exist_ok=True)
        return directory

    def artefact(self, environment: str) -> str:
        return os.path.join(self.build_directory(environment), "program")

    def cleanup(self) -> None:
        self.root.cleanup()


def host_environment(structure: str | None = None, *, entry_point: bool = True, **options):
    """One host environment's options, as the build file would declare them."""
    terms = ["+<control/>"]
    if structure is not None:
        terms.append(f"+<plant/{structure}/>")
    if entry_point:
        terms.append("+<app/native/>")
    declared = {"platform": "native", "build_src_filter": " ".join(terms)}
    declared.update(options)
    return declared


def declare_environments(project: str, environments) -> str:
    """Write a build file declaring `[(name, options), ...]` and nothing else."""
    lines: list[str] = []
    for name, options in environments:
        lines.append(f"[env:{name}]")
        lines.extend(f"{option} = {value}" for option, value in options.items())
        lines.append("")
    path = os.path.join(project, "platformio.ini")
    write(path, "\n".join(lines))
    return path


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
    """SOL-PLANT-STRUCTURE-SEAM-FIRST-STRUCTURE.C6: one structure's symbols, and no other's.

    SOL-PLANT-SEAM-GATE-COVERAGE.C1: every structure is covered without being named.

    What the check concludes is the first criterion's and is unchanged. What is
    added here is that it reaches every structure in the tree from one
    invocation naming none of them, so a structure nobody remembered cannot go
    unchecked -- including the case that used to be invisible, a structure with
    no artefact at all.
    """

    @classmethod
    def setUpClass(cls):
        cls.compiler = os.environ.get("CC", "clang")
        if subprocess.run([cls.compiler, "--version"], capture_output=True, check=False).returncode:
            raise unittest.SkipTest(f"{cls.compiler} is not available on this host")

    def setUp(self):
        self.tree = SyntheticTree()
        self.addCleanup(self.tree.cleanup)

    def build(self, environment: str, *prefixes: str) -> str:
        """Link the environment's artefact, defining each named structure's symbol."""
        source = os.path.join(self.tree.root.name, f"{environment}.c")
        binary = self.tree.artefact(environment)
        definitions = "".join(f"void {prefix}_advance(void) {{}}\n" for prefix in prefixes)
        calls = "".join(f"    {prefix}_advance();\n" for prefix in prefixes)
        with open(source, "w", encoding="utf-8") as handle:
            handle.write(f"{definitions}int main(void) {{\n{calls}    return 0;\n}}\n")
        subprocess.run([self.compiler, "-o", binary, source], check=True)
        return binary

    def declare(self, *structures: str) -> None:
        self.tree.declare(
            [(f"host_{structure}", host_environment(structure)) for structure in structures]
        )

    def check(self, plant_root: str | None = None):
        return run_check(
            "check_structure_exclusive.py",
            "--project",
            self.tree.root.name,
            "--plant-root",
            plant_root or self.tree.plant,
            "--include-dir",
            self.tree.include,
        )

    def test_every_structure_is_covered_by_an_invocation_naming_none_of_them(self):
        self.declare("alpha", "beta")
        self.build("host_alpha", "alpha")
        self.build("host_beta", "beta")
        result = self.check()
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("'alpha'", result.stdout)
        self.assertIn("'beta'", result.stdout)

    def test_a_structure_added_to_the_tree_is_covered_with_no_change_to_the_invocation(self):
        # The invocation below is the same one the previous test makes. Adding
        # a structure and the environment that builds it is the whole change,
        # and it is what a forgotten line used to leave unchecked.
        self.tree.structure("gamma")
        self.declare("alpha", "beta", "gamma")
        self.build("host_alpha", "alpha")
        self.build("host_beta", "beta")
        self.build("host_gamma", "gamma")
        result = self.check()
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("'gamma'", result.stdout)

    def test_a_structure_no_environment_builds_is_reported_rather_than_skipped(self):
        # The failure the naming form could not see: beta is in the tree, and
        # nothing builds an artefact carrying it, so nothing checks it.
        self.declare("alpha")
        self.build("host_alpha", "alpha")
        result = self.check()
        self.assertEqual(1, result.returncode)
        self.assertIn("built by no environment", result.stderr)
        self.assertIn("beta", result.stderr)

    def test_an_artefact_built_for_the_other_structure_fails(self):
        self.declare("alpha", "beta")
        self.build("host_alpha", "beta")
        self.build("host_beta", "beta")
        result = self.check()
        self.assertEqual(1, result.returncode)
        self.assertIn("alpha_advance", result.stderr)
        self.assertIn("is not in the artefact", result.stderr)

    def test_a_second_structure_surviving_into_the_artefact_fails(self):
        self.declare("alpha", "beta")
        self.build("host_alpha", "alpha", "beta")
        self.build("host_beta", "beta")
        result = self.check()
        self.assertEqual(1, result.returncode)
        self.assertIn("beta_advance", result.stderr)
        self.assertIn("survived into the artefact", result.stderr)

    def test_a_failure_in_the_second_artefact_is_found_as_well_as_the_first(self):
        # A gate that stopped at the first artefact would cover the rest in
        # name only.
        self.declare("alpha", "beta")
        self.build("host_alpha", "alpha")
        self.build("host_beta", "beta", "alpha")
        result = self.check()
        self.assertEqual(1, result.returncode)
        self.assertIn("host_beta", result.stderr)
        self.assertIn("alpha_advance", result.stderr)

    def test_one_structure_leaves_nothing_to_exclude(self):
        single = SyntheticTree(structures=("alpha",))
        self.addCleanup(single.cleanup)
        self.declare("alpha")
        self.build("host_alpha", "alpha")
        result = self.check(plant_root=single.plant)
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
        self.declare("alpha", "beta")
        self.build("host_alpha", "alpha")
        self.build("host_beta", "beta")
        result = self.check()
        self.assertEqual(2, result.returncode)
        self.assertIn("no symbol unique to them", result.stderr)

    def test_a_missing_artefact_is_an_error_not_a_pass(self):
        self.declare("alpha", "beta")
        self.build("host_alpha", "alpha")
        result = self.check()
        self.assertEqual(2, result.returncode)
        self.assertIn("not been built", result.stderr)


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

    def build(self, environment: str, body: str) -> None:
        """Link one environment's artefact against a separate implementation of the seam.

        The consuming translation unit must *reference* the operation rather
        than define it -- an object that defines what it calls is not reaching
        through a seam at all, and the check says so rather than passing.

        Everything is placed where the build system places it, since that is
        where the check now goes looking rather than being handed the paths.
        """
        consumer = os.path.join(self.dir.name, f"{environment}.c")
        implementation = os.path.join(self.dir.name, f"{environment}_implementation.c")
        objects = os.path.join(self.dir.name, ".pio", "build", environment, "src", "app", "native")
        os.makedirs(objects, exist_ok=True)
        obj = os.path.join(objects, "consumer.o")
        binary = os.path.join(self.dir.name, ".pio", "build", environment, "program")

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

    def declare(self, *environments: str) -> None:
        declare_environments(
            self.dir.name, [(name, host_environment("alpha")) for name in environments]
        )

    def check(self):
        return run_check(
            "check_direct_calls.py",
            "--project",
            self.dir.name,
            "--header",
            self.header,
            "--objects-in",
            os.path.join("src", "app", "native"),
        )

    DIRECT = "int main(void) { return plant_model_step(1) - 1; }\n"
    THROUGH_A_POINTER = (
        "static int (*volatile dispatch)(int) = plant_model_step;\n"
        "int main(void) { return dispatch(1) - 1; }\n"
    )

    def test_a_direct_call_through_the_plant_seam_passes(self):
        self.declare("host")
        self.build("host", self.DIRECT)
        result = self.check()
        self.assertEqual(0, result.returncode, result.stderr)

    def test_binding_the_structure_through_a_pointer_fails(self):
        self.declare("host")
        self.build("host", self.THROUGH_A_POINTER)
        result = self.check()
        self.assertEqual(1, result.returncode)

    def test_a_second_artefact_is_inspected_as_well_as_the_first(self):
        # SOL-PLANT-SEAM-GATE-COVERAGE.C1: the artefacts are discovered, so an
        # environment added after the invocation was written is still covered.
        self.declare("host", "host_second")
        self.build("host", self.DIRECT)
        self.build("host_second", self.THROUGH_A_POINTER)
        result = self.check()
        self.assertEqual(1, result.returncode)
        self.assertIn("host_second", result.stderr)


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

    def setUp(self):
        sys.path.insert(0, TOOLS)
        import build_environments

        self.environment = build_environments.Environment(
            name="native", options=host_environment("thermoblock")
        )

    def test_the_required_flags_cover_analysis_and_the_strict_warnings(self):
        import check_sanitizers

        required = set(check_sanitizers.SANITIZER_FLAGS) | set(check_sanitizers.STRICT_FLAGS)
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

        required = check_sanitizers.SANITIZER_FLAGS + check_sanitizers.STRICT_FLAGS
        for dropped in required:
            kept = [f for f in required if f != dropped]
            database = [{"directory": project, "file": source, "arguments": ["cc", *kept, source]}]
            problems = check_sanitizers.analysis_problems(database, project, self.environment)
            self.assertTrue(
                any(dropped in problem for problem in problems),
                f"dropping {dropped} was not reported: {problems}",
            )

    def test_a_build_compiling_no_project_source_has_no_subject(self):
        import check_sanitizers

        project = tempfile.mkdtemp()
        os.makedirs(os.path.join(project, "src"))
        problems = check_sanitizers.analysis_problems([], project, self.environment)
        self.assertTrue(any("no subject" in problem for problem in problems), problems)

# --- check_support_status ---------------------------------------------------


SUPPORT_VOCABULARY = """
#ifndef PLANT_SUPPORT_H
#define PLANT_SUPPORT_H
typedef enum {
    PLANT_SUPPORT_UNVERIFIED = 0,
    PLANT_SUPPORT_HARDWARE_VERIFIED
} plant_support_status_t;
#endif
"""


class SupportTree:
    """A temporary tree of structures, a vocabulary, and a documented table."""

    def __init__(self, structures: tuple[str, ...] = ("alpha", "beta")):
        self.root = tempfile.TemporaryDirectory()
        self.include = os.path.join(self.root.name, "include")
        self.plant = os.path.join(self.root.name, "src", "plant")
        self.documentation = os.path.join(self.root.name, "README.md")
        os.makedirs(self.include)
        os.makedirs(self.plant)
        write(os.path.join(self.include, "plant_types.h"), NEUTRAL_TYPES)
        write(os.path.join(self.include, "plant_model.h"), NEUTRAL_MODEL)
        write(os.path.join(self.include, "plant_support.h"), SUPPORT_VOCABULARY)
        for name in structures:
            self.structure(name, "PLANT_SUPPORT_UNVERIFIED")
        self.document({name: "PLANT_SUPPORT_UNVERIFIED" for name in structures})

    def structure(self, name: str, status: str | None, evidence: str | None = None) -> str:
        """Write one structure, optionally declaring a status and a citation."""
        directory = os.path.join(self.plant, name)
        os.makedirs(directory, exist_ok=True)
        body = structure_header(name).replace(
            '#include "plant_types.h"', '#include "plant_support.h"\n#include "plant_types.h"'
        )
        declarations = ""
        if status is not None:
            declarations += f"#define PLANT_STRUCTURE_SUPPORT_STATUS {status}\n"
        if evidence is not None:
            declarations += f"#define PLANT_STRUCTURE_SUPPORT_EVIDENCE {evidence}\n"
        path = os.path.join(directory, "plant_structure.h")
        write(path, body.replace('#include "plant_types.h"\n', f'#include "plant_types.h"\n{declarations}'))
        return path

    def document(self, rows: dict, evidence: dict | None = None) -> None:
        """Write the documentation an adopter reads, with a status table in it."""
        evidence = evidence or {}
        lines = [
            "# Firmware",
            "",
            "| Path | What it holds |",
            "| --- | --- |",
            "| `src/plant/` | The structures. |",
            "",
            "| Structure | Support status | Evidence |",
            "| --- | --- | --- |",
        ]
        for name, status in rows.items():
            lines.append(f"| `{name}` | `{status}` | {evidence.get(name, '—')} |")
        write(self.documentation, "\n".join(lines) + "\n")

    def cleanup(self) -> None:
        self.root.cleanup()


class SupportTreeCase(unittest.TestCase):
    """A tree of structures, a vocabulary and a documented table, and the check."""

    def setUp(self):
        self.tree = SupportTree()
        self.addCleanup(self.tree.cleanup)

    def check(self, **overrides):
        return run_check(
            "check_support_status.py",
            "--plant-root",
            overrides.get("plant_root", self.tree.plant),
            "--include-dir",
            self.tree.include,
            "--documentation",
            overrides.get("documentation", self.tree.documentation),
        )


class StructureCarriesAStatus(SupportTreeCase):
    """SOL-PLANT-STRUCTURE-SUPPORT-STATUS.C1: no structure reaches the seam unanswered."""

    def test_every_structure_carrying_a_declared_status_passes(self):
        result = self.check()
        self.assertEqual(0, result.returncode, result.stderr)

    def test_a_structure_carrying_no_status_fails_and_names_it(self):
        self.tree.structure("beta", None)
        result = self.check()
        self.assertEqual(1, result.returncode)
        self.assertIn("beta", result.stderr)
        self.assertIn("PLANT_STRUCTURE_SUPPORT_STATUS", result.stderr)

    def test_a_status_outside_the_vocabulary_fails(self):
        self.tree.structure("beta", "PLANT_SUPPORT_PROBABLY_FINE")
        self.tree.document(
            {"alpha": "PLANT_SUPPORT_UNVERIFIED", "beta": "PLANT_SUPPORT_UNVERIFIED"}
        )
        result = self.check()
        self.assertEqual(1, result.returncode)
        self.assertIn("PLANT_SUPPORT_PROBABLY_FINE", result.stderr)
        self.assertIn("not one of the declared values", result.stderr)

    def test_a_structure_claiming_two_statuses_is_reported_rather_than_resolved(self):
        path = os.path.join(self.tree.plant, "beta", "plant_structure.h")
        with open(path, "a", encoding="utf-8") as handle:
            handle.write("#define PLANT_STRUCTURE_SUPPORT_STATUS PLANT_SUPPORT_HARDWARE_VERIFIED\n")
        result = self.check()
        self.assertEqual(1, result.returncode)
        self.assertIn("2 times", result.stderr)

    def test_a_commented_out_status_is_not_a_status(self):
        # The one that would otherwise let a structure look answered to a
        # reader skimming the header and to nothing else.
        self.tree.structure("beta", None)
        path = os.path.join(self.tree.plant, "beta", "plant_structure.h")
        with open(path, "a", encoding="utf-8") as handle:
            handle.write("/* #define PLANT_STRUCTURE_SUPPORT_STATUS PLANT_SUPPORT_UNVERIFIED */\n")
        result = self.check()
        self.assertEqual(1, result.returncode)
        self.assertIn("defines no PLANT_STRUCTURE_SUPPORT_STATUS", result.stderr)

    def test_a_structure_nothing_compiles_still_has_to_answer(self):
        # The check runs over the tree rather than over the structure a build
        # selected, so the structure nobody builds is not the one that escapes.
        self.tree.structure("gamma", None)
        self.tree.document(
            {
                "alpha": "PLANT_SUPPORT_UNVERIFIED",
                "beta": "PLANT_SUPPORT_UNVERIFIED",
                "gamma": "PLANT_SUPPORT_UNVERIFIED",
            }
        )
        result = self.check()
        self.assertEqual(1, result.returncode)
        self.assertIn("gamma", result.stderr)

    def test_a_status_carrying_a_trailing_comment_is_still_that_status(self):
        # The headers here are dense with explanation, so a note beside the
        # declaration is the natural way to write one. Reading the value off
        # the uncommented source is what keeps that from reading as a claim of
        # something outside the vocabulary.
        self.tree.structure("beta", "PLANT_SUPPORT_UNVERIFIED /* nothing on a bench yet */")
        result = self.check()
        self.assertEqual(0, result.returncode, result.stderr)

    def test_a_status_the_preprocessor_discards_is_not_a_status(self):
        self.tree.structure("beta", None)
        path = os.path.join(self.tree.plant, "beta", "plant_structure.h")
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(
                "#if 0\n#define PLANT_STRUCTURE_SUPPORT_STATUS PLANT_SUPPORT_UNVERIFIED\n#endif\n"
            )
        result = self.check()
        self.assertEqual(1, result.returncode)
        self.assertIn("defines no PLANT_STRUCTURE_SUPPORT_STATUS", result.stderr)

    def test_a_status_in_the_compiled_branch_of_a_conditional_still_counts(self):
        # The other side of the same handling: skipping a disabled branch must
        # not skip the branch that survives it.
        self.tree.structure("beta", None)
        path = os.path.join(self.tree.plant, "beta", "plant_structure.h")
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(
                "#if 0\n#define PLANT_STRUCTURE_SUPPORT_STATUS PLANT_SUPPORT_HARDWARE_VERIFIED\n"
                "#else\n#define PLANT_STRUCTURE_SUPPORT_STATUS PLANT_SUPPORT_UNVERIFIED\n#endif\n"
            )
        result = self.check()
        self.assertEqual(0, result.returncode, result.stderr)

    def test_no_structures_fails_rather_than_passing_vacuously(self):
        empty = tempfile.TemporaryDirectory()
        self.addCleanup(empty.cleanup)
        result = self.check(plant_root=empty.name)
        self.assertEqual(2, result.returncode)
        self.assertIn("nothing", result.stderr)

    def test_a_missing_plant_root_is_the_same_answer_as_an_empty_one(self):
        result = self.check(plant_root=os.path.join(self.tree.root.name, "nowhere"))
        self.assertEqual(2, result.returncode)
        self.assertIn("no plant root", result.stderr)

    def test_a_missing_vocabulary_is_an_error_not_a_pass(self):
        os.remove(os.path.join(self.tree.include, "plant_support.h"))
        result = self.check()
        self.assertEqual(2, result.returncode)
        self.assertIn("no vocabulary header", result.stderr)

    def test_a_vocabulary_declaring_no_status_type_is_an_error(self):
        write(os.path.join(self.tree.include, "plant_support.h"), "#define NOTHING 1\n")
        result = self.check()
        self.assertEqual(2, result.returncode)
        self.assertIn("declares no plant_support_status_t", result.stderr)


class VocabularyDrawsTheVerificationLine(SupportTreeCase):
    """SOL-PLANT-STRUCTURE-SUPPORT-STATUS.C2: verified or not, and no other distinction."""

    def test_a_vocabulary_that_has_grown_a_third_distinction_fails(self):
        write(
            os.path.join(self.tree.include, "plant_support.h"),
            SUPPORT_VOCABULARY.replace(
                "    PLANT_SUPPORT_HARDWARE_VERIFIED",
                "    PLANT_SUPPORT_PARTIALLY_VERIFIED,\n    PLANT_SUPPORT_HARDWARE_VERIFIED",
            ),
        )
        result = self.check()
        self.assertEqual(1, result.returncode)
        self.assertIn("PLANT_SUPPORT_PARTIALLY_VERIFIED", result.stderr)
        self.assertIn("beyond whether hardware has verified", result.stderr)

    def test_a_vocabulary_missing_the_verified_value_fails(self):
        write(
            os.path.join(self.tree.include, "plant_support.h"),
            SUPPORT_VOCABULARY.replace(",\n    PLANT_SUPPORT_HARDWARE_VERIFIED", ""),
        )
        result = self.check()
        self.assertEqual(1, result.returncode)
        self.assertIn("PLANT_SUPPORT_HARDWARE_VERIFIED", result.stderr)


class VerificationCostsACitation(SupportTreeCase):
    """SOL-PLANT-STRUCTURE-SUPPORT-STATUS.C3: the claimable value costs evidence."""

    def test_verification_claimed_with_a_citation_passes(self):
        self.tree.structure("beta", "PLANT_SUPPORT_HARDWARE_VERIFIED", '"run against a Gaggia Classic, 2026-01"')
        self.tree.document(
            {"alpha": "PLANT_SUPPORT_UNVERIFIED", "beta": "PLANT_SUPPORT_HARDWARE_VERIFIED"},
            evidence={"beta": "Gaggia Classic, 2026-01"},
        )
        result = self.check()
        self.assertEqual(0, result.returncode, result.stderr)

    def test_verification_claimed_with_nothing_cited_fails(self):
        self.tree.structure("beta", "PLANT_SUPPORT_HARDWARE_VERIFIED")
        self.tree.document(
            {"alpha": "PLANT_SUPPORT_UNVERIFIED", "beta": "PLANT_SUPPORT_HARDWARE_VERIFIED"},
            evidence={"beta": "trust me"},
        )
        result = self.check()
        self.assertEqual(1, result.returncode)
        self.assertIn("defines no PLANT_STRUCTURE_SUPPORT_EVIDENCE", result.stderr)

    def test_verification_claimed_with_an_empty_citation_fails(self):
        self.tree.structure("beta", "PLANT_SUPPORT_HARDWARE_VERIFIED", '""')
        self.tree.document(
            {"alpha": "PLANT_SUPPORT_UNVERIFIED", "beta": "PLANT_SUPPORT_HARDWARE_VERIFIED"},
            evidence={"beta": "somewhere"},
        )
        result = self.check()
        self.assertEqual(1, result.returncode)
        self.assertIn("says nothing about what was run", result.stderr)

    def test_a_placeholder_citation_is_refused_on_the_same_floor_as_the_table(self):
        # A dash in the table and a question mark in the header are the same
        # non-answer, so they meet the same floor. Whether a real citation is
        # a good one is a review question, not this check's.
        self.tree.structure("beta", "PLANT_SUPPORT_HARDWARE_VERIFIED", '"?"')
        self.tree.document(
            {"alpha": "PLANT_SUPPORT_UNVERIFIED", "beta": "PLANT_SUPPORT_HARDWARE_VERIFIED"},
            evidence={"beta": "somewhere"},
        )
        result = self.check()
        self.assertEqual(1, result.returncode)
        self.assertIn("says nothing about what was run", result.stderr)

    def test_a_citation_that_is_not_text_is_reported_as_unreadable(self):
        self.tree.structure("beta", "PLANT_SUPPORT_HARDWARE_VERIFIED", "BENCH_LOG_2026")
        self.tree.document(
            {"alpha": "PLANT_SUPPORT_UNVERIFIED", "beta": "PLANT_SUPPORT_HARDWARE_VERIFIED"},
            evidence={"beta": "a bench log"},
        )
        result = self.check()
        self.assertEqual(1, result.returncode)
        self.assertIn("not text this check or an adopter can read", result.stderr)

    def test_a_citation_split_over_several_lines_is_read_whole(self):
        self.tree.structure(
            "beta",
            "PLANT_SUPPORT_HARDWARE_VERIFIED",
            '"run against a Gaggia Classic, " \\\n    "2026-01"',
        )
        self.tree.document(
            {"alpha": "PLANT_SUPPORT_UNVERIFIED", "beta": "PLANT_SUPPORT_HARDWARE_VERIFIED"},
            evidence={"beta": "Gaggia Classic, 2026-01"},
        )
        result = self.check()
        self.assertEqual(0, result.returncode, result.stderr)

    def test_a_citation_on_a_structure_claiming_no_verification_is_refused(self):
        self.tree.structure("beta", "PLANT_SUPPORT_UNVERIFIED", '"ran it once, seemed fine"')
        result = self.check()
        self.assertEqual(1, result.returncode)
        self.assertIn("reads as verification the structure is not claiming", result.stderr)


class DocumentationSaysWhatTheSourcesSay(SupportTreeCase):
    """SOL-PLANT-STRUCTURE-SUPPORT-STATUS.C1: the status an adopter reads is the one claimed."""

    def test_a_structure_absent_from_the_documentation_fails(self):
        self.tree.document({"alpha": "PLANT_SUPPORT_UNVERIFIED"})
        result = self.check()
        self.assertEqual(1, result.returncode)
        self.assertIn("no row for the 'beta' structure", result.stderr)

    def test_documentation_disagreeing_with_the_source_fails(self):
        self.tree.document(
            {"alpha": "PLANT_SUPPORT_UNVERIFIED", "beta": "PLANT_SUPPORT_HARDWARE_VERIFIED"},
            evidence={"beta": "a bench, once"},
        )
        result = self.check()
        self.assertEqual(1, result.returncode)
        self.assertIn("documents the 'beta' structure as PLANT_SUPPORT_HARDWARE_VERIFIED", result.stderr)

    def test_documentation_of_a_structure_that_is_not_there_fails(self):
        self.tree.document(
            {
                "alpha": "PLANT_SUPPORT_UNVERIFIED",
                "beta": "PLANT_SUPPORT_UNVERIFIED",
                "ghost": "PLANT_SUPPORT_HARDWARE_VERIFIED",
            },
            evidence={"ghost": "a machine nobody has"},
        )
        result = self.check()
        self.assertEqual(1, result.returncode)
        self.assertIn("the tree has no such structure", result.stderr)

    def test_two_rows_for_one_structure_are_reported_rather_than_resolved(self):
        # The sources refuse two status claims outright; collapsing two
        # documented rows to whichever came last would publish one of them and
        # bury the other, in the half an adopter actually reads.
        with open(self.tree.documentation, "a", encoding="utf-8") as handle:
            handle.write("| `beta` | `PLANT_SUPPORT_HARDWARE_VERIFIED` | a bench, allegedly |\n")
        result = self.check()
        self.assertEqual(1, result.returncode)
        self.assertIn("documents the 'beta' structure 2 times", result.stderr)

    def test_documentation_carrying_no_status_table_fails(self):
        write(self.tree.documentation, "# Firmware\n\nNothing about support here.\n")
        result = self.check()
        self.assertEqual(1, result.returncode)
        self.assertIn("documents no structure's support status", result.stderr)

    def test_documented_verification_citing_nothing_fails(self):
        self.tree.structure("beta", "PLANT_SUPPORT_HARDWARE_VERIFIED", '"run against a Gaggia Classic"')
        self.tree.document(
            {"alpha": "PLANT_SUPPORT_UNVERIFIED", "beta": "PLANT_SUPPORT_HARDWARE_VERIFIED"},
            evidence={"beta": "—"},
        )
        result = self.check()
        self.assertEqual(1, result.returncode)
        self.assertIn("cites nothing an adopter can read", result.stderr)

    def test_missing_documentation_is_an_error_not_a_pass(self):
        result = self.check(documentation=os.path.join(self.tree.root.name, "nowhere.md"))
        self.assertEqual(2, result.returncode)
        self.assertIn("no documentation", result.stderr)


if __name__ == "__main__":
    unittest.main()
