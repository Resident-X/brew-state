"""Where a board's pads sit, how far apart a net's pads are, and the shortest straight-line tree joining them.

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
                 angle: float, shape: str, layers: Sequence[str]):
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

    def contains(self, point: Point, margin: float = 1e-6) -> bool:
        """Whether a board point lies on the pad's copper.

        A circle is read as a circle and an oval as the rounded shape it is; a
        rectangle, a rounded or chamfered rectangle, a trapezoid and a custom
        shape are read as the rectangle of the pad's size, which bounds each.
        """
        x, y = self.local(point)
        width, height = self.size
        if self.shape == "circle":
            return math.hypot(x, y) <= width / 2 + margin
        if self.shape == "oval":
            radius = min(width, height) / 2
            reach_x, reach_y = max(width / 2 - radius, 0.0), max(height / 2 - radius, 0.0)
            return math.hypot(max(abs(x) - reach_x, 0.0), max(abs(y) - reach_y, 0.0)) <= radius + margin
        return abs(x) <= width / 2 + margin and abs(y) <= height / 2 + margin

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
        found.append(Pad(name, str(node[1]) if len(node) > 1 else "", item_net(node, table, what), centre,
                         (width, height), angle, str(node[3]) if len(node) > 3 else "",
                         [str(layer) for layer in (layers or [])[1:]]))
    return found


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
