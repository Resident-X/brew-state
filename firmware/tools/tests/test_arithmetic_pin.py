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
import shutil
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

PIN = "-ffp-contract=off"

#: Maths-library functions whose last bit differs between hosts. The plant is
#: not allowed to name one: it has its own, which does not.
HOST_DEFINED = ("exp", "expf", "expm1", "expm1f", "sin", "sinf", "cos", "cosf", "tan", "tanf",
                "log", "logf", "log2f", "pow", "powf", "tanhf", "atanf", "atan2f", "cbrtf",
                "hypotf", "fmaf", "fma")

CALL = re.compile(r"(?<![A-Za-z0-9_])(" + "|".join(HOST_DEFINED) + r")\s*\(")


def without_comments(text: str) -> str:
    """C source with its comments and string literals blanked, line structure kept."""

    def blank(match: re.Match) -> str:
        return re.sub(r"[^\n]", " ", match.group(0))

    return re.sub(r"/\*.*?\*/|//[^\n]*|\"(?:\\.|[^\"\\])*\"", blank, text, flags=re.S)


def plant_sources() -> list[str]:
    """Every C source that is compiled into a build of the plant model, or the control path."""
    found = []
    for subdirectory in ("plant", "control", "estimator"):
        for directory, _, files in os.walk(os.path.join(FIRMWARE, "src", subdirectory)):
            found += [os.path.join(directory, name) for name in sorted(files) if name.endswith(".c")]
    return sorted(found)


def compiling_the_plant(environments):
    """The environments whose source filter names a plant directory."""
    return [environment for environment in environments if "plant/" in environment.source_filter]


class PinnedContraction(unittest.TestCase):
    # SOL-HOST-ARITHMETIC-REPRODUCIBLE-ACROSS-HOSTS.C5: Every build that compiles the plant computes with the same pinned arithmetic
    def test_every_environment_that_compiles_the_plant_refuses_to_fuse(self):
        environments = build_environments.load(FIRMWARE)
        compiling = compiling_the_plant(environments)

        self.assertTrue(any(environment.is_host for environment in compiling))
        self.assertTrue(
            any(not environment.is_host for environment in compiling),
            "the target build is one of the builds that compile the plant, so it is held to the pin",
        )
        unpinned = [
            environment.name
            for environment in compiling
            if PIN not in environment.get("build_flags").split()
        ]
        self.assertEqual([], unpinned, "environments compiling the plant without " + PIN)

    # SOL-HOST-ARITHMETIC-REPRODUCIBLE-ACROSS-HOSTS.C5: Every build that compiles the plant computes with the same pinned arithmetic
    def test_the_mutation_build_names_the_pin_itself(self):
        with open(os.path.join(TOOLS, "pio_mutation.py"), encoding="utf-8") as handle:
            text = handle.read()
        line = next(
            (line for line in text.splitlines() if line.startswith("MUTATION_FLAGS =")), None
        )

        self.assertIsNotNone(line, "pio_mutation.py declares no MUTATION_FLAGS")
        self.assertIn(f'"{PIN}"', line)

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
        self.assertIn(PIN, commands[0])
        compiled = [os.path.basename(argument) for argument in commands[0]]
        self.assertIn("plant_maths.c", compiled)

    # SOL-HOST-ARITHMETIC-REPRODUCIBLE-ACROSS-HOSTS.C5: Every build that compiles the plant computes with the same pinned arithmetic
    def test_the_pin_stops_a_multiply_and_an_add_rounding_once(self):
        compiler = os.environ.get("CC") or shutil.which("cc")
        self.assertIsNotNone(compiler, "no C compiler on this host")

        # (1 + 2^-12)^2 is 1 + 2^-11 + 2^-24 exactly, which a float rounds to
        # 1 + 2^-11. Adding -(1 + 2^-11) then gives zero if the product was
        # rounded first and 2^-24 if the pair was fused into one rounding.
        probe = """
        #include <stdio.h>
        int main(int argc, char **argv)
        {
            volatile float a = 1.0f + 0x1p-12f;
            volatile float c = -(1.0f + 0x1p-11f);
            (void)argv;
            float r = a * a + c;
            printf("%a\\n", (double)r);
            return argc > 5;
        }
        """
        with tempfile.TemporaryDirectory() as scratch:
            source = os.path.join(scratch, "probe.c")
            binary = os.path.join(scratch, "probe")
            with open(source, "w", encoding="utf-8") as handle:
                handle.write(probe)
            built = subprocess.run(
                [compiler, "-std=c11", "-O1", PIN, "-o", binary, source],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(0, built.returncode, built.stderr)
            ran = subprocess.run([binary], capture_output=True, text=True, check=False)

        self.assertEqual("0x0p+0", ran.stdout.strip())


class NoHostMaths(unittest.TestCase):
    # SOL-HOST-ARITHMETIC-REPRODUCIBLE-ACROSS-HOSTS.C5: Every build that compiles the plant computes with the same pinned arithmetic
    def test_no_plant_or_control_source_calls_a_function_the_hosts_round_differently(self):
        offending = []
        for path in plant_sources():
            with open(path, encoding="utf-8") as handle:
                text = without_comments(handle.read())
            for number, line in enumerate(text.splitlines(), start=1):
                for match in CALL.finditer(line):
                    offending.append(
                        f"{os.path.relpath(path, FIRMWARE)}:{number}: {match.group(1)}"
                    )
        self.assertEqual([], offending)

    # SOL-HOST-ARITHMETIC-REPRODUCIBLE-ACROSS-HOSTS.C5: Every build that compiles the plant computes with the same pinned arithmetic
    def test_the_detector_sees_a_call_the_plant_must_not_make(self):
        text = without_comments("float f(float x) { return expf(-x) + (sinf)(x) + myexpf(x); }")

        self.assertEqual(["expf"], [match.group(1) for match in CALL.finditer(text)])

    # SOL-HOST-ARITHMETIC-REPRODUCIBLE-ACROSS-HOSTS.C5: Every build that compiles the plant computes with the same pinned arithmetic
    def test_the_detector_ignores_a_name_in_a_comment_or_a_string(self):
        text = without_comments('/* expf(x) */ // sinf(x)\nconst char *s = "expf(x)";\n')

        self.assertEqual([], [match.group(1) for match in CALL.finditer(text)])

    # SOL-HOST-ARITHMETIC-REPRODUCIBLE-ACROSS-HOSTS.C5: Every build that compiles the plant computes with the same pinned arithmetic
    def test_the_shared_maths_is_compiled_into_every_build_that_compiles_the_plant(self):
        environments = build_environments.load(FIRMWARE)

        for environment in compiling_the_plant(environments):
            self.assertIn("+<plant/common/>", environment.source_filter, environment.name)
        self.assertTrue(
            os.path.isfile(os.path.join(FIRMWARE, "src", "plant", "common", "plant_maths.c"))
        )


class OneRecordedLiteral(unittest.TestCase):
    # SOL-HOST-ARITHMETIC-REPRODUCIBLE-ACROSS-HOSTS.C1: The golden-trajectory test passes on correct code on every supported host
    def test_the_trajectory_test_carries_no_literal_keyed_to_a_toolchain_or_architecture(self):
        with open(os.path.join(FIRMWARE, "test", "test_plant", "test_plant.c"), encoding="utf-8") as handle:
            text = handle.read()
        start = text.index("static void test_the_trajectory_is_what_it_was_before")
        body = text[start : text.index("\nstatic void test_", start)]

        self.assertNotIn("#if", body)
        self.assertNotIn("#ifdef", body)
        self.assertNotIn("__x86_64__", text)
        self.assertNotIn("PLANT_TEST_MUTATION_TOOLCHAIN", text)

    # SOL-HOST-ARITHMETIC-REPRODUCIBLE-ACROSS-HOSTS.C1: The golden-trajectory test passes on correct code on every supported host
    def test_the_mutation_build_tells_the_sources_nothing_about_its_toolchain(self):
        with open(os.path.join(TOOLS, "pio_mutation.py"), encoding="utf-8") as handle:
            text = handle.read()

        self.assertNotIn("PLANT_TEST_MUTATION_TOOLCHAIN", text)


if __name__ == "__main__":
    unittest.main()
