#!/usr/bin/env python3
"""The fill difference: the copper two boards' zone fills hold that the other's do not, per zone and layer.

A refill, a router import or a script's edit changes zone fills, and the board
check reports only what the result violates, not what moved. This command loads
two boards in KiCad's interpreter (named by KICAD_PYTHON, or by `--kicad-python`)
and, for each zone and each copper layer the zone is filled on, reports the area
of copper the first board has and the second does not, and the area the second
has and the first does not, in mm2. A zone is matched across the boards by its
name when it has one and by its uuid otherwise; zones sharing one name are taken
as one zone. A zone on one board only is wholly its board's copper.

KiCad's save adds noise to a fill: it writes the polygons it holds with their
corners rounded to its internal unit and in its own order, and a board loaded and
saved without a refill differs from the original by slivers of copper along the
edges. A difference at or below `--tolerance` (default 0.01 mm2) in both
directions is that noise and is not reported. Only filled copper of copper zones
is compared; differences outside zones are for the other checks.

    zone_fill_diff.py --first A.kicad_pcb --second B.kicad_pcb [--tolerance MM2] [--kicad-python PATH] [--format text|json]

Exit status: 0 when no zone and layer differs by more than the tolerance, 1 when
one does or a board cannot be read, 2 when the comparison cannot run, for example
because KICAD_PYTHON is unset.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import List, Optional

DEFAULT_TOLERANCE = 0.01


# --- The worker: runs in KiCad's interpreter, imports nothing but pcbnew -----------------


def worker(first: str, second: str) -> dict:
    import pcbnew

    def fills(path: str):
        """{(zone, layer name): SHAPE_POLY_SET} of every copper zone's filled copper on the board at `path`."""
        board = pcbnew.LoadBoard(path)
        found = {}
        for zone in board.Zones():
            if zone.GetIsRuleArea():
                continue
            name = zone.GetZoneName() or zone.m_Uuid.AsString()
            for layer in zone.GetLayerSet().Seq():
                if not pcbnew.IsCopperLayer(layer):
                    continue
                key = (name, board.GetLayerName(layer))
                polys = pcbnew.SHAPE_POLY_SET(zone.GetFilledPolysList(layer))
                if key in found:
                    found[key].BooleanAdd(polys)
                else:
                    found[key] = polys
        return found

    try:
        a, b = fills(first), fills(second)
    except Exception as error:  # noqa: BLE001 - whatever KiCad raises is the board's reason
        return {"error": f"KiCad cannot load the boards ({error})"}
    empty = pcbnew.SHAPE_POLY_SET
    rows = []
    for key in sorted(set(a) | set(b)):
        one, two = a.get(key, empty()), b.get(key, empty())
        only_first, only_second = pcbnew.SHAPE_POLY_SET(one), pcbnew.SHAPE_POLY_SET(two)
        only_first.BooleanSubtract(two)
        only_second.BooleanSubtract(one)
        rows.append({"zone": key[0], "layer": key[1], "in_first": key in a, "in_second": key in b,
                     "only_first": only_first.Area() / 1e12, "only_second": only_second.Area() / 1e12})
    return {"rows": rows}


if __name__ == "__main__" and sys.argv[1:2] == ["--worker"]:
    print(json.dumps(worker(sys.argv[2], sys.argv[3])))
    sys.exit(0)


sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import kicad_scripting  # noqa: E402
import zone_refill  # noqa: E402
from board_check import CannotRun  # noqa: E402
from board_geometry import Unreadable  # noqa: E402


def compare(first: str, second: str, tolerance: float, kicad_python: Optional[str], out, as_json: bool) -> int:
    findings: List[dict] = []
    summary = {"first": first, "second": second, "tolerance_mm2": tolerance}

    def done(result: str, detail: str, status: int, rows: Optional[list] = None) -> int:
        kicad_scripting.emit(dict(summary, result=result, detail=detail, findings=findings, differences=rows or []), out, as_json)
        return status

    if tolerance < 0:
        findings.append({"finding": "REFUSED", "item": "--tolerance", "detail": f"{tolerance} is below zero; give an area of 0 mm2 or more"})
        return done("REFUSED", "nothing was compared", 1)
    python = kicad_scripting.interpreter(kicad_python)
    for path in (first, second):
        try:
            zone_refill.read_text(path)
        except Unreadable as error:
            findings.append({"finding": "UNREADABLE", "item": path, "detail": str(error)})
    if findings:
        return done("REFUSED", "a board cannot be read, so nothing was compared", 1)
    reply = kicad_scripting.run_worker(python, os.path.abspath(__file__), [os.path.abspath(first), os.path.abspath(second)])
    if "error" in reply:
        findings.append({"finding": "UNREADABLE", "item": f"{first} {second}", "detail": reply["error"]})
        return done("REFUSED", "KiCad cannot load the boards, so nothing was compared", 1)
    rows = []
    for row in reply["rows"]:
        if row["only_first"] <= tolerance and row["only_second"] <= tolerance:
            continue
        where = ("only on the first board" if not row["in_second"] else "only on the second board" if not row["in_first"]
                 else "on both boards")
        findings.append({"finding": "DIFFERENT", "item": f"zone {row['zone']} on {row['layer']}",
                         "detail": f"{where}: {row['only_first']:.4f} mm2 of copper in the first board and not the second, "
                                   f"{row['only_second']:.4f} mm2 in the second and not the first"})
        rows.append(row)
    if rows:
        return done("DIFFERENT", f"{len(rows)} zone layer{'s' if len(rows) != 1 else ''} differ by more than {tolerance} mm2 "
                                 f"of {len(reply['rows'])} compared", 1, rows)
    return done("SAME", f"no zone differs by more than {tolerance} mm2 on any of {len(reply['rows'])} zone layers compared", 0)


def main(argv: Optional[List[str]] = None, out=sys.stdout) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--first", required=True, help="the first layout file (.kicad_pcb)")
    parser.add_argument("--second", required=True, help="the second layout file (.kicad_pcb)")
    parser.add_argument("--tolerance", type=float, default=DEFAULT_TOLERANCE,
                        help="the area in mm2 up to which a difference is the noise of KiCad's save (default: %(default)s)")
    parser.add_argument("--kicad-python", default=None,
                        help=f"KiCad's bundled Python (default: the environment variable {kicad_scripting.VARIABLE})")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)
    try:
        return compare(args.first, args.second, args.tolerance, args.kicad_python, out, args.format == "json")
    except CannotRun as error:
        return kicad_scripting.cannot_run(error, out, args.format == "json")


if __name__ == "__main__":
    sys.exit(main())
