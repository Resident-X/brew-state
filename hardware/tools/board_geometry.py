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
point, and KiCad's connectivity joins a track to a pad wherever the track's
copper reaches the pad's copper: by an end cap that reaches it, or by the
track running over it anywhere along its length, through the pad's centre or
off it. The tests hold that reading to the installed KiCad's own report. A pad's
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

import heapq
import math
from typing import Dict, List, Optional, Sequence, Set, Tuple

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
        #: The corner radius of a rounded rectangle, as a share of its shorter side.
        self.rounding = rounding
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

    def box(self) -> Tuple[float, float, float, float]:
        """The board's axes-aligned box about the pad's full size, turned as the pad is: (left, top, right, bottom)."""
        width, height = self.size
        cos, sin = abs(math.cos(math.radians(self.angle))), abs(math.sin(math.radians(self.angle)))
        half_x, half_y = (width * cos + height * sin) / 2, (width * sin + height * cos) / 2
        return self.centre[0] - half_x, self.centre[1] - half_y, self.centre[0] + half_x, self.centre[1] + half_y

    def outline(self, steps: int = 16) -> List[Point]:
        """The pad's copper as a convex polygon on the board, each rounded corner in `steps` pieces.

        A pad whose copper is not sized here is its full size's rectangle, the
        most it can be taken to cover without guessing at its shape.
        """
        half_x, half_y, radius = (self.size[0] / 2, self.size[1] / 2, 0.0) if self.unsized else self.core
        ring = []
        for quadrant, (sign_x, sign_y) in enumerate(((1, 1), (-1, 1), (-1, -1), (1, -1))):
            if radius <= 0:
                ring.append((sign_x * half_x, sign_y * half_y))
                continue
            for step in range(steps + 1):
                angle = math.radians(90 * (quadrant + step / steps))
                ring.append((sign_x * half_x + radius * math.cos(angle), sign_y * half_y + radius * math.sin(angle)))
        turned_ring = [turned(point, self.angle) for point in ring]
        return [(self.centre[0] + x, self.centre[1] + y) for x, y in turned_ring]

    def resized(self, size: Tuple[float, float], shape: Optional[str] = None) -> "Pad":
        """The same pad, in the same place, at another size, and in another shape where one is given.

        A pad given a shape is sized by it, so one whose copper is not sized
        here becomes the rectangle of its full size.
        """
        return Pad(self.reference, self.number, self.net, self.centre, size, self.angle, shape or self.shape, self.layers,
                   self.rounding, "" if shape else self.unsized)


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

    KiCad joins them wherever the track's copper reaches the pad's: the cap
    at either end reaching it, or any piece of the track running over it, off
    the pad's centre as much as through it.
    """
    if len(line) == 1:
        return end_reaches(pad, line[0], width)
    return any(line_reaches(pad, a, b, width) for a, b in zip(line, line[1:]))


# --- Copper as polygons --------------------------------------------------------------


Polygon = List[Point]


def polygon_area(polygon: Sequence[Point]) -> float:
    """The area a closed polygon encloses, whichever way round it is drawn."""
    return abs(sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(polygon, list(polygon[1:]) + list(polygon[:1])))) / 2


def clip_to_box(polygon: Sequence[Point], box: Tuple[float, float, float, float]) -> Polygon:
    """The part of a polygon inside an axes-aligned box (left, top, right, bottom), by clipping against one side at a time."""
    left, top, right, bottom = box
    sides = (
        (lambda p: p[0] - left, lambda a, b: (left, a[1] + (b[1] - a[1]) * (left - a[0]) / (b[0] - a[0]))),
        (lambda p: right - p[0], lambda a, b: (right, a[1] + (b[1] - a[1]) * (right - a[0]) / (b[0] - a[0]))),
        (lambda p: p[1] - top, lambda a, b: (a[0] + (b[0] - a[0]) * (top - a[1]) / (b[1] - a[1]), top)),
        (lambda p: bottom - p[1], lambda a, b: (a[0] + (b[0] - a[0]) * (bottom - a[1]) / (b[1] - a[1]), bottom)),
    )
    ring = list(polygon)
    for inside, cross in sides:
        kept: Polygon = []
        for a, b in zip(ring, ring[1:] + ring[:1]):
            if inside(a) >= 0:
                kept.append(a)
            if (inside(a) >= 0) != (inside(b) >= 0):
                kept.append(cross(a, b))
        ring = kept
        if not ring:
            break
    return ring


def overlap_area(polygon: Sequence[Point], window: Sequence[Point]) -> float:
    """How much of a polygon's area lies inside a convex window, by clipping against one side of the window at a time."""
    turn = 1 if sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(window, list(window[1:]) + list(window[:1]))) >= 0 else -1
    ring = list(polygon)
    for a, b in zip(window, list(window[1:]) + list(window[:1])):
        if not ring:
            break
        kept: Polygon = []
        for p, q in zip(ring, ring[1:] + ring[:1]):
            side_p, side_q = turn * orientation(a, b, p), turn * orientation(a, b, q)
            if side_p >= 0:
                kept.append(p)
            if (side_p >= 0) != (side_q >= 0):
                t = side_p / (side_p - side_q)
                kept.append((p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t))
        ring = kept
    return polygon_area(ring) if len(ring) > 2 else 0.0


def clipped_area(polygon: Sequence[Point], box: Tuple[float, float, float, float]) -> float:
    """How much of a polygon's area lies inside an axes-aligned box (left, top, right, bottom)."""
    ring = clip_to_box(polygon, box)
    return polygon_area(ring) if len(ring) > 2 else 0.0


def within(point: Point, polygon: Sequence[Point]) -> bool:
    """Whether a point lies inside a polygon by the even-odd rule, so inside a hole is outside."""
    inside = False
    for a, b in zip(polygon, list(polygon[1:]) + list(polygon[:1])):
        if (a[1] > point[1]) != (b[1] > point[1]) and point[0] < a[0] + (b[0] - a[0]) * (point[1] - a[1]) / (b[1] - a[1]):
            inside = not inside
    return inside


def disc(centre: Point, radius: float, steps: int = 64) -> Polygon:
    """A circle as a polygon of `steps` corners, one on each axis, so it never reaches past the circle."""
    return [(centre[0] + radius * math.cos(2 * math.pi * i / steps), centre[1] + radius * math.sin(2 * math.pi * i / steps))
            for i in range(steps)]


def swept(line: Sequence[Point], width: float, steps: int = 32) -> List[Polygon]:
    """The copper of a track along a centre line of straight pieces, `width` wide, as convex polygons that do not overlap:
    a rectangle for each piece and a half circle beyond each end of the line."""
    radius = width / 2
    pieces = [(a, b) for a, b in zip(line, line[1:]) if math.dist(a, b) > 0]
    if not pieces:
        return [disc(line[0], radius, 2 * steps)]
    found = []
    for a, b in pieces:
        length = math.dist(a, b)
        nx, ny = -(b[1] - a[1]) / length * radius, (b[0] - a[0]) / length * radius
        found.append([(a[0] + nx, a[1] + ny), (b[0] + nx, b[1] + ny), (b[0] - nx, b[1] - ny), (a[0] - nx, a[1] - ny)])
    for end, other in ((pieces[0][0], pieces[0][1]), (pieces[-1][1], pieces[-1][0])):
        heading = math.atan2(end[1] - other[1], end[0] - other[0])
        found.append([(end[0] + radius * math.cos(heading + math.pi * (i / steps - 0.5)),
                       end[1] + radius * math.sin(heading + math.pi * (i / steps - 0.5))) for i in range(steps + 1)])
    return found


def orientation(a: Point, b: Point, c: Point) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def segment_distance(a: Point, b: Point, c: Point, d: Point) -> float:
    """How far the straight line from a to b passes from the straight line from c to d, 0 where they cross."""
    if orientation(a, b, c) * orientation(a, b, d) < 0 and orientation(c, d, a) * orientation(c, d, b) < 0:
        return 0.0
    return min(distance_to_segment(c, a, b), distance_to_segment(d, a, b),
               distance_to_segment(a, c, d), distance_to_segment(b, c, d))


def polygon_distance(one: Sequence[Point], other: Sequence[Point]) -> float:
    """How far apart two simple polygons stand, convex or not, 0 where they touch, cross or one lies inside the other.

    A corner of either inside the other (by the even-odd rule, so inside a
    hole is outside) is contact; otherwise the polygons are apart by the least
    distance between a side of one and a side of the other.
    """
    if any(within(point, other) for point in one) or any(within(point, one) for point in other):
        return 0.0
    return min(segment_distance(a, b, c, d)
               for a, b in zip(one, list(one[1:]) + list(one[:1])) for c, d in zip(other, list(other[1:]) + list(other[:1])))


# --- The board outline and its slots ------------------------------------------------

#: How far an arc of the outline may lie off the straight pieces it is written as, in mm.
OUTLINE_SAG = 1e-3

#: How near the ends of two pieces of the outline must be to be one point, in mm.
OUTLINE_JOIN = 1e-4

#: How far every point of a closed cut-out may lie from one circle, in mm, for the cut-out to be a round hole.
ROUND_HOLE = 1e-3

#: The layer the board's outline and its cut-outs are drawn on.
OUTLINE_LAYER = "Edge.Cuts"


class Loop:
    """One closed line of the outline layer: its corners, and whether it is a round hole."""

    def __init__(self, points: Sequence[Point], round_: bool):
        self.points = list(points)
        self.round = round_
        xs, ys = [p[0] for p in self.points], [p[1] for p in self.points]
        self.bounds = (min(xs), min(ys), max(xs), max(ys))

    def area(self) -> float:
        return polygon_area(self.points)

    def label(self) -> str:
        left, top, right, bottom = self.bounds
        return f"the cut-out at ({(left + right) / 2:.2f}, {(top + bottom) / 2:.2f}) mm, {right - left:.2f} by {bottom - top:.2f} mm"


def circumcircle(a: Point, b: Point, c: Point) -> Optional[Tuple[Point, float]]:
    """The centre and radius of the circle through three points, or None where they lie on one line."""
    d = 2 * (a[0] * (b[1] - c[1]) + b[0] * (c[1] - a[1]) + c[0] * (a[1] - b[1]))
    if abs(d) < 1e-12:
        return None
    ux = ((a[0] ** 2 + a[1] ** 2) * (b[1] - c[1]) + (b[0] ** 2 + b[1] ** 2) * (c[1] - a[1])
          + (c[0] ** 2 + c[1] ** 2) * (a[1] - b[1])) / d
    uy = ((a[0] ** 2 + a[1] ** 2) * (c[0] - b[0]) + (b[0] ** 2 + b[1] ** 2) * (a[0] - c[0])
          + (c[0] ** 2 + c[1] ** 2) * (b[0] - a[0])) / d
    return (ux, uy), math.hypot(a[0] - ux, a[1] - uy)


def arc_points(start: Point, mid: Point, end: Point) -> List[Point]:
    """The points along an arc written as its start, a point on it and its end, no piece between two lying more than OUTLINE_SAG off it."""
    found = circumcircle(start, mid, end)
    if found is None:
        return [start, end]
    centre, radius = found
    first, through, last = (math.atan2(p[1] - centre[1], p[0] - centre[0]) for p in (start, mid, end))
    sweep = (last - first) % (2 * math.pi)
    if (through - first) % (2 * math.pi) > sweep:
        sweep -= 2 * math.pi
    step = 2 * math.acos(max(-1.0, 1 - OUTLINE_SAG / radius))
    pieces = max(8, math.ceil(abs(sweep) / step))
    points = [(centre[0] + radius * math.cos(first + sweep * i / pieces), centre[1] + radius * math.sin(first + sweep * i / pieces))
              for i in range(pieces + 1)]
    points[0], points[-1] = start, end
    return points


def circle_points(centre: Point, radius: float) -> List[Point]:
    """A circle as the corners of a polygon no side of which lies more than OUTLINE_SAG off it."""
    step = 2 * math.acos(max(-1.0, 1 - OUTLINE_SAG / radius)) if radius > OUTLINE_SAG else math.pi / 4
    pieces = max(16, math.ceil(2 * math.pi / step))
    return [(centre[0] + radius * math.cos(2 * math.pi * i / pieces), centre[1] + radius * math.sin(2 * math.pi * i / pieces))
            for i in range(pieces)]


def is_round(points: Sequence[Point]) -> bool:
    """Whether every corner of a closed line lies within ROUND_HOLE of one circle, as a circular hole's do."""
    if len(points) < 8:
        return False
    found = circumcircle(points[0], points[len(points) // 3], points[2 * len(points) // 3])
    if found is None:
        return False
    centre, radius = found
    return all(abs(math.dist(point, centre) - radius) <= ROUND_HOLE for point in points)


def outline_shapes(tree: list) -> List[Tuple[str, List[Point]]]:
    """Every shape drawn on the outline layer, as ('open' or 'closed', its corners): the layout's own and those of its footprints, placed."""
    found: List[Tuple[str, List[Point]]] = []

    def read(node: list, place, what: str) -> None:
        layer = sexpr.child(node, "layer")
        if layer is None or len(layer) < 2 or str(layer[1]) != OUTLINE_LAYER:
            return
        head = sexpr.head(node)
        if head in ("gr_line", "fp_line"):
            found.append(("open", [place(xy(sexpr.child(node, "start"), what)), place(xy(sexpr.child(node, "end"), what))]))
        elif head in ("gr_arc", "fp_arc"):
            found.append(("open", [place(p) for p in arc_points(xy(sexpr.child(node, "start"), what), xy(sexpr.child(node, "mid"), what),
                                                                xy(sexpr.child(node, "end"), what))]))
        elif head in ("gr_circle", "fp_circle"):
            centre, edge = xy(sexpr.child(node, "center"), what), xy(sexpr.child(node, "end"), what)
            found.append(("circle", [place(p) for p in circle_points(centre, math.dist(centre, edge))]))
        elif head in ("gr_rect", "fp_rect"):
            (x1, y1), (x2, y2) = xy(sexpr.child(node, "start"), what), xy(sexpr.child(node, "end"), what)
            found.append(("closed", [place(p) for p in ((x1, y1), (x2, y1), (x2, y2), (x1, y2))]))
        elif head in ("gr_poly", "fp_poly"):
            corners = sexpr.child(node, "pts")
            if corners is None or len(corners) < 4:
                raise Unreadable(f"{what} has a polygon on {OUTLINE_LAYER} with fewer than three corners")
            found.append(("closed", [place(xy(corner, what)) for corner in corners[1:]]))
        elif head in ("gr_curve", "fp_curve"):
            raise Unreadable(f"{what} draws a curve on {OUTLINE_LAYER}, which is not read; draw it as an arc")

    for node in tree[1:]:
        if isinstance(node, list) and sexpr.head(node).startswith("gr_"):
            read(node, lambda point: point, "the board outline")
    for footprint in sexpr.children(tree, "footprint"):
        name = reference(footprint) or "?"
        at = placement(footprint, f"the footprint {name}")
        for node in footprint[1:]:
            if isinstance(node, list) and sexpr.head(node).startswith("fp_"):
                read(node, lambda point, at=at: placed(point, at), f"the footprint {name}")
    return found


def edge_loops(tree: list) -> List[Loop]:
    """The closed lines the outline layer draws: the board's outline, its slots and its round holes.

    Lines and arcs are chained end to end, where their ends lie within
    OUTLINE_JOIN of one another, into closed lines; a circle, a rectangle and a
    polygon are each a closed line of their own. A chain that does not close
    raises Unreadable, since an outline that does not close has no inside.
    """
    loops: List[Loop] = []
    pieces: List[List[Point]] = []
    for kind, points in outline_shapes(tree):
        if kind == "open":
            pieces.append(points)
        else:
            loops.append(Loop(points, kind == "circle" or is_round(points)))
    while pieces:
        chain = pieces.pop(0)
        while math.dist(chain[0], chain[-1]) > OUTLINE_JOIN:
            for index, piece in enumerate(pieces):
                if math.dist(piece[0], chain[-1]) <= OUTLINE_JOIN:
                    chain += piece[1:]
                elif math.dist(piece[-1], chain[-1]) <= OUTLINE_JOIN:
                    chain += piece[-2::-1]
                else:
                    continue
                del pieces[index]
                break
            else:
                where = f"({chain[0][0]:g}, {chain[0][1]:g}) mm"
                raise Unreadable(f"the lines drawn on {OUTLINE_LAYER} from {where} do not close into an outline or a cut-out")
        loops.append(Loop(chain[:-1], is_round(chain[:-1])))
    return loops


def barrier_slots(tree: list) -> List[Loop]:
    """The closed cut-outs inside the board's outline that are not round holes.

    The outline is the closed line enclosing the most area; a notch that
    reaches it is part of it and is not a slot.
    """
    loops = edge_loops(tree)
    if len(loops) < 2:
        return []
    outline = max(loops, key=Loop.area)
    return [loop for loop in loops if loop is not outline and not loop.round and within(loop.points[0], outline.points)]


# --- Nearness of large polygons ---------------------------------------------------------

#: The corners above which a polygon is indexed by a grid of its sides rather than walked side by side.
INDEXED_CORNERS = 64

#: The cells of the grid a large polygon's sides are held in, along its longer axis.
GRID_CELLS = 64

INFINITE = float("inf")


class Shape:
    """The polygons of one piece of copper, a large one indexed by a grid of its sides so a nearby side is found without walking them all."""

    def __init__(self, polygons: Sequence[Sequence[Point]]):
        self.polygons = [list(polygon) for polygon in polygons]
        points = [point for polygon in self.polygons for point in polygon]
        self.bounds = (min(x for x, _ in points), min(y for _, y in points), max(x for x, _ in points), max(y for _, y in points))
        self.corners = len(points)
        self.sides: List[Tuple[Point, Point]] = []
        self.grid: Dict[Tuple[int, int], List[int]] = {}
        self.rows: Dict[int, List[int]] = {}
        self.size = 1.0
        if self.corners > INDEXED_CORNERS:
            left, top, right, bottom = self.bounds
            self.size = max((right - left), (bottom - top), 1e-6) / GRID_CELLS
            for polygon in self.polygons:
                for a, b in zip(polygon, polygon[1:] + polygon[:1]):
                    index = len(self.sides)
                    self.sides.append((a, b))
                    for row in range(self.cell(min(a[1], b[1])), self.cell(max(a[1], b[1])) + 1):
                        self.rows.setdefault(row, []).append(index)
                        for column in range(self.cell(min(a[0], b[0])), self.cell(max(a[0], b[0])) + 1):
                            self.grid.setdefault((column, row), []).append(index)

    def cell(self, value: float) -> int:
        return math.floor(value / self.size)

    def indexed(self) -> bool:
        return bool(self.sides)

    def edges(self) -> List[Tuple[Point, Point]]:
        if self.sides:
            return self.sides
        return [(a, b) for polygon in self.polygons for a, b in zip(polygon, polygon[1:] + polygon[:1])]

    def near(self, box: Tuple[float, float, float, float], reach: float) -> List[Tuple[Point, Point]]:
        """The sides that may lie within `reach` of a box: every one whose cell the box grown by `reach` meets."""
        if not self.sides:
            return self.edges()
        left, top, right, bottom = box[0] - reach, box[1] - reach, box[2] + reach, box[3] + reach
        found = set()
        for column in range(self.cell(left), self.cell(right) + 1):
            for row in range(self.cell(top), self.cell(bottom) + 1):
                found.update(self.grid.get((column, row), ()))
        return [self.sides[index] for index in sorted(found)]

    def contains(self, point: Point) -> bool:
        """Whether a point is inside the polygons by the even-odd rule, for the polygons taken together."""
        if not (self.bounds[0] <= point[0] <= self.bounds[2] and self.bounds[1] <= point[1] <= self.bounds[3]):
            return False
        if not self.sides:
            return any(within(point, polygon) for polygon in self.polygons)
        inside = False
        for index in self.rows.get(self.cell(point[1]), ()):
            a, b = self.sides[index]
            if (a[1] > point[1]) != (b[1] > point[1]) and point[0] < a[0] + (b[0] - a[0]) * (point[1] - a[1]) / (b[1] - a[1]):
                inside = not inside
        return inside


def apart(one: Shape, other: Shape, reach: float) -> bool:
    """Whether the boxes of two shapes, one grown by `reach`, miss one another."""
    return (one.bounds[0] > other.bounds[2] + reach or one.bounds[2] < other.bounds[0] - reach
            or one.bounds[1] > other.bounds[3] + reach or one.bounds[3] < other.bounds[1] - reach)


def shape_distance(one: Shape, other: Shape, reach: float) -> float:
    """How far apart two shapes stand where that is under `reach`, 0 where they touch, cross or one lies inside the other.

    Where they stand `reach` or more apart the result is at least `reach`, and
    may be infinite. A large shape is walked only where the other lies within
    `reach` of it, so the result is polygon_distance's wherever that is under
    `reach`.
    """
    if apart(one, other, reach):
        return INFINITE
    small, large = (one, other) if one.corners <= other.corners else (other, one)
    corners = [point for polygon in small.polygons for point in polygon]
    if any(large.contains(point) for point in corners):
        return 0.0
    box = small.bounds
    nearer = [side[0] for side in large.near(box, 0.0) if box[0] <= side[0][0] <= box[2] and box[1] <= side[0][1] <= box[3]]
    if any(small.contains(point) for point in nearer):
        return 0.0
    best = INFINITE
    pieces = [(c, d, (min(c[0], d[0]), min(c[1], d[1]), max(c[0], d[0]), max(c[1], d[1]))) for c, d in small.edges()]
    for a, b in large.near(small.bounds, reach):
        for c, d, box_ in pieces:
            if side_gap(a, b, box_) >= min(best, reach):
                continue
            best = min(best, segment_distance(a, b, c, d))
    return best


def side_gap(a: Point, b: Point, box: Tuple[float, float, float, float]) -> float:
    """A lower bound on how far the straight line from a to b stands from a box (left, top, right, bottom): the gap between their boxes."""
    gap_x = max(min(a[0], b[0]) - box[2], box[0] - max(a[0], b[0]), 0.0)
    gap_y = max(min(a[1], b[1]) - box[3], box[1] - max(a[1], b[1]), 0.0)
    return math.hypot(gap_x, gap_y)


def closest_points(one: Point, two: Point, three: Point, four: Point) -> Tuple[float, Point, Point]:
    """The least distance between two straight lines, from a to b and from c to d, and a point of each where they stand that far apart."""
    if orientation(one, two, three) * orientation(one, two, four) < 0 and orientation(three, four, one) * orientation(three, four, two) < 0:
        t = orientation(three, four, one) / (orientation(three, four, one) - orientation(three, four, two))
        crossing = (one[0] + (two[0] - one[0]) * t, one[1] + (two[1] - one[1]) * t)
        return 0.0, crossing, crossing
    best: Tuple[float, Point, Point] = (INFINITE, one, three)
    for point, start, end, flip in ((three, one, two, False), (four, one, two, False), (one, three, four, True), (two, three, four, True)):
        foot = nearest_on_segment(point, start, end)
        distance = math.dist(point, foot)
        if distance < best[0]:
            best = (distance, foot, point) if not flip else (distance, point, foot)
    return best


def nearest_on_segment(point: Point, a: Point, b: Point) -> Point:
    """The point of the straight line from a to b nearest `point`."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    length = dx * dx + dy * dy
    if length == 0:
        return a
    t = max(0.0, min(1.0, ((point[0] - a[0]) * dx + (point[1] - a[1]) * dy) / length))
    return a[0] + dx * t, a[1] + dy * t


#: How far a turn may be from nought, in mm squared, to count as no turn.
STRAIGHT = 1e-9


def crosses(a: Point, b: Point, c: Point, d: Point) -> bool:
    """Whether the straight line from a to b crosses that from c to d properly, one passing through the other and not merely meeting it."""
    first, second = orientation(a, b, c), orientation(a, b, d)
    third, fourth = orientation(c, d, a), orientation(c, d, b)
    return ((first > STRAIGHT and second < -STRAIGHT) or (first < -STRAIGHT and second > STRAIGHT)) and (
        (third > STRAIGHT and fourth < -STRAIGHT) or (third < -STRAIGHT and fourth > STRAIGHT))


def blocked(a: Point, b: Point, slots: Sequence[Sequence[Point]]) -> bool:
    """Whether the straight line from a to b passes through the inside of any slot, running along or touching a wall being open."""
    middle = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
    for slot in slots:
        ring = list(zip(slot, slot[1:] + slot[:1]))
        if any(crosses(a, b, c, d) for c, d in ring):
            return True
        if within(middle, slot) and min(distance_to_segment(middle, c, d) for c, d in ring) > 1e-7:
            return True
    return False


def route_length(first: Shape, second: Shape, slots: Sequence[Loop], reach: float,
                 straight: Optional[float] = None) -> Tuple[float, int]:
    """The shortest way from one piece of copper to another seen from above that does not cross a slot, and how many slots it goes round.

    A way is a run of straight lines, each clear of every slot's inside, that
    bends only at a corner of a slot; the ends are the nearest points of the
    two pieces the first and last lines meet, so a slot corner is the only
    place a way can turn. Where no slot lies within `reach` of the pieces the
    way is the straight line between them. The length is exact for the polygons
    given, not gridded. The count is of the slots a corner of which the way
    turns at. `straight` is the distance between the pieces where that is known.
    """
    box = (min(first.bounds[0], second.bounds[0]) - reach, min(first.bounds[1], second.bounds[1]) - reach,
           max(first.bounds[2], second.bounds[2]) + reach, max(first.bounds[3], second.bounds[3]) + reach)
    near = [slot for slot in slots if slot.bounds[0] <= box[2] and slot.bounds[2] >= box[0]
            and slot.bounds[1] <= box[3] and slot.bounds[3] >= box[1]]
    straight = shape_distance(first, second, reach) if straight is None else straight
    if not near or straight >= reach:
        return straight, 0
    rings = [slot.points for slot in near]
    best = INFINITE
    first_sides = first.near(second.bounds, reach)
    second_sides = second.near(first.bounds, reach)
    seconds = [(c, d, (min(c[0], d[0]), min(c[1], d[1]), max(c[0], d[0]), max(c[1], d[1]))) for c, d in second_sides]
    for a, b in first_sides:
        for c, d, box_ in seconds:
            if side_gap(a, b, box_) >= min(best, reach):
                continue
            distance, p, q = closest_points(a, b, c, d)
            if distance < best and not blocked(p, q, rings):
                best = distance
    nodes = [(index, corner) for index, ring in enumerate(rings) for corner in ring]

    def reaching(sides: Sequence[Tuple[Point, Point]], corner: Point) -> float:
        found = INFINITE
        for a, b in sides:
            foot = nearest_on_segment(corner, a, b)
            distance = math.dist(corner, foot)
            if distance < min(found, reach) and not blocked(corner, foot, rings):
                found = distance
        return found

    start = [reaching(first_sides, corner) for _, corner in nodes]
    finish = [reaching(second_sides, corner) for _, corner in nodes]
    cost = {position: (start[position], frozenset([nodes[position][0]]) if start[position] < INFINITE else frozenset())
            for position in range(len(nodes))}
    settled: Set[int] = set()
    queue = [(cost[position][0], position) for position in cost if cost[position][0] < INFINITE]
    heapq.heapify(queue)
    found: Tuple[float, int] = (best, 0)
    while queue:
        distance, position = heapq.heappop(queue)
        if position in settled or distance >= found[0]:
            continue
        settled.add(position)
        if distance + finish[position] < found[0]:
            found = (distance + finish[position], len(cost[position][1]))
        for other in range(len(nodes)):
            if other in settled:
                continue
            step = math.dist(nodes[position][1], nodes[other][1])
            if distance + step < cost[other][0] and not blocked(nodes[position][1], nodes[other][1], rings):
                cost[other] = (distance + step, cost[position][1] | {nodes[other][0]})
                heapq.heappush(queue, (distance + step, other))
    return found
