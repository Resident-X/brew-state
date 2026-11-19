#!/usr/bin/env python3
"""The footprint audit: how near part bodies stand, what a footprint's pads are, and which turn lands its pads.

Three commands over a KiCad layout, none of which needs KiCad itself:

    footprint_audit.py gaps --board B.kicad_pcb --bodies TABLE.yaml [--ref REF ...] [--min-gap MM] [--access-zones] [--all-pairs] [--format text|json]
    footprint_audit.py pads --board B.kicad_pcb REF [REF ...] [--format text|json]
    footprint_audit.py rotation --board B.kicad_pcb --ref REF --pad NUMBER=X,Y [--pad ...] [--origin X,Y] [--step DEGREES] [--tolerance MM] [--format text|json]

`gaps` measures the gap between each pair of part bodies. A body is a set of
rectangles the body table gives in the footprint's own coordinates, as the
maker's drawing dimensions them, keyed by the footprint's name; each part's
rectangles are put on the board by the part's position, turn and side, and the
gap of two parts is the least gap of their rectangles. A gap is the distance
between two rectangles, 0 where they touch, and the depth they overlap by,
negative, where they overlap. A rectangle of a part turned to an angle that is
not a multiple of 90 degrees is held as the box around it. Any pair standing
nearer than `--min-gap` (default 1 mm) is a finding. A part on the board, or
named with `--ref`, whose footprint the table does not hold is named as missing:
its gap cannot be measured, and the run fails. A table entry may take the
footprint's courtyard for its body (`from: courtyard`), which marks the body as
no maker reading: the report gives each part's basis, and its verdict line counts
the parts measured on such a stand-in and names them (`courtyard_stand_ins` in JSON). `--access-zones` also measures the table's access zones, the
space a mating part or a hand needs.

`pads` lists each pad of the footprints named, with its number, kind, shape,
position in the footprint, size, angle as the board file writes it, layers,
drill and position on the board.

`rotation` takes a part on the board, a target position for each of the pads
named, and the pads' positions in the footprint, and returns the turns, among
multiples of `--step` degrees (default 90), at which each named pad lands within
`--tolerance` mm (default 0.01) of its target with the footprint's origin held at
the part's present position or at `--origin`; or says that none does. A pad number
that several pads carry lands when any of them does.

Exit status: 0 when the run is clean (no pair too near and no part missing; the
pads listed; a turn exists), 1 when it found something (a pair too near, a part
missing, a reference not on the board, no turn), 2 when it cannot run (a board
or table that cannot be read, a bad argument).
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from typing import Dict, List, Optional, Sequence, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import sexpr  # noqa: E402
import board_geometry  # noqa: E402
from board_check import CannotRun, clean  # noqa: E402

Rect = Tuple[float, float, float, float]

DEFAULT_MIN_GAP = 1.0
DEFAULT_STEP = 90.0
DEFAULT_TOLERANCE = 0.01

#: The keys a body table entry may carry.
ENTRY_KEYS = {"kind", "height_mm", "hand_fitted", "source", "rects", "access_zones", "from"}
RECT_KEYS = {"name", "x0", "y0", "x1", "y1", "height_mm"}


# --- Reading the board ----------------------------------------------------------------


def read_layout(path: str) -> list:
    try:
        with open(path, encoding="utf-8") as handle:
            tree = sexpr.parse_one(handle.read())
    except (OSError, UnicodeDecodeError, sexpr.SexprError) as error:
        raise CannotRun(f"the board {path} cannot be read ({error})") from error
    if sexpr.head(tree) != "kicad_pcb":
        raise CannotRun(f"{path} is not a KiCad layout: it begins ({sexpr.head(tree) or '?'} ...), not (kicad_pcb ...)")
    return tree


class Part:
    """One footprint on the board: its reference, footprint name, position, turn and side."""

    def __init__(self, node: list):
        self.node = node
        self.reference = board_geometry.reference(node)
        self.footprint = str(node[1]) if len(node) > 1 and isinstance(node[1], str) else ""
        what = f"the footprint {self.reference or self.footprint or '?'}"
        if sexpr.child(node, "at") is None:
            raise CannotRun(f"{what} has no (at ...) where KiCad writes its position")
        try:
            self.x, self.y, self.angle = board_geometry.placement(node, what)
        except board_geometry.Unreadable as error:
            raise CannotRun(str(error)) from error
        layer = sexpr.child(node, "layer")
        self.layer = str(layer[1]) if layer is not None and len(layer) > 1 else "F.Cu"

    @property
    def back(self) -> bool:
        return self.layer == "B.Cu"

    def point(self, local: Tuple[float, float], origin: Optional[Tuple[float, float]] = None, angle: Optional[float] = None):
        """A point of the footprint's own, as it lies on the board."""
        x, y = origin if origin is not None else (self.x, self.y)
        return board_geometry.placed(local, (x, y, self.angle if angle is None else angle))


def parts(layout: list) -> List[Part]:
    return [Part(node) for node in sexpr.children(layout, "footprint")]


# --- The body table -------------------------------------------------------------------


class Entry:
    """A footprint's body in the table: rectangles in the footprint's own frame, or its courtyard."""

    def __init__(self, name: str, courtyard: bool, rects: List[Tuple[str, Rect, Optional[float]]],
                 zones: List[Tuple[str, Rect, Optional[float]]], source: str):
        self.name = name
        self.courtyard = courtyard
        self.rects = rects
        self.zones = zones
        self.source = source


def number(value, what: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise CannotRun(f"{what} is {json.dumps(value)}, not a number in millimetres")
    return float(value)


def read_rects(raw, what: str) -> List[Tuple[str, Rect, Optional[float]]]:
    if not isinstance(raw, list):
        raise CannotRun(f"{what} is not a list of rectangles")
    found = []
    for index, item in enumerate(raw):
        label = f"{what}[{index}]"
        if not isinstance(item, dict):
            raise CannotRun(f"{label} is not a mapping with name, x0, y0, x1, y1")
        unknown = sorted(set(item) - RECT_KEYS)
        if unknown:
            raise CannotRun(f"{label} carries {', '.join(unknown)}, which a rectangle does not take")
        missing = [key for key in ("name", "x0", "y0", "x1", "y1") if key not in item]
        if missing:
            raise CannotRun(f"{label} lacks {', '.join(missing)}")
        x0, y0, x1, y1 = (number(item[key], f"{label}.{key}") for key in ("x0", "y0", "x1", "y1"))
        if x1 <= x0 or y1 <= y0:
            raise CannotRun(f"{label} ({item['name']}) has no area: x1 must exceed x0 and y1 exceed y0")
        height = item.get("height_mm")
        found.append((str(item["name"]), (x0, y0, x1, y1), None if height is None else number(height, f"{label}.height_mm")))
    return found


def read_table(path: str) -> Dict[str, Entry]:
    """The body table: footprint name -> Entry. Raises CannotRun when it cannot be read as a body table."""
    try:
        import yaml
        with open(path, encoding="utf-8") as handle:
            raw = yaml.safe_load(handle)
    except ImportError as error:
        raise CannotRun("the body table is read with PyYAML, which is not installed; install the package pyyaml") from error
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as error:
        raise CannotRun(f"the body table {path} cannot be read ({' '.join(str(error).split())})") from error
    if not isinstance(raw, dict) or not isinstance(raw.get("footprints"), dict):
        raise CannotRun(f"the body table {path} has no `footprints:` mapping of footprint name to body")
    table: Dict[str, Entry] = {}
    for name, item in raw["footprints"].items():
        what = f"the entry for {name}"
        if not isinstance(item, dict):
            raise CannotRun(f"{what} is not a mapping")
        unknown = sorted(set(item) - ENTRY_KEYS)
        if unknown:
            raise CannotRun(f"{what} carries {', '.join(unknown)}, which an entry does not take")
        courtyard = item.get("from") if "from" in item else None
        if "from" in item and courtyard != "courtyard":
            raise CannotRun(f"{what} says from: {json.dumps(courtyard)}; the only source a body may be taken from is courtyard")
        if courtyard and item.get("rects"):
            raise CannotRun(f"{what} gives both rects and from: courtyard; give one")
        if not courtyard:
            if not isinstance(item.get("rects"), list) or not item["rects"]:
                raise CannotRun(f"{what} gives no rects and does not say from: courtyard, so it holds no body")
            source = item.get("source")
            if not isinstance(source, str) or not source.strip():
                raise CannotRun(f"{what} gives rects but no `source` naming the maker reading they come from "
                                f"(a non-blank string); without one it is not a maker reading")
        elif "rects" in item:
            raise CannotRun(f"{what} says from: courtyard and carries a rects key; give one")
        if "source" in item and not isinstance(item["source"], str):
            raise CannotRun(f"{what} has a `source` that is {json.dumps(item['source'])}, not a string")
        if "height_mm" in item:
            number(item["height_mm"], f"{what}.height_mm")
        if "hand_fitted" in item and not isinstance(item["hand_fitted"], bool):
            raise CannotRun(f"{what} has a `hand_fitted` that is {json.dumps(item['hand_fitted'])}, not true or false")
        if "kind" in item and not isinstance(item["kind"], str):
            raise CannotRun(f"{what} has a `kind` that is {json.dumps(item['kind'])}, not a string")
        if "access_zones" in item and item["access_zones"] is not None and not isinstance(item["access_zones"], list):
            raise CannotRun(f"{what}.access_zones is not a list of rectangles")
        rects = [] if courtyard else read_rects(item["rects"], f"{what}.rects")
        zones = read_rects(item["access_zones"], f"{what}.access_zones") if item.get("access_zones") else []
        table[str(name)] = Entry(str(name), bool(courtyard), rects, zones, str(item.get("source") or ""))
    return table


# --- Geometry -------------------------------------------------------------------------


def rect_gap(a: Rect, b: Rect) -> float:
    """The distance between two rectangles, 0 where they touch, and minus the depth they overlap by where they overlap."""
    dx = max(a[0] - b[2], b[0] - a[2])
    dy = max(a[1] - b[3], b[1] - a[3])
    if dx < 0 and dy < 0:
        return max(dx, dy)
    return math.hypot(max(dx, 0.0), max(dy, 0.0))


def placed_rect(part: Part, rect: Rect, stored_frame: bool = False) -> Rect:
    """A rectangle of the footprint's own as the box it fills on the board.

    A body table is drawn as the maker's drawing shows the part from above,
    which a part on the back is the mirror of, so x is mirrored for it. A
    courtyard read from the board is already in the frame the board stores.
    """
    x0, y0, x1, y1 = rect
    corners = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    if part.back and not stored_frame:
        corners = [(-x, y) for x, y in corners]
    points = [part.point(corner) for corner in corners]
    return (min(p[0] for p in points), min(p[1] for p in points), max(p[0] for p in points), max(p[1] for p in points))


def courtyard_rect(part: Part) -> Optional[Rect]:
    """The box around the part's courtyard graphics in the footprint's own frame, or None when it draws none."""
    layer = "B.CrtYd" if part.back else "F.CrtYd"
    points: List[Tuple[float, float]] = []
    what = f"the courtyard of {part.reference or part.footprint}"
    for node in part.node:
        if sexpr.head(node) not in ("fp_rect", "fp_line", "fp_poly", "fp_circle", "fp_arc"):
            continue
        on = sexpr.child(node, "layer")
        if on is None or len(on) < 2 or str(on[1]) != layer:
            continue
        try:
            for key in ("start", "end", "center", "mid"):
                for item in sexpr.children(node, key):
                    points.append(board_geometry.xy(item, what))
            for item in sexpr.children(node, "pts"):
                points += [board_geometry.xy(p, what) for p in sexpr.children(item, "xy")]
        except board_geometry.Unreadable as error:
            raise CannotRun(str(error)) from error
    if not points:
        return None
    return (min(p[0] for p in points), min(p[1] for p in points), max(p[0] for p in points), max(p[1] for p in points))


def mm(value: float) -> str:
    text = f"{value:.3f}".rstrip("0").rstrip(".")
    return "0" if text in ("", "-0") else text


# --- gaps -----------------------------------------------------------------------------


#: What a part's measured body was taken from, as the reports say it.
BASIS_MAKER = "maker reading"
BASIS_COURTYARD = "courtyard substitute"


def body_rects(part: Part, entry: Entry, access: bool) -> Tuple[List[Tuple[str, Rect]], str]:
    """A part's rectangles on the board as (name, box), and the basis they were taken on."""
    if entry.courtyard:
        rect = courtyard_rect(part)
        if rect is None:
            raise CannotRun(f"{part.reference} ({part.footprint}) takes its body from its courtyard and draws none on "
                            f"{'B' if part.back else 'F'}.CrtYd")
        found = [("courtyard", placed_rect(part, rect, True))]
        basis = BASIS_COURTYARD
    else:
        found = [(name, placed_rect(part, rect)) for name, rect, _ in entry.rects]
        basis = BASIS_MAKER
    if access:
        found += [(f"access {name}", placed_rect(part, rect)) for name, rect, _ in entry.zones]
    return found, basis


def audit_gaps(board: str, table_path: str, references: Sequence[str], min_gap: float, access: bool) -> dict:
    layout = read_layout(board)
    table = read_table(table_path)
    on_board = parts(layout)
    by_ref = {part.reference: part for part in on_board if part.reference}
    findings: List[dict] = []
    chosen: List[Part] = []
    if references:
        for reference in references:
            if reference not in by_ref:
                findings.append({"finding": "MISSING", "item": reference, "detail": f"the board carries no part {reference}"})
            elif by_ref[reference] not in chosen:
                chosen.append(by_ref[reference])
    else:
        chosen = [part for part in on_board if part.reference]
        for part in on_board:
            if not part.reference:
                findings.append({"finding": "UNREFERENCED", "item": f"{part.footprint or '?'} at ({mm(part.x)}, {mm(part.y)})",
                                 "detail": "the part carries no reference, so its body is not measured"})
    measured: List[Tuple[Part, List[Tuple[str, Rect]]]] = []
    basis: Dict[str, str] = {}
    for part in chosen:
        entry = table.get(part.footprint)
        if entry is None:
            findings.append({"finding": "MISSING", "item": part.reference,
                             "detail": f"the body table holds no entry for its footprint {part.footprint}, so its body cannot be measured"})
            continue
        rects, how = body_rects(part, entry, access)
        basis[part.reference] = how
        measured.append((part, rects))
    pairs: List[dict] = []
    for index, (one, rects_one) in enumerate(measured):
        for other, rects_other in measured[index + 1:]:
            best = None
            for name_one, box_one in rects_one:
                for name_other, box_other in rects_other:
                    gap = rect_gap(box_one, box_other)
                    if best is None or gap < best[0]:
                        best = (gap, name_one, name_other)
            if best is not None:
                pairs.append({"a": one.reference, "a_body": best[1], "b": other.reference, "b_body": best[2], "gap_mm": round(best[0], 6)})
    pairs.sort(key=lambda pair: (pair["gap_mm"], pair["a"], pair["b"]))
    for pair in pairs:
        gap = pair["gap_mm"]
        if gap < min_gap:
            state = (f"overlap by {mm(-gap)} mm" if gap < 0 else "touch" if gap == 0 else f"are {mm(gap)} mm apart")
            findings.append({"finding": "OVERLAP" if gap < 0 else "NEAR", "item": f"{pair['a']} {pair['a_body']} / {pair['b']} {pair['b_body']}",
                             "detail": f"the bodies {state}, nearer than {mm(min_gap)} mm"})
    failed = bool(findings)
    detail = (f"{len(findings)} finding{'s' if len(findings) != 1 else ''} over {len(pairs)} pair{'s' if len(pairs) != 1 else ''} "
              f"of {len(measured)} part{'s' if len(measured) != 1 else ''}" if failed else
              f"{len(pairs)} pair{'s' if len(pairs) != 1 else ''} of {len(measured)} part{'s' if len(measured) != 1 else ''} "
              f"all at least {mm(min_gap)} mm apart")
    stand_ins = sorted(reference for reference, how in basis.items() if how == BASIS_COURTYARD)
    detail += (f"; {len(stand_ins)} part{'s' if len(stand_ins) != 1 else ''} on a courtyard stand-in, not a maker's drawing "
               f"({', '.join(stand_ins)})" if stand_ins else "; 0 parts on a courtyard stand-in")
    return {"result": "FAIL" if failed else "PASS", "detail": detail, "findings": findings, "min_gap_mm": min_gap,
            "parts_measured": len(measured), "courtyard_stand_ins": stand_ins, "basis": basis, "pairs": pairs}


def print_gaps(report: dict, all_pairs: bool, out) -> None:
    for finding in report["findings"]:
        print(f"{finding['finding']} | {clean(finding['item'])} | {clean(finding['detail'])}", file=out)
    for reference, how in sorted(report["basis"].items()):
        print(f"BASIS | {clean(reference)} | {how}", file=out)
    if all_pairs:
        for pair in report["pairs"]:
            print(f"GAP | {pair['a']} {clean(pair['a_body'])} / {pair['b']} {clean(pair['b_body'])} | {mm(pair['gap_mm'])} mm", file=out)
    print(f"RESULT | {report['result']} | {clean(report['detail'])}", file=out)


# --- pads -----------------------------------------------------------------------------


def pad_rows(part: Part) -> List[dict]:
    what = f"a pad of {part.reference}"
    rows = []
    try:
        for node in sexpr.children(part.node, "pad"):
            own = sexpr.child(node, "at")
            local = board_geometry.xy(own, what)
            angle = board_geometry.number(own, 3, what) if len(own) > 3 else 0.0
            size = sexpr.child(node, "size")
            if size is None or len(size) < 3:
                raise CannotRun(f"{what} has no (size ...) where KiCad writes one")
            drill = sexpr.child(node, "drill")
            drill_text = None
            if drill is not None:
                drill_text = " ".join(str(item) for item in drill[1:] if not isinstance(item, list))
            layers = sexpr.child(node, "layers")
            board = part.point(local)
            rows.append({"number": str(node[1]) if len(node) > 1 else "", "type": str(node[2]) if len(node) > 2 else "",
                         "shape": str(node[3]) if len(node) > 3 else "", "x": local[0], "y": local[1],
                         "width": board_geometry.number(size, 1, what), "height": board_geometry.number(size, 2, what),
                         "angle": angle, "layers": [str(item) for item in (layers or [])[1:]], "drill": drill_text,
                         "board_x": round(board[0], 6), "board_y": round(board[1], 6)})
    except board_geometry.Unreadable as error:
        raise CannotRun(str(error)) from error
    return rows


def audit_pads(board: str, references: Sequence[str]) -> dict:
    layout = read_layout(board)
    by_ref = {part.reference: part for part in parts(layout) if part.reference}
    found, findings = [], []
    for reference in references:
        part = by_ref.get(reference)
        if part is None:
            findings.append({"finding": "MISSING", "item": reference, "detail": f"the board carries no part {reference}"})
            continue
        found.append({"reference": reference, "footprint": part.footprint, "x": part.x, "y": part.y, "angle": part.angle,
                      "layer": part.layer, "pads": pad_rows(part)})
    failed = bool(findings)
    total = sum(len(item["pads"]) for item in found)
    return {"result": "FAIL" if failed else "PASS",
            "detail": (f"{len(findings)} part{'s' if len(findings) != 1 else ''} not on the board" if failed else
                       f"{total} pad{'s' if total != 1 else ''} of {len(found)} part{'s' if len(found) != 1 else ''}"),
            "findings": findings, "parts": found}


def print_pads(report: dict, out) -> None:
    for item in report["parts"]:
        print(f"PART | {item['reference']} | {clean(item['footprint'])} at {mm(item['x'])} {mm(item['y'])} turn {mm(item['angle'])} on {item['layer']}", file=out)
        for pad in item["pads"]:
            drill = f" drill {clean(pad['drill'])}" if pad["drill"] is not None else ""
            print(f"PAD | {item['reference']} {clean(pad['number']) or '(unnumbered)'} | {pad['type']} {pad['shape']} at {mm(pad['x'])} {mm(pad['y'])} "
                  f"size {mm(pad['width'])}x{mm(pad['height'])} angle {mm(pad['angle'])} layers {','.join(pad['layers'])}{drill} "
                  f"board {mm(pad['board_x'])} {mm(pad['board_y'])}", file=out)
    for finding in report["findings"]:
        print(f"{finding['finding']} | {clean(finding['item'])} | {clean(finding['detail'])}", file=out)
    print(f"RESULT | {report['result']} | {clean(report['detail'])}", file=out)


# --- rotation -------------------------------------------------------------------------


def parse_target(text: str) -> Tuple[str, Tuple[float, float]]:
    name, equals, where = text.partition("=")
    bits = where.split(",")
    try:
        if not equals or not name or len(bits) != 2:
            raise ValueError
        return name, (float(bits[0]), float(bits[1]))
    except ValueError:
        raise CannotRun(f"--pad {text!r} is not NUMBER=X,Y (a pad number, then the position in mm it should land on)") from None


def solve_rotation(board: str, reference: str, targets: Sequence[str], origin: Optional[str], step: float, tolerance: float) -> dict:
    if not targets:
        raise CannotRun("name at least one --pad NUMBER=X,Y to land on its target")
    if not (0 < step <= 360):
        raise CannotRun(f"--step {step} is not a number of degrees above zero and at most 360")
    if not (tolerance >= 0 and math.isfinite(tolerance)):
        raise CannotRun(f"--tolerance {tolerance} is not a distance in mm of zero or more")
    wanted = [parse_target(text) for text in targets]
    start: Optional[Tuple[float, float]] = None
    if origin is not None:
        bits = origin.split(",")
        try:
            if len(bits) != 2:
                raise ValueError
            start = (float(bits[0]), float(bits[1]))
        except ValueError:
            raise CannotRun(f"--origin {origin!r} is not X,Y in mm") from None
    layout = read_layout(board)
    part = next((p for p in parts(layout) if p.reference == reference), None)
    if part is None:
        return {"result": "FAIL", "detail": f"the board carries no part {reference}", "exists": False, "part": reference,
                "rotations": [], "candidates": [], "findings": [{"finding": "MISSING", "item": reference,
                                                                "detail": f"the board carries no part {reference}"}]}
    rows = pad_rows(part)
    findings = []
    for number_, _ in wanted:
        if not any(row["number"] == number_ for row in rows):
            findings.append({"finding": "MISSING", "item": f"{reference} pad {number_}", "detail": "the footprint has no pad of this number"})
    if findings:
        return {"result": "FAIL", "detail": f"{len(findings)} pad{'s' if len(findings) != 1 else ''} not in the footprint", "exists": False,
                "part": reference, "rotations": [], "candidates": [], "findings": findings}
    origin_at = start if start is not None else (part.x, part.y)
    candidates = []
    count = int(math.floor(360 / step - 1e-9)) + 1
    for k in range(count):
        angle = k * step
        if angle >= 360 - 1e-9:
            break
        worst = 0.0
        landings = []
        for number_, target in wanted:
            best = None
            for row in rows:
                if row["number"] != number_:
                    continue
                x, y = part.point((row["x"], row["y"]), origin_at, angle)
                miss = math.hypot(x - target[0], y - target[1])
                if best is None or miss < best[0]:
                    best = (miss, x, y)
            worst = max(worst, best[0])
            landings.append({"pad": number_, "x": round(best[1], 6), "y": round(best[2], 6), "miss_mm": round(best[0], 6)})
        candidates.append({"rotation": round(angle, 6), "worst_miss_mm": round(worst, 6), "lands": worst <= tolerance, "pads": landings})
    rotations = [item["rotation"] for item in candidates if item["lands"]]
    nearest = min(candidates, key=lambda item: item["worst_miss_mm"])
    if rotations:
        detail = f"{reference} lands on its targets at {', '.join(mm(r) for r in rotations)} degrees"
    else:
        detail = (f"no turn in steps of {mm(step)} degrees lands the pads within {mm(tolerance)} mm of their targets; "
                  f"nearest is {mm(nearest['rotation'])} degrees, {mm(nearest['worst_miss_mm'])} mm out")
    return {"result": "PASS" if rotations else "FAIL", "detail": detail, "exists": bool(rotations), "part": reference,
            "origin": [origin_at[0], origin_at[1]], "step": step, "tolerance_mm": tolerance, "rotations": rotations,
            "candidates": candidates, "findings": []}


def print_rotation(report: dict, out) -> None:
    for finding in report["findings"]:
        print(f"{finding['finding']} | {clean(finding['item'])} | {clean(finding['detail'])}", file=out)
    for angle in report["rotations"]:
        print(f"ROTATION | {report['part']} | {mm(angle)} degrees", file=out)
    print(f"RESULT | {report['result']} | {clean(report['detail'])}", file=out)


# --- Command line ---------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("gaps", "pads", "rotation"):
        command = sub.add_parser(name)
        command.add_argument("--board", required=True, help="the layout file (.kicad_pcb)")
        command.add_argument("--format", choices=("text", "json"), default="text")
    gaps = sub.choices["gaps"]
    gaps.add_argument("--bodies", required=True, help="the body table (YAML) in the board's folder")
    gaps.add_argument("--ref", action="append", default=[], help="a part to audit (repeatable); default: every part on the board")
    gaps.add_argument("--min-gap", type=float, default=DEFAULT_MIN_GAP, help="the least gap in mm a pair may stand at (default: %(default)s)")
    gaps.add_argument("--access-zones", action="store_true", help="also measure the table's access zones")
    gaps.add_argument("--all-pairs", action="store_true", help="list the gap of every pair measured, not only the findings")
    sub.choices["pads"].add_argument("references", nargs="+", metavar="REF", help="the parts whose pads to list")
    rotation = sub.choices["rotation"]
    rotation.add_argument("--ref", required=True, help="the part to turn")
    rotation.add_argument("--pad", action="append", default=[], metavar="NUMBER=X,Y", help="a pad and the board position it must land on (repeatable)")
    rotation.add_argument("--origin", default=None, metavar="X,Y", help="the footprint origin to hold (default: the part's present position)")
    rotation.add_argument("--step", type=float, default=DEFAULT_STEP, help="the turns tried, in degrees (default: %(default)s)")
    rotation.add_argument("--tolerance", type=float, default=DEFAULT_TOLERANCE, help="how near a pad must land, in mm (default: %(default)s)")
    return parser


def finish(report: dict, as_json: bool, printer, out) -> int:
    if as_json:
        print(json.dumps(report, indent=2, sort_keys=True), file=out)
    else:
        printer(report)
    return 0 if report["result"] == "PASS" else 1


def main(argv: Optional[List[str]] = None, out=sys.stdout) -> int:
    args = build_parser().parse_args(argv)
    as_json = args.format == "json"
    try:
        if args.command == "gaps":
            if not (args.min_gap >= 0 and math.isfinite(args.min_gap)):
                raise CannotRun(f"--min-gap {args.min_gap} is not a distance in mm of zero or more")
            report = audit_gaps(args.board, args.bodies, args.ref, args.min_gap, args.access_zones)
            return finish(report, as_json, lambda r: print_gaps(r, args.all_pairs, out), out)
        if args.command == "pads":
            return finish(audit_pads(args.board, args.references), as_json, lambda r: print_pads(r, out), out)
        report = solve_rotation(args.board, args.ref, args.pad, args.origin, args.step, args.tolerance)
        return finish(report, as_json, lambda r: print_rotation(r, out), out)
    except CannotRun as error:
        message = clean(str(error))
        if as_json:
            print(json.dumps({"result": "CANNOT RUN", "detail": message, "findings": []}, indent=2), file=out)
        print(f"CANNOT RUN | {message}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
