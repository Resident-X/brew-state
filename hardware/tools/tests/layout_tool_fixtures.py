"""Synthetic boards and runners for the layout tools' tests: the safe refill, the fill difference and the chain runner.

Every board here is written from text in a temporary directory. The tools that
run KiCad's scripting interface are run against the real interpreter, named by
the environment variable KICAD_PYTHON, and a test module that needs it stops
with a `CANNOT RUN` line naming that variable when it is not set. Nothing is
skipped when it is absent: a tool that cannot be exercised has not been shown to work.
"""

from __future__ import annotations

import io
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
import zlib
from typing import List, Tuple

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import board_check  # noqa: E402
import kicad_scripting  # noqa: E402

VARIABLE = kicad_scripting.VARIABLE


def require_kicad_python() -> str:
    """The KiCad interpreter named by KICAD_PYTHON, or stop the module naming the variable."""
    try:
        return kicad_scripting.interpreter()
    except board_check.CannotRun as error:
        print(f"CANNOT RUN | {board_check.clean(str(error))}", file=sys.stderr, flush=True)
        raise


def zone(name: str, net: str, layer: str, corners: List[Tuple[float, float]], clearance: str = "(clearance 0.5)",
         locked: str = "") -> str:
    """A copper zone as KiCad 10 writes it, filled by nothing yet; `clearance` is the whole text of its clearance, or empty."""
    points = " ".join(f"(xy {x} {y})" for x, y in corners)
    pads = f"(connect_pads {clearance}) " if clearance else ""
    uuid = "00000000-0000-4000-8000-" + format(zlib.crc32(name.encode()), "012d")
    return (f'(zone (net "{net}") {locked}(layer "{layer}") (uuid "{uuid}") (name "{name}") (hatch edge 0.5) {pads}'
            f'(min_thickness 0.25) (fill (thermal_gap 0.5) (thermal_bridge_width 0.5)) (polygon (pts {points})))')


def square(x: float, y: float, size: float) -> List[Tuple[float, float]]:
    return [(x, y), (x + size, y), (x + size, y + size), (x, y + size)]


def track(net: str, start, end, layer: str = "F.Cu", width: float = 0.25, number: int = 1) -> str:
    return (f'(segment (start {start[0]} {start[1]}) (end {end[0]} {end[1]}) (width {width}) (layer "{layer}") '
            f'(net "{net}") (uuid "00000000-0000-4000-8000-{number:012d}"))')


def board_text(items, properties: Tuple[Tuple[str, str], ...] = ()) -> str:
    """A KiCad 10 layout of `items`, carrying the board-level `properties` as (name, value)."""
    extra = "".join(f'\t(property "{name}" "{value}")\n' for name, value in properties)
    body = "".join(f"\t{item}\n" for item in items)
    return ('(kicad_pcb\n\t(version 20260206)\n\t(generator "pcbnew")\n\t(generator_version "10.0")\n'
            '\t(general (thickness 1.6))\n\t(paper "A4")\n'
            '\t(layers\n\t\t(0 "F.Cu" signal)\n\t\t(4 "In1.Cu" signal)\n\t\t(6 "In2.Cu" signal)\n'
            '\t\t(2 "B.Cu" signal)\n\t\t(25 "Edge.Cuts" user)\n\t)\n' + extra + body + ")\n")


class Work(unittest.TestCase):
    """A scratch folder per test, and runners that capture a tool's output and exit status."""

    def setUp(self):
        scratch = tempfile.TemporaryDirectory(prefix="layout-tool-test-")
        self.addCleanup(scratch.cleanup)
        self.work = scratch.name

    def path(self, name: str) -> str:
        return os.path.join(self.work, name)

    def write(self, name: str, text: str) -> str:
        path = self.path(name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
        return path

    def read(self, path: str) -> str:
        with open(path, encoding="utf-8", newline="") as handle:
            return handle.read()

    def run_tool(self, main, *argv):
        """(exit status, standard output lines) of a tool's main()."""
        out = io.StringIO()
        return main(list(argv), out=out), out.getvalue().splitlines()

    def run_json(self, main, *argv):
        """(exit status, the one JSON object printed) of a tool's main() run with --format json."""
        out = io.StringIO()
        status = main(list(argv) + ["--format", "json"], out=out)
        return status, json.loads(out.getvalue())

    def property_lines(self, text: str) -> List[str]:
        return re.findall(r'\n\t\(property "[A-Z_0-9]+" "[^"\n]*"\)', text)


def run_python(python: str, *argv: str, env=None) -> subprocess.CompletedProcess:
    """A command run with `python` and the environment given, its output captured."""
    return subprocess.run([python, *argv], capture_output=True, text=True, env=env, timeout=600)
