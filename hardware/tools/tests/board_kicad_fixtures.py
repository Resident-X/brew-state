"""What the board check's KiCad tests share: the tool check, the seeded-fault proof's pooled outcomes, a copy of the proof design and the exclusion of what needs the proof.

The check's KiCad tests are divided by topic into the files
test_board_check_kicad_*.py, each run in a process of its own, and every one of
them takes its setup from here, so the division changes where a test lives and
nothing about it.

Every seeded fault is proved once per file that asks for it and shared inside
that file, since each costs two KiCad runs; a test then asks of those outcomes
what each criterion needs.

What needs the proof is exactly what derives from Proved, and the one test that
runs the whole proof as the shipped command does. Run with the variable named
by WITHOUT_PROOF set, each file loads everything else and nothing of those:
that is the part a build round and the nightly run, the proof itself staying on
demand. A test that needs the pooled proof therefore derives from Proved, and a
test that does not must not, or it drops out of the round without anyone
choosing that.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)

import board_fixtures  # noqa: E402
import board_prove  # noqa: E402

KICAD_CLI = os.environ.get("KICAD_CLI") or "kicad-cli"

#: The environment variable that, set to anything, leaves out every test that needs the seeded-fault proof.
WITHOUT_PROOF = "BOARD_TESTS_WITHOUT_PROOF"

_OUTCOMES = {}


def setUpModule():
    board_fixtures.require_tools(KICAD_CLI)


class _Outcomes:
    """The seeded faults' outcomes by name -> (caught, evidence), each proved the first time it is asked for."""

    def __contains__(self, name):
        return any(fault[0] == name for fault in board_prove.FAULTS)

    def __getitem__(self, name):
        if name not in _OUTCOMES:
            fault = next((fault for fault in board_prove.FAULTS if fault[0] == name), None)
            if fault is None:
                raise KeyError(name)
            _OUTCOMES[name] = board_prove.prove(fault, KICAD_CLI)
        return _OUTCOMES[name]


def outcomes():
    """Every seeded fault's outcome, proved when asked for and then kept: name -> (caught, evidence)."""
    return _Outcomes()


class Proved(unittest.TestCase):
    """A test that needs the seeded-fault proof: it asks the pooled outcomes, or runs the proof itself."""

    def assertCaught(self, *names: str):
        found = outcomes()
        for name in names:
            with self.subTest(fault=name):
                self.assertIn(name, found, "no such seeded fault")
                caught, evidence = found[name]
                self.assertTrue(caught, evidence)


def tests_of(suite):
    """Every test case in a suite, however deeply the suites nest."""
    for test in suite:
        if isinstance(test, unittest.TestSuite):
            yield from tests_of(test)
        else:
            yield test


def load_tests(loader, tests, pattern):
    """Every test of the module, or all but those needing the proof when WITHOUT_PROOF is set."""
    if not os.environ.get(WITHOUT_PROOF):
        return tests
    return unittest.TestSuite(test for test in tests_of(tests) if not isinstance(test, Proved))


class Copy(unittest.TestCase):
    """A fresh copy of the proof design in its own git work tree."""

    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory(prefix="board-test-")
        self.addCleanup(self.scratch.cleanup)
        self.seed = board_prove.prepare(self.scratch.name)

    def check(self):
        status, lines, stderr = board_prove.check(self.seed, KICAD_CLI)
        self.assertNotEqual(status, 2, stderr)
        return status, lines

    def violations(self, lines):
        return [line.split(" | ") for line in lines if line.startswith("VIOLATION | ")]

    def drc(self, *flags):
        """KiCad's own DRC report on the copy as it stands, without the check in between."""
        out = os.path.join(self.scratch.name, "drc.json")
        subprocess.run([KICAD_CLI, "pcb", "drc", "--format", "json", "--severity-all", *flags, "-o", out,
                        board_prove.NAME + ".kicad_pcb"], cwd=self.seed.design, check=True, capture_output=True)
        with open(out, encoding="utf-8") as handle:
            return json.load(handle)
