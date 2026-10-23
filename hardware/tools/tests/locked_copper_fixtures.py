"""The locked-copper check, driven on synthetic boards against the real kicad-cli.

Each board here is written from text in a temporary directory: a few tracks,
an arc, a via and a zone on nets in critical classes, and copper on a net in
none. The check is run as its command runs it, through main(), so the class
membership it acts on is KiCad's own answer for the board and its project file.
Nothing is skipped when KiCad is absent: a check that cannot be exercised has
not been shown to work.
"""

from __future__ import annotations

import copy
import io
import json
import os
import sys
import tempfile
import unittest

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import board_fixtures  # noqa: E402
import locked_copper  # noqa: E402
import sexpr  # noqa: E402


REPO = os.path.dirname(os.path.dirname(TOOLS))


KICAD_CLI = os.environ.get("KICAD_CLI") or "kicad-cli"


PROOF_PROJECT = os.path.join(REPO, "hardware", "proof", "gate-proof", "gate-proof.kicad_pro")


def setUpModule():
    board_fixtures.require_tools(KICAD_CLI)


#: The base board's items, by name, as KiCad 10 writes them. /PWR is in Power by
#: the project's assignment, /GND_A and /GND_B in Ground by its pattern, /LV in
#: no critical class. /GND_B reaches the board only on a pad, so it is a critical
#: net with no copper when recorded, as a net the router has yet to route is.
ITEMS = {
    "track": '(segment (start 0 0) (end 5 0) (width 0.5) (locked yes) (layer "F.Cu") (net "/PWR") '
             '(uuid "00000000-0000-4000-8000-000000000001"))',
    "arc": '(arc (start 0 10) (mid 2 12) (end 4 10) (width 0.5) (locked yes) (layer "F.Cu") (net "/GND_A") '
           '(uuid "00000000-0000-4000-8000-000000000002"))',
    "via": '(via (at 20 20) (size 0.8) (drill 0.4) (layers "F.Cu" "B.Cu") (locked yes) (net "/GND_A") '
           '(uuid "00000000-0000-4000-8000-000000000003"))',
    "zone": '(zone (net "/PWR") (locked yes) (layer "B.Cu") (uuid "00000000-0000-4000-8000-000000000004") '
            '(hatch edge 0.5) (connect_pads (clearance 0.5)) (min_thickness 0.25) '
            '(fill (thermal_gap 0.5) (thermal_bridge_width 0.5)) '
            '(polygon (pts (xy 30 30) (xy 40 30) (xy 40 40) (xy 30 40))))',
    "lv": '(segment (start 60 0) (end 65 0) (width 0.25) (layer "F.Cu") (net "/LV") '
          '(uuid "00000000-0000-4000-8000-000000000006"))',
    "pad": '(footprint "test:Pad" (layer "F.Cu") (uuid "00000000-0000-4000-8000-0000000000f0") (at 25 25) '
           '(property "Reference" "J1" (at 0 -2 0) (layer "F.SilkS") (uuid "00000000-0000-4000-8000-0000000000f1") '
           '(effects (font (size 1 1) (thickness 0.15)))) '
           '(pad "1" thru_hole circle (at 0 0) (size 1.7 1.7) (drill 1) (layers "*.Cu" "*.Mask") (net "/GND_B") '
           '(uuid "00000000-0000-4000-8000-0000000000f2")))',
}


def layout(items, extra: str = "") -> str:
    body = "".join(f"\t{item}\n" for item in items)
    return ('(kicad_pcb\n\t(version 20260206)\n\t(generator "pcbnew")\n\t(generator_version "10.0")\n'
            '\t(general (thickness 1.6))\n\t(paper "A4")\n'
            '\t(layers\n\t\t(0 "F.Cu" signal)\n\t\t(4 "In1.Cu" signal)\n\t\t(6 "In2.Cu" signal)\n'
            '\t\t(2 "B.Cu" signal)\n\t\t(25 "Edge.Cuts" user)\n\t)\n'
            + extra + body + ")\n")


def project(assignments=None, patterns=None, classes=("Power", "Ground"), mains="none") -> str:
    """A project file defining `classes` beside Default and declaring MAINS as `mains` (None: undeclared)."""
    with open(PROOF_PROJECT, encoding="utf-8") as handle:
        data = json.load(handle)
    settings = data["net_settings"]
    default, template = settings["classes"][0], settings["classes"][1]
    settings["classes"] = [default] + [dict(copy.deepcopy(template), name=name, priority=index)
                                       for index, name in enumerate(classes)]
    settings["netclass_assignments"] = assignments
    settings["netclass_patterns"] = patterns or []
    data["text_variables"] = {} if mains is None else {"MAINS": mains}
    return json.dumps(data, indent=1)


BASE_PROJECT = project({"/PWR": "Power"}, [{"netclass": "Ground", "pattern": "/GND_*"}])


class Board(unittest.TestCase):
    """A board and its project in their own folder, and a working folder outside it for the record."""

    def setUp(self):
        scratch = tempfile.TemporaryDirectory(prefix="locked-copper-test-")
        self.addCleanup(scratch.cleanup)
        self.folder = os.path.join(scratch.name, "design")
        self.work = os.path.join(scratch.name, "work")
        os.makedirs(self.folder)
        os.makedirs(self.work)
        self.board = os.path.join(self.folder, "b.kicad_pcb")
        self.project = os.path.join(self.folder, "b.kicad_pro")
        self.record_path = os.path.join(self.work, "b.record.json")
        self.write(layout(ITEMS.values()), BASE_PROJECT)

    def write(self, board_text: str, project_text: str = None):
        with open(self.board, "w", encoding="utf-8") as handle:
            handle.write(board_text)
        if project_text is not None:
            with open(self.project, "w", encoding="utf-8") as handle:
                handle.write(project_text)

    def run_check(self, *argv):
        out = io.StringIO()
        status = locked_copper.main(["--kicad-cli", KICAD_CLI, *argv], out=out)
        return status, out.getvalue().splitlines()

    def record(self, *classes, record_path=None):
        args = ["record", "--board", self.board, "--project", self.project, "--record", record_path or self.record_path]
        for name in classes or ("Power", "Ground"):
            args += ["--class", name]
        return self.run_check(*args)

    def on_classes(self, command, *classes):
        """Run `command` (confirm or lock) on the board with `classes`, Power and Ground by default."""
        args = [command, "--board", self.board, "--project", self.project]
        for name in classes or ("Power", "Ground"):
            args += ["--class", name]
        return self.run_check(*args)

    def board_text(self):
        with open(self.board, encoding="utf-8", newline="") as handle:
            return handle.read()

    def compare(self, record_path=None):
        return self.run_check("compare", "--board", self.board, "--project", self.project,
                              "--record", record_path or self.record_path)

    def recorded(self):
        status, lines = self.record()
        self.assertEqual(status, 0, lines)
        return lines

    def findings(self, lines, kind):
        return [line.split(" | ") for line in lines if line.startswith(kind + " | ")]


#: The base board's items with no lock on any of them.
UNLOCKED_ITEMS = {name: text.replace(" (locked yes)", "") for name, text in ITEMS.items()}


#: A track on a mains net, for the boards that declare mains.
AC_TRACK = ('(segment (start 0 40) (end 5 40) (width 0.5) (layer "F.Cu") (net "/AC") '
            '(uuid "00000000-0000-4000-8000-000000000007"))')


#: A custom rules file KiCad loads.
RULES = ('(version 1)\n(rule "Power width"\n\t(condition "A.hasNetclass(\'Power\')")\n'
         '\t(constraint track_width (min 0.4mm)))\n')


def without_locks(tree):
    """A parsed layout with every (locked ...) child taken out of its tracks, arcs, vias and zones."""
    return [[part for part in node if sexpr.head(part) != "locked"] if sexpr.head(node) in locked_copper.KIND_OF
            else node for node in tree]


if __name__ == "__main__":
    unittest.main()
