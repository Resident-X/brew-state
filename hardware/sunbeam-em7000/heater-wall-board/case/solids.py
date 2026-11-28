"""Solid and polygon helpers shared by the case model, its core rules and its skins.

Everything here is geometry only: boxes, prisms from plan polygons, chamfered prisms, offsets of plan polygons and the
tessellation the checks and renders work on. Plan polygons are lists of (u, v) points in millimetres.
"""

from __future__ import annotations

import math
from typing import Any, List, Optional, Sequence, Tuple

import numpy as np
import trimesh
from OCP.BRep import BRep_Tool
from OCP.TopAbs import TopAbs_FACE, TopAbs_Orientation
from OCP.TopExp import TopExp_Explorer
from OCP.TopLoc import TopLoc_Location
from OCP.TopoDS import TopoDS
from build123d import Box, Cylinder, Face, Part, Plane, Polygon, Pos, Rot, Shell, Solid, Vector, Wire, extrude


def box(u0: float, u1: float, v0: float, v1: float, z0: float, z1: float) -> Part:
    return Pos((u0 + u1) / 2, (v0 + v1) / 2, (z0 + z1) / 2) * Box(u1 - u0, v1 - v0, z1 - z0)


def ccw(points: Sequence[Tuple[float, float]]) -> List[Tuple[float, float]]:
    """The corners counter-clockwise, which fixes the side a face extrudes to."""
    pts = [tuple(p) for p in points]
    area = sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(pts, pts[1:] + pts[:1]))
    return pts if area > 0 else pts[::-1]


def prism(points: Sequence[Tuple[float, float]], z0: float, z1: float) -> Part:
    """A polygon given in (u, v) lifted from z0 to z1."""
    return extrude(Pos(0, 0, z0) * Polygon(*ccw(points), align=None), z1 - z0)


def prism_vz(points: Sequence[Tuple[float, float]], u0: float, u1: float) -> Part:
    """A polygon given in (v, z) extruded along u from u0 to u1."""
    return extrude(Plane.YZ.offset(u0) * Polygon(*ccw(points), align=None), u1 - u0)


def prism_uz(points: Sequence[Tuple[float, float]], v0: float, v1: float) -> Part:
    """A polygon given in (u, z) extruded along v from v0 to v1."""
    return extrude(Plane.XZ.offset(-v1) * Polygon(*ccw(points), align=None), v1 - v0)


def cyl_v(u: float, z: float, v0: float, v1: float, radius: float) -> Part:
    return Pos(u, (v0 + v1) / 2, z) * Rot(X=90) * Cylinder(radius, v1 - v0)


def tear_v(u: float, z: float, v0: float, v1: float, radius: float) -> Part:
    """A hole along v with a 45 degree point on its roof, so it prints without support or a bridge."""
    k = 0.8 * radius
    pts = [(u - k, z), (u + k, z), (u + k, z + 0.6 * radius), (u, z + 1.55 * radius), (u - k, z + 0.6 * radius)]
    return cyl_v(u, z, v0, v1, radius) + prism_uz(pts, v0, v1)


def tear_point_v(u: float, z: float, v0: float, v1: float, radius: float) -> Part:
    """A hole along v whose roof is the true tear-drop: two 45 degree tangents to the circle meeting at a point radius x sqrt(2) above its axis."""
    k = radius * math.sqrt(0.5)
    return cyl_v(u, z, v0, v1, radius) + prism_uz([(u - k, z), (u + k, z), (u + k, z + k), (u, z + radius * math.sqrt(2.0)), (u - k, z + k)], v0, v1)


def cyl_z(u: float, v: float, z0: float, z1: float, radius: float) -> Part:
    return Pos(u, v, (z0 + z1) / 2) * Cylinder(radius, z1 - z0)


def fuse(shapes: Sequence[Any]) -> Any:
    shapes = [s for s in shapes if s is not None]
    result = shapes[0]
    for shape in shapes[1:]:
        result = result + shape
    return result


def chamfered(points: Sequence[Tuple[float, float]], size: float, keep_square_at_v: Optional[float] = None) -> List[Tuple[float, float]]:
    """A counter-clockwise polygon with each convex corner cut by a chamfer of the given leg, except corners at the given v."""
    n = len(points)
    out: List[Tuple[float, float]] = []
    for i in range(n):
        p0, p1, p2 = points[i - 1], points[i], points[(i + 1) % n]
        a = (p1[0] - p0[0], p1[1] - p0[1])
        b = (p2[0] - p1[0], p2[1] - p1[1])
        cross = a[0] * b[1] - a[1] * b[0]
        if cross > 1e-9 and not (keep_square_at_v is not None and abs(p1[1] - keep_square_at_v) < 1e-6):
            la, lb = math.hypot(*a), math.hypot(*b)
            s = min(size, la / 2 - 1e-6, lb / 2 - 1e-6)
            out.append((p1[0] - a[0] / la * s, p1[1] - a[1] / la * s))
            out.append((p1[0] + b[0] / lb * s, p1[1] + b[1] / lb * s))
        else:
            out.append(p1)
    return out


def clean_polygon(points: Sequence[Tuple[float, float]], tol: float = 1e-6) -> List[Tuple[float, float]]:
    """A counter-clockwise polygon without repeated points and without points that lie on the line of their neighbours."""
    pts = ccw(points)
    out: List[Tuple[float, float]] = []
    for p in pts:
        if not out or math.dist(out[-1], p) > tol:
            out.append(p)
    if len(out) > 1 and math.dist(out[0], out[-1]) <= tol:
        out.pop()
    changed = True
    while changed and len(out) > 3:
        changed = False
        for i in range(len(out)):
            a, b, c = out[i - 1], out[i], out[(i + 1) % len(out)]
            cross = (b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0])
            dot = (b[0] - a[0]) * (c[0] - b[0]) + (b[1] - a[1]) * (c[1] - b[1])
            if abs(cross) <= tol and dot > 0:
                del out[i]
                changed = True
                break
    return out


def offset_polygon(points: Sequence[Tuple[float, float]], d: Any) -> List[Tuple[float, float]]:
    """A counter-clockwise polygon moved inward by d on every side, each corner a mitre of its two moved sides.

    d is one distance or a list with one distance for each side (side i runs from point i to point i + 1).
    """
    pts = [tuple(p) for p in points]
    n = len(pts)
    ds = [float(d)] * n if isinstance(d, (int, float)) else [float(x) for x in d]
    lines = []
    for i in range(n):
        (x0, y0), (x1, y1) = pts[i], pts[(i + 1) % n]
        dx, dy = x1 - x0, y1 - y0
        length = math.hypot(dx, dy)
        nx, ny = -dy / length, dx / length
        lines.append(((x0 + nx * ds[i], y0 + ny * ds[i]), (dx / length, dy / length), (nx, ny)))
    out = []
    for i in range(n):
        (p, a, na), (q, b, nb) = lines[i - 1], lines[i]
        cross = a[0] * b[1] - a[1] * b[0]
        if abs(cross) < 1e-9:
            out.append((pts[i][0] + nb[0] * ds[i], pts[i][1] + nb[1] * ds[i]))
            continue
        t = ((q[0] - p[0]) * b[1] - (q[1] - p[1]) * b[0]) / cross
        out.append((p[0] + a[0] * t, p[1] + a[1] * t))
    return out


def _ring(points: Sequence[Tuple[float, float]], z: float) -> Wire:
    return Wire.make_polygon([Vector(x, y, z) for x, y in points], close=True)


def frustum(lo: Sequence[Tuple[float, float]], z_lo: float, hi: Sequence[Tuple[float, float]], z_hi: float) -> Solid:
    """The solid between two plan polygons with the same number of corners at two heights, every face planar.

    Each side is a trapezoid, which is planar when the corresponding sides of the two polygons are parallel, as they are
    for an offset_polygon of the other. Planar faces keep exact distances between solids fast.
    """
    n = len(lo)
    faces = [Face(_ring(lo, z_lo)), Face(_ring(hi, z_hi))]
    for i in range(n):
        j = (i + 1) % n
        quad = [Vector(*lo[i], z_lo), Vector(*lo[j], z_lo), Vector(*hi[j], z_hi), Vector(*hi[i], z_hi)]
        faces.append(Face(Wire.make_polygon(quad, close=True)))
    return Solid(Shell(faces))


def polyhedron_between(lo: Sequence[Tuple[float, float]], z_lo: float, hi: Sequence[Tuple[float, float]], z_hi: float) -> Solid:
    """Like frustum for rings whose sides need not be parallel: a side that is not planar is split into two triangles."""
    n = len(lo)
    faces = [Face(_ring(lo, z_lo)), Face(_ring(hi, z_hi))]
    for i in range(n):
        j = (i + 1) % n
        a, b, c, d = (Vector(*lo[i], z_lo), Vector(*lo[j], z_lo), Vector(*hi[j], z_hi), Vector(*hi[i], z_hi))
        normal = (b - a).cross(d - a)
        flat = abs((c - a).dot(normal)) < 1e-9 * max(1.0, normal.length)
        if flat:
            faces.append(Face(Wire.make_polygon([a, b, c, d], close=True)))
        else:
            faces.append(Face(Wire.make_polygon([a, b, c], close=True)))
            faces.append(Face(Wire.make_polygon([a, c, d], close=True)))
    return Solid(Shell(faces))


def chamfer_prism(points: Sequence[Tuple[float, float]], z0: float, z1: float, top: float = 0.0, bottom: float = 0.0,
                  square_at_v: Optional[float] = None) -> Part:
    """A prism of a counter-clockwise plan polygon from z0 to z1 with a 45 degree chamfer of the given leg round its top
    perimeter and round its bottom perimeter; a side of the polygon that lies on the line v = square_at_v keeps its bottom edge square."""
    pts = clean_polygon(points)
    zl, zh = z0 + bottom, z1 - top
    parts = [prism(pts, zl, zh)] if zh - zl > 1e-6 else []
    if bottom > 0:
        n = len(pts)
        dists = [0.0 if (square_at_v is not None and abs(pts[i][1] - square_at_v) < 1e-6 and abs(pts[(i + 1) % n][1] - square_at_v) < 1e-6)
                 else bottom for i in range(n)]
        parts.append(frustum(offset_polygon(pts, dists), z0, pts, zl))
    if top > 0:
        parts.append(frustum(pts, zh, offset_polygon(pts, top), z1))
    return fuse(parts)


def chamfer_top(points: Sequence[Tuple[float, float]], z0: float, z1: float, ch: float) -> Part:
    """A prism from z0 to z1 whose top perimeter carries a 45 degree chamfer of leg ch."""
    return chamfer_prism(points, z0, z1, top=ch)


def triangulation(shape: Any, tolerance: float, angular: float) -> Tuple[np.ndarray, np.ndarray]:
    """The shape's triangulation as vertex and triangle arrays, read straight from the kernel's face triangulations.

    The same vertices and triangles, in the same order, as the shape's own `tessellate`, without building a Python
    vector object for every node, which makes that call cost minutes on a part of tens of thousands of triangles.
    """
    shape.mesh(tolerance, angular)
    explorer = TopExp_Explorer(shape.wrapped, TopAbs_FACE)
    faces, seen = [], set()
    while explorer.More():
        face = TopoDS.Face(explorer.Current())
        key = hash(face)
        if key not in seen:
            seen.add(key)
            faces.append(face)
        explorer.Next()
    vertices: List[Tuple[float, float, float]] = []
    triangles: List[Tuple[int, int, int]] = []
    offset = 0
    for face in faces:
        location = TopLoc_Location()
        poly = BRep_Tool.Triangulation_s(face, location)
        if poly is None:
            continue
        transform = location.Transformation()
        count = poly.NbNodes()
        for k in range(1, count + 1):
            node = poly.Node(k).Transformed(transform)
            vertices.append((node.X(), node.Y(), node.Z()))
        reverse = face.Orientation() == TopAbs_Orientation.TopAbs_REVERSED
        for k in range(1, poly.NbTriangles() + 1):
            tri = poly.Triangle(k)
            a, b, c = tri.Value(1) + offset - 1, tri.Value(2) + offset - 1, tri.Value(3) + offset - 1
            triangles.append((a, c, b) if reverse else (a, b, c))
        offset += count
    return np.array(vertices, dtype=float).reshape(-1, 3), np.array(triangles, dtype=int).reshape(-1, 3)


def to_mesh(shape: Any, tolerance: float = 0.02, angular: float = 0.2) -> trimesh.Trimesh:
    vertices, triangles = triangulation(shape, tolerance, angular)
    mesh = trimesh.Trimesh(vertices=vertices, faces=triangles, process=True)
    mesh.merge_vertices()
    mesh.update_faces(mesh.nondegenerate_faces())
    mesh.remove_unreferenced_vertices()
    return mesh
