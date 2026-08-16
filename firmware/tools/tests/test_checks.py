"""Tests for the build-time checks that enforce the hardware seam.

The checks are what turn the seam's properties into things the toolchain
asserts, so a check that cannot fail asserts nothing. Every check here is
therefore exercised against a violation as well as against clean input, with
synthetic fixtures compiled in a temporary directory rather than against the
project's own sources -- the checks have to keep working when the project's
sources change.

Run with: python3 -m unittest discover -s firmware/tools/tests
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import textwrap
import unittest

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)

import check_control_identical  # noqa: E402
import check_direct_calls  # noqa: E402
import check_encapsulation  # noqa: E402
import check_sanitizers  # noqa: E402
import vendor_symbols  # noqa: E402

CC = os.environ.get("CC", "clang")


def write(directory: str, name: str, content: str) -> str:
    path = os.path.join(directory, name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(textwrap.dedent(content))
    return path


def run_tool(script: str, *arguments: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, os.path.join(TOOLS, script), *arguments],
        capture_output=True,
        text=True,
        check=False,
    )


class VendorSymbolDetection(unittest.TestCase):
    """SOL-CONTROL-HARDWARE-SEAM-HOST-SIM.C5: what counts as reaching the vendor."""

    def test_hal_call_is_a_violation(self):
        violations = vendor_symbols.find_violations("a.c", "void f(void) { HAL_GPIO_Init(); }\n")
        self.assertEqual(1, len(violations))
        self.assertEqual("HAL_GPIO_Init", violations[0].symbol)

    def test_device_header_include_is_a_violation(self):
        violations = vendor_symbols.find_violations("a.c", '#include "stm32f4xx_hal.h"\n')
        self.assertEqual(1, len(violations))
        self.assertEqual("vendor header include", violations[0].kind)

    def test_peripheral_instance_and_handle_type_are_violations(self):
        source = "static ADC_HandleTypeDef adc;\nvoid f(void) { x = GPIOA; }\n"
        symbols = {violation.symbol for violation in vendor_symbols.find_violations("a.c", source)}
        self.assertIn("ADC_HandleTypeDef", symbols)
        self.assertIn("GPIOA", symbols)

    def test_line_numbers_survive_comment_stripping(self):
        source = "/* a\n   multi-line\n   comment */\nvoid f(void) { HAL_Init(); }\n"
        violations = vendor_symbols.find_violations("a.c", source)
        self.assertEqual([4], [violation.line for violation in violations])

    def test_a_vendor_name_in_a_comment_is_not_a_violation(self):
        source = "/* reaches hardware without HAL_GPIO_Init or GPIOA */\nint f(void) { return 0; }\n"
        self.assertEqual([], vendor_symbols.find_violations("a.c", source))

    def test_a_vendor_name_in_a_string_is_not_a_violation(self):
        source = 'const char *m = "HAL_Init failed on GPIOA";\n'
        self.assertEqual([], vendor_symbols.find_violations("a.c", source))

    def test_a_clean_control_source_reports_nothing(self):
        source = '#include "hw_interface.h"\nvoid f(void) { hw_output_set(0, 0); }\n'
        self.assertEqual([], vendor_symbols.find_violations("a.c", source))

    def test_one_symbol_is_reported_once_even_when_several_rules_match(self):
        violations = vendor_symbols.find_violations("a.c", "void f(void) { __HAL_RCC_X(); }\n")
        self.assertEqual(1, len(violations))


class EncapsulationCheck(unittest.TestCase):
    """SOL-CONTROL-HARDWARE-SEAM-HOST-SIM.C5: a direct vendor reference fails the build."""

    def test_clean_control_directory_passes(self):
        with tempfile.TemporaryDirectory() as scratch:
            write(scratch, "control/loop.c", '#include "hw_interface.h"\nint f(void){return 0;}\n')
            result = run_tool("check_encapsulation.py", os.path.join(scratch, "control"))
            self.assertEqual(0, result.returncode, result.stderr)

    def test_vendor_reference_fails_and_names_file_line_and_symbol(self):
        with tempfile.TemporaryDirectory() as scratch:
            write(
                scratch,
                "control/loop.c",
                """\
                #include "hw_interface.h"
                int f(void) { return (int)HAL_GetTick(); }
                """,
            )
            result = run_tool("check_encapsulation.py", os.path.join(scratch, "control"))
            self.assertEqual(1, result.returncode)
            self.assertIn("loop.c:2", result.stderr)
            self.assertIn("HAL_GetTick", result.stderr)

    def test_violation_in_a_header_is_found_too(self):
        with tempfile.TemporaryDirectory() as scratch:
            write(scratch, "control/loop.h", "typedef TIM_HandleTypeDef timer_t;\n")
            result = run_tool("check_encapsulation.py", os.path.join(scratch, "control"))
            self.assertEqual(1, result.returncode)

    def test_a_directory_with_no_sources_fails_rather_than_passing_vacuously(self):
        with tempfile.TemporaryDirectory() as scratch:
            os.makedirs(os.path.join(scratch, "control"))
            result = run_tool("check_encapsulation.py", os.path.join(scratch, "control"))
            self.assertEqual(2, result.returncode)
            self.assertIn("without inspecting anything", result.stderr)

    def test_a_missing_path_is_an_error_not_a_pass(self):
        result = run_tool("check_encapsulation.py", "/nonexistent/control")
        self.assertEqual(2, result.returncode)

    def test_nested_sources_are_reached(self):
        with tempfile.TemporaryDirectory() as scratch:
            write(scratch, "control/inner/deep.c", "int f(void){ return LL_ADC_Enable(); }\n")
            result = run_tool("check_encapsulation.py", os.path.join(scratch, "control"))
            self.assertEqual(1, result.returncode)


class HeaderNeutralityCheck(unittest.TestCase):
    """SOL-CONTROL-HARDWARE-SEAM-HOST-SIM.C1: the seam header is vendor-neutral."""

    NEUTRAL = """\
        #ifndef FIXTURE_SEAM_H
        #define FIXTURE_SEAM_H
        #include <stdbool.h>
        #include <stdint.h>
        bool fixture_drive(uint16_t level);
        #endif
        """

    def test_a_neutral_header_passes(self):
        with tempfile.TemporaryDirectory() as scratch:
            header = write(scratch, "fixture_seam.h", self.NEUTRAL)
            result = run_tool("check_header_neutral.py", header, "--cc", CC)
            self.assertEqual(0, result.returncode, result.stderr)

    def test_a_vendor_type_in_a_signature_fails(self):
        with tempfile.TemporaryDirectory() as scratch:
            header = write(
                scratch,
                "fixture_seam.h",
                """\
                #ifndef FIXTURE_SEAM_H
                #define FIXTURE_SEAM_H
                #include <stdint.h>
                uint32_t fixture_now(ADC_HandleTypeDef *handle);
                #endif
                """,
            )
            result = run_tool("check_header_neutral.py", header, "--cc", CC)
            self.assertEqual(1, result.returncode)
            self.assertIn("ADC_HandleTypeDef", result.stderr)

    def test_a_header_needing_a_vendor_include_path_fails_to_compile_standalone(self):
        with tempfile.TemporaryDirectory() as scratch:
            header = write(
                scratch,
                "fixture_seam.h",
                """\
                #ifndef FIXTURE_SEAM_H
                #define FIXTURE_SEAM_H
                #include "vendor_device_registers.h"
                int fixture_read(void);
                #endif
                """,
            )
            result = run_tool("check_header_neutral.py", header, "--cc", CC)
            self.assertEqual(1, result.returncode)
            self.assertIn("does not compile standalone", result.stderr)

    def test_a_missing_header_is_an_error(self):
        result = run_tool("check_header_neutral.py", "/nonexistent/seam.h")
        self.assertEqual(2, result.returncode)


class SeamDeclarationParsing(unittest.TestCase):
    """SOL-CONTROL-HARDWARE-SEAM-HOST-SIM.C6: which symbols the check must prove direct."""

    def test_every_declared_operation_is_collected(self):
        with tempfile.TemporaryDirectory() as scratch:
            header = write(
                scratch,
                "seam.h",
                """\
                #include <stdint.h>
                typedef struct { int v; } fixture_reading_t;
                fixture_reading_t fixture_read(int channel);
                bool fixture_drive(int channel, uint16_t level);
                uint32_t fixture_now(void);
                """,
            )
            symbols = check_direct_calls.seam_symbols(header)
            for name in ("fixture_read", "fixture_drive", "fixture_now"):
                self.assertIn(name, symbols)
                self.assertIn(f"_{name}", symbols)

    def test_a_header_declaring_nothing_is_an_error(self):
        with tempfile.TemporaryDirectory() as scratch:
            header = write(scratch, "seam.h", "#define FIXTURE_FULL_SCALE 1000\n")
            with self.assertRaises(SystemExit):
                check_direct_calls.seam_symbols(header)


class DirectCallCheck(unittest.TestCase):
    """SOL-CONTROL-HARDWARE-SEAM-HOST-SIM.C6: seam calls are direct in the linked binary."""

    SEAM_HEADER = """\
        #ifndef FIXTURE_SEAM_H
        #define FIXTURE_SEAM_H
        int fixture_read(void);
        #endif
        """

    SEAM_IMPLEMENTATION = """\
        #include "fixture_seam.h"
        int fixture_read(void) { return 7; }
        """

    DIRECT_CONTROL = """\
        #include "fixture_seam.h"
        int fixture_control(void) { return fixture_read() + 1; }
        """

    # A mutable table with external linkage is what a run-time-selected seam
    # looks like: the compiler cannot fold the pointer away, so the call really
    # is indirect in the linked binary.
    INDIRECT_CONTROL = """\
        #include "fixture_seam.h"
        typedef struct { int (*read)(void); } fixture_seam_table_t;
        fixture_seam_table_t fixture_seam_table = { fixture_read };
        int fixture_control(void) { return fixture_seam_table.read() + 1; }
        """

    def build(self, scratch: str, control_source: str) -> tuple[str, str]:
        """Compile a fixture into a control object and a linked executable."""
        write(scratch, "fixture_seam.h", self.SEAM_HEADER)
        write(scratch, "seam_impl.c", self.SEAM_IMPLEMENTATION)
        write(scratch, "control/control.c", control_source)
        write(scratch, "main.c", "int fixture_control(void);\nint main(void){return fixture_control()==8?0:1;}\n")

        control_object = os.path.join(scratch, "control", "control.o")
        for source, output in (
            (os.path.join(scratch, "control", "control.c"), control_object),
            (os.path.join(scratch, "seam_impl.c"), os.path.join(scratch, "seam_impl.o")),
            (os.path.join(scratch, "main.c"), os.path.join(scratch, "main.o")),
        ):
            result = subprocess.run(
                [CC, "-O0", "-g", "-I", scratch, "-c", source, "-o", output],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(0, result.returncode, result.stderr)

        executable = os.path.join(scratch, "fixture")
        result = subprocess.run(
            [
                CC,
                "-o",
                executable,
                control_object,
                os.path.join(scratch, "seam_impl.o"),
                os.path.join(scratch, "main.o"),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        return executable, os.path.join(scratch, "control")

    def test_a_direct_call_through_the_seam_passes(self):
        with tempfile.TemporaryDirectory() as scratch:
            executable, control = self.build(scratch, self.DIRECT_CONTROL)
            problems = check_direct_calls.check(
                executable, os.path.join(scratch, "fixture_seam.h"), [control]
            )
            self.assertEqual([], problems)

    def test_a_call_through_a_function_pointer_fails(self):
        with tempfile.TemporaryDirectory() as scratch:
            executable, control = self.build(scratch, self.INDIRECT_CONTROL)
            problems = check_direct_calls.check(
                executable, os.path.join(scratch, "fixture_seam.h"), [control]
            )
            self.assertTrue(problems, "an indirect seam call was not detected")
            self.assertTrue(
                any("indirect call" in problem or "reached by no direct call" in problem
                    for problem in problems),
                problems,
            )

    def test_no_object_files_fails_rather_than_passing_vacuously(self):
        with tempfile.TemporaryDirectory() as scratch:
            executable, _control = self.build(scratch, self.DIRECT_CONTROL)
            empty = os.path.join(scratch, "empty")
            os.makedirs(empty)
            problems = check_direct_calls.check(
                executable, os.path.join(scratch, "fixture_seam.h"), [empty]
            )
            self.assertTrue(problems)
            self.assertIn("no object files found", problems[0])

    def test_control_objects_referencing_no_seam_operation_fail(self):
        with tempfile.TemporaryDirectory() as scratch:
            executable, control = self.build(
                scratch, "int fixture_control(void) { return 8; }\n"
            )
            problems = check_direct_calls.check(
                executable, os.path.join(scratch, "fixture_seam.h"), [control]
            )
            self.assertTrue(problems)
            self.assertIn("nothing to prove direct", problems[0])


class PreprocessedComparison(unittest.TestCase):
    """SOL-CONTROL-HARDWARE-SEAM-HOST-SIM.C3: comparison after preprocessing."""

    def test_only_the_projects_own_text_is_compared(self):
        with tempfile.TemporaryDirectory() as scratch:
            own = os.path.realpath(os.path.join(scratch, "control"))
            os.makedirs(own)
            preprocessed = (
                f'# 1 "{own}/control.c"\n'
                "int ours = 1;\n"
                '# 1 "/usr/include/stdint.h"\n'
                "typedef long theirs;\n"
                f'# 4 "{own}/control.c"\n'
                "int also_ours = 2;\n"
            )
            tokens = check_control_identical.own_tokens(preprocessed, [own])
            self.assertIn("ours", tokens)
            self.assertIn("also_ours", tokens)
            self.assertNotIn("theirs", tokens)

    def test_whitespace_differences_are_not_a_difference(self):
        with tempfile.TemporaryDirectory() as scratch:
            own = os.path.realpath(os.path.join(scratch, "control"))
            os.makedirs(own)
            marker = f'# 1 "{own}/control.c"\n'
            spaced = check_control_identical.own_tokens(marker + "int *p = ((void *)0);\n", [own])
            tight = check_control_identical.own_tokens(marker + "int*p=((void*)0);\n", [own])
            self.assertEqual(spaced, tight)

    def test_a_macro_expanding_differently_is_a_difference(self):
        with tempfile.TemporaryDirectory() as scratch:
            own = os.path.realpath(os.path.join(scratch, "control"))
            os.makedirs(own)
            marker = f'# 1 "{own}/control.c"\n'
            one = check_control_identical.own_tokens(marker + "int probe = 1;\n", [own])
            two = check_control_identical.own_tokens(marker + "int probe = 2;\n", [own])
            self.assertNotEqual(one, two)

    def test_identical_units_report_no_difference(self):
        per_environment = {"native": {"control.c": ["int", "x"]}, "stm32": {"control.c": ["int", "x"]}}
        self.assertEqual([], check_control_identical.differences(["native", "stm32"], per_environment))

    def test_differing_units_are_reported_with_a_diff(self):
        per_environment = {
            "native": {"control.c": ["int", "probe", "=", "1"]},
            "stm32": {"control.c": ["int", "probe", "=", "2"]},
        }
        problems = check_control_identical.differences(["native", "stm32"], per_environment)
        self.assertEqual(1, len(problems))
        self.assertIn("differs between", problems[0])
        self.assertIn("-1", problems[0])
        self.assertIn("+2", problems[0])

    def test_a_unit_compiled_in_only_one_environment_is_reported(self):
        per_environment = {"native": {"control.c": ["int"]}, "stm32": {}}
        problems = check_control_identical.differences(["native", "stm32"], per_environment)
        self.assertEqual(["control.c: compiled only in 'native'"], problems)

    def test_no_units_at_all_fails_rather_than_passing_vacuously(self):
        per_environment = {"native": {}, "stm32": {}}
        problems = check_control_identical.differences(["native", "stm32"], per_environment)
        self.assertIn("no control translation unit", problems[0])


class SanitizerRuntimeDetection(unittest.TestCase):
    """SOL-CONTROL-HARDWARE-SEAM-HOST-SIM.C4: the executable is really under analysis."""

    SOURCE = "int main(void) { return 0; }\n"

    def compile(self, scratch: str, name: str, *flags: str) -> str:
        source = write(scratch, f"{name}.c", self.SOURCE)
        executable = os.path.join(scratch, name)
        result = subprocess.run(
            [CC, *flags, "-o", executable, source], capture_output=True, text=True, check=False
        )
        self.assertEqual(0, result.returncode, result.stderr)
        return executable

    def test_a_sanitized_executable_is_recognised(self):
        with tempfile.TemporaryDirectory() as scratch:
            executable = self.compile(scratch, "sanitized", "-fsanitize=address,undefined")
            self.assertTrue(check_sanitizers.runtime_linked(executable))

    def test_an_unsanitized_executable_is_not_mistaken_for_one(self):
        with tempfile.TemporaryDirectory() as scratch:
            executable = self.compile(scratch, "plain")
            self.assertFalse(check_sanitizers.runtime_linked(executable))


class SourceCollection(unittest.TestCase):
    """SOL-CONTROL-HARDWARE-SEAM-HOST-SIM.C5: the check inspects what it claims to."""

    def test_only_c_sources_and_headers_are_collected(self):
        with tempfile.TemporaryDirectory() as scratch:
            write(scratch, "control/loop.c", "int f(void){return 0;}\n")
            write(scratch, "control/loop.h", "int f(void);\n")
            write(scratch, "control/notes.md", "HAL_GetTick is mentioned here\n")
            collected = check_encapsulation.collect_sources([os.path.join(scratch, "control")])
            self.assertEqual(
                ["loop.c", "loop.h"], sorted(os.path.basename(path) for path in collected)
            )

    def test_a_single_file_can_be_given_directly(self):
        with tempfile.TemporaryDirectory() as scratch:
            path = write(scratch, "control/loop.c", "int f(void){return 0;}\n")
            self.assertEqual([path], check_encapsulation.collect_sources([path]))


if __name__ == "__main__":
    unittest.main()
