#!/usr/bin/env python3
"""The copy of a proof design that the tests of one class share is made once, and a test that changes it is caught.

These need no KiCad: the shared copy's design and check are replaced by a small
folder and a canned result, and the class is run under a loader of its own.
"""

from __future__ import annotations

import os
import sys
import unittest
from unittest import mock

TESTS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TESTS)
sys.path.insert(0, os.path.dirname(TESTS))

import board_kicad_fixtures  # noqa: E402

PREPARED = []
CHECKED = []


def run(case) -> unittest.TestResult:
    """Run the tests of `case` alone, as a loader does, and return what happened."""
    result = unittest.TestResult()
    unittest.defaultTestLoader.loadTestsFromTestCase(case).run(result)
    return result


def make_case(*bodies):
    """A SharedCopy class over a synthetic design folder whose tests are `bodies`, named test_0, test_1 and so on."""

    class Shared(board_kicad_fixtures.SharedCopy):
        @classmethod
        def prepare_seed(cls, root):
            PREPARED.append(root)
            os.makedirs(os.path.join(root, "design"))
            for name in ("a.txt", "b.txt"):
                with open(os.path.join(root, "design", name), "w", encoding="utf-8") as handle:
                    handle.write(name)
            return mock.Mock(root=os.path.join(root, "design"))

    for index, body in enumerate(bodies):
        setattr(Shared, f"test_{index}", body)
    return Shared


def reads(self):
    with open(os.path.join(self.seed.root, "a.txt"), encoding="utf-8") as handle:
        self.assertEqual("a.txt", handle.read())
    self.assertEqual((0, ["ok"]), self.check())


def edits(self):
    with open(os.path.join(self.seed.root, "a.txt"), "w", encoding="utf-8") as handle:
        handle.write("changed")


def adds(self):
    with open(os.path.join(self.seed.root, "new.txt"), "w", encoding="utf-8") as handle:
        handle.write("new")


def removes(self):
    os.remove(os.path.join(self.seed.root, "b.txt"))


class TheClassSharesOneCopyAndOneCheck(unittest.TestCase):
    def setUp(self):
        PREPARED.clear()
        CHECKED.clear()

        def check(seed, kicad_cli):
            CHECKED.append(seed)
            return 0, ["ok"], ""

        patcher = mock.patch.object(board_kicad_fixtures.board_prove, "check", check)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_the_copy_is_made_and_checked_once_for_the_tests_of_a_class(self):
        # SOL-BOARD-TIER-TESTS-RUN-SIDE-BY-SIDE.C1: Over a synthetic directory of test files, the stage runs each file in a process of its own from the serial run's working directory, with the serial run's environment and test selection, several at once, at most four unless asked for more; reports each file's result as it finishes; and exits non-zero naming every file that fails, a file that crashes or cannot be imported included. A directory holding no test file fails the stage rather than passing. A file that cannot run because a tool it needs is missing makes the stage report that tool by name on its error output in the form the round reads as a failure to look, once however many files report it, so the round stops naming the tool rather than reporting a finding. The stage gives the same verdict run side by side as run one file after another, and two synthetic files that each need the one installed CAD tool both pass when run side by side. The on-demand full run of the board tooling's tests runs its files the same way. A test file divided to shorten the stage keeps every test it held, each in exactly one of the files it is divided into: the stage runs the same tests before and after the division, and the tests that need the seeded-fault proof stay outside the stage and inside the on-demand full run, as before. Tests of one class that only read a copy of a proof design and the result of checking it share one copy and one check made for the class, and a test that changes its copy has a copy of its own, so a test that changed a shared copy would be caught and no test sees another's change. Every test process the stage starts makes its git commits unsigned, whatever signing the user's own git configuration asks for, so scratch commits neither queue on one signing agent across the files run at once nor wait on a passphrase. The stage states its wall time and how many files it ran at once when it finishes. Out of scope: selecting tiers by changed path and the seeded-fault proof.
        result = run(make_case(reads, reads, reads))
        self.assertEqual(3, result.testsRun)
        self.assertEqual([], [str(problem) for problem in result.failures + result.errors])
        self.assertEqual(1, len(PREPARED))
        self.assertEqual(1, len(CHECKED))

    def test_a_test_that_changes_the_shared_copy_fails_and_the_tests_that_only_read_it_pass(self):
        # SOL-BOARD-TIER-TESTS-RUN-SIDE-BY-SIDE.C1: Over a synthetic directory of test files, the stage runs each file in a process of its own from the serial run's working directory, with the serial run's environment and test selection, several at once, at most four unless asked for more; reports each file's result as it finishes; and exits non-zero naming every file that fails, a file that crashes or cannot be imported included. A directory holding no test file fails the stage rather than passing. A file that cannot run because a tool it needs is missing makes the stage report that tool by name on its error output in the form the round reads as a failure to look, once however many files report it, so the round stops naming the tool rather than reporting a finding. The stage gives the same verdict run side by side as run one file after another, and two synthetic files that each need the one installed CAD tool both pass when run side by side. The on-demand full run of the board tooling's tests runs its files the same way. A test file divided to shorten the stage keeps every test it held, each in exactly one of the files it is divided into: the stage runs the same tests before and after the division, and the tests that need the seeded-fault proof stay outside the stage and inside the on-demand full run, as before. Tests of one class that only read a copy of a proof design and the result of checking it share one copy and one check made for the class, and a test that changes its copy has a copy of its own, so a test that changed a shared copy would be caught and no test sees another's change. Every test process the stage starts makes its git commits unsigned, whatever signing the user's own git configuration asks for, so scratch commits neither queue on one signing agent across the files run at once nor wait on a passphrase. The stage states its wall time and how many files it ran at once when it finishes. Out of scope: selecting tiers by changed path and the seeded-fault proof.
        for name, change in (("edits", edits), ("adds a file", adds), ("removes a file", removes)):
            with self.subTest(change=name):
                result = run(make_case(reads, change))
                self.assertEqual(2, result.testsRun)
                broken = result.failures + result.errors
                self.assertEqual(1, len(broken), [str(problem) for problem in broken])
                self.assertIn("test_1", str(broken[0][0]))
                self.assertIn("changed the copy of the design its class shares", broken[0][1])

    def test_a_copy_of_each_tests_own_is_not_shared(self):
        # SOL-BOARD-TIER-TESTS-RUN-SIDE-BY-SIDE.C1: Over a synthetic directory of test files, the stage runs each file in a process of its own from the serial run's working directory, with the serial run's environment and test selection, several at once, at most four unless asked for more; reports each file's result as it finishes; and exits non-zero naming every file that fails, a file that crashes or cannot be imported included. A directory holding no test file fails the stage rather than passing. A file that cannot run because a tool it needs is missing makes the stage report that tool by name on its error output in the form the round reads as a failure to look, once however many files report it, so the round stops naming the tool rather than reporting a finding. The stage gives the same verdict run side by side as run one file after another, and two synthetic files that each need the one installed CAD tool both pass when run side by side. The on-demand full run of the board tooling's tests runs its files the same way. A test file divided to shorten the stage keeps every test it held, each in exactly one of the files it is divided into: the stage runs the same tests before and after the division, and the tests that need the seeded-fault proof stay outside the stage and inside the on-demand full run, as before. Tests of one class that only read a copy of a proof design and the result of checking it share one copy and one check made for the class, and a test that changes its copy has a copy of its own, so a test that changed a shared copy would be caught and no test sees another's change. Every test process the stage starts makes its git commits unsigned, whatever signing the user's own git configuration asks for, so scratch commits neither queue on one signing agent across the files run at once nor wait on a passphrase. The stage states its wall time and how many files it ran at once when it finishes. Out of scope: selecting tiers by changed path and the seeded-fault proof.
        class Own(board_kicad_fixtures.Copy):
            def setUp(self):
                PREPARED.append(self)
                self.scratch = mock.Mock()

        Own.test_a = lambda self: None
        Own.test_b = lambda self: None
        run(Own)
        self.assertEqual(2, len(PREPARED))


if __name__ == "__main__":
    unittest.main()
