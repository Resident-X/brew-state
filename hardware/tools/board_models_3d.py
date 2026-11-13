#!/usr/bin/env python3
"""Shared reading of a board file for the 3D picture commands (fetch_3d_models.py, render_board_3d.py).

Pictures of a board are for looking at, so the board's own files carry no vendor model: a footprint that
the board does not give a model is given one only in a scratch copy, from a git-ignored cache folder.
This module holds what both commands share: the footprint blocks of a board file, the part number each
footprint carries, which footprints are drawn without a body, and the line that gives a footprint a model.
"""

from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import sexpr  # noqa: E402

# A footprint of one of these kinds has no physical body to draw.
NO_BODY_MARKS = ("TestPoint", "Fiducial", "MountingHole", "NetTie")


@dataclass
class Pad:
    name: str
    kind: str
    x: float
    y: float
    w: float
    h: float
    rot: float
    drill: float = 0.0


@dataclass
class Footprint:
    lib_id: str
    reference: str
    layer: str
    lcsc: str
    has_model: bool
    start: int
    end: int
    pads: List[Pad] = field(default_factory=list)
    courtyard: Optional[Tuple[float, float, float, float]] = None
    x: float = 0.0
    y: float = 0.0
    rot: float = 0.0

    @property
    def short_name(self) -> str:
        return self.lib_id.split(":", 1)[-1]

    @property
    def has_body(self) -> bool:
        return not any(mark in self.lib_id for mark in NO_BODY_MARKS) and bool(self.pads)


def _num(node) -> float:
    return float(node)


def footprint_spans(text: str) -> List[Tuple[int, int]]:
    """(start, end) offsets of every top-level `(footprint ...)` block of a board file, end just past its ')'."""
    spans = []
    for match in re.finditer(r"\n\t\(footprint ", text):
        start = match.start() + 2
        depth = 0
        i = start
        in_string = False
        while i < len(text):
            c = text[i]
            if in_string:
                if c == "\\":
                    i += 1
                elif c == '"':
                    in_string = False
            elif c == '"':
                in_string = True
            elif c == "(":
                depth += 1
            elif c == ")":
                depth -= 1
                if depth == 0:
                    spans.append((start, i + 1))
                    break
            i += 1
    return spans


def read_footprints(text: str) -> List[Footprint]:
    result = []
    for start, end in footprint_spans(text):
        node = sexpr.parse(text[start:end])[0]
        lib_id = str(node[1])
        layer = ""
        lcsc = ""
        reference = ""
        has_model = False
        pads: List[Pad] = []
        crt: List[float] = []
        x = y = rot = 0.0
        for item in node[2:]:
            key = sexpr.head(item)
            if key == "layer":
                layer = str(item[1])
            elif key == "at":
                x, y = _num(item[1]), _num(item[2])
                rot = _num(item[3]) if len(item) > 3 else 0.0
            elif key == "model":
                has_model = True
            elif key == "property":
                if str(item[1]) == "LCSC":
                    lcsc = str(item[2]).strip()
                elif str(item[1]) == "Reference":
                    reference = str(item[2])
            elif key == "pad":
                pad = _read_pad(item)
                if pad is not None:
                    pads.append(pad)
            elif key in ("fp_rect", "fp_line", "fp_poly", "fp_circle", "fp_arc"):
                layer_node = sexpr.child(item, "layer")
                if layer_node is not None and str(layer_node[1]).endswith("CrtYd"):
                    crt.extend(_points(item))
        courtyard = None
        if crt:
            xs, ys = crt[0::2], crt[1::2]
            courtyard = (min(xs), min(ys), max(xs), max(ys))
        result.append(Footprint(lib_id, reference, layer, lcsc, has_model, start, end, pads, courtyard, x, y, rot))
    return result


def _points(item) -> List[float]:
    out: List[float] = []
    for key in ("start", "end", "center", "mid"):
        node = sexpr.child(item, key)
        if node is not None:
            out.extend([_num(node[1]), _num(node[2])])
    pts = sexpr.child(item, "pts")
    if pts is not None:
        for p in sexpr.children(pts, "xy"):
            out.extend([_num(p[1]), _num(p[2])])
    return out


def _read_pad(item) -> Optional[Pad]:
    kind = str(item[2])
    if kind == "np_thru_hole":
        return None
    at = sexpr.child(item, "at")
    size = sexpr.child(item, "size")
    if at is None or size is None:
        return None
    rot = _num(at[3]) if len(at) > 3 else 0.0
    w, h = _num(size[1]), _num(size[2])
    if round(rot) % 180 == 90:
        w, h = h, w
    drill = 0.0
    drill_node = sexpr.child(item, "drill")
    if drill_node is not None:
        nums = [t for t in drill_node[1:] if re.fullmatch(r"-?[\d.]+", str(t))]
        drill = _num(nums[0]) if nums else 0.0
    return Pad(str(item[1]), kind, _num(at[1]), _num(at[2]), w, h, rot, drill)


def model_line(path: str, offset=(0.0, 0.0, 0.0), rotate=(0.0, 0.0, 0.0)) -> str:
    """The `(model ...)` block KiCad reads, indented to sit as the last child of a footprint block."""
    return (
        f'\t\t(model "{path}"\n'
        f"\t\t\t(offset\n\t\t\t\t(xyz {offset[0]:.4f} {offset[1]:.4f} {offset[2]:.4f})\n\t\t\t)\n"
        "\t\t\t(scale\n\t\t\t\t(xyz 1 1 1)\n\t\t\t)\n"
        f"\t\t\t(rotate\n\t\t\t\t(xyz {rotate[0]:.4f} {rotate[1]:.4f} {rotate[2]:.4f})\n\t\t\t)\n"
        "\t\t)\n"
    )


def inject_models(text: str, lines_by_index: dict) -> str:
    """Return `text` with the model block in `lines_by_index` (footprint order -> block text) added at
    the end of that footprint. The footprints keep their order; only their closing ')' moves down."""
    spans = footprint_spans(text)
    out: List[str] = []
    cursor = 0
    for index, (start, end) in enumerate(spans):
        block = lines_by_index.get(index)
        if not block:
            continue
        out.append(text[cursor : end - 1].rstrip("\t"))
        if not out[-1].endswith("\n"):
            out.append("\n")
        out.append(block)
        out.append("\t")
        cursor = end - 1
    out.append(text[cursor:])
    return "".join(out)
