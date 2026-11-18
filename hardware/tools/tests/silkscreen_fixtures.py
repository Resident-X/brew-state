"""Synthetic boards and runners for the silkscreen command's tests.

Every board here is written from text in a temporary directory, in the form
KiCad 10 writes (tab-indented, the way a board saved by KiCad reads), and loaded by
the real KiCad interpreter named by KICAD_PYTHON. The packages the command needs
(numpy, shapely and Pillow) are imported by the command itself; a test module that
needs them stops with a `CANNOT RUN` line naming the one that is missing.
"""

from __future__ import annotations

import importlib
import io
import json
import os
import sys
import tempfile
import unittest
import zlib
from typing import Dict, List, Optional, Sequence, Tuple

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import board_check  # noqa: E402
import kicad_scripting  # noqa: E402
import layout_tool_fixtures  # noqa: E402

PACKAGES = (("numpy", "numpy"), ("shapely", "shapely"), ("PIL", "Pillow"))


def require_tools() -> str:
    """KiCad's interpreter and the three packages, or stop the module naming what is missing."""
    layout_tool_fixtures.require_kicad_python()
    for module, package in PACKAGES:
        try:
            importlib.import_module(module)
        except ImportError:
            print(f"CANNOT RUN | the Python package {package} is not installed; the silkscreen command needs numpy, "
                  f"shapely and Pillow (hardware/README.md)", file=sys.stderr, flush=True)
            raise
    return kicad_scripting.interpreter()


def _uuid(*parts) -> str:
    text = "|".join(str(part) for part in parts)
    return "00000000-0000-4000-8000-%012d" % (zlib.crc32(text.encode()) % 10 ** 12)


def pad(number, x, y, w=0.9, h=0.9, net="", through=False, drill=0.6) -> dict:
    return {"number": str(number), "x": x, "y": y, "w": w, "h": h, "net": net, "through": through, "drill": drill}


def part(ref: str, lib: str, x: float, y: float, rot: float = 0, side: str = "F", value: str = "", pads=None,
         body: Tuple[float, float] = (2.0, 1.0), rating: str = "", silk_body: bool = True) -> dict:
    return {"ref": ref, "lib": lib, "x": x, "y": y, "rot": rot, "side": side, "value": value or ref,
            "pads": list(pads) if pads is not None else [pad(1, -body[0] / 2 + 0.4, 0, 0.8, 0.8), pad(2, body[0] / 2 - 0.4, 0, 0.8, 0.8)],
            "body": body, "rating": rating, "silk_body": silk_body}


def resistor(ref: str, x: float, y: float, rot: float = 0, side: str = "F", value: str = "10k") -> dict:
    return part(ref, "Lib:R_0603", x, y, rot, side, value, body=(3.6, 1.2))


def _footprint(p: dict) -> str:
    side, ref = p["side"], p["ref"]
    cu, mask, silk, court = (("F.Cu", "F.Mask", "F.SilkS", "F.CrtYd") if side == "F"
                             else ("B.Cu", "B.Mask", "B.SilkS", "B.CrtYd"))
    mirror = "\t\t\t\t(justify mirror)\n" if side == "B" else ""
    effects = (f"\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1 1)\n\t\t\t\t\t(thickness 0.15)\n\t\t\t\t)\n{mirror}\t\t\t)\n")
    w, h = p["body"]
    lines = [f'\t(footprint "{p["lib"]}"\n\t\t(layer "{cu}")\n\t\t(uuid "{_uuid("fp", ref)}")\n'
             f'\t\t(at {p["x"]} {p["y"]} {p["rot"]})\n'
             f'\t\t(property "Reference" "{ref}"\n\t\t\t(at 0 {-h / 2 - 1.5} 0)\n\t\t\t(unlocked yes)\n\t\t\t(layer "{silk}")\n'
             f'\t\t\t(uuid "{_uuid("ref", ref)}")\n{effects}\t\t)\n'
             f'\t\t(property "Value" "{p["value"]}"\n\t\t\t(at 0 {h / 2 + 1.5} 0)\n\t\t\t(layer "{silk.replace("SilkS", "Fab")}")\n'
             f'\t\t\t(uuid "{_uuid("val", ref)}")\n{effects}\t\t)\n']
    if p["rating"]:
        lines.append(f'\t\t(property "Rating" "{p["rating"]}"\n\t\t\t(at 0 0 0)\n\t\t\t(layer "{silk.replace("SilkS", "Fab")}")\n'
                     f'\t\t\t(hide yes)\n\t\t\t(uuid "{_uuid("rating", ref)}")\n{effects}\t\t)\n')
    if p["silk_body"]:
        inner = min([abs(pd["x"]) - pd["w"] / 2 for pd in p["pads"]] or [w / 2])
        hw = min(w / 2, inner - 0.35)
        if hw >= 0.1:
            lines.append(f'\t\t(fp_rect\n\t\t\t(start {-hw} {-h / 2})\n\t\t\t(end {hw} {h / 2})\n\t\t\t(stroke\n\t\t\t\t(width 0.12)\n'
                     f'\t\t\t\t(type default)\n\t\t\t)\n\t\t\t(fill no)\n\t\t\t(layer "{silk}")\n\t\t\t(uuid "{_uuid("body", ref)}")\n\t\t)\n')
    lines.append(f'\t\t(fp_rect\n\t\t\t(start {-w / 2 - 0.25} {-h / 2 - 0.25})\n\t\t\t(end {w / 2 + 0.25} {h / 2 + 0.25})\n\t\t\t(stroke\n'
                 f'\t\t\t\t(width 0.05)\n\t\t\t\t(type default)\n\t\t\t)\n\t\t\t(fill no)\n\t\t\t(layer "{court}")\n\t\t\t(uuid "{_uuid("court", ref)}")\n\t\t)\n')
    for pd in p["pads"]:
        net = f'\t\t\t(net "{pd["net"]}")\n' if pd["net"] else ""
        if pd["through"]:
            lines.append(f'\t\t(pad "{pd["number"]}" thru_hole circle\n\t\t\t(at {pd["x"]} {pd["y"]})\n\t\t\t(size {pd["w"]} {pd["h"]})\n'
                         f'\t\t\t(drill {pd["drill"]})\n\t\t\t(layers "*.Cu" "*.Mask")\n{net}\t\t\t(uuid "{_uuid("pad", ref, pd["number"])}")\n\t\t)\n')
        else:
            lines.append(f'\t\t(pad "{pd["number"]}" smd rect\n\t\t\t(at {pd["x"]} {pd["y"]})\n\t\t\t(size {pd["w"]} {pd["h"]})\n'
                         f'\t\t\t(layers "{cu}" "{mask}")\n{net}\t\t\t(uuid "{_uuid("pad", ref, pd["number"])}")\n\t\t)\n')
    lines.append("\t)\n")
    return "".join(lines)


def outline(x0: float, y0: float, x1: float, y1: float) -> str:
    return (f'\t(gr_rect\n\t\t(start {x0} {y0})\n\t\t(end {x1} {y1})\n\t\t(stroke\n\t\t\t(width 0.1)\n\t\t\t(type default)\n\t\t)\n'
            f'\t\t(fill no)\n\t\t(layer "Edge.Cuts")\n\t\t(uuid "{_uuid("outline", x0, y0, x1, y1)}")\n\t)\n')


def rule_area(name: str, x0: float, y0: float, x1: float, y1: float) -> str:
    """A rule area (keepout-free region marker) named `name`, as the main board's mains region is."""
    pts = f"(xy {x0} {y0}) (xy {x1} {y0}) (xy {x1} {y1}) (xy {x0} {y1})"
    return (f'\t(zone\n\t\t(net 0)\n\t\t(net_name "")\n\t\t(layers "F.Cu" "B.Cu")\n\t\t(uuid "{_uuid("rule", name)}")\n\t\t(name "{name}")\n'
            f'\t\t(hatch edge 0.5)\n\t\t(connect_pads\n\t\t\t(clearance 0)\n\t\t)\n\t\t(min_thickness 0.25)\n\t\t(filled_areas_thickness no)\n'
            f'\t\t(keepout\n\t\t\t(tracks allowed)\n\t\t\t(vias allowed)\n\t\t\t(pads allowed)\n\t\t\t(copperpour allowed)\n\t\t\t(footprints allowed)\n\t\t)\n'
            f'\t\t(placement\n\t\t\t(enabled no)\n\t\t\t(sheetname "")\n\t\t)\n'
            f'\t\t(polygon\n\t\t\t(pts\n\t\t\t\t{pts}\n\t\t\t)\n\t\t)\n\t)\n')


def copper_zone(name: str, net: str, x0: float, y0: float, x1: float, y1: float, layer: str = "F.Cu") -> str:
    pts = f"(xy {x0} {y0}) (xy {x1} {y0}) (xy {x1} {y1}) (xy {x0} {y1})"
    return (f'\t(zone\n\t\t(net "{net}")\n\t\t(layer "{layer}")\n\t\t(uuid "{_uuid("zone", name)}")\n\t\t(name "{name}")\n\t\t(hatch edge 0.5)\n'
            f'\t\t(connect_pads\n\t\t\t(clearance 0.5)\n\t\t)\n\t\t(min_thickness 0.25)\n'
            f'\t\t(fill\n\t\t\t(thermal_gap 0.5)\n\t\t\t(thermal_bridge_width 0.5)\n\t\t)\n'
            f'\t\t(polygon\n\t\t\t(pts\n\t\t\t\t{pts}\n\t\t\t)\n\t\t)\n\t)\n')


def segment(net: str, x0: float, y0: float, x1: float, y1: float, layer: str = "F.Cu", width: float = 0.25) -> str:
    return (f'\t(segment\n\t\t(start {x0} {y0})\n\t\t(end {x1} {y1})\n\t\t(width {width})\n\t\t(layer "{layer}")\n\t\t(net "{net}")\n'
            f'\t\t(uuid "{_uuid("seg", net, x0, y0, x1, y1)}")\n\t)\n')


def via(net: str, x: float, y: float, size: float = 0.8, drill: float = 0.4) -> str:
    return (f'\t(via\n\t\t(at {x} {y})\n\t\t(size {size})\n\t\t(drill {drill})\n\t\t(layers "F.Cu" "B.Cu")\n\t\t(net "{net}")\n'
            f'\t\t(uuid "{_uuid("via", net, x, y)}")\n\t)\n')


def free_text(text: str, x: float, y: float, layer: str = "F.SilkS", size: float = 1.0) -> str:
    mirror = "\t\t\t(justify mirror)\n" if layer.startswith("B") else ""
    return (f'\t(gr_text "{text}"\n\t\t(at {x} {y} 0)\n\t\t(layer "{layer}")\n\t\t(uuid "{_uuid("text", text, x, y)}")\n\t\t(effects\n'
            f'\t\t\t(font\n\t\t\t\t(size {size} {size})\n\t\t\t\t(thickness 0.15)\n\t\t\t)\n{mirror}\t\t)\n\t)\n')


HEADER = ('(kicad_pcb\n\t(version 20260206)\n\t(generator "pcbnew")\n\t(generator_version "10.0")\n\t(general\n\t\t(thickness 1.6)\n'
          '\t\t(legacy_teardrops no)\n\t)\n\t(paper "A4")\n\t(layers\n\t\t(0 "F.Cu" signal)\n\t\t(2 "B.Cu" signal)\n'
          '\t\t(13 "F.Paste" user)\n\t\t(15 "B.Paste" user)\n\t\t(5 "F.SilkS" user "F.Silkscreen")\n\t\t(7 "B.SilkS" user "B.Silkscreen")\n'
          '\t\t(1 "F.Mask" user)\n\t\t(3 "B.Mask" user)\n\t\t(25 "Edge.Cuts" user)\n\t\t(31 "F.CrtYd" user "F.Courtyard")\n'
          '\t\t(29 "B.CrtYd" user "B.Courtyard")\n\t\t(35 "F.Fab" user)\n\t\t(33 "B.Fab" user)\n\t)\n\t(setup\n'
          '\t\t(pad_to_mask_clearance 0.05)\n\t)\n')


def board_text(parts: Sequence[dict] = (), extra: Sequence[str] = (), box: Tuple[float, float, float, float] = (0, 0, 40, 30)) -> str:
    """A board of `parts` and the `extra` item texts, inside the Edge.Cuts rectangle `box`."""
    return HEADER + outline(*box) + "".join(extra) + "".join(_footprint(p) for p in parts) + ")\n"


def small_board() -> str:
    """A board of a few parts: a row of resistors, a fuse holder, a connector, an IC and a test point, with a mains area."""
    parts = [
        resistor("R1", 8, 8), resistor("R2", 8, 12), resistor("R3", 14, 8, 90),
        part("F1", "Fuseholder_5x20", 30, 8, value="10A_T_250V", body=(6, 3), rating="slow-blow 250V AC"),
        part("J1", "Conn_2pin", 30, 22, value="POWER_IN", body=(5, 4),
             pads=[pad(1, -1.5, 0, 1.6, 1.6, "VIN", True, 1.0), pad(2, 1.5, 0, 1.6, 1.6, "GND", True, 1.0)]),
        part("U1", "SOIC-4", 14, 22, value="MCU", body=(4, 3),
             pads=[pad(1, -1.5, -1, 1.0, 0.6, "A"), pad(2, -1.5, 1, 1.0, 0.6, "B"), pad(3, 1.5, 1, 1.0, 0.6, "C"), pad(4, 1.5, -1, 1.0, 0.6, "D")]),
        part("TP1", "TestPoint_Pad", 22, 15, value="TP", body=(1.5, 1.5), pads=[pad(1, 0, 0, 1.5, 1.5, "/Net_A")], silk_body=False),
    ]
    extra = [rule_area("mains", 26, 2, 38, 28), segment("VIN", 10, 20, 20, 20), via("GND", 20, 10),
             copper_zone("pour", "GND", 2, 26, 12, 29)]
    return board_text(parts, extra)


class Work(unittest.TestCase):
    """A scratch folder per test, and runners that capture a tool's output and exit status."""

    def setUp(self):
        scratch = tempfile.TemporaryDirectory(prefix="silkscreen-test-")
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
        """(exit status, the one JSON object printed) of main() run with --format json."""
        out = io.StringIO()
        status = main(list(argv) + ["--format", "json"], out=out)
        return status, json.loads(out.getvalue())
