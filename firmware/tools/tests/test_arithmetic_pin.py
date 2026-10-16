#!/usr/bin/env python3
"""Every build that compiles the plant computes with the same pinned arithmetic.

The plant model's recorded trajectory and the analysis records generated from it
are compared byte for byte on whichever host a contributor builds on, so the
arithmetic has to be the same on every host. That rests on two things the build
carries: no build lets the compiler fuse a multiply with the add that follows it,
and no build takes the exponential, the exponential less one or the sine from
the host's maths library.

Both are judged on what the build produced, by `check_plant_arithmetic.py`: the
flags of the compile commands, the symbols the plant's objects leave undefined,
the fused instructions in their disassembly. The tests here show that check
refusing each way round it that a plausible change could take, and accepting a
build that is right, using the text each host's own tools print. What no
artefact shows -- a pragma, a builtin or an attribute that the compiler folds or
re-pins without leaving a symbol -- is held out of the sources by a rule of zero
occurrences rather than a list of spellings.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIRMWARE = os.path.dirname(TOOLS)
sys.path.insert(0, TOOLS)
sys.path.insert(0, os.path.join(FIRMWARE, "emulation", "tools"))

import build_environments  # noqa: E402
import build_plant_library  # noqa: E402
import check_direct_calls  # noqa: E402
import check_plant_arithmetic as check  # noqa: E402
import check_sanitizers  # noqa: E402
import mull_toolchain  # noqa: E402

PIN = check.PIN

PLANT_TEXT = "Every build that compiles the plant computes with the same pinned arithmetic"

#: Two compile commands as the build's database carries them: one string, or an argument list.
CLEAN_COMMAND = "cc -std=c11 -ffp-contract=off -Wall -O1 -c src/plant/common/plant_maths.c -o plant_maths.o"

#: What each host's own tools print for the same few instructions.
OTOOL_ARM64 = (
    "(__TEXT,__text) section\n_plant_expf:\n"
    "0000000000000000\tstp\tx29, x30, [sp, #-0x10]!\n"
    "0000000000000008\tfcmp\ts0, s0\n"
    "0000000000000020\tfmul\ts0, s0, s1\n"
    "0000000000000024\tfadd\ts0, s0, s2\n"
)
OTOOL_ARM64_FUSED = OTOOL_ARM64 + "0000000000000028\tfmadd\ts0, s0, s1, s2\n"
OBJDUMP_MACH_O_FUSED = (
    "0000000000000000 <ltmp0>:\n       0:      \tstp\tx29, x30, [sp, #-0x10]!\n"
    "      40:      \tfnmsub\ts0, s1, s2, s3\n"
)
OBJDUMP_ARM64_VECTOR_FUSED = "  1c:\tfmla\tv0.4s, v1.4s, v2.4s\n  20:\tfmla.4s\tv0, v1, v2\n"
OBJDUMP_X86_CLEAN = (
    "0000000000000000 <plant_expf>:\n"
    "   4:\tmulss  %xmm1,%xmm0\n   8:\taddss  %xmm2,%xmm0\n  10:\tpxor   %xmm1,%xmm1\n"
)
OBJDUMP_X86_FUSED = OBJDUMP_X86_CLEAN + "  14:\tvfmadd231ss %xmm1,%xmm2,%xmm0\n  1a:\tvfnmsub213sd %xmm1,%xmm2,%xmm0\n"
OBJDUMP_M4_CLEAN = "00000000 <plant_expf>:\n   0:\tpush\t{r3, lr}\n   6:\tbl\t0 <__aeabi_fmul>\n"
OBJDUMP_M4_FUSED = (
    "00000000 <plant_expf>:\n   0:\tvmul.f32\ts0, s0, s1\n   4:\tvfma.f32\ts0, s1, s2\n"
    "   8:\tvfnms.f32\ts0, s1, s2\n   c:\tvfms.f32\ts0, s1, s2\n  10:\tvfnma.f32\ts0, s1, s2\n"
)

NM_MACH_O = (
    "                 U ___asan_init\n                 U ___ubsan_handle_add_overflow_abort\n"
    "                 U _sqrtf\n                 U _fmaxf\n                 U _memcpy\n"
    "                 U _strtof\n                 U ___error\n                 U _plant_expf\n"
    "0000000000000000 T _plant_step\n0000000000000188 t _asan.module_ctor\n"
)
NM_ELF_SOFT_FLOAT = (
    "         U __aeabi_fadd\n         U __aeabi_fcmpge\n         U __aeabi_i2f\n"
    "         U __aeabi_ui2f\n         U __errno\n         U plant_expf\n"
    "00000000 T plant_step\n"
)


def compiling_the_plant(environments):
    """The environments whose source filter names a plant directory."""
    return [environment for environment in environments if "plant/" in environment.source_filter]


def without_comments(text: str) -> str:
    """C source with its comments and string literals blanked, line structure kept."""

    def blank(match: re.Match) -> str:
        return re.sub(r"[^\n]", " ", match.group(0))

    return re.sub(r"/\*.*?\*/|//[^\n]*|\"(?:\\.|[^\"\\])*\"", blank, text, flags=re.S)


def c_sources() -> list[str]:
    """Every C source and header that any build of the firmware compiles."""
    found = []
    for subdirectory in ("src", "include"):
        for directory, _, files in os.walk(os.path.join(FIRMWARE, subdirectory)):
            found += [
                os.path.join(directory, name) for name in sorted(files) if name.endswith((".c", ".h"))
            ]
    return sorted(found)


#: What the compiler can fold, re-pin or re-optimise from inside a source, none of
#: which leaves a trace in the object. Every one is refused outright: a rule of
#: zero occurrences has no spelling to get around.
SOURCE_CONSTRUCT = re.compile(
    r"^\s*#\s*pragma\b(?!\s+once\b)|_Pragma\b|__builtin_|__attribute__"
)


def source_constructs(text: str) -> list[tuple[int, str]]:
    """Every pragma other than `once`, builtin and attribute in a source, as (line, text)."""
    found = []
    for number, line in enumerate(without_comments(text).splitlines(), start=1):
        if SOURCE_CONSTRUCT.search(line) or re.search(r"_Pragma\b|__builtin_|__attribute__", line):
            found.append((number, line.strip()))
    return found


def preprocessor_conditionals(text: str) -> list[tuple[int, str]]:
    """Every preprocessor conditional in a source, as (line, text)."""
    return [
        (number, line.strip())
        for number, line in enumerate(without_comments(text).splitlines(), start=1)
        if re.match(r"\s*#\s*(?:if|ifdef|ifndef|elif|elifdef|elifndef|else)\b", line)
    ]


class Environments(unittest.TestCase):
    def synthetic(self, name, **options):
        return build_environments.Environment(name, options)

    # SOL-HOST-ARITHMETIC-REPRODUCIBLE-ACROSS-HOSTS.C5: Every build that compiles the plant computes with the same pinned arithmetic
    def test_the_check_covers_every_built_environment_that_compiles_the_plant(self):
        declared = [
            self.synthetic("host", platform="native", build_src_filter="+<control/> +<plant/common/>"),
            self.synthetic("target", platform="ststm32", build_src_filter="+<plant/common/>"),
            self.synthetic("no_plant", platform="native", build_src_filter="+<control/>"),
            self.synthetic("refused", platform="native", build_src_filter="+<plant/>",
                           custom_must_not_build="two structures"),
            self.synthetic("swept", platform="native", build_src_filter="+<plant/>",
                           custom_mutation_sweep="built for the sweep"),
        ]

        self.assertEqual(["host", "target"], [e.name for e in check.covered(declared)])

    # SOL-HOST-ARITHMETIC-REPRODUCIBLE-ACROSS-HOSTS.C5: Every build that compiles the plant computes with the same pinned arithmetic
    def test_the_environments_the_build_declares_include_a_host_and_the_target(self):
        covered = check.covered(build_environments.load(FIRMWARE))

        self.assertTrue(any(environment.is_host for environment in covered))
        self.assertTrue(any(not environment.is_host for environment in covered))
        self.assertEqual(
            {environment.name for environment in compiling_the_plant(build_environments.load(FIRMWARE))
             if not environment.must_not_build_reason and not environment.mutation_sweep_reason},
            {environment.name for environment in covered},
        )

    # SOL-HOST-ARITHMETIC-REPRODUCIBLE-ACROSS-HOSTS.C5: Every build that compiles the plant computes with the same pinned arithmetic
    def test_the_shared_maths_is_compiled_into_every_build_that_compiles_the_plant(self):
        environments = build_environments.load(FIRMWARE)

        for environment in compiling_the_plant(environments):
            self.assertIn("+<plant/common/>", environment.source_filter, environment.name)
        self.assertTrue(
            os.path.isfile(os.path.join(FIRMWARE, "src", "plant", "common", "plant_maths.c"))
        )

    # SOL-HOST-ARITHMETIC-REPRODUCIBLE-ACROSS-HOSTS.C5: Every build that compiles the plant computes with the same pinned arithmetic
    def test_the_instruction_set_follows_the_environment_and_the_machine(self):
        host = self.synthetic("h", platform="native")
        target = self.synthetic("t", platform="ststm32")

        self.assertEqual("arm64", check.architecture_of(host, "arm64"))
        self.assertEqual("arm64", check.architecture_of(host, "aarch64"))
        self.assertEqual("x86-64", check.architecture_of(host, "x86_64"))
        self.assertEqual("cortex-m4", check.architecture_of(target, "x86_64"))


class UndefinedSymbols(unittest.TestCase):
    def findings(self, listing, defined_here=frozenset(), leading_underscore=False):
        _, undefined = check_direct_calls.parse_nm(listing)
        return check.undefined_findings("obj", undefined, set(defined_here), leading_underscore)

    # SOL-HOST-ARITHMETIC-REPRODUCIBLE-ACROSS-HOSTS.C5: Every build that compiles the plant computes with the same pinned arithmetic
    def test_a_mach_o_object_calling_only_the_exact_routines_is_accepted(self):
        self.assertEqual([], self.findings(NM_MACH_O, {"_plant_expf"}, leading_underscore=True))

    # SOL-HOST-ARITHMETIC-REPRODUCIBLE-ACROSS-HOSTS.C5: Every build that compiles the plant computes with the same pinned arithmetic
    def test_a_soft_float_elf_object_calling_only_the_exact_routines_is_accepted(self):
        self.assertEqual([], self.findings(NM_ELF_SOFT_FLOAT, {"plant_expf"}))

    # SOL-HOST-ARITHMETIC-REPRODUCIBLE-ACROSS-HOSTS.C5: Every build that compiles the plant computes with the same pinned arithmetic
    def test_a_routine_the_hosts_maths_library_defines_is_refused_however_it_is_named(self):
        for symbol in ("exp10f", "expf", "sinf", "powf", "log1pf", "exp", "sin", "lroundl", "__aeabi_dadd",
                       "__expf_finite", "tanhf"):
            for leading_underscore in (False, True):
                spelled = ("_" if leading_underscore else "") + symbol
                with self.subTest(symbol=spelled):
                    found = self.findings(f"          U {spelled}\n", leading_underscore=leading_underscore)
                    self.assertEqual(1, len(found))
                    self.assertIn(spelled, found[0])

    # SOL-HOST-ARITHMETIC-REPRODUCIBLE-ACROSS-HOSTS.C5: Every build that compiles the plant computes with the same pinned arithmetic
    def test_a_name_only_the_mach_o_prefix_would_make_exact_is_refused_on_elf(self):
        self.assertEqual(1, len(self.findings("          U _sqrtf\n", leading_underscore=False)))
        self.assertEqual([], self.findings("          U _sqrtf\n", leading_underscore=True))

    # SOL-HOST-ARITHMETIC-REPRODUCIBLE-ACROSS-HOSTS.C5: Every build that compiles the plant computes with the same pinned arithmetic
    def test_a_name_that_only_begins_like_an_exact_one_is_refused(self):
        for symbol in ("sqrtf_fast", "memcpy_chk_x", "__aeabi", "__asan", "my_strtof"):
            with self.subTest(symbol=symbol):
                self.assertEqual(1, len(self.findings(f"          U {symbol}\n")))

    # SOL-HOST-ARITHMETIC-REPRODUCIBLE-ACROSS-HOSTS.C5: Every build that compiles the plant computes with the same pinned arithmetic
    def test_a_symbol_another_project_object_defines_is_not_the_hosts(self):
        self.assertEqual([], self.findings("          U plant_expf\n", {"plant_expf"}))
        self.assertEqual(1, len(self.findings("          U plant_expf\n", set())))

    # SOL-HOST-ARITHMETIC-REPRODUCIBLE-ACROSS-HOSTS.C5: Every build that compiles the plant computes with the same pinned arithmetic
    def test_the_linux_and_sanitizer_spellings_are_exact(self):
        listing = (
            "          U __errno_location\n          U __asan_report_load4\n"
            "          U __ubsan_handle_mul_overflow_abort\n          U __stack_chk_fail\n"
            "          U __sanitizer_cov_trace_pc\n          U __aeabi_fdiv\n"
        )
        self.assertEqual([], self.findings(listing))


class CompileCommands(unittest.TestCase):
    PLANT = "src/plant/common/plant_maths.c"

    def database(self, *commands, source=PLANT):
        return [{"directory": FIRMWARE, "file": source, "command": command} for command in commands]

    def findings(self, *commands, source=PLANT):
        return check.plant_flag_findings(self.database(*commands, source=source), FIRMWARE, "env")

    # SOL-HOST-ARITHMETIC-REPRODUCIBLE-ACROSS-HOSTS.C5: Every build that compiles the plant computes with the same pinned arithmetic
    def test_a_command_that_ends_with_the_pin_and_relaxes_nothing_is_accepted(self):
        self.assertEqual([], self.findings(CLEAN_COMMAND))
        self.assertEqual([], self.findings("cc -ffp-contract=fast -ffp-contract=off -O2 -c x.c"))
        self.assertEqual([], self.findings("cc -ffp-contract=off -fno-fast-math -ffp-model=precise -c x.c"))

    # SOL-HOST-ARITHMETIC-REPRODUCIBLE-ACROSS-HOSTS.C5: Every build that compiles the plant computes with the same pinned arithmetic
    def test_a_later_setting_that_undoes_the_pin_is_refused_in_whatever_form(self):
        for later in ("-ffp-contract=fast", "-ffp-contract=on", "-ffp-contract=fast-honor-pragmas"):
            with self.subTest(later=later):
                found = self.findings(f"cc -ffp-contract=off {later} -O1 -c x.c")
                self.assertEqual(1, len(found))
                self.assertIn(later, found[0])

    # SOL-HOST-ARITHMETIC-REPRODUCIBLE-ACROSS-HOSTS.C5: Every build that compiles the plant computes with the same pinned arithmetic
    def test_a_dropped_pin_is_refused(self):
        found = self.findings("cc -std=c11 -O1 -Wall -c x.c")
        self.assertEqual(1, len(found))
        self.assertIn("absent", found[0])

    # SOL-HOST-ARITHMETIC-REPRODUCIBLE-ACROSS-HOSTS.C5: Every build that compiles the plant computes with the same pinned arithmetic
    def test_every_flag_that_licenses_rearranging_arithmetic_is_refused_even_after_the_pin(self):
        for flag in sorted(check.RELAXING_FLAGS):
            with self.subTest(flag=flag):
                found = self.findings(f"cc -ffp-contract=off {flag} -c x.c")
                self.assertEqual(1, len(found))
                self.assertIn(flag, found[0])

    # SOL-HOST-ARITHMETIC-REPRODUCIBLE-ACROSS-HOSTS.C5: Every build that compiles the plant computes with the same pinned arithmetic
    def test_the_documented_relaxing_flags_include_the_fast_model_and_the_fast_optimisation_level(self):
        for flag in ("-ffast-math", "-Ofast", "-ffp-model=fast", "-ffp-model=aggressive", "-mrecip"):
            self.assertIn(flag, check.RELAXING_FLAGS)

    # SOL-HOST-ARITHMETIC-REPRODUCIBLE-ACROSS-HOSTS.C5: Every build that compiles the plant computes with the same pinned arithmetic
    def test_the_flags_are_read_from_an_argument_list_as_well_as_a_command_string(self):
        database = [{
            "directory": FIRMWARE, "file": self.PLANT,
            "arguments": ["cc", "-ffp-contract=off", "-ffp-model=fast", "-c", self.PLANT],
        }]
        self.assertEqual(1, len(check.plant_flag_findings(database, FIRMWARE, "env")))

    # SOL-HOST-ARITHMETIC-REPRODUCIBLE-ACROSS-HOSTS.C5: Every build that compiles the plant computes with the same pinned arithmetic
    def test_a_source_outside_the_plant_is_not_judged_and_no_plant_source_at_all_is_refused(self):
        outside = self.findings("cc -ffast-math -c x.c", source="src/control/control.c")

        self.assertEqual(1, len(outside))
        self.assertIn("no plant translation unit", outside[0])

    # SOL-HOST-ARITHMETIC-REPRODUCIBLE-ACROSS-HOSTS.C5: Every build that compiles the plant computes with the same pinned arithmetic
    def test_each_plant_source_is_judged_on_its_own_command(self):
        database = self.database(CLEAN_COMMAND, "cc -c y.c", source="src/plant/common/plant_maths.c")
        database[1]["file"] = "src/plant/common/plant_step.c"

        found = check.plant_flag_findings(database, FIRMWARE, "env")

        self.assertEqual(1, len(found))
        self.assertIn("plant_step.c", found[0])


class FusedInstructions(unittest.TestCase):
    # SOL-HOST-ARITHMETIC-REPRODUCIBLE-ACROSS-HOSTS.C5: Every build that compiles the plant computes with the same pinned arithmetic
    def test_unfused_arithmetic_on_each_architecture_is_accepted_and_counted(self):
        for text, architecture, count in (
            (OTOOL_ARM64, "arm64", 2),
            (OBJDUMP_X86_CLEAN, "x86-64", 2),
            (OBJDUMP_M4_CLEAN + "  8:\tvadd.f32\ts0, s0, s1\n", "cortex-m4", 1),
        ):
            with self.subTest(architecture=architecture):
                self.assertEqual(([], count), check.fused_findings("obj", text, architecture))

    # SOL-HOST-ARITHMETIC-REPRODUCIBLE-ACROSS-HOSTS.C5: Every build that compiles the plant computes with the same pinned arithmetic
    def test_a_fused_instruction_is_found_in_each_hosts_own_disassembly_text(self):
        for text, architecture, expected in (
            (OTOOL_ARM64_FUSED, "arm64", ["fmadd"]),
            (OBJDUMP_MACH_O_FUSED, "arm64", ["fnmsub"]),
            (OBJDUMP_ARM64_VECTOR_FUSED, "arm64", ["fmla", "fmla.4s"]),
            (OBJDUMP_X86_FUSED, "x86-64", ["vfmadd231ss", "vfnmsub213sd"]),
            (OBJDUMP_M4_FUSED, "cortex-m4", ["vfma.f32", "vfnms.f32", "vfms.f32", "vfnma.f32"]),
        ):
            with self.subTest(architecture=architecture):
                found, _ = check.fused_findings("obj", text, architecture)
                self.assertEqual(len(expected), len(found), found)
                for mnemonic, line in zip(expected, found):
                    self.assertIn(mnemonic, line)

    # SOL-HOST-ARITHMETIC-REPRODUCIBLE-ACROSS-HOSTS.C5: Every build that compiles the plant computes with the same pinned arithmetic
    def test_a_name_that_contains_a_fused_mnemonic_is_not_an_instruction(self):
        text = (
            "0000000000000000 <fmadd_helper>:\n  4:\tbl\t0x10 <fmla_table>\n"
            "  8:\tfmov\ts0, w8\n  c:\tfcmp\ts0, s1\n"
        )
        self.assertEqual(([], 0), check.fused_findings("obj", text, "arm64"))

    # SOL-HOST-ARITHMETIC-REPRODUCIBLE-ACROSS-HOSTS.C5: Every build that compiles the plant computes with the same pinned arithmetic
    def test_a_build_with_no_floating_point_instruction_says_the_scan_was_vacuous(self):
        _, held = check.fused_findings("obj", OBJDUMP_M4_CLEAN, "cortex-m4")

        note = check.scan_note("stm32", "cortex-m4", held)

        self.assertEqual(0, held)
        self.assertIn("vacuous", note)
        self.assertIn("soft-float", note)
        self.assertNotIn("none fused", note)
        self.assertIn("none fused", check.scan_note("native", "arm64", 195))


class TheToolchainThatReadsTheObjects(unittest.TestCase):
    # SOL-HOST-ARITHMETIC-REPRODUCIBLE-ACROSS-HOSTS.C5: Every build that compiles the plant computes with the same pinned arithmetic
    def test_a_cross_compiler_names_its_own_binutils_and_a_host_compiler_the_hosts(self):
        with tempfile.TemporaryDirectory() as scratch:
            for name in ("arm-none-eabi-gcc", "arm-none-eabi-nm"):
                open(os.path.join(scratch, name), "w").close()

            self.assertEqual(
                os.path.join(scratch, "arm-none-eabi-nm"),
                check.toolchain_tool(os.path.join(scratch, "arm-none-eabi-gcc"), "nm"),
            )
            self.assertEqual("objdump", check.toolchain_tool(os.path.join(scratch, "arm-none-eabi-gcc"), "objdump"))
        self.assertEqual("nm", check.toolchain_tool("/usr/bin/gcc", "nm"))
        self.assertEqual("nm", check.toolchain_tool("cc", "nm"))


class OneEnvironmentEndToEnd(unittest.TestCase):
    """The pieces joined, with the build's tools replaced by text the hosts really print."""

    def run_environment(self, commands, nm_for, disassembly):
        with tempfile.TemporaryDirectory() as project:
            database = self.database(project, *commands)
            environment = build_environments.Environment(
                "native", {"platform": "native", "build_src_filter": "+<plant/>"}
            )
            source = os.path.join(environment.build_directory(project), "src", "plant", "common")
            os.makedirs(source)
            for name in ("plant_maths.o", "plant_step.o"):
                open(os.path.join(source, name), "w").close()

            def symbols(objects, nm="nm", definitions=("T", "t")):
                return check_direct_calls.parse_nm(
                    "".join(nm_for(os.path.basename(obj)) for obj in objects), definitions
                )

            with mock.patch.object(check_sanitizers, "compile_commands", return_value=database), \
                    mock.patch.object(check.check_direct_calls, "symbols_of", side_effect=symbols), \
                    mock.patch.object(check, "disassembly_of", return_value=disassembly):
                return check.check_environment(project, environment, "pio", "arm64"), project

    def database(self, project, *commands):
        return [
            {"directory": project, "file": "src/plant/common/plant_maths.c", "command": command}
            for command in commands
        ]

    # SOL-HOST-ARITHMETIC-REPRODUCIBLE-ACROSS-HOSTS.C5: Every build that compiles the plant computes with the same pinned arithmetic
    def test_a_clean_environment_finds_nothing_and_reports_what_it_scanned(self):
        (problems, blockers, notes), _ = self.run_environment(
            [CLEAN_COMMAND],
            lambda name: "          U sqrtf\n          U plant_expf\n0000000000000000 T plant_expf\n",
            OTOOL_ARM64,
        )

        self.assertEqual(([], []), (problems, blockers))
        self.assertEqual(1, len(notes))
        self.assertIn("none fused", notes[0])

    # SOL-HOST-ARITHMETIC-REPRODUCIBLE-ACROSS-HOSTS.C5: Every build that compiles the plant computes with the same pinned arithmetic
    def test_a_dropped_pin_a_host_routine_and_a_fused_instruction_are_each_reported(self):
        (problems, blockers, _), _ = self.run_environment(
            ["cc -std=c11 -ffp-contract=fast-honor-pragmas -c x.c"],
            lambda name: "          U exp10f\n",
            OTOOL_ARM64_FUSED,
        )

        self.assertEqual([], blockers)
        self.assertTrue(any("contraction" in problem for problem in problems), problems)
        self.assertTrue(any("exp10f" in problem for problem in problems), problems)
        self.assertTrue(any("fused multiply-add" in problem for problem in problems), problems)

    # SOL-HOST-ARITHMETIC-REPRODUCIBLE-ACROSS-HOSTS.C5: Every build that compiles the plant computes with the same pinned arithmetic
    def test_an_environment_that_was_not_built_is_a_blocker_not_a_clean_result(self):
        with tempfile.TemporaryDirectory() as project:
            environment = build_environments.Environment("native", {"platform": "native"})
            with mock.patch.object(check_sanitizers, "compile_commands",
                                   return_value=self.database(project, CLEAN_COMMAND)):
                problems, blockers, notes = check.check_environment(project, environment, "pio", "arm64")

        self.assertEqual([], problems)
        self.assertEqual(1, len(blockers))
        self.assertIn("not built", blockers[0])
        self.assertEqual([], notes)

    # SOL-HOST-ARITHMETIC-REPRODUCIBLE-ACROSS-HOSTS.C5: Every build that compiles the plant computes with the same pinned arithmetic
    def test_a_compile_database_that_cannot_be_made_is_a_blocker(self):
        with tempfile.TemporaryDirectory() as project:
            environment = build_environments.Environment("native", {"platform": "native"})
            with mock.patch.object(check_sanitizers, "compile_commands",
                                   side_effect=check_sanitizers.CannotInspect("no database")):
                problems, blockers, _ = check.check_environment(project, environment, "pio", "arm64")

        self.assertEqual(([], 1), (problems, len(blockers)))


class Construction:
    """The slice of an SCons construction environment the mutation script touches."""

    def __init__(self, ccflags):
        self.flags = {"CCFLAGS": list(ccflags), "LINKFLAGS": []}
        self.compiler = {}
        self.environment = {}

    def get(self, name, default=None):
        return self.flags.get(name, default)

    def Replace(self, **values):
        for name, value in values.items():
            if name in ("CC", "LINK"):
                self.compiler[name] = value
            else:
                self.flags[name] = list(value)

    def Append(self, **values):
        for name, value in values.items():
            self.flags[name] += list(value)

    def __getitem__(self, name):
        return self.environment.setdefault(name, {})

    def subst(self, _):
        return FIRMWARE


class TheBuildsTheCheckDoesNotCompile(unittest.TestCase):
    """The builds `fw:check` cannot reach, held by what their own scripts add."""

    def run_script(self, existing):
        """Run the mutation build's script against stubs; return its namespace and the two it instrumented."""
        namespace = {"__name__": "pio_mutation"}
        constructions = {"env": Construction(existing), "projenv": Construction(existing)}
        namespace["Import"] = lambda name: namespace.__setitem__(name, constructions[name])
        toolchain = {"clang": "/llvm/bin/clang", "compile_flags": ["-fpass-plugin=mull"]}
        with open(os.path.join(TOOLS, "pio_mutation.py"), encoding="utf-8") as handle:
            code = compile(handle.read(), "pio_mutation.py", "exec")
        with mock.patch.object(mull_toolchain, "resolved", return_value=toolchain):
            exec(code, namespace)  # noqa: S102 -- the script under test, run against stubs
        return namespace, constructions

    def instrumented(self, existing):
        return self.run_script(existing)[1]

    # SOL-HOST-ARITHMETIC-REPRODUCIBLE-ACROSS-HOSTS.C5: Every build that compiles the plant computes with the same pinned arithmetic
    def test_the_mutation_build_ends_with_the_pin_whatever_the_environment_set_before(self):
        existing = ["-std=c11", "-O1", "-ffp-contract=fast", "-ffast-math"]
        constructions = self.instrumented(existing)

        for name, construction in constructions.items():
            with self.subTest(construction=name):
                final = construction.flags["CCFLAGS"]
                settings = [flag for flag in final if flag.startswith("-ffp-contract=")]
                self.assertEqual(PIN, settings[-1])
                self.assertEqual("/llvm/bin/clang", construction.compiler["CC"])
                self.assertIn("-O0", final)
                self.assertNotIn("-O1", final)
                self.assertIn(PIN, construction.flags["LINKFLAGS"])

    # SOL-HOST-ARITHMETIC-REPRODUCIBLE-ACROSS-HOSTS.C5: Every build that compiles the plant computes with the same pinned arithmetic
    def test_a_mutation_build_that_stopped_appending_the_pin_is_refused(self):
        namespace, _ = self.run_script(["-std=c11"])
        namespace["MUTATION_FLAGS"] = ["-fpass-plugin=mull", "-O0"]
        fused = Construction(["-std=c11", "-ffp-contract=fast"])

        namespace["instrument"](fused)

        findings = check.flag_findings("mutation", fused.flags["CCFLAGS"])
        self.assertEqual(1, len(findings))
        self.assertIn("-ffp-contract=fast", findings[0])

    # SOL-HOST-ARITHMETIC-REPRODUCIBLE-ACROSS-HOSTS.C5: Every build that compiles the plant computes with the same pinned arithmetic
    def test_the_mutation_scripts_final_flags_pass_the_same_judgement_as_every_other_build(self):
        constructions = self.instrumented(["-std=c11", "-ffp-contract=on"])

        self.assertEqual([], check.flag_findings("mutation", constructions["env"].flags["CCFLAGS"]))

    # SOL-HOST-ARITHMETIC-REPRODUCIBLE-ACROSS-HOSTS.C5: Every build that compiles the plant computes with the same pinned arithmetic
    def test_the_emulation_library_is_compiled_with_the_pin_and_the_shared_maths(self):
        commands = []

        def record(command, **_):
            commands.append(command)
            return subprocess.CompletedProcess(command, 0, "", "")

        with tempfile.TemporaryDirectory() as scratch:
            with mock.patch.object(build_plant_library.subprocess, "run", side_effect=record):
                build_plant_library.build(scratch, cc="cc")

        self.assertEqual(1, len(commands))
        self.assertEqual([], check.flag_findings("emulation library", commands[0]))
        compiled = [os.path.basename(argument) for argument in commands[0]]
        self.assertIn("plant_maths.c", compiled)


class NothingInTheSourcesThatTheObjectsWouldHide(unittest.TestCase):
    # SOL-HOST-ARITHMETIC-REPRODUCIBLE-ACROSS-HOSTS.C5: Every build that compiles the plant computes with the same pinned arithmetic
    def test_no_source_carries_a_pragma_a_builtin_or_an_attribute(self):
        offending = []
        for path in c_sources():
            with open(path, encoding="utf-8") as handle:
                offending += [
                    f"{os.path.relpath(path, FIRMWARE)}:{number}: {text}"
                    for number, text in source_constructs(handle.read())
                ]
        self.assertEqual([], offending)

    # SOL-HOST-ARITHMETIC-REPRODUCIBLE-ACROSS-HOSTS.C5: Every build that compiles the plant computes with the same pinned arithmetic
    def test_the_rule_refuses_each_construct_that_re_pins_or_folds_arithmetic(self):
        bypasses = {
            "a clang contraction pragma": "#pragma clang fp contract(fast)\n",
            "a spaced gcc pragma": "  #  pragma GCC optimize (\"fast-math\")\n",
            "an stdc pragma": "#pragma STDC FP_CONTRACT ON\n",
            "the pragma operator": "float f(void) { _Pragma(\"clang fp contract(fast)\") return 1.0f; }\n",
            "a builtin": "float f(float x) { return __builtin_expf(x); }\n",
            "a folded builtin": "float f(void) { return __builtin_expf(2.0f); }\n",
            "an optimize attribute": "__attribute__((optimize(\"O3\"))) float f(float x);\n",
        }
        for label, source in bypasses.items():
            with self.subTest(label):
                self.assertNotEqual([], source_constructs(source))

    # SOL-HOST-ARITHMETIC-REPRODUCIBLE-ACROSS-HOSTS.C5: Every build that compiles the plant computes with the same pinned arithmetic
    def test_the_rule_accepts_pragma_once_and_ignores_comments_and_strings(self):
        text = (
            "#pragma once\n/* #pragma clang fp contract(fast) */\n// __builtin_expf\n"
            "const char *s = \"__attribute__ #pragma\";\n"
        )
        self.assertEqual([], source_constructs(text))

    # SOL-HOST-ARITHMETIC-REPRODUCIBLE-ACROSS-HOSTS.C5: Every build that compiles the plant computes with the same pinned arithmetic
    def test_the_scan_reaches_every_directory_a_build_compiles(self):
        for directory in ("plant", "control", "estimator", "delivery", "sim", "common"):
            self.assertTrue(
                any(directory in os.path.relpath(path, FIRMWARE).split(os.sep) for path in c_sources()),
                directory,
            )
        self.assertTrue(any(path.endswith(".h") for path in c_sources()))


class OneRecordedLiteral(unittest.TestCase):
    # SOL-HOST-ARITHMETIC-REPRODUCIBLE-ACROSS-HOSTS.C1: The golden-trajectory test passes on correct code on every supported host
    def test_the_trajectory_test_file_contains_no_preprocessor_conditional(self):
        with open(os.path.join(FIRMWARE, "test", "test_plant", "test_plant.c"), encoding="utf-8") as handle:
            text = handle.read()

        self.assertEqual([], preprocessor_conditionals(text))

    # SOL-HOST-ARITHMETIC-REPRODUCIBLE-ACROSS-HOSTS.C1: The golden-trajectory test passes on correct code on every supported host
    def test_the_guard_refuses_a_conditional_however_it_is_written(self):
        for directive in ("#if defined(__aarch64__)", "#ifdef __x86_64__", "# if !defined(X) && 1",
                          "#elif defined Y", "  #  ifndef LITERAL", "#else", "#if 0", "#elifdef Z"):
            with self.subTest(directive=directive):
                text = f"{directive}\n#define LITERAL 1\n#endif\nstatic void test_the_trajectory(void) {{}}\n"
                self.assertEqual(1, len(preprocessor_conditionals(text)))

    # SOL-HOST-ARITHMETIC-REPRODUCIBLE-ACROSS-HOSTS.C1: The golden-trajectory test passes on correct code on every supported host
    def test_the_guard_accepts_includes_defines_and_a_conditional_named_in_a_comment(self):
        text = "#include <math.h>\n#define LITERAL 1\n/* #if __aarch64__ */\n// #ifdef X\nconst char *s = \"#if\";\n"
        self.assertEqual([], preprocessor_conditionals(text))

    # SOL-HOST-ARITHMETIC-REPRODUCIBLE-ACROSS-HOSTS.C1: The golden-trajectory test passes on correct code on every supported host
    def test_the_mutation_build_tells_the_sources_nothing_about_its_toolchain(self):
        with open(os.path.join(TOOLS, "pio_mutation.py"), encoding="utf-8") as handle:
            text = handle.read()

        self.assertNotIn("PLANT_TEST_MUTATION_TOOLCHAIN", text)


if __name__ == "__main__":
    unittest.main()
