#!/usr/bin/env python3
"""Which host runs state the steam casting bound, observed on the built executable.

The runs that draw steam state the bound before they drive the machine; the
plain exercise and the protection-margin record draw none and state none. The
first is asserted beside the second so the absence is a finding about those two
runs and not about a search for a line that nothing prints.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest

FIRMWARE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PARAMS = os.path.join(FIRMWARE, "params")
PROGRAM = os.path.join(FIRMWARE, ".pio", "build", "native", "program")

#: The finding name a run states the bound under, in both its text and JSON lines.
BOUND_FINDING = "steam-casting-ceiling"

#: What a margin record states, so a run that printed nothing is not read as silent.
MARGIN_FINDING = "margin-corner"


def pio() -> str:
    """The PlatformIO command, as the Taskfile finds it: the variable, the default install, the path."""
    for candidate in (
        os.environ.get("PIO"),
        os.path.expanduser("~/.platformio/penv/bin/pio"),
        shutil.which("pio"),
    ):
        if candidate and os.path.exists(candidate):
            return candidate
    raise AssertionError("PlatformIO is not installed where the Taskfile looks for it")


def build_the_host_executable() -> None:
    done = subprocess.run(
        [pio(), "run", "-e", "native"], cwd=FIRMWARE, capture_output=True, text=True, check=False
    )
    if done.returncode != 0:
        raise AssertionError("the host executable did not build:\n" + done.stdout + done.stderr)


def run(*arguments: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [PROGRAM, os.path.join(PARAMS, "thermoblock.params"), os.path.join(PARAMS, "thermoblock.limits"),
         *arguments],
        capture_output=True, text=True, check=False, timeout=120,
    )


class HostRunBounds(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        build_the_host_executable()

    # SOL-PLANT-STEAM-FLASH-GENERATOR.C3: Each host run that draws steam reports the bound in both text and JSON form.
    def test_the_plain_exercise_draws_no_steam_and_states_no_bound(self) -> None:
        done = run()
        self.assertEqual(0, done.returncode, done.stderr)
        self.assertIn("host exercise: control path reconstructs", done.stdout)
        self.assertNotIn(BOUND_FINDING, done.stdout)
        self.assertNotIn(BOUND_FINDING, done.stderr)

    # SOL-PLANT-STEAM-FLASH-GENERATOR.C3: Each host run that draws steam reports the bound in both text and JSON form.
    def test_the_protection_margin_record_draws_no_steam_and_states_no_bound(self) -> None:
        done = run("--protection-margin-record", os.path.join(PARAMS, "steam_control.declaration"))
        self.assertEqual(0, done.returncode, done.stderr)
        self.assertIn(MARGIN_FINDING, done.stdout)
        self.assertNotIn(BOUND_FINDING, done.stdout)
        self.assertNotIn(BOUND_FINDING, done.stderr)

    # SOL-PLANT-STEAM-FLASH-GENERATOR.C3: Each host run that draws steam reports the bound in both text and JSON form.
    def test_the_run_that_draws_steam_states_the_bound_in_both_forms(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            course = os.path.join(root, "course")
            with open(course, "w", encoding="utf-8") as handle:
                handle.write("10 1000\n" * 20)
            done = run("--steam-draw", os.path.join(PARAMS, "steam_control.declaration"), "137", course)
        self.assertEqual(0, done.returncode, done.stderr)
        lines = [line for line in done.stdout.splitlines() if BOUND_FINDING in line]
        self.assertEqual(2, len(lines), "the bound is stated once as text and once as JSON")
        self.assertEqual(1, len([line for line in lines if line.startswith("HOST-JSON {")]))
        self.assertEqual(1, len([line for line in lines if line.startswith("HOST ")]))


if __name__ == "__main__":
    unittest.main()
