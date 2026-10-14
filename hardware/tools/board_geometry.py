"""Where a board's pads sit, where their copper reaches, how far apart a net's pads are, and the shortest straight-line tree joining them.

A layout file places each footprint at a point and turns it by an angle, and
writes each of its pads at a point of the footprint's own, so a pad's place on
the board is found by turning its point as KiCad turns it and adding the
footprint's. Its shape, size and the angle it is turned to on the board are
written beside it, the angle already including the footprint's. This is read
here once, for every tool that needs to know where a net's pads are: the
pre-order check, which measures each net's track length against the shortest
tree joining its pads; the layout review views, which frame a circuit's
decoupling parts; and the placement checkpoint, which measures how far apart a
placement leaves the pads each net must join.

Whether a track meets a pad is judged here too, once, from the copper and
never from the track's centre line alone. A track's copper is its centre line
swept by a circle of half its width, so its end is a round cap about its end
point, and KiCad's connectivity joins a track to a pad when that cap reaches
the pad's copper, or when the pad's centre lies on the track's copper. A pad's
copper is sized from its shape and size as the layout file writes them: a
circle, an oval, a rectangle and a rounded rectangle are each a rectangle,
perhaps of no width or height, grown on every side by a radius, and are sized
exactly. A pad of any other copper, a custom shape, chamfered corners, a
trapezoid or a shape that differs from layer to layer, is not sized, and asking
where its copper reaches raises Unsized naming it, so no tool guesses it.

The shortest straight-line tree joining a set of points is their minimum
spanning tree under straight-line distance, the shortest set of straight lines
pad to pad that joins every pad to every other. A route that branches only at
pads can be no shorter than it, so how much longer a net's tracks are than the
tree is how far the route wanders from the most direct one its pads allow.

Everything is read in the one form KiCad writes it, and anything else raises
Unreadable naming what could not be read, rather than being taken as nothing.
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Sequence, Tuple

import sexpr

Point = Tuple[float, float]


class Unreadable(Exception):
    """A board, project file or record that cannot be read in the form KiCad or this check writes it."""


class Unsized(Unreadable):
    """A pad whose copper the board file does not size in a shape read here, asked where its copper reaches."""


#: How near two pieces of copper must come to be read as touching, in mm: well
#: under anything drawn, well over a floating-point remainder.
CONTACT = 1e-6

#: The corner radius of a rounded rectangle pad, as a share of its shorter
#: side, that KiCad takes when the pad does not write its own.
ROUNDRECT_RATIO = 0.25


# --- Reading positions -----------------------------------------------------------


def number(node, index: int, what: str) -> float:
    try:
        return float(node[index])
    except (TypeError, ValueError, IndexError) as error:
        raise Unreadable(f"{what} is {sexpr.dump(node)}, not a position in millimetres") from error


def xy(node, what: str) -> Point:
    if not isinstance(node, list) or len(node) < 3:
        raise Unreadable(f"{what} has no position where KiCad writes one")
    return number(node, 1, what), number(node, 2, what)


def net_table(layout: list) -> Dict[str, str]:
    """The numbered net table an older layout file carries at its top level, number -> name; empty in KiCad 10's form."""
    return {str(node[1]): str(node[2]) for node in sexpr.children(layout, "net") if len(node) == 3}


def item_net(node: list, table: Dict[str, str], what: str) -> str:
    """The net an item carries, '' for none."""
    nets = sexpr.children(node, "net")
    if len(nets) > 1:
        raise Unreadable(f"{what} names its net {len(nets)} times")
    if not nets:
        return ""
    if len(nets[0]) != 2 or isinstance(nets[0][1], list):
        raise Unreadable(f"{what} names its net as {sexpr.dump(nets[0])}, where KiCad writes (net \"name\")")
    raw = str(nets[0][1])
    return table.get(raw, raw) if table and not isinstance(nets[0][1], sexpr.Quoted) else raw


def reference(footprint: list) -> str:
    for node in sexpr.children(footprint, "property"):
        if len(node) > 2 and str(node[1]) == "Reference":
            return str(node[2])
    for node in sexpr.children(footprint, "fp_text"):
        if len(node) > 2 and str(node[1]) == "reference":
            return str(node[2])
    return ""


def placement(footprint: list, what: str) -> Tuple[float, float, float]:
    """A footprint's position on the board and the angle it is turned to, in degrees."""
    at = sexpr.child(footprint, "at")
    x, y = xy(at, what)
    return x, y, number(at, 3, what) if len(at) > 3 else 0.0


def placed(point: Point, at: Tuple[float, float, float]) -> Point:
    """A footprint's own point in board coordinates, turned as KiCad turns it."""
    x, y, angle = at
    cos, sin = math.cos(math.radians(angle)), math.sin(math.radians(angle))
    return x + point[0] * cos + point[1] * sin, y - point[0] * sin + point[1] * cos


def turned(vector: Point, angle: float) -> Point:
    """A direction of a pad's own, as it lies on the board once the pad is turned to `angle`."""
    return placed(vector, (0.0, 0.0, angle))


def pad_centres(footprint: list) -> List[Point]:
    """The centre of each of a footprint's pads on the board."""
    what = f"a pad of the footprint {reference(footprint) or '?'}"
    at = placement(footprint, what)
    return [placed(xy(sexpr.child(pad, "at"), what), at) for pad in sexpr.children(footprint, "pad")]


# --- Pads --------------------------------------------------------------------------


class Pad:
    """One pad on the board: its net, where its copper is, its shape and size, and the copper layers it is on."""

    def __init__(self, reference: str, number: str, net: str, centre: Point, size: Tuple[float, float],
                 angle: float, shape: str, layers: Sequence[str], rounding: float = ROUNDRECT_RATIO, unsized: str = ""):
        self.reference = reference
        self.number = number
        self.net = net
        #: The centre of the pad's copper on the board, which a drill offset moves off its hole.
        self.centre = centre
        #: Its size along its own x and y, before it is turned.
        self.size = size
        #: The angle it is turned to on the board, in degrees, the footprint's turn included.
        self.angle = angle
        self.shape = shape
        self.layers = tuple(layers)
        #: What makes the pad's copper a shape not sized here, or '' when it is sized.
        self.unsized = (f"its shape is {shape or 'not written'}" if shape not in ("circle", "oval", "rect", "roundrect")
                        else unsized)
        #: The pad's copper in its own frame, as the half-width and half-height
        #: of a rectangle and the radius it is grown by on every side.
        width, height = size
        radius = {"circle": width / 2, "oval": min(width, height) / 2, "rect": 0.0,
                  "roundrect": min(width, height) * rounding}.get(shape, 0.0)
        self.core = (max(width / 2 - radius, 0.0), max(height / 2 - radius, 0.0), radius) if shape != "circle" else (0.0, 0.0, radius)

    def name(self) -> str:
        return f"pad {self.number or '(unnumbered)'} of {self.reference or '?'}"

    def on(self, layer: str) -> bool:
        """Whether the pad has copper on a copper layer."""
        return layer in self.layers or "*.Cu" in self.layers or (
            "F&B.Cu" in self.layers and layer in ("F.Cu", "B.Cu"))

    def local(self, point: Point) -> Point:
        """A board point in the pad's own frame, its centre at the origin and its sides along the axes."""
        dx, dy = point[0] - self.centre[0], point[1] - self.centre[1]
        cos, sin = math.cos(math.radians(self.angle)), math.sin(math.radians(self.angle))
        # The inverse of placed(): the pad's own x lies along (cos, -sin) on the board, its own y along (sin, cos).
        return dx * cos - dy * sin, dx * sin + dy * cos

    def sized(self) -> bool:
        """Whether the pad's copper is a shape sized here."""
        return not self.unsized

    def grown(self) -> Tuple[float, float, float]:
        if self.unsized:
            raise Unsized(f"{self.name()} has copper the check cannot size from the board file: {self.unsized}")
        return self.core

    def distance(self, point: Point) -> float:
        """How far a board point lies from the pad's copper, 0 on it."""
        half_x, half_y, radius = self.grown()
        x, y = self.local(point)
        return max(math.hypot(max(abs(x) - half_x, 0.0), max(abs(y) - half_y, 0.0)) - radius, 0.0)

    def distance_to_line(self, a: Point, b: Point) -> float:
        """How far the straight line from a to b passes from the pad's copper, 0 where it runs on it."""
        half_x, half_y, radius = self.grown()
        return max(line_to_box(self.local(a), self.local(b), half_x, half_y) - radius, 0.0)

    def long_axis(self) -> Optional[Point]:
        """The direction on the board of the pad's long axis, or None for a pad no longer than it is wide."""
        width, height = self.size
        if abs(width - height) <= 1e-6:
            return None
        return turned((1.0, 0.0) if width > height else (0.0, 1.0), self.angle)


def footprint_pads(footprint: list, table: Dict[str, str]) -> List[Pad]:
    """Every pad of a footprint, placed on the board."""
    name = reference(footprint)
    what = f"a pad of the footprint {name or '?'}"
    at = placement(footprint, what)
    found = []
    for node in sexpr.children(footprint, "pad"):
        own = sexpr.child(node, "at")
        point = xy(own, what)
        # KiCad writes a pad's angle as it lies on the board, the footprint's
        # own turn included, and leaves it out when it is nought.
        angle = number(own, 3, what) if len(own) > 3 else 0.0
        size = sexpr.child(node, "size")
        if size is None or len(size) < 3:
            raise Unreadable(f"{what} has no (size ...) where KiCad writes one")
        width, height = number(size, 1, what), number(size, 2, what)
        drill = sexpr.child(node, "drill")
        offset = sexpr.child(drill, "offset") if drill is not None else None
        centre = placed(point, at)
        if offset is not None:
            shift = turned(xy(offset, what), angle)
            centre = centre[0] + shift[0], centre[1] + shift[1]
        layers = sexpr.child(node, "layers")
        rratio = sexpr.child(node, "roundrect_rratio")
        found.append(Pad(name, str(node[1]) if len(node) > 1 else "", item_net(node, table, what), centre,
                         (width, height), angle, str(node[3]) if len(node) > 3 else "",
                         [str(layer) for layer in (layers or [])[1:]],
                         number(rratio, 1, what) if rratio is not None else ROUNDRECT_RATIO, unsized_by(node)))
    return found


def unsized_by(pad: list) -> str:
    """What, beyond its shape, makes a pad's copper a shape not sized here, or '' for nothing."""
    chamfer = sexpr.child(pad, "chamfer")
    if chamfer is not None and len(chamfer) > 1:
        return "its corners are chamfered"
    if sexpr.child(pad, "padstack") is not None:
        return "its copper is set layer by layer"
    if sexpr.child(pad, "primitives") is not None:
        return "it carries custom copper"
    return ""


def pads(layout: list) -> List[Pad]:
    """Every pad on the board, of every footprint."""
    table = net_table(layout)
    found: List[Pad] = []
    for footprint in sexpr.children(layout, "footprint"):
        found += footprint_pads(footprint, table)
    return found


def by_net(placed_pads: Sequence[Pad]) -> Dict[str, List[Pad]]:
    """Each pad that carries a net, by net."""
    found: Dict[str, List[Pad]] = {}
    for pad in placed_pads:
        if pad.net:
            found.setdefault(pad.net, []).append(pad)
    return found


def net_pads(layout: list) -> Dict[str, List[Pad]]:
    """Every pad on the board that carries a net, by net."""
    return by_net(pads(layout))


# --- The shortest straight-line tree ------------------------------------------------


def spanning_tree(points: Sequence[Point]) -> Tuple[float, List[Tuple[int, int]]]:
    """The minimum spanning tree of `points` under straight-line distance: its total length and its edges.

    Each edge joins two of the points by their indices. Fewer than two points
    make a tree of no length and no edges.
    """
    count = len(points)
    if count < 2:
        return 0.0, []
    inside = [False] * count
    nearest = [math.inf] * count
    parent = [-1] * count
    nearest[0] = 0.0
    total, edges = 0.0, []
    for _ in range(count):
        index = min((i for i in range(count) if not inside[i]), key=lambda i: nearest[i])
        inside[index] = True
        if parent[index] >= 0:
            total += nearest[index]
            edges.append((parent[index], index))
        for other in range(count):
            if not inside[other]:
                distance = math.dist(points[index], points[other])
                if distance < nearest[other]:
                    nearest[other], parent[other] = distance, index
    return total, edges


def pad_tree(net_pads_: Sequence[Pad]) -> float:
    """The length of the shortest straight-line tree joining the centres of a net's pads."""
    return spanning_tree([pad.centre for pad in net_pads_])[0]


# --- Where copper meets ------------------------------------------------------------


def distance_to_segment(point: Point, a: Point, b: Point) -> float:
    """How far a point lies from the straight line from a to b."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    size = dx * dx + dy * dy
    t = 0.0 if size == 0 else max(0.0, min(1.0, ((point[0] - a[0]) * dx + (point[1] - a[1]) * dy) / size))
    return math.hypot(point[0] - (a[0] + t * dx), point[1] - (a[1] + t * dy))


def line_to_box(a: Point, b: Point, half_x: float, half_y: float) -> float:
    """How far the straight line from a to b passes from the rectangle about the origin of the given half-sides, 0 where it crosses it."""
    # Clip the line to the rectangle, grown by a hair so one of no width still holds a line crossing it.
    low, high = 0.0, 1.0
    for start, step, half in ((a[0], b[0] - a[0], half_x + CONTACT), (a[1], b[1] - a[1], half_y + CONTACT)):
        if step == 0:
            if abs(start) > half:
                break
            continue
        enter, leave = sorted(((-half - start) / step, (half - start) / step))
        low, high = max(low, enter), min(high, leave)
    else:
        if low <= high:
            return 0.0
    # Apart, the two come nearest at an end of the line or at a corner of the rectangle.
    corners = [(sx * half_x, sy * half_y) for sx in (-1, 1) for sy in (-1, 1)]
    ends = [math.hypot(max(abs(x) - half_x, 0.0), max(abs(y) - half_y, 0.0)) for x, y in (a, b)]
    return min(ends + [distance_to_segment(corner, a, b) for corner in corners])


def end_reaches(pad: Pad, end: Point, width: float) -> bool:
    """Whether a track's end, a round cap of half its width about its end point, reaches a pad's copper."""
    return pad.distance(end) <= width / 2 + CONTACT


def line_reaches(pad: Pad, a: Point, b: Point, width: float) -> bool:
    """Whether a straight piece of track, its centre line from a to b swept by half its width, reaches a pad's copper anywhere."""
    return pad.distance_to_line(a, b) <= width / 2 + CONTACT


def joins(pad: Pad, line: Sequence[Point], width: float) -> bool:
    """Whether a track along `line`, a centre line of straight pieces, is joined to a pad as KiCad's connectivity joins them.

    KiCad joins them when the cap at either end of the track reaches the pad's
    copper, or when the pad's centre lies on the track's copper.
    """
    return (end_reaches(pad, line[0], width) or end_reaches(pad, line[-1], width)
            or any(distance_to_segment(pad.centre, a, b) <= width / 2 + CONTACT for a, b in zip(line, line[1:])))
