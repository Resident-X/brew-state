"""The Staircase logo engraved: grooves cut into a face, read from staircase-logo.svg.

The vector has `viewBox="0 0 W 100"` (height normalised to 100, y down) and four groups: `silhouette` (the outline polygon),
`light` (one polygon per light face), `dark` (one polygon per dark face, each with `data-hatch-angle`, the direction of a
hatch groove in degrees measured in the vector's own frame: x right, y down, so a positive angle runs down to the right) and
`sheets` (stacked-sheet lines). Placed at a height, the engraving is one rule, shared by the model and by the preview that
trace_logo.py draws:

    the silhouette as one groove `groove_width` wide;
    light faces plain; where two light faces meet, a groove `face_groove_width` wide along their shared edge, only when both
    faces are at least `light_face_min` across at the placed size, otherwise no line;
    dark faces with no outline of their own, shown as tone: parallel hatch grooves `hatch_width` wide at `hatch_pitch` along
    the face's angle, centred on the face and clipped to it, so they touch the silhouette groove where the face meets the
    outside; a dark face too thin for two hatch lines carries one groove along its centre line instead;
    sheet lines `sheet_width` wide, kept only where they stay `sheet_clear` clear of every other groove;
    the lot cleaned up to a least land and a least groove of `min_feature`: grooves nearer than that are merged and anything
    narrower is dropped.

Every groove has one depth, so no pocket is wider than the groove width except where two grooves meet.
"""

from __future__ import annotations

import math
import os
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Any, Callable, List, Optional, Sequence, Tuple

import shapely
from shapely import affinity
from shapely.geometry import LineString, MultiLineString, Polygon as ShPolygon
from shapely.ops import unary_union

HERE = os.path.dirname(os.path.abspath(__file__))
LOGO_SVG = os.path.join(HERE, "staircase-logo.svg")

SHARED_EDGE_TOL = 0.05          # mm: two face edges this near are one shared edge
SHARED_EDGE_MIN = 1.0           # mm: a shared edge shorter than this is a corner touch, not a boundary
HATCH_RUN_MIN = 0.8             # mm: a hatch run shorter than this is not a line
SHEET_PIECE_MIN = 1.5           # mm: a sheet line kept only in pieces at least this long


@dataclass
class LogoVector:
    width: float
    height: float
    silhouette: ShPolygon
    light: List[ShPolygon]
    dark: List[Tuple[ShPolygon, float]]
    sheets: List[LineString]


@dataclass
class Engraving:
    """The engraved logo at a placed height, in a frame with x right, y up and the silhouette's lower left corner at the origin."""
    geometry: Any                                       # every groove, one shapely geometry
    outline: ShPolygon                                  # the silhouette
    width: float
    height: float
    boundary: Any = None                                # the silhouette groove and the light/light grooves
    hatch: Any = None                                   # the dark faces' hatch and centre-line grooves
    sheets: Any = None
    sheets_kept: int = 0
    sheets_dropped: int = 0
    dark_faces: int = 0
    light_faces: int = 0
    centre_line_faces: int = 0                          # dark faces too thin for two hatch lines
    light_grooves: int = 0                              # light/light boundaries given a groove

    def placed(self, face: str, centre: Tuple[float, float]) -> Tuple[Any, ShPolygon]:
        """The grooves and the outline in the case MODEL frame (u, v), centred on `centre`, reading upright for the viewer who stands in
        front of the wall the plate is on, facing it.

        Derived in the physical frame (X = u, Y = -v, Z = z; right-handed), where the wall is toward +Y and, in the installed orientation,
        gravity is +Z, so the viewer's forward is +Y, the viewer's up is -Z and the viewer's right is forward x up = Y x (-Z) = -X = -u:
        on both faces the logo's x (to the right as the artwork reads) runs along -u.

        The tray's outer top face faces up and is seen from above: the top of the view is forward, toward the wall, which is -v, so y
        (up) runs along -v. The lid face faces down and is seen from below, looking up: what is nearer the viewer is higher in the view
        and the wall side is at the bottom, so the top of the view is away from the wall, +v, and y runs along +v. (An earlier
        statement put the wall toward the top of the view on the lid too; that was drawn from a mirrored view.)"""
        y_sign = -1.0 if face == "tray" else 1.0
        matrix = (-1.0, 0.0, 0.0, y_sign, centre[0] + self.width / 2, centre[1] - y_sign * self.height / 2)
        return affinity.affine_transform(self.geometry, matrix), affinity.affine_transform(self.outline, matrix)


def _numbers(text: str) -> List[Tuple[float, float]]:
    return [tuple(float(v) for v in pair.split(",")) for pair in text.split()]  # type: ignore[misc]


def read_vector(path: Optional[str] = None) -> LogoVector:
    """The logo vector at `path` (staircase-logo.svg beside this module by default), in its own units, y up."""
    root = ET.parse(path or LOGO_SVG).getroot()
    ns = "{http://www.w3.org/2000/svg}"
    box = [float(v) for v in root.attrib["viewBox"].replace(",", " ").split()]
    if abs(box[1]) > 1e-9 or abs(box[3] - 100.0) > 1e-6:
        raise SystemExit(f"{path or LOGO_SVG}: viewBox must be 0 0 W 100, got {root.attrib['viewBox']}")
    width, height = box[2], box[3]

    def group(name: str) -> List[ET.Element]:
        for g in root.iter(f"{ns}g"):
            if g.attrib.get("id") == name:
                return list(g)
        raise SystemExit(f"{path or LOGO_SVG}: no group with id {name!r}")

    def flip(pts: Sequence[Tuple[float, float]]) -> List[Tuple[float, float]]:
        return [(x, height - y) for x, y in pts]

    def poly(el: ET.Element) -> ShPolygon:
        return ShPolygon(flip(_numbers(el.attrib["points"]))).buffer(0)

    silhouette = [poly(e) for e in group("silhouette") if e.tag == f"{ns}polygon"]
    if len(silhouette) != 1:
        raise SystemExit("the silhouette group holds one polygon")
    light = [poly(e) for e in group("light") if e.tag == f"{ns}polygon"]
    dark = [(poly(e), float(e.attrib["data-hatch-angle"])) for e in group("dark") if e.tag == f"{ns}polygon"]
    sheets = [LineString(flip([(float(e.attrib["x1"]), float(e.attrib["y1"])), (float(e.attrib["x2"]), float(e.attrib["y2"]))]))
              for e in group("sheets") if e.tag == f"{ns}line"]
    return LogoVector(width, height, silhouette[0], light, dark, sheets)


def across(face: ShPolygon) -> float:
    """How wide a face is: the diameter of the largest circle that fits in it."""
    return 2.0 * float(shapely.maximum_inscribed_circle(face, 0.01).length) if not face.is_empty else 0.0


def _pieces(geom: Any, kind: str = "LineString") -> List[Any]:
    if geom is None or geom.is_empty:
        return []
    parts = list(geom.geoms) if hasattr(geom, "geoms") else [geom]
    out: List[Any] = []
    for p in parts:
        if p.geom_type == kind:
            out.append(p)
        elif hasattr(p, "geoms"):
            out += _pieces(p, kind)
    return out


def _stroke(line: Any, width: float, round_ends: bool = True) -> Any:
    return line.buffer(width / 2, cap_style=1 if round_ends else 2, join_style=1, quad_segs=6)


def hatch_family(face: ShPolygon, angle_deg: float, pitch: float) -> Tuple[List[LineString], float]:
    """The hatch lines of a dark face and the face's extent across them.

    The lines run along the face's angle, `pitch` apart, symmetric about the middle of the face's extent across them, as many
    as fit without a line's edge leaving the extent. Returns the lines clipped to the face (runs shorter than the least run are
    left out) and the extent across.
    """
    a = math.radians(angle_deg)
    d = (math.cos(a), -math.sin(a))     # the vector's y points down, ours up
    n = (-d[1], d[0])
    coords = list(face.exterior.coords)
    s = [x * n[0] + y * n[1] for x, y in coords]
    smin, smax = min(s), max(s)
    extent = smax - smin
    count = int(math.floor(extent / pitch)) + 1 if extent >= pitch else 1
    mid = (smin + smax) / 2
    reach = max(face.bounds[2] - face.bounds[0], face.bounds[3] - face.bounds[1]) * 2 + pitch
    cx, cy = face.centroid.x, face.centroid.y
    along0 = cx * d[0] + cy * d[1]
    runs: List[LineString] = []
    for i in range(count):
        offset = mid + (i - (count - 1) / 2) * pitch
        base = (n[0] * offset + d[0] * along0, n[1] * offset + d[1] * along0)
        line = LineString([(base[0] - d[0] * reach, base[1] - d[1] * reach), (base[0] + d[0] * reach, base[1] + d[1] * reach)])
        for piece in _pieces(line.intersection(face)):
            if piece.length >= HATCH_RUN_MIN:
                runs.append(piece)
    return runs, extent


def _dark_grooves(face: ShPolygon, angle: float, hatch_width: float, pitch: float) -> Tuple[Any, bool]:
    """The grooves of one dark face and whether it took the single centre line."""
    runs, extent = hatch_family(face, angle, pitch)
    clipped = lambda lines: unary_union([_stroke(l, hatch_width, False) for l in lines]).intersection(face)  # noqa: E731
    if extent >= pitch + hatch_width and len(runs) >= 2:
        return clipped(runs), False
    a = math.radians(angle)
    d = (math.cos(a), -math.sin(a))     # the vector's y points down, ours up
    n = (-d[1], d[0])
    s = [x * n[0] + y * n[1] for x, y in face.exterior.coords]
    offset = (min(s) + max(s)) / 2
    along0 = face.centroid.x * d[0] + face.centroid.y * d[1]
    reach = max(face.bounds[2] - face.bounds[0], face.bounds[3] - face.bounds[1]) * 2 + pitch
    base = (n[0] * offset + d[0] * along0, n[1] * offset + d[1] * along0)
    line = LineString([(base[0] - d[0] * reach, base[1] - d[1] * reach), (base[0] + d[0] * reach, base[1] + d[1] * reach)])
    pieces = _pieces(line.intersection(face))
    if not pieces:
        return ShPolygon(), True
    longest = max(pieces, key=lambda p: p.length)
    return _stroke(longest, hatch_width, True), True


def engrave(P: Callable[[str], Any], height: float, path: Optional[str] = None) -> Engraving:
    """The engraving at a placed height (mm), with the groove figures of params.yaml `logo`."""
    vec = read_vector(path)
    k = height / vec.height
    gw, fw = P("logo.groove_width_mm"), P("logo.face_groove_width_mm")
    hw, pitch = P("logo.hatch_width_mm"), P("logo.hatch_pitch_mm")
    sw, clear = P("logo.sheet_width_mm"), P("logo.sheet_clear_mm")
    light_min, feature = P("logo.light_face_min_mm"), P("logo.min_feature_mm")

    def scale(g: Any) -> Any:
        return affinity.scale(g, xfact=k, yfact=k, origin=(0, 0))

    silhouette = scale(vec.silhouette).simplify(0.05)
    light = [scale(f) for f in vec.light]
    dark = [(scale(f), a) for f, a in vec.dark]

    outline_groove = _stroke(LineString(list(silhouette.exterior.coords)), gw)
    # a boundary between two light faces, drawn only when both are wide enough to read
    wide = [f for f in light if across(f) >= light_min]
    seams = []
    for i, a in enumerate(wide):
        for b in wide[i + 1:]:
            shared = a.exterior.buffer(SHARED_EDGE_TOL).intersection(b.exterior)
            lines = [p for p in _pieces(shared) if p.length >= SHARED_EDGE_MIN]
            if lines:
                seams.append(_stroke(unary_union(lines), fw))
    light_seams = unary_union(seams) if seams else ShPolygon()
    # dark faces as tone
    hatches, centre_faces = [], 0
    for face, angle in dark:
        g, centred = _dark_grooves(face, angle, hw, pitch)
        centre_faces += int(centred)
        hatches.append(g)
    hatch = unary_union(hatches) if hatches else ShPolygon()
    # sheet lines, longest first, kept only where clear of every other groove and of the sheet lines already kept
    others = unary_union([outline_groove, light_seams, hatch])
    kept: List[LineString] = []
    dropped = 0
    for line in sorted((scale(s) for s in vec.sheets), key=lambda s: -s.length):
        free = line.difference(others.buffer(clear + sw / 2))
        pieces = [p for p in _pieces(free) if p.length >= SHEET_PIECE_MIN]
        if not pieces:
            dropped += 1
            continue
        for p in pieces:
            kept.append(p)
            others = unary_union([others, _stroke(p, sw, False)])
    sheets = unary_union([_stroke(p, sw, False) for p in kept]) if kept else ShPolygon()
    # a least land and a least groove: nearer grooves merge, narrower ones go
    r = feature / 2 - 1e-3
    merged = unary_union([outline_groove, light_seams, hatch, sheets])
    merged = merged.buffer(r, quad_segs=6).buffer(-r, quad_segs=6)
    merged = merged.buffer(-r, quad_segs=6).buffer(r, quad_segs=6)
    geometry = merged.intersection(silhouette.buffer(gw / 2 + 0.01))
    b = silhouette.bounds
    move = lambda g: affinity.translate(g, -b[0], -b[1])  # noqa: E731
    boundary = unary_union([outline_groove, light_seams])
    return Engraving(move(geometry), move(silhouette), b[2] - b[0], b[3] - b[1], move(boundary), move(hatch), move(sheets), len(kept), dropped,
                     len(dark), len(light), centre_faces, len(seams))
