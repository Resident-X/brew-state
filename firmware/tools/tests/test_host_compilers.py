#!/usr/bin/env python3
"""The host tier's own sources compile without a warning under each compiler a host defaults to.

A conversion warning is only as strict as the compiler asked: one compiler
accepts an implicit narrowing another rejects, and a contributor on the first
host never learns of it until a contributor on the second does. So the sources
the host tier compiles are compiled here, under the strict settings the build
file declares for them, with every compiler of each family found on the host
running these tests -- the GCC a Linux host defaults to and the clang a macOS
host defaults to.

What a host has is what it has. Run locally, a family with no compiler on this
host is reported as skipped, with the reason, and never as a pass. On a hosted CI
run the host's own default family is not optional: a Linux host without a GCC, or
a macOS host without a clang, fails these tests, because the job that was meant
to carry that half no longer does and a skip would read as a pass.

Each source is compiled under the flags its environment resolves to rather than
under a list kept here, so a source added, a structure added or a flag changed
in `platformio.ini` is what these tests see. Nothing is linked and nothing is
run: a warning is a property of compiling.
"""

from __future__ import annotations

import concurrent.futures
import glob
import os
import platform
import re
import shlex
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIRMWARE = os.path.dirname(TOOLS)
sys.path.insert(0, TOOLS)

import build_environments  # noqa: E402
import filter_terms  # noqa: E402

GCC = "gcc"
CLANG = "clang"
FAMILIES = (GCC, CLANG)

#: What the build file says is applied to this project's own sources and to
#: nothing else, and what a conversion has to be to fail the build.
STRICT_FLAGS = ("-Werror", "-Wconversion", "-Wshadow", "-Wdouble-promotion")
BASE_FLAGS = ("-Wall", "-Wextra")

#: The names a host's own C compiler goes by. The host's default, `cc`, is the
#: one PlatformIO's native platform picks up; the others are how a second
#: compiler of the same family is commonly installed beside it.
GENERIC_NAMES = ("cc", "gcc", "clang")
VERSIONED_NAMES = ("gcc-[0-9]*", "clang-[0-9]*")


def family_of(banner: str) -> str | None:
    """Which family a compiler's version banner says it belongs to.

    Clang is checked first because Apple's `gcc` is clang under another name, and
    reading the file name would count it as a GCC that was never run.
    """
    lowered = banner.lower()
    if "clang" in lowered:
        return CLANG
    if "gcc" in lowered or "free software foundation" in lowered:
        return GCC
    return None


def find_compilers(path_directories: list[str]) -> dict[str, list[str]]:
    """Every distinct compiler of each family on the path, by the path to run it.

    Two names that print the same banner are one compiler: on a host where `cc`
    and `gcc` are the same program, compiling everything twice would only say
    the same thing twice. A name that does not run, or prints no banner of
    either family, is not a compiler of either.
    """
    found: dict[str, list[str]] = {family: [] for family in FAMILIES}
    seen: set[tuple[str, str]] = set()
    names: list[str] = []
    for directory in path_directories:
        for pattern in GENERIC_NAMES + VERSIONED_NAMES:
            names.extend(sorted(glob.glob(os.path.join(directory, pattern))))
    for path in names:
        if not os.access(path, os.X_OK):
            continue
        try:
            banner = subprocess.run(
                [path, "--version"], capture_output=True, text=True, timeout=30, check=False
            ).stdout
        except (OSError, subprocess.SubprocessError):
            continue
        family = family_of(banner)
        if family is None or (family, banner) in seen:
            continue
        seen.add((family, banner))
        found[family].append(path)
    return found


def host_compilers() -> dict[str, list[str]]:
    return find_compilers([d for d in os.environ.get("PATH", "").split(os.pathsep) if d])


#: The family each kind of host defaults to, which a hosted run must therefore have.
DEFAULT_FAMILY_OF_HOST = {"Linux": GCC, "Darwin": CLANG}


def absence_is_failure(family: str, system: str, environ: dict[str, str]) -> bool:
    """Whether a missing compiler of this family fails the run rather than skips it.

    On a hosted CI run the family a host's own default compiler belongs to has to
    be present: a job without it has stopped carrying its half of the check, and
    a skip is indistinguishable from a pass there.
    """
    return environ.get("GITHUB_ACTIONS") == "true" and DEFAULT_FAMILY_OF_HOST.get(system) == family


def compilers_of(case: unittest.TestCase, family: str) -> list[str]:
    """The compilers of a family on this host, or the failure or skip their absence is."""
    compilers = host_compilers()
    if not any(compilers.values()):
        case.fail("no C compiler of either family is on this host's path, and the host build needs one")
    if not compilers[family]:
        reason = (
            f"no {family} compiler is on this host's path, so the {family} half of the host "
            "tier's check did not run here"
        )
        if absence_is_failure(family, platform.system(), os.environ):
            case.fail(f"{reason}, and a hosted run on this kind of host is where it has to")
        case.skipTest(f"{reason}; the hosted nightly runs it on a host whose default compiler is {family}")
    return compilers[family]


def covered_environments() -> list[build_environments.Environment]:
    """The host environments that compile this project's sources under the strict settings.

    An environment that declares an exemption compiles a runner's generated
    support file through the same path and so carries none; its own sources are
    the ones the environment it extends compiles, and are covered there.
    """
    environments = build_environments.load(FIRMWARE)
    return [
        environment
        for environment in build_environments.host_environments(environments)
        if not environment.strict_flags_exemption
    ]


def own_sources(environment: build_environments.Environment) -> list[str]:
    """The project's own C sources an environment compiles, walked in filter order."""
    terms = filter_terms.terms(environment.source_filter)
    root = os.path.join(FIRMWARE, "src")
    chosen = []
    for directory, _, files in os.walk(root):
        for name in sorted(files):
            if not name.endswith(".c"):
                continue
            path = os.path.join(directory, name)
            relative = os.path.relpath(path, root).replace(os.sep, "/")
            included = False
            for sign, term in terms:
                if filter_terms.covers(term, relative):
                    included = sign == "+"
            if included:
                chosen.append(path)
    return sorted(chosen)


def flags_of(environment: build_environments.Environment) -> list[str]:
    """What the build passes the compiler for this project's own sources.

    The directories PlatformIO adds on its own are added here too, because a
    source that includes through them has to be found.
    """
    resolved = " ".join(
        [environment.get("build_flags"), environment.source_flags]
    ).replace("$PROJECT_DIR", FIRMWARE)
    return shlex.split(resolved) + [
        "-I", os.path.join(FIRMWARE, "include"), "-I", os.path.join(FIRMWARE, "src"),
    ]


def compile_source(compiler: str, flags: list[str], source: str) -> tuple[int, str]:
    result = subprocess.run(
        [compiler, *flags, "-c", "-o", os.devnull, source],
        capture_output=True, text=True, check=False, cwd=FIRMWARE,
    )
    return result.returncode, (result.stdout + result.stderr).strip()


def compile_everything(compiler: str) -> list[str]:
    """Every own source of every covered environment compiled, and what failed."""
    jobs = [
        (flags_of(environment), source, environment.name)
        for environment in covered_environments()
        for source in own_sources(environment)
    ]
    with concurrent.futures.ThreadPoolExecutor(max_workers=os.cpu_count() or 1) as pool:
        outcomes = list(pool.map(lambda job: compile_source(compiler, job[0], job[1]), jobs))
    return [
        f"{os.path.relpath(source, FIRMWARE)} in {name}: {output}"
        for (_, source, name), (status, output) in zip(jobs, outcomes)
        if status != 0 or output
    ]


class TheHostCompilersAreFoundByTheirBanner(unittest.TestCase):
    def fake(self, directory: str, name: str, banner: str) -> None:
        path = os.path.join(directory, name)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(f"#!/bin/sh\ncat <<'EOF'\n{banner}\nEOF\n")
        os.chmod(path, os.stat(path).st_mode | stat.S_IEXEC)

    def test_a_compiler_is_counted_by_what_it_says_it_is_not_by_its_name(self):
        # SOL-PLANT-FIXTURES-BUILD-CLEAN-UNDER-GCC.C1: The host tier compiles without warnings under both GCC and clang
        with tempfile.TemporaryDirectory() as directory:
            self.fake(directory, "cc", "cc (Ubuntu 13.2.0-23ubuntu4) 13.2.0\nCopyright (C) 2023 Free Software Foundation, Inc.")
            self.fake(directory, "gcc", "Apple clang version 21.0.0 (clang-2100.1.1.101)")
            self.fake(directory, "clang-19", "Ubuntu clang version 19.1.7")
            self.fake(directory, "gcc-13", "cc (Ubuntu 13.2.0-23ubuntu4) 13.2.0\nCopyright (C) 2023 Free Software Foundation, Inc.")
            found = find_compilers([directory])
        self.assertEqual([os.path.join(directory, "cc")], found[GCC])
        self.assertEqual(
            [os.path.join(directory, "clang-19"), os.path.join(directory, "gcc")], sorted(found[CLANG])
        )

    def test_a_name_that_prints_nothing_of_either_family_or_will_not_run_is_no_compiler(self):
        # SOL-PLANT-FIXTURES-BUILD-CLEAN-UNDER-GCC.C1: The host tier compiles without warnings under both GCC and clang
        with tempfile.TemporaryDirectory() as directory:
            self.fake(directory, "cc", "tcc version 0.9.27")
            with open(os.path.join(directory, "gcc"), "w", encoding="utf-8") as handle:
                handle.write("#!/nonexistent/interpreter\n")
            os.chmod(os.path.join(directory, "gcc"), 0o755)
            self.assertEqual({GCC: [], CLANG: []}, find_compilers([directory]))

    def test_an_empty_path_finds_none(self):
        # SOL-PLANT-FIXTURES-BUILD-CLEAN-UNDER-GCC.C1: The host tier compiles without warnings under both GCC and clang
        self.assertEqual({GCC: [], CLANG: []}, find_compilers([]))


class AMissingDefaultCompilerFailsAHostedRunAndSkipsALocalOne(unittest.TestCase):
    ONLY = {GCC: [], CLANG: ["/usr/bin/clang"]}
    NEITHER = {GCC: [], CLANG: []}

    def outcome(self, family, system, ci, found):
        environ = {"GITHUB_ACTIONS": "true"} if ci else {}
        with mock.patch.object(sys.modules[__name__], "host_compilers", return_value=found), \
                mock.patch("platform.system", return_value=system), \
                mock.patch.dict(os.environ, environ, clear=True):
            try:
                return compilers_of(unittest.TestCase(), family)
            except unittest.SkipTest:
                return "skipped"
            except AssertionError:
                return "failed"

    def test_a_linux_host_under_ci_without_gcc_fails(self):
        # SOL-PLANT-FIXTURES-BUILD-CLEAN-UNDER-GCC.C2: A narrowing reintroduced into a plant structure, built under the compiler that rejects it, fails that run
        self.assertEqual("failed", self.outcome(GCC, "Linux", True, {GCC: [], CLANG: ["/usr/bin/clang"]}))

    def test_a_macos_host_under_ci_without_clang_fails(self):
        # SOL-PLANT-FIXTURES-BUILD-CLEAN-UNDER-GCC.C2: A narrowing reintroduced into a plant structure, built under the compiler that rejects it, fails that run
        self.assertEqual("failed", self.outcome(CLANG, "Darwin", True, {GCC: ["/usr/bin/gcc"], CLANG: []}))

    def test_the_same_absence_off_ci_skips(self):
        # SOL-PLANT-FIXTURES-BUILD-CLEAN-UNDER-GCC.C2: A narrowing reintroduced into a plant structure, built under the compiler that rejects it, fails that run
        self.assertEqual("skipped", self.outcome(GCC, "Linux", False, self.ONLY))
        self.assertEqual("skipped", self.outcome(CLANG, "Darwin", False, {GCC: ["/usr/bin/gcc"], CLANG: []}))

    def test_a_family_that_is_not_the_hosts_default_skips_even_under_ci(self):
        # SOL-PLANT-FIXTURES-BUILD-CLEAN-UNDER-GCC.C2: A narrowing reintroduced into a plant structure, built under the compiler that rejects it, fails that run
        self.assertEqual("skipped", self.outcome(CLANG, "Linux", True, {GCC: ["/usr/bin/gcc"], CLANG: []}))
        self.assertEqual("skipped", self.outcome(GCC, "Darwin", True, self.ONLY))

    def test_a_host_of_another_kind_under_ci_skips(self):
        # SOL-PLANT-FIXTURES-BUILD-CLEAN-UNDER-GCC.C2: A narrowing reintroduced into a plant structure, built under the compiler that rejects it, fails that run
        self.assertEqual("skipped", self.outcome(GCC, "Windows", True, self.ONLY))

    def test_a_ci_variable_that_is_not_true_is_not_ci(self):
        # SOL-PLANT-FIXTURES-BUILD-CLEAN-UNDER-GCC.C2: A narrowing reintroduced into a plant structure, built under the compiler that rejects it, fails that run
        self.assertFalse(absence_is_failure(GCC, "Linux", {"GITHUB_ACTIONS": "false"}))
        self.assertFalse(absence_is_failure(GCC, "Linux", {}))
        self.assertTrue(absence_is_failure(GCC, "Linux", {"GITHUB_ACTIONS": "true"}))

    def test_a_host_with_no_compiler_at_all_fails_everywhere(self):
        # SOL-PLANT-FIXTURES-BUILD-CLEAN-UNDER-GCC.C2: A narrowing reintroduced into a plant structure, built under the compiler that rejects it, fails that run
        self.assertEqual("failed", self.outcome(GCC, "Linux", False, self.NEITHER))

    def test_a_present_family_returns_its_compilers_under_ci(self):
        # SOL-PLANT-FIXTURES-BUILD-CLEAN-UNDER-GCC.C2: A narrowing reintroduced into a plant structure, built under the compiler that rejects it, fails that run
        self.assertEqual(
            ["/usr/bin/gcc"], self.outcome(GCC, "Linux", True, {GCC: ["/usr/bin/gcc"], CLANG: []})
        )


class TheStrictSettingsAreTheOnesTheBuildDeclares(unittest.TestCase):
    def test_every_covered_environment_still_carries_every_strict_setting(self):
        # SOL-PLANT-FIXTURES-BUILD-CLEAN-UNDER-GCC.C1: The host tier compiles without warnings under both GCC and clang
        # A narrowing fixed by turning the conversion check down would pass
        # every compile below, so the settings are asserted as they stand.
        environments = covered_environments()
        self.assertTrue(environments, "no host environment carries the strict settings")
        for environment in environments:
            flags = flags_of(environment)
            with self.subTest(environment=environment.name):
                for wanted in STRICT_FLAGS + BASE_FLAGS:
                    self.assertIn(wanted, flags)
                self.assertEqual([], [flag for flag in flags if flag.startswith("-Wno-")])
                self.assertNotIn("-w", flags)

    def test_every_plant_structure_is_compiled_under_them_somewhere(self):
        # SOL-PLANT-FIXTURES-BUILD-CLEAN-UNDER-GCC.C1: The host tier compiles without warnings under both GCC and clang
        # A structure no covered environment compiles would be a place a
        # narrowing could sit under no compiler at all.
        compiled = {
            os.path.relpath(source, FIRMWARE)
            for environment in covered_environments()
            for source in own_sources(environment)
        }
        plant_root = os.path.join(FIRMWARE, "src", "plant")
        structures = sorted(
            name for name in os.listdir(plant_root)
            if name != "common" and os.path.isdir(os.path.join(plant_root, name))
        )
        self.assertTrue(structures)
        for structure in structures:
            with self.subTest(structure=structure):
                implementation = os.path.join("src", "plant", structure, "plant_structure.c")
                self.assertTrue(os.path.exists(os.path.join(FIRMWARE, implementation)))
                self.assertIn(implementation, compiled)


class EveryOwnSourceCompilesWithoutAWarning(unittest.TestCase):
    def check_family(self, family: str) -> None:
        for compiler in compilers_of(self, family):
            with self.subTest(compiler=compiler):
                self.assertEqual([], compile_everything(compiler))

    def test_under_gcc(self):
        # SOL-PLANT-FIXTURES-BUILD-CLEAN-UNDER-GCC.C1: The host tier compiles without warnings under both GCC and clang
        self.check_family(GCC)

    def test_under_clang(self):
        # SOL-PLANT-FIXTURES-BUILD-CLEAN-UNDER-GCC.C1: The host tier compiles without warnings under both GCC and clang
        self.check_family(CLANG)


class AReintroducedNarrowingIsCaught(unittest.TestCase):
    """Compiling clean proves nothing unless compiling dirty is shown to fail.

    The fixture structure's own source, with one line seeded, is compiled the
    way the build compiles it. The environment is read from the build file, so
    the seed meets the flags the build really applies.
    """

    FIXTURE = os.path.join(FIRMWARE, "src", "plant", "fixture", "plant_structure.c")
    ASSIGNMENT = re.compile(r"\*mass = \(point == PLANT_DELIVERY_POINT_GROUP\) \?[^;]*;")

    def seeded(self, directory: str, replacement: str) -> str:
        with open(self.FIXTURE, encoding="utf-8") as handle:
            text = handle.read()
        self.assertEqual(
            1, len(self.ASSIGNMENT.findall(text)),
            "the fixture structure no longer assigns the heated-mass identifier this seed replaces",
        )
        path = os.path.join(directory, "plant_structure.c")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(self.ASSIGNMENT.sub(lambda _: replacement, text))
        return path

    def flags(self) -> list[str]:
        (environment,) = [e for e in covered_environments() if e.name == "native_fixture"]
        return flags_of(environment) + ["-I", os.path.dirname(self.FIXTURE)]

    def rejected_by(self, family: str, replacement: str) -> None:
        for compiler in compilers_of(self, family):
            with self.subTest(compiler=compiler), tempfile.TemporaryDirectory() as directory:
                source = self.seeded(directory, replacement)
                status, output = compile_source(compiler, self.flags(), source)
                self.assertNotEqual(0, status, "the seeded narrowing compiled")
                self.assertIn("conversion", output.lower())

    def test_a_wide_value_assigned_to_the_identifier_fails_under_gcc(self):
        # SOL-PLANT-FIXTURES-BUILD-CLEAN-UNDER-GCC.C1: The host tier compiles without warnings under both GCC and clang
        self.rejected_by(GCC, "*mass = (plant_heated_mass_id_t)0u + (unsigned)point * 300u;")

    def test_a_wide_value_assigned_to_the_identifier_fails_under_clang(self):
        # SOL-PLANT-FIXTURES-BUILD-CLEAN-UNDER-GCC.C1: The host tier compiles without warnings under both GCC and clang
        self.rejected_by(CLANG, "*mass = (plant_heated_mass_id_t)0u + (unsigned)point * 300u;")

    def test_the_conditional_the_nightly_reported_fails_under_gcc(self):
        # SOL-PLANT-FIXTURES-BUILD-CLEAN-UNDER-GCC.C1: The host tier compiles without warnings under both GCC and clang
        # The form the first hosted run was stopped by: a conditional of plain
        # unsigned type assigned to the eight-bit identifier. Clang accepts it,
        # which is how it reached main, so only GCC is asked to reject it.
        self.rejected_by(GCC, "*mass = (point == PLANT_DELIVERY_POINT_GROUP) ? 0u : 1u;")

    def test_the_conditional_with_each_branch_of_the_identifiers_own_type_is_accepted(self):
        # SOL-PLANT-FIXTURES-BUILD-CLEAN-UNDER-GCC.C1: The host tier compiles without warnings under both GCC and clang
        # The same line as delivered: if this were rejected the seeded
        # failures above could be about the harness and not the narrowing.
        compilers = host_compilers()
        found = [compiler for family in FAMILIES for compiler in compilers[family]]
        if not found:
            self.fail("no C compiler of either family is on this host's path, and the host build needs one")
        for compiler in found:
            with self.subTest(compiler=compiler), tempfile.TemporaryDirectory() as directory:
                source = self.seeded(
                    directory,
                    "*mass = (point == PLANT_DELIVERY_POINT_GROUP) ? (plant_heated_mass_id_t)0u"
                    " : (plant_heated_mass_id_t)1u;",
                )
                status, output = compile_source(compiler, self.flags(), source)
                self.assertEqual((0, ""), (status, output))


class TheNarrowIdentifierSitesAreNotWrittenAsPlainUnsignedConditionals(unittest.TestCase):
    def test_no_plant_structure_assigns_a_bare_unsigned_conditional_to_a_heated_mass_identifier(self):
        # SOL-PLANT-FIXTURES-BUILD-CLEAN-UNDER-GCC.C1: The host tier compiles without warnings under both GCC and clang
        # The compile tests are the authority. This is only a text heuristic: it
        # matches a literal numeric conditional assigned to a mass identifier,
        # the one form that stopped the nightly, and nothing else. A narrowing
        # written any other way is caught by the compile tests alone.
        pattern = re.compile(r"\*\w*mass\w*\s*=\s*[^;]*\?\s*\d+u?\s*:\s*\d+u?\s*;")
        structures = glob.glob(os.path.join(FIRMWARE, "src", "plant", "*", "plant_structure.c"))
        self.assertGreaterEqual(len(structures), 6)
        for path in structures:
            with open(path, encoding="utf-8") as handle:
                text = handle.read()
            with self.subTest(structure=os.path.relpath(path, FIRMWARE)):
                self.assertIsNone(pattern.search(text))

    def test_the_pattern_it_looks_for_is_the_one_that_was_reported(self):
        # SOL-PLANT-FIXTURES-BUILD-CLEAN-UNDER-GCC.C1: The host tier compiles without warnings under both GCC and clang
        pattern = re.compile(r"\*\w*mass\w*\s*=\s*[^;]*\?\s*\d+u?\s*:\s*\d+u?\s*;")
        self.assertIsNotNone(
            pattern.search("*mass = (point == PLANT_DELIVERY_POINT_GROUP) ? 0u : 1u;")
        )
        self.assertIsNone(pattern.search("*mass = 0u;"))
        self.assertIsNone(
            pattern.search(
                "*mass = (point == X) ? (plant_heated_mass_id_t)0u : (plant_heated_mass_id_t)1u;"
            )
        )


if __name__ == "__main__":
    unittest.main()
