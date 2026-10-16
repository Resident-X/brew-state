#!/usr/bin/env python3
"""Every build that compiles the plant computes with the same pinned arithmetic.

The plant model's recorded trajectory and the analysis records generated from it
are compared byte for byte on whichever host a contributor builds on, so the
arithmetic has to be the same on every host. That rests on two things the build
carries and nothing else checks: no build lets the compiler fuse a multiply with
the add that follows it, and no build takes the exponential, the exponential less
one or the sine from the host's maths library.

Each is read here from the place the build puts it -- the build file's resolved
environments, the mutation script's flags, the command the emulation tier's
library is compiled with, the sources themselves -- rather than from a list kept
in this file, so an environment added, a source added or a flag dropped is what
these tests see.
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
import mull_toolchain  # noqa: E402

PIN = "-ffp-contract=off"

#: Flags that let the compiler rearrange or fuse arithmetic, so that one expression
#: stops giving one answer on every host.
LOOSENING = re.compile(
    r"^(-ffast-math|-Ofast|-funsafe-math-optimizations|-fassociative-math|-freciprocal-math"
    r"|-ffp-contract=(?:fast|on))$"
)
CONTRACTION = re.compile(r"^-ffp-contract=(\w+)$")

#: The real-number families of C11 <math.h>. Each takes the `f` (float) and `l` (long
#: double) suffix as well as the bare double form, and the compiler's `__builtin_`
#: spelling of any of them.
MATH_FAMILIES = (
    "acos acosh asin asinh atan atan2 atanh cbrt ceil copysign cos cosh erf erfc exp exp2 expm1 "
    "fabs fdim floor fma fmax fmin fmod frexp hypot ilogb ldexp lgamma llrint llround log log10 "
    "log1p log2 logb lrint lround modf nan nearbyint nextafter nexttoward pow remainder remquo "
    "rint round scalbln scalbn sin sinh sqrt tan tanh tgamma trunc"
).split()
MATH_NAMES = sorted(
    {family + suffix for family in MATH_FAMILIES for suffix in ("", "f", "l")}
    | {"__builtin_" + family + suffix for family in MATH_FAMILIES for suffix in ("", "f", "l")}
    | {"fpclassify", "isfinite", "isinf", "isnan", "isnormal", "signbit",
       "isgreater", "isgreaterequal", "isless", "islessequal", "islessgreater", "isunordered",
       "__builtin_isfinite", "__builtin_isinf", "__builtin_isnan", "__builtin_isnormal",
       "__builtin_signbit", "__builtin_fpclassify", "__builtin_huge_valf", "__builtin_inff",
       "__builtin_nanf"}
)

#: What the plant, the control path and the estimator genuinely use from <math.h>.
#: Each is exact under IEEE 754 -- correctly rounded, or a bit or comparison test --
#: so no host can give a different last bit. Anything else the code reaches for is
#: the host's own rounding until shown otherwise.
EXACT_MATHS = frozenset({"fabsf", "fmaxf", "fminf", "isfinite", "isinf", "lroundf", "sqrtf"})

MATH_USE = re.compile(
    r"(?<![A-Za-z0-9_])(" + "|".join(re.escape(name) for name in MATH_NAMES) + r")(?![A-Za-z0-9_])"
)

#: Macros that select code by the machine, operating system or compiler.
SELECTING_MACROS = (
    "__x86_64__", "__amd64__", "__aarch64__", "__arm64__", "__i386__", "__APPLE__",
    "__linux__", "_WIN32", "__clang__", "__GNUC__", "PLANT_TEST_MUTATION_TOOLCHAIN",
)


def without_comments(text: str) -> str:
    """C source with its comments and string literals blanked, line structure kept."""

    def blank(match: re.Match) -> str:
        return re.sub(r"[^\n]", " ", match.group(0))

    return re.sub(r"/\*.*?\*/|//[^\n]*|\"(?:\\.|[^\"\\])*\"", blank, text, flags=re.S)


def host_maths_uses(text: str) -> list[tuple[int, str]]:
    """Every use of a <math.h> real function that is not an exact one, as (line, name).

    A use is any appearance of the identifier -- a call, a parenthesised call, a
    function-pointer assignment -- so how it is written does not matter.
    """
    uses = []
    for number, line in enumerate(without_comments(text).splitlines(), start=1):
        for match in MATH_USE.finditer(line):
            if match.group(1) not in EXACT_MATHS:
                uses.append((number, match.group(1)))
    return uses


def c_sources() -> list[str]:
    """Every C source and header that any build of the firmware compiles."""
    found = []
    for subdirectory in ("src", "include"):
        for directory, _, files in os.walk(os.path.join(FIRMWARE, subdirectory)):
            found += [
                os.path.join(directory, name) for name in sorted(files) if name.endswith((".c", ".h"))
            ]
    return sorted(found)


def compiling_the_plant(environments):
    """The environments whose source filter names a plant directory."""
    return [environment for environment in environments if "plant/" in environment.source_filter]


def flag_findings(flags: list[str], must_pin: bool) -> list[str]:
    """What is wrong with the flags one compile ends up with, in the order given."""
    findings = [f"{flag} loosens the arithmetic" for flag in flags if LOOSENING.match(flag)]
    settings = [flag for flag in flags if CONTRACTION.match(flag)]
    if must_pin and (not settings or settings[-1] != PIN):
        findings.append(f"the last contraction setting is {settings[-1] if settings else 'absent'}, not {PIN}")
    return findings


def quoted_flags(text: str) -> list[str]:
    """Every quoted string in a script that is spelled as a compiler flag."""
    return re.findall(r"[\"'](-[A-Za-z][^\"'\s]*)[\"']", text)


def script_flags(environment, firmware: str) -> list[str]:
    """The flags the scripts an environment runs can append, in the order it runs them."""
    flags = []
    for line in environment.get("extra_scripts").split():
        path = line.split(":", 1)[-1]
        with open(os.path.join(firmware, path), encoding="utf-8") as handle:
            flags += quoted_flags(handle.read())
    return flags


def effective_flags(environment, firmware: str) -> list[str]:
    """Every compiler flag one environment's sources are compiled with, last word last."""
    return (
        environment.get("build_flags").split()
        + environment.get("build_src_flags").split()
        + script_flags(environment, firmware)
    )


class PinnedContraction(unittest.TestCase):
    # SOL-HOST-ARITHMETIC-REPRODUCIBLE-ACROSS-HOSTS.C5: Every build that compiles the plant computes with the same pinned arithmetic
    def test_every_environment_that_compiles_the_plant_ends_with_contraction_off(self):
        environments = build_environments.load(FIRMWARE)
        compiling = compiling_the_plant(environments)

        self.assertTrue(any(environment.is_host for environment in compiling))
        self.assertTrue(
            any(not environment.is_host for environment in compiling),
            "the target build is one of the builds that compile the plant, so it is held to the pin",
        )
        found = {
            environment.name: flag_findings(effective_flags(environment, FIRMWARE), must_pin=True)
            for environment in compiling
        }
        self.assertEqual({}, {name: wrong for name, wrong in found.items() if wrong})

    # SOL-HOST-ARITHMETIC-REPRODUCIBLE-ACROSS-HOSTS.C5: Every build that compiles the plant computes with the same pinned arithmetic
    def test_no_environment_at_all_loosens_the_arithmetic(self):
        environments = build_environments.load(FIRMWARE)
        found = {
            environment.name: flag_findings(effective_flags(environment, FIRMWARE), must_pin=False)
            for environment in environments
        }
        self.assertEqual({}, {name: wrong for name, wrong in found.items() if wrong})

    # SOL-HOST-ARITHMETIC-REPRODUCIBLE-ACROSS-HOSTS.C5: Every build that compiles the plant computes with the same pinned arithmetic
    def test_the_mutation_build_ends_with_contraction_off(self):
        with open(os.path.join(TOOLS, "pio_mutation.py"), encoding="utf-8") as handle:
            text = handle.read()
        line = next(
            (line for line in text.splitlines() if line.startswith("MUTATION_FLAGS =")), None
        )
        self.assertIsNotNone(line, "pio_mutation.py declares no MUTATION_FLAGS")

        flags = mull_toolchain.compile_flags("plugin") + quoted_flags(line)

        self.assertEqual([], flag_findings(flags, must_pin=True))
        self.assertEqual([], flag_findings(quoted_flags(text), must_pin=False))

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
        self.assertEqual([], flag_findings(commands[0], must_pin=True))
        compiled = [os.path.basename(argument) for argument in commands[0]]
        self.assertIn("plant_maths.c", compiled)

    # SOL-HOST-ARITHMETIC-REPRODUCIBLE-ACROSS-HOSTS.C5: Every build that compiles the plant computes with the same pinned arithmetic
    def test_the_guard_refuses_a_later_setting_that_undoes_the_pin(self):
        later_fast = ["-std=c11", PIN, "-O1", "-ffp-contract=fast"]
        later_on = [PIN, "-ffp-contract=on"]
        never_set = ["-std=c11", "-O1"]

        self.assertEqual(2, len(flag_findings(later_fast, must_pin=True)))
        self.assertEqual(2, len(flag_findings(later_on, must_pin=True)))
        self.assertEqual(1, len(flag_findings(never_set, must_pin=True)))
        self.assertEqual([], flag_findings([PIN, "-O1"], must_pin=True))

    # SOL-HOST-ARITHMETIC-REPRODUCIBLE-ACROSS-HOSTS.C5: Every build that compiles the plant computes with the same pinned arithmetic
    def test_the_guard_refuses_every_flag_that_licenses_rearranging_arithmetic(self):
        for flag in ("-ffast-math", "-Ofast", "-funsafe-math-optimizations",
                     "-fassociative-math", "-freciprocal-math"):
            with self.subTest(flag=flag):
                self.assertEqual(1, len(flag_findings([PIN, flag], must_pin=True)))

    # SOL-HOST-ARITHMETIC-REPRODUCIBLE-ACROSS-HOSTS.C5: Every build that compiles the plant computes with the same pinned arithmetic
    def test_the_guard_reads_a_loosening_a_script_appends_to_an_environment(self):
        class Synthetic:
            def get(self, option):
                return {"build_flags": f"-std=c11 {PIN}", "build_src_flags": "-Wall",
                        "extra_scripts": "post:tools/loosen.py"}.get(option, "")

        with tempfile.TemporaryDirectory() as scratch:
            os.makedirs(os.path.join(scratch, "tools"))
            with open(os.path.join(scratch, "tools", "loosen.py"), "w", encoding="utf-8") as handle:
                handle.write('env.Append(CCFLAGS=["-O2", "-ffp-contract=fast"])\n')
            flags = effective_flags(Synthetic(), scratch)

        self.assertEqual(["-std=c11", PIN, "-Wall", "-O2", "-ffp-contract=fast"], flags)
        self.assertEqual(2, len(flag_findings(flags, must_pin=True)))


class NoHostMaths(unittest.TestCase):
    # SOL-HOST-ARITHMETIC-REPRODUCIBLE-ACROSS-HOSTS.C5: Every build that compiles the plant computes with the same pinned arithmetic
    def test_no_source_names_a_maths_function_the_hosts_round_differently(self):
        offending = []
        for path in c_sources():
            with open(path, encoding="utf-8") as handle:
                text = handle.read()
            offending += [
                f"{os.path.relpath(path, FIRMWARE)}:{number}: {name}"
                for number, name in host_maths_uses(text)
            ]
        self.assertEqual([], offending)

    # SOL-HOST-ARITHMETIC-REPRODUCIBLE-ACROSS-HOSTS.C5: Every build that compiles the plant computes with the same pinned arithmetic
    def test_every_exact_function_the_sources_use_is_one_the_guard_allows(self):
        used = set()
        for path in c_sources():
            with open(path, encoding="utf-8") as handle:
                used |= {match.group(1) for match in MATH_USE.finditer(without_comments(handle.read()))}

        self.assertLessEqual(EXACT_MATHS - used, set(), "the allowlist names a function nothing uses")

    # SOL-HOST-ARITHMETIC-REPRODUCIBLE-ACROSS-HOSTS.C5: Every build that compiles the plant computes with the same pinned arithmetic
    def test_the_guard_refuses_each_way_of_reaching_the_host_maths(self):
        bypasses = {
            "a call": "float f(float x) { return expf(-x); }",
            "a parenthesised call": "float f(float x) { return (sinf)(x); }",
            "a function pointer": "float (*f)(float) = sinf;",
            "a family the old list omitted": "float f(float x) { return exp2f(x * 1.4426950f); }",
            "log1p": "float f(float x) { return log1pf(x); }",
            "a hyperbolic": "float f(float x) { return sinhf(x); }",
            "a double form": "double f(double x) { return atan(x); }",
            "a long double form": "long double f(long double x) { return expm1l(x); }",
            "a builtin": "float f(float x) { return __builtin_expf(x); }",
            "a builtin double": "double f(double x) { return __builtin_sin(x); }",
            "spread over a line": "float f(float x) { return expf\n(x); }",
        }
        for label, source in bypasses.items():
            with self.subTest(label):
                self.assertNotEqual([], host_maths_uses(source))

    # SOL-HOST-ARITHMETIC-REPRODUCIBLE-ACROSS-HOSTS.C5: Every build that compiles the plant computes with the same pinned arithmetic
    def test_the_guard_accepts_the_exact_functions_and_a_name_that_only_contains_one(self):
        text = (
            "float f(float x) { return sqrtf(fabsf(x)) + fmaxf(x, 1.0f) + fminf(x, 0.0f)"
            " + (float)lroundf(x) + (float)isfinite(x) + (float)isinf(x) + myexpf(x) + expf_table[0]; }"
        )
        self.assertEqual([], host_maths_uses(text))

    # SOL-HOST-ARITHMETIC-REPRODUCIBLE-ACROSS-HOSTS.C5: Every build that compiles the plant computes with the same pinned arithmetic
    def test_the_guard_ignores_a_name_in_a_comment_or_a_string(self):
        self.assertEqual([], host_maths_uses('/* expf(x) */ // sinf(x)\nconst char *s = "expf(x)";\n'))

    # SOL-HOST-ARITHMETIC-REPRODUCIBLE-ACROSS-HOSTS.C5: Every build that compiles the plant computes with the same pinned arithmetic
    def test_the_scan_reaches_every_directory_a_build_compiles(self):
        for directory in ("plant", "control", "estimator", "delivery", "sim", "common"):
            self.assertTrue(
                any(directory in os.path.relpath(path, FIRMWARE).split(os.sep) for path in c_sources()),
                directory,
            )
        self.assertTrue(any(path.endswith(".h") for path in c_sources()))

    # SOL-HOST-ARITHMETIC-REPRODUCIBLE-ACROSS-HOSTS.C5: Every build that compiles the plant computes with the same pinned arithmetic
    def test_the_shared_maths_is_compiled_into_every_build_that_compiles_the_plant(self):
        environments = build_environments.load(FIRMWARE)

        for environment in compiling_the_plant(environments):
            self.assertIn("+<plant/common/>", environment.source_filter, environment.name)
        self.assertTrue(
            os.path.isfile(os.path.join(FIRMWARE, "src", "plant", "common", "plant_maths.c"))
        )


def conditional_macros(text: str) -> list[str]:
    """Every selecting macro named in a preprocessor conditional, wherever it sits."""
    named = []
    for line in without_comments(text).splitlines():
        if re.match(r"\s*#\s*(?:if|ifdef|ifndef|elif)\b", line):
            named += [macro for macro in SELECTING_MACROS if re.search(rf"\b{macro}\b", line)]
    return named


class OneRecordedLiteral(unittest.TestCase):
    # SOL-HOST-ARITHMETIC-REPRODUCIBLE-ACROSS-HOSTS.C1: The golden-trajectory test passes on correct code on every supported host
    def test_the_trajectory_test_carries_no_literal_keyed_to_a_toolchain_or_architecture(self):
        with open(os.path.join(FIRMWARE, "test", "test_plant", "test_plant.c"), encoding="utf-8") as handle:
            text = handle.read()

        self.assertEqual([], conditional_macros(text))
        self.assertNotIn("PLANT_TEST_MUTATION_TOOLCHAIN", without_comments(text))

    # SOL-HOST-ARITHMETIC-REPRODUCIBLE-ACROSS-HOSTS.C1: The golden-trajectory test passes on correct code on every supported host
    def test_the_guard_refuses_a_toolchain_split_wherever_it_is_written(self):
        for macro in SELECTING_MACROS:
            for directive in ("#if defined(%s)", "#ifdef %s", "# if !defined(%s) && 1", "#elif defined %s"):
                with self.subTest(macro=macro, directive=directive):
                    above_the_function = (
                        directive % macro + "\n#define LITERAL 1\n#endif\n"
                        "static void test_the_trajectory_is_what_it_was_before(void) {}\n"
                    )
                    self.assertEqual([macro], conditional_macros(above_the_function))

    # SOL-HOST-ARITHMETIC-REPRODUCIBLE-ACROSS-HOSTS.C1: The golden-trajectory test passes on correct code on every supported host
    def test_the_guard_ignores_a_conditional_that_selects_nothing_by_machine(self):
        text = "#ifndef LITERAL\n#define LITERAL 1\n#endif\n/* #if __aarch64__ */\n"
        self.assertEqual([], conditional_macros(text))

    # SOL-HOST-ARITHMETIC-REPRODUCIBLE-ACROSS-HOSTS.C1: The golden-trajectory test passes on correct code on every supported host
    def test_the_mutation_build_tells_the_sources_nothing_about_its_toolchain(self):
        with open(os.path.join(TOOLS, "pio_mutation.py"), encoding="utf-8") as handle:
            text = handle.read()

        self.assertNotIn("PLANT_TEST_MUTATION_TOOLCHAIN", text)


if __name__ == "__main__":
    unittest.main()
