#!/usr/bin/env python3
"""The board check's KiCad tests are divided into files without losing, duplicating or moving across the proof line any test.

The tests need no KiCad: they load the divided files and compare the test ids
they yield with the list recorded in fixtures/board_check_kicad_test_ids.txt,
one line per test, `P` for a test that needs the seeded-fault proof and `-` for
one that does not, then the test's class and method.
"""

from __future__ import annotations

import glob
import importlib
import os
import sys
import unittest
from unittest import mock

TESTS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TESTS)
sys.path.insert(0, os.path.dirname(TESTS))

import board_kicad_fixtures  # noqa: E402

RECORDED = os.path.join(TESTS, "fixtures", "board_check_kicad_test_ids.txt")


def recorded():
    """The recorded tests: (needs the proof, "Class.method") for each."""
    with open(RECORDED, encoding="utf-8") as handle:
        return [(line[0] == "P", line[2:].strip()) for line in handle if line.strip()]


def divided_modules():
    """The divided files' module names, found by their names the way the stage finds files."""
    return sorted(os.path.basename(path)[: -len(".py")] for path in glob.glob(os.path.join(TESTS, "test_board_check_kicad_*.py")))


def loaded(without_proof: bool):
    """(module, "Class.method", needs the proof) for every test the divided files yield."""
    found = []
    with mock.patch.dict(os.environ):
        os.environ.pop(board_kicad_fixtures.WITHOUT_PROOF, None)
        if without_proof:
            os.environ[board_kicad_fixtures.WITHOUT_PROOF] = "1"
        for name in divided_modules():
            module = importlib.import_module(name)
            suite = unittest.TestLoader().loadTestsFromModule(module)
            for test in board_kicad_fixtures.tests_of(suite):
                found.append((name, f"{type(test).__name__}.{test._testMethodName}",
                              isinstance(test, board_kicad_fixtures.Proved)))
    return found


class TheKiCadTestsAreDividedWithoutLosingOne(unittest.TestCase):
    def test_the_divided_files_yield_exactly_the_tests_the_one_file_held_each_once(self):
        # SOL-BOARD-TIER-TESTS-RUN-SIDE-BY-SIDE.C1: Over a synthetic directory of test files, the stage runs each file in a process of its own from the serial run's working directory, with the serial run's environment and test selection, several at once, at most four unless asked for more; reports each file's result as it finishes; and exits non-zero naming every file that fails, a file that crashes or cannot be imported included. A directory holding no test file fails the stage rather than passing. A file that cannot run because a tool it needs is missing makes the stage report that tool by name on its error output in the form the round reads as a failure to look, once however many files report it, so the round stops naming the tool rather than reporting a finding. The stage gives the same verdict run side by side as run one file after another, and two synthetic files that each need the one installed CAD tool both pass when run side by side. The on-demand full run of the board tooling's tests runs its files the same way. A test file divided to shorten the stage keeps every test it held, each in exactly one of the files it is divided into: the stage runs the same tests before and after the division, and the tests that need the seeded-fault proof stay outside the stage and inside the on-demand full run, as before. Tests of one class that only read a copy of a proof design and the result of checking it share one copy and one check made for the class, and a test that changes its copy has a copy of its own, so a test that changed a shared copy would be caught and no test sees another's change. Every test process the stage starts makes its git commits unsigned, whatever signing the user's own git configuration asks for, so scratch commits neither queue on one signing agent across the files run at once nor wait on a passphrase. The stage states its wall time and how many files it ran at once when it finishes. Out of scope: selecting tiers by changed path and the seeded-fault proof.
        found = loaded(False)
        ids = [test for _, test, _ in found]
        self.assertEqual([], sorted(test for test in set(ids) if ids.count(test) > 1), "a test is in more than one file")
        want = [test for _, test in recorded()]
        self.assertEqual([], sorted(set(want) - set(ids)), "a test the one file held is in none of the divided files")
        self.assertEqual([], sorted(set(ids) - set(want)), "a test is in the divided files that the one file did not hold")
        self.assertEqual(len(want), len(ids))

    def test_the_proof_line_is_where_it_was_with_and_without_the_variable(self):
        # SOL-BOARD-TIER-TESTS-RUN-SIDE-BY-SIDE.C1: Over a synthetic directory of test files, the stage runs each file in a process of its own from the serial run's working directory, with the serial run's environment and test selection, several at once, at most four unless asked for more; reports each file's result as it finishes; and exits non-zero naming every file that fails, a file that crashes or cannot be imported included. A directory holding no test file fails the stage rather than passing. A file that cannot run because a tool it needs is missing makes the stage report that tool by name on its error output in the form the round reads as a failure to look, once however many files report it, so the round stops naming the tool rather than reporting a finding. The stage gives the same verdict run side by side as run one file after another, and two synthetic files that each need the one installed CAD tool both pass when run side by side. The on-demand full run of the board tooling's tests runs its files the same way. A test file divided to shorten the stage keeps every test it held, each in exactly one of the files it is divided into: the stage runs the same tests before and after the division, and the tests that need the seeded-fault proof stay outside the stage and inside the on-demand full run, as before. Tests of one class that only read a copy of a proof design and the result of checking it share one copy and one check made for the class, and a test that changes its copy has a copy of its own, so a test that changed a shared copy would be caught and no test sees another's change. Every test process the stage starts makes its git commits unsigned, whatever signing the user's own git configuration asks for, so scratch commits neither queue on one signing agent across the files run at once nor wait on a passphrase. The stage states its wall time and how many files it ran at once when it finishes. Out of scope: selecting tiers by changed path and the seeded-fault proof.
        with_proof = {test for _, test, _ in loaded(False)}
        without = loaded(True)
        proof = {test for needs, test in recorded() if needs}
        self.assertTrue(proof)
        self.assertEqual({test for needs, test in recorded() if not needs}, {test for _, test, _ in without})
        self.assertEqual([], [test for _, test, needs in without if needs], "a test needing the proof is in the stage")
        self.assertEqual(proof, {test for _, test, needs in loaded(False) if needs})
        self.assertLessEqual(proof, with_proof)

    def test_a_divided_file_that_dropped_the_proof_exclusion_would_be_seen(self):
        # SOL-BOARD-TIER-TESTS-RUN-SIDE-BY-SIDE.C1: Over a synthetic directory of test files, the stage runs each file in a process of its own from the serial run's working directory, with the serial run's environment and test selection, several at once, at most four unless asked for more; reports each file's result as it finishes; and exits non-zero naming every file that fails, a file that crashes or cannot be imported included. A directory holding no test file fails the stage rather than passing. A file that cannot run because a tool it needs is missing makes the stage report that tool by name on its error output in the form the round reads as a failure to look, once however many files report it, so the round stops naming the tool rather than reporting a finding. The stage gives the same verdict run side by side as run one file after another, and two synthetic files that each need the one installed CAD tool both pass when run side by side. The on-demand full run of the board tooling's tests runs its files the same way. A test file divided to shorten the stage keeps every test it held, each in exactly one of the files it is divided into: the stage runs the same tests before and after the division, and the tests that need the seeded-fault proof stay outside the stage and inside the on-demand full run, as before. Tests of one class that only read a copy of a proof design and the result of checking it share one copy and one check made for the class, and a test that changes its copy has a copy of its own, so a test that changed a shared copy would be caught and no test sees another's change. Every test process the stage starts makes its git commits unsigned, whatever signing the user's own git configuration asks for, so scratch commits neither queue on one signing agent across the files run at once nor wait on a passphrase. The stage states its wall time and how many files it ran at once when it finishes. Out of scope: selecting tiers by changed path and the seeded-fault proof.
        # Every divided file carries the loader hook itself; a file without it would keep the proof's tests in the stage.
        for name in divided_modules():
            with self.subTest(module=name):
                module = importlib.import_module(name)
                self.assertIs(module.load_tests, board_kicad_fixtures.load_tests)
                self.assertIs(module.setUpModule, board_kicad_fixtures.setUpModule)


DIVIDED_RECORDS = os.path.join(TESTS, "fixtures", "divided_test_ids")
DIVIDED = ("test_board_views", "test_board_history", "test_locked_copper", "test_review_proof_rules")


def ids_of(modules):
    """Every "Class.method" the named modules yield, with the module each is in."""
    found = []
    for name in modules:
        module = importlib.import_module(name)
        for test in board_kicad_fixtures.tests_of(unittest.TestLoader().loadTestsFromModule(module)):
            found.append((name, f"{type(test).__name__}.{test._testMethodName}"))
    return found


class TheOtherLongFilesAreDividedWithoutLosingOne(unittest.TestCase):
    def test_each_divided_file_yields_exactly_the_tests_its_original_held_each_once(self):
        # SOL-BOARD-TIER-TESTS-RUN-SIDE-BY-SIDE.C1: Over a synthetic directory of test files, the stage runs each file in a process of its own from the serial run's working directory, with the serial run's environment and test selection, several at once, at most four unless asked for more; reports each file's result as it finishes; and exits non-zero naming every file that fails, a file that crashes or cannot be imported included. A directory holding no test file fails the stage rather than passing. A file that cannot run because a tool it needs is missing makes the stage report that tool by name on its error output in the form the round reads as a failure to look, once however many files report it, so the round stops naming the tool rather than reporting a finding. The stage gives the same verdict run side by side as run one file after another, and two synthetic files that each need the one installed CAD tool both pass when run side by side. The on-demand full run of the board tooling's tests runs its files the same way. A test file divided to shorten the stage keeps every test it held, each in exactly one of the files it is divided into: the stage runs the same tests before and after the division, and the tests that need the seeded-fault proof stay outside the stage and inside the on-demand full run, as before. Tests of one class that only read a copy of a proof design and the result of checking it share one copy and one check made for the class, and a test that changes its copy has a copy of its own, so a test that changed a shared copy would be caught and no test sees another's change. Every test process the stage starts makes its git commits unsigned, whatever signing the user's own git configuration asks for, so scratch commits neither queue on one signing agent across the files run at once nor wait on a passphrase. The stage states its wall time and how many files it ran at once when it finishes. Out of scope: selecting tiers by changed path and the seeded-fault proof.
        for original in DIVIDED:
            with self.subTest(original=original):
                parts = sorted(os.path.basename(path)[: -len(".py")] for path in glob.glob(os.path.join(TESTS, original + "_*.py")))
                self.assertGreaterEqual(len(parts), 2, "the file is not divided")
                self.assertFalse(os.path.exists(os.path.join(TESTS, original + ".py")), "the undivided file is still there")
                with open(os.path.join(DIVIDED_RECORDS, original + ".txt"), encoding="utf-8") as handle:
                    want = sorted(line.strip() for line in handle if line.strip())
                found = [test for _, test in ids_of(parts)]
                self.assertEqual([], sorted(set(test for test in found if found.count(test) > 1)), "a test is in more than one file")
                self.assertEqual([], sorted(set(want) - set(found)), "a test the original held is in none of its parts")
                self.assertEqual([], sorted(set(found) - set(want)), "a part holds a test the original did not")
                self.assertEqual(len(want), len(found))


if __name__ == "__main__":
    unittest.main()
