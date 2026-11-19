"""Synthetic boards and body tables for the footprint audit's tests, written from text in a temporary directory."""

from __future__ import annotations

import zlib
from typing import Iterable, List, Optional, Sequence, Tuple


def pad(number: str, x: float, y: float, angle: Optional[float] = None, size=(1.6, 1.0), kind: str = "thru_hole",
        shape: str = "rect", drill: Optional[str] = "0.8", layers: str = '"*.Cu" "*.Mask"') -> str:
    """A pad as KiCad writes it in a board: its angle is the angle it lies at on the board, the footprint's turn included."""
    at = f"(at {x} {y} {angle})" if angle else f"(at {x} {y})"
    hole = f" (drill {drill})" if drill else ""
    return f'(pad "{number}" {kind} {shape} {at} (size {size[0]} {size[1]}){hole} (layers {layers}))'


def courtyard(x0: float, y0: float, x1: float, y1: float, layer: str = "F.CrtYd") -> str:
    return f'(fp_rect (start {x0} {y0}) (end {x1} {y1}) (stroke (width 0.05) (type solid)) (fill no) (layer "{layer}"))'


def footprint(reference: str, name: str, x: float, y: float, angle: float = 0.0, layer: str = "F.Cu",
              items: Sequence[str] = ()) -> str:
    at = f"(at {x} {y} {angle})" if angle else f"(at {x} {y})"
    inner = "".join(f"\n\t\t{item}" for item in items)
    return (f'(footprint "{name}" (layer "{layer}") (uuid "00000000-0000-4000-8000-{zlib.crc32(reference.encode()):012d}") {at}'
            f'\n\t\t(property "Reference" "{reference}" (at 0 0) (layer "F.SilkS")){inner}\n\t)')


def board(footprints: Iterable[str]) -> str:
    body = "".join(f"\t{item}\n" for item in footprints)
    return ('(kicad_pcb\n\t(version 20260206)\n\t(generator "pcbnew")\n\t(generator_version "10.0")\n\t(general (thickness 1.6))\n'
            '\t(paper "A4")\n\t(layers\n\t\t(0 "F.Cu" signal)\n\t\t(2 "B.Cu" signal)\n\t\t(25 "Edge.Cuts" user)\n\t)\n' + body + ")\n")


def table(entries: dict) -> str:
    """A body table of `entries`: footprint name -> {"rects": [(name, x0, y0, x1, y1)], "zones": [...], "courtyard": bool}."""
    lines: List[str] = ["footprints:"]
    for name, entry in entries.items():
        lines.append(f'  "{name}":')
        lines.append("    kind: test part")
        lines.append("    source: a synthetic maker drawing")
        if entry.get("courtyard"):
            lines.append("    from: courtyard")
        for key, label in (("rects", "rects"), ("zones", "access_zones")):
            if entry.get(key):
                lines.append(f"    {label}:")
                for rect in entry[key]:
                    n, x0, y0, x1, y1 = rect
                    lines.append(f"      - {{name: {n}, x0: {x0}, y0: {y0}, x1: {x1}, y1: {y1}, height_mm: 5}}")
    return "\n".join(lines) + "\n"
