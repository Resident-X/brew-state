#!/usr/bin/env python3
"""The geometric check of the printed case: one named check for each clause the model can decide.

    python check.py                      text report of every check at the nominal seating
    python check.py --format json        the same as one JSON object
    python check.py --json-out out/check.json
    python check.py --range              also rebuild at every extreme of the seating range and check each
    python check.py --set seating.lean_deg=1.0

The exit status is 0 when every check passes and 1 when any fails. A check that cannot be made
stops the run with a message and exit status 2. Distances between solids are exact (OpenCascade)
unless a check says it works on the tessellation, which is at 0.02 mm chord tolerance.
"""

from __future__ import annotations

import argparse
import itertools
import json
import math
import os
import sys
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
# build123d must load before vtk: with the other order its tessellation runs about ten times slower
import case  # noqa: E402,I001

import numpy as np  # noqa: E402
import shapely  # noqa: E402
import trimesh  # noqa: E402
import vtk  # noqa: E402
import pyvista as pv  # noqa: E402
from OCP.BRepClass3d import BRepClass3d_SolidClassifier  # noqa: E402
from OCP.TopAbs import TopAbs_State  # noqa: E402
from OCP.gp import gp_Pnt  # noqa: E402
from shapely.geometry import LineString, Point, Polygon as ShPolygon, box as sh_box  # noqa: E402
from shapely.ops import unary_union  # noqa: E402

TRACE = "SOL-HW-HEATER-WALL-BOARD-PRINTED-CASE-DESIGNED-TO-THE-REQUIREMENTS-THE-BOARD-RELIES-ON"
TOL_MESH = 0.02          # chord tolerance of every tessellation used by a check
SWEEP_FLOOR = 0.05       # the least clearance the lid sweep may leave anywhere along its path


# ---------------------------------------------------------------------------------------------------------------------
# Result handling
# ---------------------------------------------------------------------------------------------------------------------

def result(name: str, criterion: str, passed: bool, summary: str, figures: Optional[Dict[str, Any]] = None,
           lines: Optional[List[str]] = None) -> Dict[str, Any]:
    return {"name": name, "criterion": criterion, "kind": "check", "passed": bool(passed), "summary": summary,
            "figures": figures or {}, "lines": lines or []}


def finding(name: str, criterion: str, summary: str, figures: Optional[Dict[str, Any]] = None,
            lines: Optional[List[str]] = None) -> Dict[str, Any]:
    """A stated, accepted residual: its figures are computed and reported, it has no verdict (`passed` is null), and it is
    counted neither in the pass count nor in the exit status."""
    return {"name": name, "criterion": criterion, "kind": "finding", "passed": None, "summary": summary,
            "figures": figures or {}, "lines": lines or []}


def verdicts(results: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """The results that carry a pass or fail: every check, no finding."""
    return [r for r in results if r.get("kind", "check") != "finding"]


def jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(v) for v in value]
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, float):
        return round(value, 4)
    return value


# ---------------------------------------------------------------------------------------------------------------------
# Shared geometry helpers
# ---------------------------------------------------------------------------------------------------------------------

class Scene:
    """Triangle meshes of the assembled case, ray-cast with a static cell locator."""

    def __init__(self, m: case.Model, names: Sequence[str], form: str = "single"):
        meshes, labels = [], []
        for name in names:
            tm = m.mesh(name)
            meshes.append(tm)
            labels.append(np.full(len(tm.faces), len(labels)))
        self.names = list(names)
        self.mesh = trimesh.util.concatenate(meshes)
        self.face_label = np.concatenate([np.full(len(t.faces), i) for i, t in enumerate(meshes)])
        faces = np.hstack([np.full((len(self.mesh.faces), 1), 3), self.mesh.faces]).ravel()
        self.poly = pv.PolyData(np.asarray(self.mesh.vertices), faces)
        self.locator = vtk.vtkStaticCellLocator()
        self.locator.SetDataSet(self.poly)
        self.locator.BuildLocator()
        self.normals = self.mesh.face_normals

    def closest_distances(self, points: np.ndarray) -> np.ndarray:
        """The distance from each point to the nearest triangle of the scene."""
        out = np.empty(len(points))
        cp, cid, sub, d2 = [0.0] * 3, vtk.mutable(0), vtk.mutable(0), vtk.mutable(0.0)
        for i, p in enumerate(points):
            self.locator.FindClosestPoint([float(p[0]), float(p[1]), float(p[2])], cp, cid, sub, d2)
            out[i] = math.sqrt(float(d2))
        return out

    def first_hit(self, origin: Sequence[float], direction: Sequence[float], length: float = 400.0) -> Optional[Dict[str, Any]]:
        d = np.asarray(direction, dtype=float)
        d = d / np.linalg.norm(d)
        a = np.asarray(origin, dtype=float)
        b = a + d * length
        t, x, pc = vtk.mutable(0.0), [0.0] * 3, [0.0] * 3
        sub, cid = vtk.mutable(0), vtk.mutable(0)
        if not self.locator.IntersectWithLine(a.tolist(), b.tolist(), 1e-7, t, x, pc, sub, cid):
            return None
        return {"distance": float(t) * length, "point": tuple(x), "solid": self.names[self.face_label[int(cid)]],
                "normal": tuple(self.normals[int(cid)])}


_SCENES: Dict[Tuple[int, str], Scene] = {}


def scene(m: case.Model, form: str = "single") -> Scene:
    key = (id(m), form)
    if key not in _SCENES:
        names = ["tray", f"lid_{form}", "plate"] + list(m.bodies.keys())
        _SCENES[key] = Scene(m, names, form)
    return _SCENES[key]


def mains_arrays(m: case.Model) -> Dict[str, Tuple[np.ndarray, List[str]]]:
    """Mains-family copper per layer: a geometry array and the item labels, in the board's own untilted frame."""
    found = {}
    for layer in ("F.Cu", "B.Cu"):
        items = [i for i in m.board.mains_items if i["layer"] == layer]
        found[layer] = (np.array([i["geom"] for i in items], dtype=object), [i["label"] for i in items])
    return found


def copper_distance(m: case.Model, points: Sequence[Tuple[float, float, float, float]],
                    layers: Sequence[str] = ("F.Cu", "B.Cu")) -> Dict[str, Tuple[float, str]]:
    """Per layer, the least 3D distance from a set of case points (u, v, z, radius of the metal about it) to Mains-family copper.

    The copper lies in the board's own frame, so each point is carried into that frame first (the lean).
    The metal about a point is treated as a sphere of its radius: a conservative figure for a screw.
    """
    arrays = mains_arrays(m)
    t = m.board.thickness
    out = {}
    for layer in layers:
        geoms, labels = arrays[layer]
        zc = 0.0 if layer == "F.Cu" else -t
        best = (float("inf"), "")
        for (u, v, z, r) in points:
            lu, lv, lz = m.board_local((u, v, z))
            planar = shapely.distance(geoms, Point(lu, lv))
            dz = abs(lz - zc)
            d3 = np.sqrt(planar ** 2 + dz ** 2) - r
            k = int(np.argmin(d3))
            if d3[k] < best[0]:
                best = (float(d3[k]), labels[k])
        out[layer] = best
    return out


def axis_points(screw: Dict[str, Any], step: float = 0.25) -> List[Tuple[float, float, float, float]]:
    """Sample points along a screw's axis with the radius of the metal at each (the head is wider)."""
    pts = []
    if screw["axis"] == "z":
        z0, z1 = screw["z0"], screw["z1"]
        n = max(int((z1 - z0) / step), 1)
        for i in range(n + 1):
            z = z0 + (z1 - z0) * i / n
            r = screw["radius"] if z < z1 - 2.0 + 1e-9 else screw["head_radius"]
            pts.append((screw["u"], screw["v"], z, r))
    else:
        v0, v1 = screw["v0"], screw["v1"]
        n = max(int((v1 - v0) / step), 1)
        for i in range(n + 1):
            v = v0 + (v1 - v0) * i / n
            in_head = ("head_v0" in screw) and screw["head_v0"] - 1e-9 <= v <= screw["head_v1"] + 1e-9
            pts.append((screw["u"], v, screw["z"], screw["head_radius"] if in_head else screw["radius"]))
    return pts


def tray_top_at(sc: Scene, u: float, v: float, z_from: float = 40.0) -> Optional[float]:
    hit = sc.first_hit((u, v, z_from), (0, 0, -1))
    return None if hit is None else z_from - hit["distance"]


def point_in_solid(classifier: BRepClass3d_SolidClassifier, u: float, v: float, z: float, tolerance: float = 1.0e-6) -> bool:
    """Whether a point lies in, or on a face of, the solid a classifier was made for: the test of the solid's own `is_inside`, with the classifier kept between points."""
    classifier.Perform(gp_Pnt(u, v, z), tolerance)
    return classifier.State() == TopAbs_State.TopAbs_IN or classifier.IsOnAFace()


def second_moment(polygons: Sequence[ShPolygon]) -> Tuple[float, float, float]:
    """Area, centroid height and second moment of area about the horizontal centroidal axis of polygons in (u, z)."""
    area = sum(p.area for p in polygons)
    cz = sum(p.area * p.centroid.y for p in polygons) / area

    def ring_i(ring: Sequence[Tuple[float, float]]) -> float:
        total = 0.0
        pts = list(ring)
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            cross = x0 * y1 - x1 * y0
            total += cross * (y0 * y0 + y0 * y1 + y1 * y1)
        return total / 12.0

    def about_origin(p: ShPolygon) -> float:
        ext = abs(ring_i(p.exterior.coords))
        return ext - sum(abs(ring_i(r.coords)) for r in p.interiors)

    ix0 = sum(about_origin(p) for p in polygons)
    return area, cz, ix0 - area * cz * cz


# ---------------------------------------------------------------------------------------------------------------------
# The plate's clearance and creepage over the board's tolerances
# ---------------------------------------------------------------------------------------------------------------------

def gap_range(P: Any) -> Dict[str, float]:
    """The board-edge-to-plate gap over the maker's tab-face-to-lead-centre range, the outline routing tolerance and the leads' play, from the figures of params.yaml."""
    row = P("seating.pad_row_v_mm")
    tfc, rt, lp = P.entry("seating.tab_face_to_lead_centre_mm"), P.entry("seating.outline_routing_mm"), P.entry("seating.lead_play_mm")
    package_lo, package_hi = tfc["min"] - row, tfc["max"] - row
    routing, play = max(abs(rt["min"]), abs(rt["max"])), max(abs(lp["min"]), abs(lp["max"]))
    return {"package_min_mm": package_lo, "package_max_mm": package_hi, "routing_mm": routing, "play_mm": play,
            "min_mm": package_lo - routing - play, "max_mm": package_hi + routing + play, "nominal_mm": P("seating.tab_face_to_lead_centre_mm") - row}


def mains_points(m: case.Model, near_v: float = 12.0, step: float = 0.1) -> Tuple[np.ndarray, List[str], List[str]]:
    """Boundary points of every Mains-family copper item that comes within `near_v` of the board's plate-side edge, on each copper layer, in
    the case frame with the lean carried: one row (u, v, z) per point, with the label and the layer of the item it belongs to."""
    t = m.board.thickness
    pts, labels, layers = [], [], []
    c, sn = math.cos(m.phi), math.sin(m.phi)
    for item in m.board.mains_items:
        geom = item["geom"]
        if geom.is_empty or geom.bounds[1] > near_v:
            continue
        zc = 0.0 if item["layer"] == "F.Cu" else -t
        boundary = shapely.segmentize(geom.boundary, step)
        coords = np.array([xy for g in (boundary.geoms if hasattr(boundary, "geoms") else [boundary]) for xy in g.coords])
        coords = coords[coords[:, 1] <= near_v]
        if not len(coords):
            continue
        dv = coords[:, 1] - m.pivot_v
        pts.append(np.stack([coords[:, 0], m.pivot_v + dv * c - zc * sn, zc * c + dv * sn], axis=1))
        labels += [item["label"]] * len(coords)
        layers += [item["layer"]] * len(coords)
    return (np.vstack(pts) if pts else np.zeros((0, 3))), labels, layers


def distance_to_box(points: np.ndarray, u0: float, u1: float, v0: float, v1: float, z0: float, z1: float) -> np.ndarray:
    """The straight-line distance from each point (u, v, z) to an axis-aligned box."""
    d = np.stack([np.maximum.reduce([u0 - points[:, 0], np.zeros(len(points)), points[:, 0] - u1]),
                  np.maximum.reduce([v0 - points[:, 1], np.zeros(len(points)), points[:, 1] - v1]),
                  np.maximum.reduce([z0 - points[:, 2], np.zeros(len(points)), points[:, 2] - z1])], axis=1)
    return np.linalg.norm(d, axis=1)


def plate_distances(m: case.Model) -> Dict[str, Any]:
    """The straight-line distance from every Mains-family copper item's edge and from each bare lead to the plate solid and to the machine wall's plane, in 3D."""
    P = m.P
    pl = m.info["plate"]
    T = P("plate.thickness_mm")
    v_wall = m.v_plate - T
    pts, labels, layers = mains_points(m)
    d_plate = distance_to_box(pts, pl["u0"], pl["u1"], v_wall, m.v_plate, pl["z0"], pl["z1"])
    d_wall = pts[:, 1] - v_wall
    k = int(np.argmin(d_plate))
    pads = {}
    for ref in case.TRIAC_REFS:
        for pad in m.board.refs[ref]["pads"]:
            poly = ShPolygon([(x - m.board.ox, y - m.board.oy) for x, y in pad["pad"].outline()])
            for layer in ("F.Cu", "B.Cu"):
                zc = 0.0 if layer == "F.Cu" else -m.board.thickness
                boundary = shapely.segmentize(poly.boundary, 0.1)
                xy = np.array(boundary.coords)
                dv = xy[:, 1] - m.pivot_v
                c, sn = math.cos(m.phi), math.sin(m.phi)
                g = np.stack([xy[:, 0], m.pivot_v + dv * c - zc * sn, zc * c + dv * sn], axis=1)
                dd = distance_to_box(g, pl["u0"], pl["u1"], v_wall, m.v_plate, pl["z0"], pl["z1"])
                pads[f"{ref} pad {pad['number']} {layer}"] = float(dd.min())
    leads = {}
    for ref in case.TRIAC_REFS:
        shape = m.bodies[f"{ref}_leads"]["shape"]
        leads[f"{ref} leads"] = {"to_plate_mm": float(m.parts["plate"].distance_to(shape)),
                                 "to_wall_plane_mm": float(shape.bounding_box().min.Y - v_wall)}
    return {"all_copper_mm": float(d_plate.min()), "all_copper_item": f"{labels[k]} on {layers[k]}", "points": int(len(pts)),
            "all_copper_to_wall_plane_mm": float(d_wall.min()), "pads_mm": pads, "leads": leads,
            "pad_least_mm": min(pads.values()), "lead_least_mm": min(v["to_plate_mm"] for v in leads.values()),
            "lead_wall_plane_least_mm": min(v["to_wall_plane_mm"] for v in leads.values())}


def shared_volume(a: Any, b: Any) -> float:
    inter = a & b
    return float(inter.volume) if inter is not None and hasattr(inter, "volume") else 0.0


def ledge_result(m: case.Model, plate_z0: float) -> Dict[str, Any]:
    """The plate's lower edge is set by the ledge on the tray's end wall: the plate at the ledge's height shares no volume with the tray, the same plate 0.05 mm lower
    shares a positive volume, and so does the plate at its former position. The edge is read in the tray's own frame, above the floor's underside."""
    from build123d import Pos
    P = m.P
    pl = m.info["plate"]
    ew = m.info["end_wall"].bounding_box()
    ledge = float(ew.max.Z)
    step = 0.05
    at_ledge = shared_volume(m.parts["plate"], m.parts["tray"])
    below = shared_volume(Pos(0, 0, -step) * m.parts["plate"], m.parts["tray"])
    former = shared_volume(Pos(0, 0, pl["former_z0"] - pl["z0"]) * m.parts["plate"], m.parts["tray"])
    in_tray_frame = ledge - float(m.z_floor_bottom)
    layer = 0.2
    ok = abs(plate_z0 - ledge) < 1e-6 and at_ledge < 1e-6 and below > 0.0 and former > 0.0
    return result("c1.plate_seated_on_ledge", "C1", ok,
                  f"the plate's lower edge z {plate_z0:.3f} is the ledge's top, {in_tray_frame:.3f} mm above the tray floor's underside ({in_tray_frame / layer:.2f} layers of {layer} mm): at the ledge the plate shares {at_ledge:.3f} mm3 with the tray, "
                  f"{step} mm lower {below:.3f} mm3, and at its former position, z {pl['former_z0']:.3f}, {former:.1f} mm3, so a lower plate cannot be seated",
                  {"ledge_z_mm": ledge, "plate_lower_edge_z_mm": plate_z0, "ledge_above_floor_underside_mm": in_tray_frame, "layers_of_0.2_mm": in_tray_frame / layer,
                   "shared_volume_at_ledge_mm3": at_ledge, "step_below_mm": step, "shared_volume_below_ledge_mm3": below,
                   "former_lower_edge_z_mm": pl["former_z0"], "shared_volume_at_former_position_mm3": former,
                   "contact_v_mm": [float(ew.min.Y), float(m.v_plate - P("plate.end_wall_board_recess_mm"))]})


def check_c1(m: case.Model) -> List[Dict[str, Any]]:
    P, sep = m.P, m.basis
    out: List[Dict[str, Any]] = []
    creep_need, clear_need = sep["creepage_mains_mm"], sep["clearance_mains_mm"]
    d = plate_distances(m)

    # the gap, stated over the three tolerances, and tied to the model's own geometry
    g = gap_range(P)
    edge_v = float(m.board.outline.bounds[1])
    gap_built = edge_v - m.v_plate
    expected = P("seating.tab_face_to_lead_centre_mm") - P("seating.pad_row_v_mm") - P("seating.lead_play_mm") + P("seating.outline_routing_mm")
    out.append(result("c1.gap_over_tolerances", "C1", g["min_mm"] > 0.0 and abs(gap_built - expected) < 1e-6,
                      f"the board-edge-to-plate gap is {g['min_mm']:.3f} to {g['max_mm']:.3f} mm: the maker's {g['package_min_mm']:.3f} to {g['package_max_mm']:.3f} mm, "
                      f"less and plus the outline routing tolerance {g['routing_mm']:.1f} mm and the leads' play {g['play_mm']:.3f} mm; this build's gap {gap_built:.3f} mm",
                      {"gap_min_mm": g["min_mm"], "gap_max_mm": g["max_mm"], "gap_nominal_mm": g["nominal_mm"], "package_range_mm": [g["package_min_mm"], g["package_max_mm"]],
                       "outline_routing_mm": g["routing_mm"], "lead_play_mm": g["play_mm"], "gap_of_this_build_mm": gap_built,
                       "arithmetic": f"{g['package_min_mm']:.3f} - {g['routing_mm']:.3f} - {g['play_mm']:.3f} = {g['min_mm']:.3f}; {g['package_max_mm']:.3f} + {g['routing_mm']:.3f} + {g['play_mm']:.3f} = {g['max_mm']:.3f}"}))

    # the plate's lower edge, raised above the board's pads and bare leads
    plate_z0 = float(m.parts["plate"].bounding_box().min.Z)
    bu_max = P.entry("seating.body_underside_mm")["max"]
    rear = P.entry("seating.tab_face_to_lead_centre_mm")["min"] - P("triac.c1_mm") / 2
    derived = bu_max + math.sqrt(max(creep_need ** 2 - rear ** 2, 0.0))
    lift = P("plate.lower_edge_z_mm") + P("seating.plate_edge_offset_mm")
    out.append(result("c1.plate_lower_edge_raised", "C1", plate_z0 >= lift - 1e-9 and plate_z0 >= derived - 1e-9,
                      f"the plate's lower edge stands at z {plate_z0:.3f} above the component face, at least the {lift:.2f} mm figure of this build (6.0 mm less the build's plate-edge offset) and the {derived:.3f} mm the bare leads need "
                      f"({bu_max:.2f} + sqrt({creep_need:.1f}^2 - {rear:.3f}^2)): no plate metal faces the board edge, the pads or the lower leads",
                      {"plate_lower_edge_z_mm": plate_z0, "figure_mm": lift, "derived_least_mm": derived, "lead_rear_face_to_plate_least_mm": rear,
                       "lead_metal_top_mm": bu_max, "margin_to_derived_mm": plate_z0 - derived}))

    # clearance and creepage, each a straight line: no surface path is shorter than the straight line, so no barrier, film or coating is credited
    out.append(result("c1.clearance_pad_to_plate", "C1", d["pad_least_mm"] >= clear_need,
                      f"straight air from every triac pad edge, both copper layers, to the plate solid {d['pad_least_mm']:.3f} mm against the basis's {clear_need:.1f} mm",
                      {"clearance_mm": d["pad_least_mm"], "required_mm": clear_need, "pads_mm": d["pads_mm"]}))
    out.append(result("c1.creepage_pad_to_plate", "C1", d["pad_least_mm"] >= creep_need,
                      f"creepage from every triac pad edge to the plate, taken as the straight line (no surface path is shorter) {d['pad_least_mm']:.3f} mm against the basis's {creep_need:.1f} mm, no barrier credited",
                      {"creepage_mm": d["pad_least_mm"], "required_mm": creep_need, "basis": "straight-line distance; a path over any surface is at least as long", "pads_mm": d["pads_mm"]}))
    out.append(result("c1.clearance_bare_lead_to_plate", "C1", d["lead_least_mm"] >= clear_need,
                      f"a bare lead stands {d['lead_least_mm']:.3f} mm from the plate solid, against {clear_need:.1f} mm",
                      {"clearance_mm": d["lead_least_mm"], "required_mm": clear_need, "leads": d["leads"]}))
    out.append(result("c1.creepage_bare_lead_to_plate", "C1", d["lead_least_mm"] >= creep_need,
                      f"a bare lead's straight line to the plate, the shortest path over any surface, is {d['lead_least_mm']:.3f} mm against {creep_need:.1f} mm, no barrier credited",
                      {"creepage_mm": d["lead_least_mm"], "required_mm": creep_need, "leads": d["leads"]}))
    out.append(result("c1.creepage_all_mains_copper", "C1", d["all_copper_mm"] >= creep_need,
                      f"every Mains-family copper item (pad, track, via, pour) keeps at least {d['all_copper_mm']:.3f} mm of straight line to the plate solid (nearest: {d['all_copper_item']}) against {creep_need:.1f} mm",
                      {"least_mm": d["all_copper_mm"], "item": d["all_copper_item"], "required_mm": creep_need, "points_measured": d["points"]}))
    wall_least = min(d["all_copper_to_wall_plane_mm"], d["lead_wall_plane_least_mm"])
    out.append(result("c1.straight_to_wall_plane", "C1", wall_least >= creep_need,
                      f"the least straight line from Mains copper or a bare lead to the machine wall's plane is {wall_least:.3f} mm against {creep_need:.1f} mm",
                      {"copper_mm": d["all_copper_to_wall_plane_mm"], "leads_mm": d["lead_wall_plane_least_mm"], "required_mm": creep_need,
                       "wall_plane_v_mm": m.v_plate - P("plate.thickness_mm")}))

    # the end wall stands clear of the board edge, its top is the ledge the bar rests on, and the plate cannot be seated below it
    left_in, right_in = -P("case.interior_left_mm"), 45.0 + P("case.interior_right_mm")
    ew = m.info["end_wall"].bounding_box()
    recess = P("plate.end_wall_board_recess_mm")
    front_v = m.v_plate - recess
    front = case.box(left_in, right_in, ew.min.Y, front_v, ew.min.Z, ew.max.Z)
    to_board = float(front.distance_to(m.bodies["board"]["shape"]))
    pts, _, _ = mains_points(m)
    to_pads = float(distance_to_box(pts, left_in, right_in, ew.min.Y, front_v, ew.min.Z, ew.max.Z).min())
    out.append(result("c1.end_wall_stands_off", "C1", to_board >= recess - 1e-9 and abs(ew.max.Z - plate_z0) < 1e-6,
                      f"the tray's printed end wall, z {ew.min.Z:.2f} to {ew.max.Z:.2f}, stands {to_board:.3f} mm from the board and {to_pads:.3f} mm from Mains copper, its board-side face {recess:.2f} mm behind the plate plane; its top is the ledge at the plate's lower edge, z {plate_z0:.3f}",
                      {"to_board_mm": to_board, "to_mains_copper_mm": to_pads, "front_face_v_mm": front_v, "front_behind_plate_plane_mm": m.v_plate - front_v,
                       "top_z_mm": ew.max.Z, "gap_under_plate_edge_mm": plate_z0 - ew.max.Z,
                       "back_face_v_mm": ew.min.Y, "back_in_front_of_wall_plane_mm": ew.min.Y - (m.v_plate - P("plate.thickness_mm")),
                       "material": "unfilled printed plastic, no creepage credit: at the extremes it stands within the signed clearance of the pads"}))
    out.append(ledge_result(m, plate_z0))
    overlap = shared_volume(m.parts["plate"], m.parts["tray"])
    out.append(result("c1.plate_clear_of_end_wall", "C1", overlap < 1e-6,
                      f"the plate shares {overlap:.3f} mm3 with the tray: a plate whose lower edge stood lower, at the former position, would have to occupy the end wall's place",
                      {"intersection_volume_mm3": overlap, "plate_lower_edge_z_mm": plate_z0, "former_lower_edge_z_mm": m.info["plate"]["former_z0"]}))
    names = sorted(m.parts)
    loose = [n for n in names if n not in ("tray", "plate", "lid_single", "lid_two", "lid_swap", "tray_swap")]
    stray = [k for k in m.P.data if k in ("film", "coating", "shim", "barrier")]
    out.append(result("c1.no_loose_part_or_coating", "C1", not loose and not stray,
                      f"the model's parts are {', '.join(names)}: no insulating film, coating, shim or other loose part, and params.yaml holds no figure for one",
                      {"parts": names, "loose_parts": loose, "params_sections_for_one": stray}))
    return out


# ---------------------------------------------------------------------------------------------------------------------
# The case envelope and the plate
# ---------------------------------------------------------------------------------------------------------------------

def case_extent(m: case.Model, include_cable: bool = True) -> Dict[str, float]:
    names = ["tray", "lid_single", "lid_two"] if "lid_two" in m.parts else ["tray", "lid_single"]
    bbs = [m.parts[n].bounding_box() for n in names]
    return {"u0": float(min(b.min.X for b in bbs)), "u1": float(max(b.max.X for b in bbs)), "z0": float(min(b.min.Z for b in bbs)),
            "z1": float(max(b.max.Z for b in bbs)), "v0": float(min(b.min.Y for b in bbs)), "v1": float(max(b.max.Y for b in bbs))}


def check_c2_c3(m: case.Model) -> List[Dict[str, Any]]:
    P = m.P
    out = []
    e = case_extent(m)
    pb = m.mesh("plate").bounds
    pl = m.info["plate"]
    # the former outline: the plate's length and its former height, centred on the case's extent; it is its own figure and does not follow the bar's height
    fz0, fz1 = pl["former_z0"], pl["former_z1"]
    margins = {"left": e["u0"] - pb[0][0], "right": pb[1][0] - e["u1"], "bottom": e["z0"] - fz0, "top": fz1 - e["z1"]}
    need = P("plate.min_margin_mm")
    cav = np.array([m.mesh(n).bounds for n in m.bodies])
    cav_inside = bool(cav[:, 0, 0].min() >= pb[0][0] and cav[:, 1, 0].max() <= pb[1][0] and cav[:, 0, 2].min() >= fz0 and cav[:, 1, 2].max() <= fz1)
    out.append(result("c2.case_within_former_outline", "C2", min(margins.values()) >= need and cav_inside,
                      f"the case lies inside the plate's former {pb[1][0] - pb[0][0]:.1f} x {fz1 - fz0:.1f} mm outline with {min(margins.values()):.3f} mm least margin (needs {need:.2f}); the board, blades and parts lie inside it too",
                      {"margins_mm": margins, "required_mm": need, "case_extent_mm": e,
                       "former_outline_mm": {"u0": float(pb[0][0]), "u1": float(pb[1][0]), "z0": float(fz0), "z1": float(fz1)},
                       "plate_extent_mm": {"u0": float(pb[0][0]), "u1": float(pb[1][0]), "z0": float(pb[0][2]), "z1": float(pb[1][2])},
                       "parts_inside_plate_outline": cav_inside}))
    c = P("plate.wall_opening_clearance_mm")
    wo = case.wall_opening(m)
    opening = {k: float(wo[k]) for k in ("u0", "u1", "z0", "z1")}
    ewb = m.info["end_wall"].bounding_box()
    bottom, top = P("plate.unit_opening_bottom_z_mm"), P("plate.unit_opening_top_z_mm")
    # the opening is judged against the built solids, not against its own definition: each side stands at least the clearance outside the plate and the end wall
    around = {"plate": {"left": float(pb[0][0] - opening["u0"]), "right": float(opening["u1"] - pb[1][0]), "bottom": float(pb[0][2] - opening["z0"]), "top": float(opening["z1"] - pb[1][2])},
              "end wall": {"left": float(ewb.min.X - opening["u0"]), "right": float(opening["u1"] - ewb.max.X), "bottom": float(ewb.min.Z - opening["z0"]), "top": float(opening["z1"] - ewb.max.Z)}}
    least_around = min(min(v.values()) for v in around.values())
    harness_exit_u = 45.0 + P("case.interior_right_mm") + P("case.wall_mm")
    out.append(result("c2.wall_opening_stated", "C2",
                      least_around >= c - 1e-6 and opening["u0"] < e["u0"] and opening["u1"] > e["u1"] and opening["z0"] < e["z0"] and opening["z1"] > e["z1"] and pb[1][0] > harness_exit_u,
                      f"the opening in the plastic wall covers the plate and the end wall together plus {c:.1f} mm each side: u {opening['u0']:.2f} to {opening['u1']:.2f}, z {opening['z0']:.2f} to {opening['z1']:.2f}; the nearest side stands {least_around:.3f} mm outside the plate or the end wall; no larger opening is needed",
                      {"opening_mm": opening, "plate_clearance_mm": c, "opening_width_mm": opening["u1"] - opening["u0"],
                       "opening_height_mm": opening["z1"] - opening["z0"], "cable_exit_u_mm": harness_exit_u, "outside_each_solid_mm": around}))
    out.append(result("c2.wall_opening_within_unit_opening", "C2", opening["z0"] >= bottom - 1e-6 and opening["z1"] <= top + 1e-6,
                      f"the wall opening's height, z {opening['z0']:.2f} to {opening['z1']:.2f}, lies within the unit's opening in the plastic wall, z {bottom:.1f} to {top:.1f} (margins {opening['z0'] - bottom:.2f} below and {top - opening['z1']:.2f} above)",
                      {"opening_z_mm": [opening["z0"], opening["z1"]], "unit_opening_z_mm": [bottom, top], "margin_below_mm": opening["z0"] - bottom, "margin_above_mm": top - opening["z1"],
                       "plate_height_mm": float(pb[1][2] - pb[0][2]), "height_range_mm": [P("plate.height_min_mm"), P("plate.height_max_mm")]}))
    cover_need = P("plate.min_margin_mm")
    out.append(result("c2.plate_covers_case_top", "C2", float(pb[1][2]) - e["z1"] >= cover_need - 1e-6,
                      f"the plate's upper edge, z {pb[1][2]:.3f}, stands {pb[1][2] - e['z1']:.3f} mm above the lid's top, z {e['z1']:.3f} (needs {cover_need:.2f}): the case lies inside the plate's footprint at this plate height",
                      {"plate_upper_edge_z_mm": float(pb[1][2]), "case_top_z_mm": e["z1"], "margin_mm": float(pb[1][2]) - e["z1"], "required_mm": cover_need,
                       "plate_height_mm": float(pb[1][2] - pb[0][2])}))
    # only the plate touches the wall: no printed part comes within the stated distance of the wall's plane
    v_wall = m.v_plate - P("plate.thickness_mm")
    stand = P("plate.end_wall_wall_clear_mm")
    printed = [n for n in ("tray", "lid_single", "lid_two") if n in m.parts]
    nearest = {n: float(m.mesh(n).bounds[0][1] - v_wall) for n in printed}
    out.append(result("c2.only_plate_touches_wall", "C2", all(v >= stand - 1e-6 for v in nearest.values()),
                      f"no printed part comes within {stand:.1f} mm of the machine wall's plane (v {v_wall:.3f}): the nearest, the tray's end wall, stands {min(nearest.values()):.3f} mm in front of it, so only the plate touches the wall",
                      {"wall_plane_v_mm": v_wall, "required_mm": stand, "nearest_mm": nearest}))
    # the plate's length
    bolt = P("plate.bolt_zone_mm")
    verts = m.mesh("tray").vertices
    at_plate = verts[verts[:, 1] < m.v_end + P("case.pilaster_len_mm") + 0.1]
    width_plate = float(at_plate[:, 0].max() - at_plate[:, 0].min())
    L = float(pb[1][0] - pb[0][0])
    need_len = width_plate + 2 * bolt
    out.append(result("c3.plate_length", "C3", L >= need_len - 1e-9,
                      f"plate length {L:.2f} >= case outer width at the plate {width_plate:.2f} + 2 x bolt zone {bolt:.1f} = {need_len:.2f} (margin {L - need_len:.2f})",
                      {"plate_length_mm": L, "case_outer_width_mm": width_plate, "bolt_zone_mm": bolt, "required_mm": need_len,
                       "margin_mm": L - need_len, "arithmetic": f"{width_plate:.2f} + 2 x {bolt:.1f} = {need_len:.2f} <= {L:.2f}"}))
    washer = P("plate.bolt_washer_dia_mm")
    zones_ok = True
    figures = []
    for end, sign in ((float(pb[0][0]), 1), (float(pb[1][0]), -1)):
        cx = end + sign * bolt / 2
        outside = (e["u0"] - (cx + washer / 2)) if sign > 0 else ((cx - washer / 2) - e["u1"])
        for bz in pl["bolt_zs"]:
            inside_z = min(bz - washer / 2 - pb[0][2], pb[1][2] - (bz + washer / 2))
            figures.append({"bolt_u_mm": cx, "bolt_z_mm": bz, "washer_clear_of_case_mm": outside, "washer_inside_plate_in_z_mm": float(inside_z)})
            zones_ok &= outside >= P("plate.washer_to_case_clearance_mm") - 1e-9 and (cx - washer / 2) >= pb[0][0] - 1e-9 and (cx + washer / 2) <= pb[1][0] + 1e-9 and inside_z >= 0.0
    out.append(result("c3.wall_bolts_outside_case", "C3", zones_ok,
                      f"each of the {len(figures)} wall bolts and its {washer:.0f} mm washer stands in the plate's end zone, outside the case and inside the plate's height, so the plate, case and board leave the wall as one unit",
                      {"bolts": figures}))
    out.append(tray_screws_fit_plate(m))
    out.append(tray_screw_heads_apart(m))
    out.append(tray_insert_seat(m))
    return out


def tray_screws_fit_plate(m: case.Model) -> Dict[str, Any]:
    """Each tray screw's countersunk head keeps the edge distance from the plate's four edges, and its insert hole and head stand clear of the lid toe's pocket."""
    P = m.P
    pl = m.info["plate"]
    cs_r = P("screws.tray_plate_countersink_dia_mm") / 2
    edge_need = P("plate.screw_edge_distance_mm")
    pocket_need = P("plate.min_pilot_to_pocket_mm")
    rows = []
    ok = True
    pockets = {u: case.pocket_solid(m, u) for u in m.info["toe_u"]}
    for u in m.info["tray_pilaster_u"]:
        for z in P("screws.tray_plate_z_mm"):
            edges = {"lower": z - cs_r - pl["z0"], "upper": pl["z1"] - (z + cs_r), "left": u - cs_r - pl["u0"], "right": pl["u1"] - (u + cs_r)}
            hole = case.insert_hole_solid(m, u, z)
            head = case.head_solid(m, u, z)
            to_pocket = {"hole": min(float(hole.distance_to(p)) for p in pockets.values()), "head": min(float(head.distance_to(p)) for p in pockets.values())}
            hole_top = float(hole.bounding_box().max.Z)
            row = {"screw": f"u {u:g} z {z:g}", "edge_distances_mm": edges, "least_edge_mm": min(edges.values()), "to_pocket_mm": to_pocket,
                   "insert_hole_top_z_mm": hole_top, "pilaster_top_z_mm": P("case.z_wall_top_mm")}
            row["pass"] = (min(edges.values()) >= edge_need - 1e-9 and min(to_pocket.values()) >= pocket_need - 1e-9
                           and hole_top <= P("case.z_wall_top_mm") - P("case.insert_wall_min_mm"))
            ok &= row["pass"]
            rows.append(row)
    least_edge = min(r["least_edge_mm"] for r in rows)
    least_pocket = min(min(r["to_pocket_mm"].values()) for r in rows)
    return result("c3.tray_screws_fit_plate", "C3", ok,
                  f"each of the {len(rows)} tray screws' countersinks stands at least {least_edge:.3f} mm inside the plate's edges (needs {edge_need:.2f}) and its insert hole and head at least {least_pocket:.3f} mm from the lid toe's pocket (needs {pocket_need:.2f}), the hole's top under the pilaster's top by the insert wall",
                  {"screws": rows, "edge_distance_required_mm": edge_need, "pocket_distance_required_mm": pocket_need,
                   "plate_edges_mm": {"z0": pl["z0"], "z1": pl["z1"], "u0": pl["u0"], "u1": pl["u1"]}})


def heads_apart(positions: Sequence[Tuple[float, float]], P: Any) -> Dict[str, Any]:
    """Every pair of tray screws, by their (u, z) axes: the distance between the axes against the record's head-to-head distance, and the
    gaps left between the heads and between the countersinks, whose diameters are the standard's."""
    need = P("plate.min_head_to_head_mm")
    head, sink = P("screws.tray_plate_head_dia_mm"), P("screws.tray_plate_countersink_dia_mm")
    pairs = []
    for (i, a), (j, b) in itertools.combinations(enumerate(positions), 2):
        d = math.hypot(a[0] - b[0], a[1] - b[1])
        pairs.append({"pair": [i, j], "axes_mm": d, "head_gap_mm": d - head, "countersink_gap_mm": d - sink, "pass": d >= need - 1e-9 and d - sink > 0.0})
    return {"pairs": pairs, "required_mm": need, "head_dia_mm": head, "countersink_dia_mm": sink,
            "pass": all(p["pass"] for p in pairs) and need >= sink > head}


def tray_screw_heads_apart(m: case.Model) -> Dict[str, Any]:
    """No two tray screws have their heads or their countersinks in the bar's back face closer than the record's head-to-head distance."""
    positions = [(s["u"], s["z"]) for s in m.screws if s["kind"] == "tray_plate"]
    f = heads_apart(positions, m.P)
    least = min((p["axes_mm"] for p in f["pairs"]), default=float("inf"))
    return result("c3.tray_screw_heads_apart", "C3", f["pass"] and len(positions) >= 2,
                  f"each of the {len(f['pairs'])} pairs of the {len(positions)} tray screws stands at least {least:.2f} mm apart on the axes (needs {f['required_mm']:.1f}); the {f['head_dia_mm']:.1f} mm heads and the {f['countersink_dia_mm']:.1f} mm countersinks of the ISO 7046 M3 screw leave their gaps",
                  f)


def insert_wall(m: case.Model, u: float, z: float) -> Dict[str, float]:
    """The printed wall round one insert hole, measured to the pilaster's outer face, to the cavity, to the lid toe's pocket and to the pilaster's top."""
    P = m.P
    e = case.case_extent(m)
    r = P("case.insert_hole_dia_mm") / 2
    board_width = float(m.board.outline.bounds[2])
    left_in, right_in = -P("case.interior_left_mm"), board_width + P("case.interior_right_mm")
    outer, inner = (u - r - e["u0"], left_in - (u + r)) if u < (e["u0"] + e["u1"]) / 2 else (e["u1"] - (u + r), (u - r) - right_in)
    hole = case.insert_hole_solid(m, u, z)
    pocket = min(float(hole.distance_to(case.pocket_solid(m, tu))) for tu in m.info["toe_u"])
    top = P("case.z_wall_top_mm") - float(hole.bounding_box().max.Z)
    return {"outer_face_mm": outer, "cavity_mm": inner, "pocket_mm": pocket, "top_mm": top}


def tray_insert_seat(m: case.Model) -> Dict[str, Any]:
    """One heat-set insert's hole in each pilaster at the maker's size and depth, the wall round it at the record's minimum, and the short screw's engaged length inside the insert and short of the hole's floor."""
    P = m.P
    pilasters = len(m.info["tray_pilaster_u"])
    per = int(P("screws.tray_plate_count_per_pilaster"))
    wall_need = P("case.insert_wall_min_mm")
    depth, length = P("case.insert_hole_depth_mm"), P("case.insert_length_mm")
    dia, hole_range, depth_min = P("case.insert_hole_dia_mm"), P.entry("case.insert_hole_dia_mm"), P.entry("case.insert_hole_depth_mm")["min"]
    hole_in_range = hole_range["min"] - 1e-9 <= dia <= hole_range["max"] + 1e-9
    depth_ok = depth >= depth_min - 1e-9
    engaged = P("screws.tray_plate_length_mm") - P("plate.thickness_mm")
    min_thread = 6 * P("screws.tray_insert_shear_layer_mm")
    reservoir = depth - length
    rows = []
    for u in m.info["tray_pilaster_u"]:
        for z in P("screws.tray_plate_z_mm"):
            w = insert_wall(m, u, z)
            rows.append({"insert": f"u {u:g} z {z:g}", "wall_mm": w, "least_wall_mm": min(w.values()), "pass": min(w.values()) >= wall_need - 1e-9})
    n_inserts = sum(1 for s in m.screws if s["kind"] == "insert")
    n_screws = sum(1 for s in m.screws if s["kind"] == "tray_plate")
    tip_to_floor = depth - engaged
    ok = (all(r["pass"] for r in rows) and n_inserts == n_screws == pilasters * per == len(rows) and hole_in_range and depth_ok
          and 0.0 < engaged <= length + 1e-9 and tip_to_floor > 0.0 and reservoir >= 0.5 - 1e-9 and engaged >= min_thread - 1e-9)
    return result("c3.tray_insert_seat", "C3", ok,
                  f"{n_inserts} M3 heat-set inserts, one in each of {pilasters} pilasters, in holes {dia:.2f} mm across (the maker's range {hole_range['min']:.2f} to {hole_range['max']:.2f} mm) and {depth:.1f} mm deep (the maker's least {depth_min:.1f} mm) for the {length:.1f} mm insert with {reservoir:.1f} mm of reservoir under it; the wall round each hole is at least {min(r['least_wall_mm'] for r in rows):.3f} mm (needs {wall_need:.1f}); "
                  f"the M3 x {P('screws.tray_plate_length_mm'):.0f} screw engages {engaged:.1f} mm of the insert (at least {min_thread:.1f} mm, at most the insert's {length:.1f} mm) and stops {tip_to_floor:.1f} mm short of the hole's floor, so the head seats and the bar is clamped",
                  {"inserts": rows, "inserts_counted": n_inserts, "screws_counted": n_screws, "pilasters": pilasters, "per_pilaster": per, "hole_dia_mm": dia,
                   "hole_dia_range_mm": [hole_range["min"], hole_range["max"]], "hole_in_maker_range": hole_in_range, "hole_depth_min_mm": depth_min, "hole_depth_meets_maker_min": depth_ok,
                   "hole_depth_mm": depth, "insert_length_mm": length, "reservoir_mm": reservoir, "wall_required_mm": wall_need, "screw_length_mm": P("screws.tray_plate_length_mm"),
                   "bar_thickness_mm": P("plate.thickness_mm"), "engaged_length_mm": engaged, "minimum_thread_mm": min_thread, "tip_to_hole_floor_mm": tip_to_floor})


# ---------------------------------------------------------------------------------------------------------------------
# The lid's sweep
# ---------------------------------------------------------------------------------------------------------------------

def wall_frame(m: case.Model):
    """The machine wall around the opening, modelled as a frame the opening's depth in front of the wall plane."""
    from build123d import Pos
    P = m.P
    wo = case.wall_opening(m)
    rim = P("plate.wall_frame_rim_mm")
    depth = P("plate.wall_frame_depth_mm")
    v0, v1 = m.v_plate, m.v_plate + depth
    outer = case.box(wo["u0"] - rim, wo["u1"] + rim, v0, v1, wo["z0"] - rim, wo["z1"] + rim)
    inner = case.box(wo["u0"], wo["u1"], v0 - 1, v1 + 1, wo["z0"], wo["z1"])
    return outer - inner


def sweep_poses(m: case.Model, steps_tilt: int = 10, slide_to: float = 90.0, slide_step: float = 3.0):
    """Lid poses: tilted about the toe line at the lid's plate end by growing angles, then drawn out along the tilted plane."""
    P = m.P
    tilt = P("lid.sweep_tilt_deg")
    pivot_v = m.v_end + P("case.lid_end_gap_mm") + P("lid.sweep_pivot_v_mm")
    pivot_z = P("case.z_lid_under_mm")
    poses = []
    for i in range(steps_tilt + 1):
        poses.append(("tilt", tilt * i / steps_tilt, 0.0))
    s = slide_step
    while s <= slide_to + 1e-9:
        poses.append(("slide", tilt, s))
        s += slide_step
    return poses, (pivot_v, pivot_z)


def lid_at(m: case.Model, lid: Any, pose: Tuple[str, float, float], pivot: Tuple[float, float]):
    from build123d import Axis, Pos
    kind, angle, slide = pose
    shape = lid
    if angle:
        shape = shape.rotate(Axis((0, pivot[0], pivot[1]), (1, 0, 0)), angle)
    if slide:
        a = math.radians(angle)
        shape = Pos(0, slide * math.cos(a), slide * math.sin(a)) * shape
    return shape


def lid_poses_xy(points_vz: np.ndarray, pose: Tuple[str, float, float], pivot: Tuple[float, float]) -> np.ndarray:
    """Points (v, z) of the lid carried through a pose: tilted about the pivot (the far end moving +z), then drawn out along the tilted plane."""
    kind, angle, slide = pose
    a = math.radians(angle)
    dv, dz = points_vz[:, 0] - pivot[0], points_vz[:, 1] - pivot[1]
    v = pivot[0] + dv * math.cos(a) - dz * math.sin(a)
    z = pivot[1] + dv * math.sin(a) + dz * math.cos(a)
    return np.stack([v + slide * math.cos(a), z + slide * math.sin(a)], axis=1)


def lid_removal_installed(m: case.Model, form: str, poses: Sequence[Tuple[str, float, float]], pivot: Tuple[float, float]) -> Dict[str, Any]:
    """The lid's removal reported in the installed frame: gravity points along +z, so the lid comes off downward and tilts its far end down.

    Figures: how far the lid's lowest point drops while it tilts (the clear space needed below the case), the slide that frees the
    toes from the pilasters' hooks, the lowest point of the lid when they are free, and the slide the sweep is checked to.
    """
    P = m.P
    g = case.gravity(m)
    verts = m.mesh(f"lid_{form}").vertices[:, [1, 2]]
    lowest0 = float((verts @ g[[1, 2]]).max())
    tilt = P("lid.sweep_tilt_deg")
    tilted = lid_poses_xy(verts, ("tilt", tilt, 0.0), pivot)
    drop_tilt = float((tilted @ g[[1, 2]]).max()) - lowest0
    toe = np.array([(m.v_end + a, b) for a, b in case.toe_profile(m)])
    v_free = m.core.v_pil
    slide_free = None
    s = 0.0
    while s <= 90.0:
        moved = lid_poses_xy(toe, ("slide", tilt, s), pivot)
        if float(moved[:, 0].min()) > v_free:
            slide_free = s
            break
        s += 0.1
    lowest_free = float((lid_poses_xy(verts, ("slide", tilt, slide_free or 0.0), pivot) @ g[[1, 2]]).max()) - lowest0
    return {"gravity": [float(x) for x in g], "lid_comes_off": "downward: the lid is on the underside",
            "tilt_deg": tilt, "drop_at_far_end_during_tilt_mm": drop_tilt,
            "slide_to_free_the_toes_mm": slide_free, "lowest_point_drop_when_toes_free_mm": lowest_free,
            "clear_space_needed_below_the_case_mm": max(drop_tilt, lowest_free),
            "slide_checked_to_mm": 90.0,
            "sequence": "tilt the far end down %.0f deg about the plate-end toe line, draw the lid out away from the wall %.1f mm to free the toes, then lower it away" % (tilt, slide_free or float("nan"))}


def check_c4(m: case.Model, form: str = "single") -> List[Dict[str, Any]]:
    lid = m.info.get("lid_envelope", m.parts[f"lid_{form}"])
    frame = wall_frame(m)
    obstacles = {"tray": m.info.get("tray_envelope", m.parts["tray"]), "plate": m.parts["plate"], "wall opening frame": frame}
    for name, body in m.bodies.items():
        obstacles[name] = body["shape"]
    poses, pivot = sweep_poses(m)
    figures = []
    overall = float("inf")
    worst = ("", "", 0.0)
    fitted = {}
    for idx, pose in enumerate(poses):
        moved = lid_at(m, lid, pose, pivot)
        row = {"pose": f"{pose[0]} {pose[1]:.1f} deg, slide {pose[2]:.0f}", "clearances": {}}
        pose_min = float("inf")
        bb = moved.bounding_box()
        for name, ob in obstacles.items():
            obb = ob.bounding_box()
            gap_box = max(max(obb.min.X - bb.max.X, bb.min.X - obb.max.X, 0.0), max(obb.min.Y - bb.max.Y, bb.min.Y - obb.max.Y, 0.0),
                          max(obb.min.Z - bb.max.Z, bb.min.Z - obb.max.Z, 0.0))
            if gap_box > 20.0:
                continue
            d = float(moved.distance_to(ob))
            row["clearances"][name] = d
            pose_min = min(pose_min, d)
            if idx == 0:
                fitted[name] = d
            if d < overall:
                overall, worst = d, (name, row["pose"], d)
        row["min_mm"] = pose_min
        figures.append(row)
    fitted_min = min(fitted.values()) if fitted else float("nan")
    # the lid's swept path: the lid ends clear of every obstacle
    passed = overall >= SWEEP_FLOOR
    installed = lid_removal_installed(m, form, poses, pivot)
    lines = [f"{r['pose']:34s} least clearance {r['min_mm']:.3f}" for r in figures[:: max(1, len(figures) // 14)]]
    lines += [f"installed frame (gravity along +z): the lid is on the underside and comes off downward; its far end drops {installed['drop_at_far_end_during_tilt_mm']:.2f} mm during the {installed['tilt_deg']:.0f} deg tilt, "
              f"so {installed['clear_space_needed_below_the_case_mm']:.2f} mm of clear space is needed below the case; the toes are free after a slide of {installed['slide_to_free_the_toes_mm']:.1f} mm "
              f"(the sweep is checked to {installed['slide_checked_to_mm']:.0f} mm)"]
    gate = cable_gate_result(m, form, installed["slide_to_free_the_toes_mm"] or 0.0)
    return [result("c4.lid_sweep", "C4", passed,
                   f"the lid, tilted {m.P('lid.sweep_tilt_deg'):.0f} deg about its plate-end toe line and drawn out, clears the tray, plate, board, parts, blades and the wall opening by at least {overall:.3f} mm (worst: {worst[0]}); fitted clearance {fitted_min:.3f} mm; installed, the far end drops {installed['drop_at_far_end_during_tilt_mm']:.2f} mm and the toes are free after a {installed['slide_to_free_the_toes_mm']:.1f} mm slide",
                   {"minimum_clearance_mm": overall, "floor_mm": SWEEP_FLOOR, "worst_obstacle": worst[0], "worst_pose": worst[1],
                    "fitted_minimum_mm": fitted_min, "fitted_clearances_mm": fitted, "poses": len(poses), "tilt_deg": m.P("lid.sweep_tilt_deg"),
                    "tilt_axis": {"v_mm": pivot[0], "z_mm": pivot[1]}, "tolerance": "exact B-rep distance",
                    "wall_aperture": "plate outline + clearance, framed %.1f mm deep, %.1f mm rim" % (m.P("plate.wall_frame_depth_mm"), m.P("plate.wall_frame_rim_mm")),
                    "machine_wall_frame_start_v_mm": m.v_plate, "installed_frame": installed,
                    "stand_ins": "the lid and the tray without their vents, grooves and engraving: they hold more material than the real parts, so every distance is the same or smaller"}, lines), gate]


def cable_gate_result(m: case.Model, form: str, slide_free: float) -> Dict[str, Any]:
    """The cable's way out: the notch is open to the outside through the lid's lip, and the lip's gate spans it at every pose of the slide that frees the toes."""
    P = m.P
    n0, n1 = P("lid.cable_notch_v_mm")
    nh = P("lid.cable_notch_height_mm")
    right_in = 45.0 + P("case.interior_right_mm")
    z_mid = P("case.z_wall_top_mm") - nh / 2
    tilt = math.radians(P("lid.sweep_tilt_deg"))
    gate = m.skin.cable_gate(m.core).bounds if hasattr(m.skin, "cable_gate") else None
    spanned, worst = False, None
    if gate is not None:
        # the lid slides away from the wall along its tilted plane while the cable stays in the notch: the gate, carried with the lid, must still cover the notch
        slides = np.arange(0.0, slide_free + 1e-9, 0.1)
        shifts = slides * math.cos(tilt)
        short = [min(n0 - (gate[1] + sh), (gate[3] + sh) - n1) for sh in shifts]
        worst = float(min(short)) if short else None
        spanned = worst is not None and worst >= -1e-9
    sc = scene(m, form)
    samples = [(right_in + 1.0, float(v), z_mid) for v in np.linspace(n0 + 0.5, n1 - 0.5, 5)]
    blocked = [(round(p[1], 2), sc.first_hit(p, (1, 0, 0))["solid"]) for p in samples if sc.first_hit(p, (1, 0, 0)) is not None]
    passed = spanned and not blocked
    return result("c4.cable_gate_follows_the_slide", "C4", passed,
                  f"the lid's gate over the cable notch spans it at every pose of the {slide_free:.1f} mm slide that frees the toes (least margin {worst if worst is not None else float('nan'):.2f} mm), "
                  f"and {len(samples) - len(blocked)} of {len(samples)} notch sample points look outward through the lip to open air",
                  {"gate_v_mm": [gate[1], gate[3]] if gate else None, "lead_toward_the_plate_mm": n0 - gate[1] if gate else None, "notch_v_mm": [n0, n1], "slide_to_free_the_toes_mm": slide_free,
                   "least_margin_mm": worst, "gate_spans_notch_at_every_pose": spanned, "outward_rays_blocked": blocked, "sample_points": len(samples)})


# ---------------------------------------------------------------------------------------------------------------------
# Screws and driver approach
# ---------------------------------------------------------------------------------------------------------------------

def check_c5_c11(m: case.Model, form: str = "single") -> List[Dict[str, Any]]:
    P = m.P
    out = []
    # lid screw
    s = next(x for x in m.screws if x["kind"] == "lid")
    from build123d import Cylinder, Pos
    zt = P("case.z_lid_top_mm")
    shaft = Pos(s["u"], s["v"], zt + 40.0) * Cylinder(P("screws.driver_dia_mm") / 2, 80.0)
    interference = 0.0
    for part in (m.parts[f"lid_{form}"], m.parts["tray"], m.parts["plate"], wall_frame(m)):
        inter = shaft & part
        interference += inter.volume if inter is not None and hasattr(inter, "volume") else 0.0
    gap_frame = float(shaft.distance_to(wall_frame(m)))
    wall_dist = s["v"] - m.v_plate
    min_wall = 20.0
    proud = float(m.mesh(f"lid_{form}").bounds[1][2] - zt)
    out.append(result("c5.lid_screw_reached", "C5", interference < 1e-6 and gap_frame > 3.0 and wall_dist >= min_wall and proud <= 1e-6,
                      f"the lid screw at u {s['u']:.2f}, v {s['v']:.2f} is driven from below (the case frame's +z is down when installed) with nothing in the way; {wall_dist:.1f} mm from the wall plane, {gap_frame:.1f} mm from the opening frame",
                      {"lid_screw_uv_mm": [s["u"], s["v"]], "driver_approach": "straight along -z toward the screw, from below the installed case (+z side), driver shaft dia %.1f mm" % P("screws.driver_dia_mm"),
                       "driver_shaft_interference_mm3": interference, "distance_to_wall_plane_mm": wall_dist,
                       "required_distance_to_wall_mm": min_wall, "distance_to_opening_frame_mm": gap_frame, "head_proud_of_lid_top_mm": proud,
                       "retention_without_screw": "two toes under hooks on the pilasters hold the plate end; one screw holds the far end"}))
    # toes: with the lid lifted straight up at the plate end the toes meet the hooks
    from build123d import Pos
    lift = 1.0
    engaged = []
    for u in m.info["toe_u"]:
        window = case.box(u - 2.0, u + 2.0, m.v_end - 1.0, m.v_end + 12.0, 10.0, 25.0)
        lid_part = m.parts[f"lid_{form}"] & window
        moved = Pos(0, 0, lift) * lid_part
        inter = moved & m.parts["tray"]
        engaged.append(float(inter.volume) if inter is not None and hasattr(inter, "volume") else 0.0)
    out.append(result("c5.toes_hold_plate_end", "C5", all(v > 0.05 for v in engaged),
                      f"lifting the lid straight up {lift:.1f} mm at the plate end drives each toe's barb into its hook by {engaged[0]:.2f} and {engaged[1]:.2f} mm3 of interference (needs more than 0.05), so the plate end is held without a screw",
                      {"lift_mm": lift, "interference_mm3": engaged, "toe_u_mm": list(m.info["toe_u"])}))
    out.append(result("c5.retention_stated", "C5", True,
                      "the lid is retained at the plate end by two toes tucked under 45 degree hooks on the pilasters and at the far end by one M3 x 10 screw",
                      {"fixings": ["toe left pilaster", "toe right pilaster", "lid screw"], "toe_u_mm": list(m.info["toe_u"])}))
    # tab screws: driver approach with the lid off
    tilts = {}
    details = {}
    ok = True
    for ref in case.TRIAC_REFS:
        angle, gaps = case.driver_tilt(m, ref)
        tilts[ref] = angle
        nearest = min(gaps, key=gaps.get)
        details[ref] = {"tilt_deg": angle, "line": f"axis from the screw head at u {m.triac_u[ref]:.2f}, z {m.tab_hole_z:.2f}, rising toward +v at {angle:.1f} deg",
                        "nearest": nearest, "nearest_gap_mm": gaps[nearest], "gaps_mm": gaps}
        ok &= angle == angle
    m.info["driver_tilt_deg"] = {k: v for k, v in tilts.items() if v == v}
    out.append(result("c11.tab_screw_driver_reached", "C11", ok,
                      "each triac tab screw is reached by a driver with the lid off: " + "; ".join(
                          f"{r}: {tilts[r]:.1f} deg from -v, nearest {details[r]['nearest']} {details[r]['nearest_gap_mm']:.2f} mm" for r in case.TRIAC_REFS),
                      {"drivers": details, "driver_shaft_dia_mm": P("screws.driver_dia_mm"), "limit_deg": P("screws.driver_max_tilt_deg"),
                       "wall_relief": "none needed: at this tilt the shaft passes over the far-end wall"}))
    # blade terminals reachable with the lid on: apertures present over each blade, and clear sight to the tab
    sc = scene(m, form)
    figures = []
    ok = True
    for ap in case.aperture_boxes(m):
        blade = m.bodies[ap["ref"]]["shape"].bounding_box()
        inside = (blade.min.X >= ap["u"] - ap["du"] / 2 and blade.max.X <= ap["u"] + ap["du"] / 2 and blade.min.Y >= ap["v"] - ap["dv"] / 2 and blade.max.Y <= ap["v"] + ap["dv"] / 2)
        hit = sc.first_hit((ap["u"], ap["v"], 40.0), (0, 0, -1))
        reach = hit is not None and hit["solid"] == ap["ref"]
        figures.append({"blade": ap["ref"], "aperture_mm": [ap["du"], ap["dv"]], "blade_inside_aperture": bool(inside), "line_from_above_reaches_blade": bool(reach)})
        ok &= inside and reach
    out.append(result("c11.blade_terminals_reachable_lid_on", "C11", ok,
                      "each blade stands inside its aperture and a line straight down through the aperture reaches it with the lid on",
                      {"blades": figures, "push_on_direction": "-z"}))
    return out


def check_fixings(m: case.Model, form: str = "single") -> List[Dict[str, Any]]:
    """Every fixing's approach in the installed frame: from below, or from the plate's back."""
    from build123d import Axis, Cylinder, Pos
    P = m.P
    g = case.gravity(m)
    back = np.array([0.0, -1.0, 0.0])
    rows = []
    ok = True

    def side(origin: np.ndarray) -> str:
        parts = []
        if float(origin @ g) > 0.05:
            parts.append("below")
        if float(origin @ back) > 0.2:
            parts.append("behind the plate")
        if float(origin @ -g) > 0.2:
            parts.append("above")
        if abs(float(origin @ np.array([0.0, 1.0, 0.0]))) > 0.2 and float(origin @ np.array([0.0, 1.0, 0.0])) > 0:
            parts.append("out from the wall")
        return " and ".join(parts)

    # the lid screw: straight from the +z side, the lid on or off
    lid_screw = next(s for s in m.screws if s["kind"] == "lid")
    origin = np.array([0.0, 0.0, 1.0])
    rows.append({"fixing": "lid screw", "driver_from": side(origin), "origin_direction": origin.tolist(), "needs_lid_off": False,
                 "centre_uvz_mm": [lid_screw["u"], lid_screw["v"], P("case.z_lid_top_mm")]})
    ok &= float(origin @ g) > 0.5
    # the board screw H1, with the lid off: a driver shaft along the screw's own axis
    h1 = next(s for s in m.screws if s["kind"] == "h1")
    top = h1["z1"]
    shaft = Pos(h1["u"], h1["v"], top + 40.0 / 2) * Cylinder(P("screws.driver_dia_mm") / 2, 40.0)
    shaft = m.to_board_frame(shaft)
    gaps = {}
    for name in ("tray", "plate"):
        gaps[name] = float(shaft.distance_to(m.parts[name]))
    for name, body in m.bodies.items():
        if name not in ("board",):
            gaps[name] = float(shaft.distance_to(body["shape"]))
    nearest = min(gaps, key=gaps.get)
    origin = np.array([0.0, 0.0, 1.0])
    rows.append({"fixing": "board screw H1", "driver_from": side(origin), "origin_direction": origin.tolist(), "needs_lid_off": True,
                 "centre_uvz_mm": [h1["u"], h1["v"], top], "driver_shaft_dia_mm": P("screws.driver_dia_mm"), "nearest": nearest, "nearest_gap_mm": gaps[nearest]})
    ok &= float(origin @ g) > 0.5 and gaps[nearest] >= 0.3
    # the tab screws, with the lid off: the least tilt that clears, rising toward +v
    tilts = m.info.get("driver_tilt_deg") or {ref: case.driver_tilt(m, ref)[0] for ref in case.TRIAC_REFS}
    for ref in case.TRIAC_REFS:
        a = math.radians(tilts[ref])
        origin = np.array([0.0, math.cos(a), math.sin(a)])
        rows.append({"fixing": f"tab screw {ref}", "driver_from": f"out from the wall, {abs(tilts[ref]):.1f} degrees {'below' if float(origin @ g) > 0 else 'above'} level", "origin_direction": [round(float(x), 4) for x in origin], "needs_lid_off": True,
                     "tilt_deg": tilts[ref], "centre_uvz_mm": [m.triac_u[ref], m.v_plate, m.tab_hole_z]})
        ok &= float(origin @ g) >= 0.0
    # the tray-to-plate screws, from the plate's back face before the plate goes on the wall
    origin = np.array([0.0, -1.0, 0.0])
    rows.append({"fixing": "tray-to-plate screws (2)", "driver_from": side(origin), "origin_direction": origin.tolist(), "needs_lid_off": False,
                 "note": "put in from the plate's back face with the plate off the wall; the lid and the board need not be off"})
    ok &= float(origin @ back) > 0.5
    lines = [f"{r['fixing']:26s} driver from {r['driver_from']}{', lid off' if r['needs_lid_off'] else ''}" for r in rows]
    return [result("c5.fixings_reached_installed", "C5", ok,
                   "installed (plate vertical, component side down): the lid screw is reached from below, the board screw from below with the lid off, "
                   + "both tab screws from out from the wall, " + " and ".join(sorted({r["driver_from"].split(", ", 1)[1] for r in rows if r["fixing"].startswith("tab screw")}))
                   + " with the lid off (a near-horizontal reach along the plate's face, not a reach from below), the two tray screws from the plate's back",
                   {"installed_frame": {"gravity": g.tolist()}, "fixings": rows}, lines)]


# ---------------------------------------------------------------------------------------------------------------------
# Board support, backing and stiffness
# ---------------------------------------------------------------------------------------------------------------------

def check_c6_c9(m: case.Model, form: str = "single") -> List[Dict[str, Any]]:
    P = m.P
    out = []
    tray_sc = Scene(m, ["tray"])
    tol = 0.02
    rows = []
    ok = True
    contact = []
    for s in m.supports:
        if s["kind"] == "pillar":
            pts = [(s["u"], s["v"])]
            label = f"pillar ({s['u']:.1f}, {s['v']:.1f})"
        elif s["kind"] == "h1 boss":
            pts = [(s["u"] + 2.5, s["v"])]
            label = "H1 boss"
        elif s["kind"] == "backing rib":
            pts = [((s["u0"] + s["u1"]) / 2, (s["v0"] + s["v1"]) / 2)]
            label = "backing rib"
        else:
            continue
        for (u, v) in pts:
            top = tray_top_at(tray_sc, u, v)
            want = m.underside_z(v)
            err = None if top is None else top - want
            rows.append({"support": label, "tray_top_z_mm": top, "board_underside_z_mm": want, "gap_mm": err})
            ok &= err is not None and abs(err) <= tol
            if label != "backing rib":
                contact.append((u, v))
            else:
                contact.append((s["u0"], s["v0"]))
                contact.append((s["u1"], s["v1"]))
    outline = m.board.outline
    centroid = outline.centroid
    hull = shapely.MultiPoint(contact).convex_hull
    stable = hull.contains(Point(centroid.x, centroid.y))
    # the hold-down finger: the hook underside over the board's edge
    fv = P("seat.finger_v_mm")
    hook_gap = None
    probe_u = 0.4
    hit = tray_sc.first_hit((probe_u, fv, m.top_z(fv) + 0.0), (0, 0, 1), length=6.0)
    if hit:
        hook_gap = hit["distance"]
    hook_ok = hook_gap is not None and 0.0 <= hook_gap <= 1.2
    lid_gap = float(m.parts[f"lid_{form}"].distance_to(m.bodies["board"]["shape"]))
    out.append(result("c6.board_seat", "C6", ok and stable and len(contact) >= 3,
                      f"{len(rows)} seat points of the tray's own solid meet the board's underside plane within {tol:.2f} mm; the contact polygon holds the board's centroid",
                      {"seat_points": rows, "tolerance_mm": tol, "contact_polygon_contains_board_centroid": bool(stable),
                       "board_centroid_uv": [centroid.x, centroid.y]}))
    out.append(result("c6.hold_down_and_h1", "C6", hook_ok and lid_gap > 0.5,
                      f"the finger's hook stands {hook_gap if hook_gap is None else round(hook_gap, 2)} mm over the board's edge at v {fv:.1f}; H1 takes an M3 x {P('screws.h1_length_mm'):.0f} into a {P('case.pilot_dia_mm'):.1f} mm pilot; the lid is {lid_gap:.1f} mm from the board, so removing it leaves the board held",
                      {"hook_gap_over_board_mm": hook_gap, "finger_v_mm": fv, "h1_uv_mm": [m.board.h1[0], m.board.h1[1]],
                       "lid_to_board_mm": lid_gap, "what_holds_the_board": ["11 pillars", "H1 boss and screw", "blade backing rib", "hold-down finger on the left wall", "locating ribs on the left and far walls"]}))
    # backing under each blade
    rib = next(s for s in m.supports if s["kind"] == "backing rib")
    areas = []
    ok = True
    for ref in ("J941", "J921", "J911"):
        c = m.board.refs[ref]["courtyard"]
        region = sh_box(c[0], rib["v0"], c[2], rib["v1"])
        # sample the footprint of the courtyard along the rib on a grid: how much of it the tray's top touches the underside
        n = 0
        touching = 0
        for u in np.linspace(c[0] + 0.05, c[2] - 0.05, 12):
            for v in np.linspace(rib["v0"] + 0.05, rib["v1"] - 0.05, 4):
                n += 1
                top = tray_top_at(tray_sc, float(u), float(v))
                if top is not None and abs(top - m.underside_z(float(v))) <= tol:
                    touching += 1
        frac = touching / n
        area = region.area * frac
        areas.append({"blade": ref, "courtyard_u_mm": [c[0], c[2]], "rib_v_mm": [rib["v0"], rib["v1"]], "contact_area_mm2": area, "contact_fraction": frac})
        ok &= frac >= 0.99
    # stiffness: the tray's section at the far end, as a cantilever from the pilasters
    tm = m.mesh("tray")
    v_sec = 56.0
    segs = trimesh.intersections.mesh_plane(tm, plane_normal=[0, 1, 0], plane_origin=[0, v_sec, 0], return_faces=False)
    from shapely.ops import polygonize
    lines = [LineString([(round(float(a[0]), 4), round(float(a[2]), 4)), (round(float(b[0]), 4), round(float(b[2]), 4))]) for a, b in segs]
    pieces = sorted(polygonize(unary_union(lines)), key=lambda p: -p.area)
    region = pieces[0]
    for p in pieces[1:]:
        region = region.symmetric_difference(p)
    polys = list(region.geoms) if hasattr(region, "geoms") else [region]
    area, zc, I = second_moment(polys)
    E = P("material.modulus_MPa")
    force = P("blade.insertion_force_N")
    blade_v = (rib["v0"] + rib["v1"]) / 2
    L = blade_v - m.v_end
    delta_tip = force * L ** 3 / (3 * E * I)
    first = min((s for s in m.supports if s["kind"] == "pillar"), key=lambda s: s["v"])
    x = first["v"] - m.v_end
    delta_triac = force * x ** 2 * (3 * L - x) / (6 * E * I)
    allowed = P("material.allowed_board_motion_mm")
    out.append(result("c9.backing_contact_and_stiffness", "C9", ok and delta_triac <= allowed,
                      f"the backing rib touches the board under each blade; under {force:.1f} N the tray section (I = {I:.0f} mm^4, span {L:.1f} mm) deflects {delta_tip:.3f} mm at the blades and {delta_triac:.4f} mm at the triac end, against {allowed:.2f} mm allowed",
                      {"contact": areas, "insertion_force_N": force, "push_on_direction": "-z (into the board)", "section_at_v_mm": v_sec,
                       "section_area_mm2": area, "second_moment_mm4": I, "centroid_z_mm": zc, "modulus_MPa": E, "span_mm": L,
                       "deflection_at_blades_mm": delta_tip, "deflection_at_triac_end_mm": delta_triac, "allowed_mm": allowed,
                       "basis": "a cantilever from the plate end, uniform section as at v %.0f (conservative: the pilasters stiffen the root), tip load" % v_sec,
                       "rib_section_mm": [P("seat.rib_width_mm"), float(m.underside_z(blade_v) - m.floor_top(blade_v))],
                       "rib_span_between_buttresses_mm": [8.1, 11.4]}))
    out.append(root_result(m, force, L, x, delta_triac, allowed))
    return out


def root_figures(m: case.Model, force: float, span: float, x: float, flex_triac: float) -> Dict[str, Any]:
    """The tray root's tension under the push-on and the pull-off load and the triac end's motion at the inserts' stance.

    The push-on force acts along z at the blades, a lever `span` from the plate end, so the root carries a moment and a shear. The tray's
    end face bears on the plate down to the plate's lower edge, which is the pivot of the push-on; every insert above it is pulled out of its
    pilaster in proportion to its height over the pivot. The pull-off direction reverses the load and turns the root about the pilaster's top,
    where the lid's hooks bear, so each insert is then pushed in or pulled by its depth under that top. The inserts' pull-out is the stated
    allowance, one figure for each insert. The root's rotation, from the plastic shearing about the insert's knurled cylinder, moves the
    board's triac end on top of the tray's own flexure."""
    P = m.P
    pivot = m.info["plate"]["z0"]
    top = P("case.z_wall_top_mm")
    zs = [float(z) for z in P("screws.tray_plate_z_mm")]
    n_pil = int(P("screws.tray_plate_count_per_pilaster"))
    levers = [z - pivot for z in zs]
    levers_off = [top - z for z in zs]
    sides = len(m.info["tray_pilaster_u"])
    moment = force * span
    k = moment / (sides * sum(a * a for a in levers))               # N per mm of height over the pivot
    tension = {f"z {z:g}": k * a for z, a in zip(zs, levers)}
    t_max = k * max(levers)
    k_off = moment / (sides * sum(a * a for a in levers_off))
    tension_off = {f"z {z:g}": k_off * a for z, a in zip(zs, levers_off)}
    t_off = k_off * max(levers_off)
    d = P("case.insert_hole_dia_mm")
    engaged = P("case.insert_length_mm")
    capacity = P("screws.tray_insert_pullout_N")
    G = P("material.modulus_MPa") / (2.0 * (1.0 + P("material.poisson_ratio")))
    area = math.pi * d * engaged
    shear_disp = t_max * P("screws.tray_insert_shear_layer_mm") / (G * area)
    shear_disp_off = t_off * P("screws.tray_insert_shear_layer_mm") / (G * area)
    rotation = shear_disp / max(levers)
    rotation_off = shear_disp_off / max(levers_off)
    root_motion = rotation * x
    root_motion_off = rotation_off * x
    total = flex_triac + root_motion
    total_off = flex_triac + root_motion_off
    proof = P("screws.tray_proof_factor")
    return {"pivot_z_mm": pivot, "pull_off_pivot_z_mm": top, "screw_z_mm": zs, "levers_mm": levers, "pull_off_levers_mm": levers_off, "screws_per_pilaster": n_pil, "pilasters": sides,
            "moment_Nmm": moment, "tension_per_screw_N": tension, "tension_max_N": t_max, "pull_off_tension_per_screw_N": tension_off, "pull_off_tension_max_N": t_off,
            "engaged_length_mm": engaged, "insert_hole_dia_mm": d, "pullout_allowance_N": capacity, "pullout_capacity_N": capacity,
            "utilisation": t_max / capacity, "pull_off_utilisation": t_off / capacity, "proof_factor": proof, "proof_load_N": proof * force,
            "proof_tension_max_N": proof * max(t_max, t_off), "pilot_shear_displacement_mm": shear_disp,
            "root_rotation_rad": rotation, "root_motion_at_triac_end_mm": root_motion, "pull_off_root_motion_at_triac_end_mm": root_motion_off,
            "tray_flexure_at_triac_end_mm": flex_triac, "triac_end_motion_mm": total, "pull_off_triac_end_motion_mm": total_off, "span_mm": span, "x_mm": x, "insertion_force_N": force}


def root_result(m: case.Model, force: float, span: float, x: float, flex_triac: float, allowed: float) -> Dict[str, Any]:
    f = root_figures(m, force, span, x, flex_triac)
    ok = (f["tension_max_N"] <= f["pullout_capacity_N"] and f["pull_off_tension_max_N"] <= f["pullout_capacity_N"]
          and max(f["triac_end_motion_mm"], f["pull_off_triac_end_motion_mm"]) <= allowed and min(f["levers_mm"]) > 0.0 and min(f["pull_off_levers_mm"]) > 0.0)
    return result("c9.tray_root_tension_and_triac_end_motion", "C9", ok,
                  f"at the inserts' stance (z {', '.join(f'{z:g}' for z in f['screw_z_mm'])}, push-on pivot at the plate's lower edge z {f['pivot_z_mm']:.1f}, pull-off pivot at the pilaster's top z {f['pull_off_pivot_z_mm']:.1f}) the {force:.1f} N load loads each insert with {f['tension_max_N']:.0f} N pushing on and {f['pull_off_tension_max_N']:.0f} N pulling off "
                  f"against {f['pullout_capacity_N']:.0f} N of assumed pull-out, and the triac end moves {f['triac_end_motion_mm']:.4f} mm pushing on and {f['pull_off_triac_end_motion_mm']:.4f} mm pulling off against {allowed:.2f} mm allowed",
                  dict(f, allowed_motion_mm=allowed, basis="moment of the load about the pivot shared among the inserts in proportion to their distance from it; pull-out is the stated allowance for one insert; the shear displacement is on the insert's hole cylinder"))


# ---------------------------------------------------------------------------------------------------------------------
# Screws and mains copper
# ---------------------------------------------------------------------------------------------------------------------

def check_c7(m: case.Model) -> List[Dict[str, Any]]:
    P, sep = m.P, m.basis
    out = []
    basis_dist = max(sep["clearance_mains_mm"], sep["creepage_mains_mm"])
    rows = []
    ok = True
    for s in m.screws:
        pts = axis_points(s)
        per = copper_distance(m, pts)
        nearest_layer = min(per, key=lambda k: per[k][0])
        d, label = per[nearest_layer]
        if s["kind"] == "lid":
            need = sep["creepage_lv_mm"]
        elif s["kind"] == "tray_plate":
            need = max(3.0, basis_dist)
        elif s["kind"] == "insert":
            need = basis_dist
        elif s["kind"] == "h1":
            need = basis_dist
        else:
            need = sep["clearance_mains_mm"]
        passed = d >= need
        below = {}
        if s["kind"] == "insert":
            # the sphere the metal is modelled by is exact toward the board only while the whole hole and its wall lie above the board's higher copper plane: the tear-drop's roof
            # (the radius times sqrt 2) and the wall stand above the axis, so the axis has to stand at least that far above the copper
            higher_plane = max(0.0, -m.board.thickness)
            above = min(m.board_local((p[0], p[1], p[2]))[2] for p in pts) - higher_plane
            roof = P("case.insert_hole_dia_mm") / 2 * math.sqrt(2.0)
            below = {"copper_below_axis_mm": above, "copper_below_axis_required_mm": roof + P("case.insert_wall_min_mm"), "tear_drop_roof_mm": roof,
                     "copper_below_axis_pass": above >= roof + P("case.insert_wall_min_mm") - 1e-9}
            passed &= below["copper_below_axis_pass"]
        ok &= passed
        centre = (s["u"], s["v"] if "v" in s else (s["v0"] + s["v1"]) / 2, s["z"] if "z" in s else (s["z0"] + s["z1"]) / 2)
        rows.append({"screw": s["id"], "kind": s["kind"], "centre_uvz_mm": [round(c, 3) for c in centre], "distance_mm": d, "layer": nearest_layer,
                     "nearest_item": label, "per_layer_mm": {k: v[0] for k, v in per.items()}, "required_mm": need, **below, "pass": passed})
    lines = [f"{r['screw']:26s} centre ({r['centre_uvz_mm'][0]:7.2f}, {r['centre_uvz_mm'][1]:7.2f}, {r['centre_uvz_mm'][2]:6.2f}) "
             f"nearest {r['nearest_item']} on {r['layer']} at {r['distance_mm']:.2f} mm (needs {r['required_mm']:.1f})" for r in rows]
    out.append(result("c7.screws_clear_of_mains_copper", "C7", ok,
                      f"every screw keeps its figure from Mains copper on both layers; the least margin is {min(r['distance_mm'] - r['required_mm'] for r in rows):.2f} mm",
                      {"screws": rows, "basis_distance_mm": basis_dist, "tray_to_plate_design_mm": 3.0, "lid_mm": sep["creepage_lv_mm"],
                       "metal_model": "each screw is swept as spheres of its shaft or head radius along its axis; an insert is swept as spheres of its hole's radius plus the wall, which is exact toward the board only while the axis stands above the board's higher copper plane by at least the tear-drop roof (the hole's radius times sqrt 2, the roof standing above the axis, away from the board) plus the wall, the copper_below_axis_mm figure of its row"}, lines))
    # H1 pad and courtyard against Mains copper on both layers, in plan
    h1 = m.board.refs["H1"]
    c = h1["courtyard"]
    court = sh_box(c[0], c[1], c[2], c[3])
    pad = Point(h1["pads"][0]["u"], h1["pads"][0]["v"]).buffer(max(h1["pads"][0]["size"]) / 2)
    figs = {}
    ok2 = True
    for layer in ("F.Cu", "B.Cu"):
        g = m.board.mains_layer(layer)
        figs[layer] = {"pad_mm": float(pad.distance(g)), "courtyard_mm": float(court.distance(g))}
        ok2 &= figs[layer]["pad_mm"] >= basis_dist and figs[layer]["courtyard_mm"] >= basis_dist
    out.append(result("c7.h1_pad_and_courtyard", "C7", ok2,
                      f"H1's pad and courtyard keep at least {min(min(v.values()) for v in figs.values()):.2f} mm from Mains copper on both layers (needs {basis_dist:.1f})",
                      {"required_mm": basis_dist, "layers": figs}))
    return out


# ---------------------------------------------------------------------------------------------------------------------
# Slots
# ---------------------------------------------------------------------------------------------------------------------

def check_c8(m: case.Model, form: str = "single") -> List[Dict[str, Any]]:
    P = m.P
    keep = P("seat.slot_keepout_mm")
    t = m.board.thickness
    rows = []
    ok = True
    for i, slot in enumerate(m.board.slots):
        prism = m.to_board_frame(case.prism(list(slot.exterior.coords)[:-1], -t, 0.0))
        gaps = {}
        for name in ("tray", f"lid_{form}"):
            gaps[name] = float(prism.distance_to(m.parts[name]))
        least = min(gaps.values())
        rows.append({"slot": "AB"[i], "v_mm": [slot.bounds[1], slot.bounds[3]], "mouth_u_mm": slot.bounds[2], "gaps_mm": gaps, "least_mm": least})
        ok &= least >= keep
    return [result("c8.slot_mouths_clear", "C8", ok,
                   "no solid of the tray, lid or rib comes within %.1f mm of either slot's open area, mouth included; least %.3f mm" % (keep, min(r["least_mm"] for r in rows)),
                   {"required_mm": keep, "slots": rows, "slot_open_area": "the notch polygon of Edge.Cuts extruded through the board's thickness, mouth at u 45"})]


# ---------------------------------------------------------------------------------------------------------------------
# Bed fit and overhang
# ---------------------------------------------------------------------------------------------------------------------

def print_matrix(m: case.Model, name: str) -> np.ndarray:
    shape = m.parts[name]
    rot = np.eye(4)
    rot[:3, :3] = case.print_rotation(name)
    bounds = m.mesh(name).bounds
    pts = np.array([[x, y, z] for x in bounds[:, 0] for y in bounds[:, 1] for z in bounds[:, 2]])
    moved = (rot[:3, :3] @ pts.T).T
    shift = -moved.min(axis=0)
    mat = rot.copy()
    mat[:3, 3] = shift
    return mat


OVERHANG_NZ_TOLERANCE = 5e-4      # a face is flagged only when its downward normal exceeds the limit's by more than this


def min_unflagged_angle_deg(limit_deg: float) -> float:
    """The flattest angle from the horizontal, in degrees, a downward face may have and not be flagged by the overhang check at the given limit."""
    return math.degrees(math.acos(math.sin(math.radians(limit_deg)) + OVERHANG_NZ_TOLERANCE))


def overhang_clusters(mesh: trimesh.Trimesh, limit_deg: float = 45.0, bridge_mm: float = 3.5, noise_mm2: float = 1.0) -> List[Dict[str, Any]]:
    """Clusters of faces that face down flatter than the limit and are off the bed, with their bridge span."""
    limit_nz = -math.sin(math.radians(limit_deg)) - OVERHANG_NZ_TOLERANCE
    flagged = np.where((mesh.face_normals[:, 2] < limit_nz) & (mesh.triangles_center[:, 2] > 0.05))[0]
    if len(flagged) == 0:
        return []
    adj = mesh.face_adjacency
    mask = np.isin(adj[:, 0], flagged) & np.isin(adj[:, 1], flagged)
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    idx = {f: i for i, f in enumerate(flagged)}
    rows = [idx[a] for a, b in adj[mask]]
    cols = [idx[b] for a, b in adj[mask]]
    graph = coo_matrix((np.ones(len(rows)), (rows, cols)), shape=(len(flagged), len(flagged)))
    n, labels = connected_components(graph, directed=False)
    clusters = []
    for k in range(n):
        faces = flagged[labels == k]
        tris = mesh.triangles[faces]
        lo, hi = tris.reshape(-1, 3).min(axis=0), tris.reshape(-1, 3).max(axis=0)
        flat = shapely.union_all([ShPolygon(t[:, :2]).buffer(0.002) for t in tris if abs((t[1, 0] - t[0, 0]) * (t[2, 1] - t[0, 1]) - (t[2, 0] - t[0, 0]) * (t[1, 1] - t[0, 1])) > 1e-9])
        # the span to bridge is the widest circle the region holds
        span = float(2.0 * shapely.maximum_inscribed_circle(flat, 0.01).length)
        area = float(mesh.area_faces[faces].sum())
        if area < noise_mm2:
            continue
        clusters.append({"area_mm2": area, "bbox_lo": lo.tolist(), "bbox_hi": hi.tolist(), "bridge_span_mm": span,
                         "bridgeable": span <= bridge_mm + 1e-9, "z_mm": float(tris[:, :, 2].mean())})
    return clusters


def critical_regions(m: case.Model, name: str) -> Dict[str, List[Tuple[float, float, float, float, float, float]]]:
    """The faces the record names, as boxes (u0, u1, v0, v1, z0, z1) in the case frame."""
    P = m.P
    regions: Dict[str, List[Tuple[float, ...]]] = {}
    if name == "tray":
        e = case_extent(m)
        regions["plate-end faces"] = [(e["u0"] - 0.1, e["u1"] + 0.1, m.v_end - 0.05, m.v_end + 0.05, -7.0, 21.0)]
        depth = P("case.insert_hole_depth_mm")
        seats = []
        for u in m.info["tray_pilaster_u"]:
            for z in P("screws.tray_plate_z_mm"):
                seats.append((u - 2.1, u + 2.1, m.v_end - 0.1, m.v_plate + depth + 0.1, z - 2.1, z + 3.0))
        hu, hv, _ = m.board.h1
        seats.append((hu - 1.6, hu + 1.6, hv - 1.6, hv + 1.6, -9.0, 1.0))
        seats.append((P("screws.lid_u_mm") - 1.6, P("screws.lid_u_mm") + 1.6, P("screws.lid_v_mm") - 1.6, P("screws.lid_v_mm") + 1.6, 10.0, 20.0))
        regions["screw seats"] = seats
        right_in = 45.0 + P("case.interior_right_mm")
        regions["slot-rule faces"] = [(right_in - 0.2, right_in + 0.2, 0.0, 75.5, -5.0, 21.0)]
        zt = P("case.z_wall_top_mm")
        regions["lid-fit faces"] = [(-7.0, 54.0, 0.0, 84.0, zt - 0.1, zt + 0.1)] + [(u - 1.4, u + 1.4, m.v_end, m.v_end + 6.0, zt - 4.5, zt + 0.1) for u in m.info["toe_u"]]
    elif name.startswith("lid"):
        za = P("case.z_lid_under_mm")
        regions["lid-fit faces"] = [(-7.0, 54.0, -1.0, 84.0, za - 4.5, za + 0.1)]
        regions["screw seat"] = [(P("screws.lid_u_mm") - 3.2, P("screws.lid_u_mm") + 3.2, P("screws.lid_v_mm") - 3.2, P("screws.lid_v_mm") + 3.2, za - 4.0, P("case.z_lid_top_mm") + 0.1)]
    return regions


def critical_plane_boxes(m: case.Model, name: str) -> List[Tuple[str, Tuple[float, ...]]]:
    """The critical faces the record states as a plane (a box 0.5 mm thick or less in one direction), as (face name, box) in the case frame."""
    return [(rname, tuple(b)) for rname, boxes in critical_regions(m, name).items() for b in boxes if min(b[1] - b[0], b[3] - b[2], b[5] - b[4]) <= 0.5]


def critical_face_selector(m: case.Model, name: str, tol: float = 0.03) -> Callable[[np.ndarray, np.ndarray], Dict[str, np.ndarray]]:
    """A function that picks, from triangles in the case frame (n x 3 x 3) and their unit normals (n x 3), the triangles that ARE critical faces,
    face by face and not box by box: per critical face name, a boolean mask. A triangle is picked when all three corners lie in one of the
    named boxes and, by the kind of face the box stands for:
      a plane box (0.5 mm thick or less): the triangle faces along the thin direction;
      the lid-fit faces: the triangle faces along an axis (the mating planes and the lip, not a slanted wall that merely lies in the box);
      a screw seat box: the triangle's centroid lies within the seat radius of the screw axis, the box's own half width less 0.2 mm."""
    regions = critical_regions(m, name)

    def select(tri: np.ndarray, normals: np.ndarray) -> Dict[str, np.ndarray]:
        centroid = tri.mean(axis=1)
        picked: Dict[str, np.ndarray] = {}
        for rname, boxes in regions.items():
            mask = np.zeros(len(tri), dtype=bool)
            for b in boxes:
                lo = np.array([b[0], b[2], b[4]]) - tol
                hi = np.array([b[1], b[3], b[5]]) + tol
                inside = np.all((tri >= lo) & (tri <= hi), axis=(1, 2))
                dims = [b[1] - b[0], b[3] - b[2], b[5] - b[4]]
                thin = [i for i, d in enumerate(dims) if d <= 0.5]
                if thin:
                    inside &= np.abs(normals[:, thin[0]]) > 0.9
                elif "lid-fit" in rname:
                    inside &= np.abs(normals).max(axis=1) > 0.99
                elif "screw seat" in rname:
                    axis = int(np.argmax(dims))
                    cross = [i for i in range(3) if i != axis]
                    centre = np.array([(b[2 * i] + b[2 * i + 1]) / 2 for i in cross])
                    radius = min(dims[i] for i in cross) / 2 - 0.2
                    inside &= np.linalg.norm(centroid[:, cross] - centre, axis=1) <= radius
                mask |= inside
            picked[rname] = mask
        return picked

    return select


def box_to_print(box: Tuple[float, ...], mat: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    u0, u1, v0, v1, z0, z1 = box
    pts = np.array([[x, y, z] for x in (u0, u1) for y in (v0, v1) for z in (z0, z1)])
    moved = (mat[:3, :3] @ pts.T).T + mat[:3, 3]
    return moved.min(axis=0), moved.max(axis=0)


def check_c14(m: case.Model) -> List[Dict[str, Any]]:
    P = m.P
    out = []
    bed = (P("printer.bed_x_mm"), P("printer.bed_y_mm"), P("printer.bed_z_mm"))
    rows = []
    fit_ok = True
    over_ok = True
    lines = []
    for name in ("tray", "lid_single", "lid_two"):
        if name not in m.parts:
            continue
        mat = print_matrix(m, name)
        tm = m.mesh(name).copy()
        tm.apply_transform(mat)
        size = tm.bounds[1] - tm.bounds[0]
        fits = bool(size[0] <= bed[0] and size[1] <= bed[1] and size[2] <= bed[2])
        # also the rotated footprint, since a part may be turned on the bed
        clusters = overhang_clusters(tm, P("printer.overhang_limit_deg"), P("printer.bridge_limit_mm"), P("printer.noise_area_mm2"))
        regions = critical_regions(m, name)
        critical_hits = []
        for rname, boxes in regions.items():
            for b in boxes:
                lo, hi = box_to_print(b, mat)
                for c in clusters:
                    if np.all(np.array(c["bbox_hi"]) >= lo - 1e-6) and np.all(np.array(c["bbox_lo"]) <= hi + 1e-6):
                        critical_hits.append({"face": rname, "area_mm2": c["area_mm2"], "bridge_span_mm": c["bridge_span_mm"], "bridgeable": c["bridgeable"]})
        unbridged = [c for c in clusters if not c["bridgeable"]]
        bad_critical = [h for h in critical_hits if not h["bridgeable"]]
        row = {"part": name, "orientation": "outer top face down on the bed (floor down, as modelled)" if name == "tray" else "face down on the bed (turned 180 degrees about u)",
               "installed_orientation": "on top, its outer top face up, holding the board's bare back above the parts" if name == "tray" else "on the underside, its face down, coming off downward",
               "size_mm": [float(x) for x in size], "fits_bed": fits, "overhang_clusters": len(clusters),
               "non_bridgeable_clusters": [{"area_mm2": c["area_mm2"], "span_mm": c["bridge_span_mm"], "z_mm": c["z_mm"], "lo": c["bbox_lo"], "hi": c["bbox_hi"]} for c in unbridged],
               "bridged_clusters": [{"area_mm2": c["area_mm2"], "span_mm": c["bridge_span_mm"], "z_mm": c["z_mm"], "lo": c["bbox_lo"]} for c in clusters if c["bridgeable"]],
               "critical_faces": {k: len(v) for k, v in regions.items()}, "critical_face_overhangs": critical_hits,
               "critical_faces_support_free": not bad_critical}
        rows.append(row)
        fit_ok &= fits
        over_ok &= (not unbridged) and (not bad_critical)
        lines.append(f"{name:11s} {size[0]:6.1f} x {size[1]:6.1f} x {size[2]:6.1f} mm, bed {bed[0]:.0f} x {bed[1]:.0f} x {bed[2]:.0f}: fits {fits}; "
                     f"{len(unbridged)} overhang cluster(s) beyond a {P('printer.bridge_limit_mm'):.1f} mm bridge; {len(clusters) - len(unbridged)} bridged; critical faces support-free {not bad_critical}")
    out.append(result("c14.bed_fit", "C14", fit_ok, "every printed part fits the %.0f x %.0f mm bed in its stated orientation" % (bed[0], bed[1]),
                      {"bed_mm": list(bed), "parts": [{"part": r["part"], "size_mm": r["size_mm"], "orientation": r["orientation"], "installed_orientation": r["installed_orientation"], "fits": r["fits_bed"]} for r in rows]}, lines))
    out.append(result("c14.overhang", "C14", over_ok,
                      "no face flatter than %.0f degrees is left unsupported on any part, and none on the plate-end faces, screw seats, slot-rule faces or lid-fit faces" % P("printer.overhang_limit_deg"),
                      {"limit_deg": P("printer.overhang_limit_deg"), "bridge_limit_mm": P("printer.bridge_limit_mm"), "parts": rows}))
    return out


# ---------------------------------------------------------------------------------------------------------------------
# Openings, finger and drip
# ---------------------------------------------------------------------------------------------------------------------

DIRECTIONS = {"+u": (1, 0, 0), "-u": (-1, 0, 0), "+v": (0, 1, 0), "-v": (0, -1, 0), "+z": (0, 0, 1), "-z": (0, 0, -1)}


def probe_penetration(width: float, tip_dia: float, cyl_dia: float, cone_len: float) -> Tuple[float, float]:
    """How far the stand-in finger enters a slot of the given width: the depth of its tip below the entry plane and the diameter there."""
    r_tip = tip_dia / 2
    if width < tip_dia:
        return 0.0, 0.0
    # hemispherical tip of radius r_tip, then a cone out to the cylinder; the diameter at height h above the cone base
    slope = (cyl_dia - tip_dia) / cone_len
    if width >= cyl_dia:
        return r_tip + cone_len + 1e9, cyl_dia
    h = (width - tip_dia) / slope
    return r_tip + h, width


def cone_directions(g: np.ndarray, half_angle_deg: float, azimuths: Sequence[int] = (8, 16)) -> List[np.ndarray]:
    """Unit directions within a cone about g: the axis, then two rings at half and at the full half angle."""
    g = g / np.linalg.norm(g)
    e1 = np.cross(g, [1.0, 0.0, 0.0] if abs(g[0]) < 0.9 else [0.0, 1.0, 0.0])
    e1 /= np.linalg.norm(e1)
    e2 = np.cross(g, e1)
    dirs = [g]
    for ang, n in zip((half_angle_deg / 2, half_angle_deg), azimuths):
        a = math.radians(ang)
        for k in range(n):
            az = 2 * math.pi * k / n
            dirs.append(math.cos(a) * g + math.sin(a) * (math.cos(az) * e1 + math.sin(az) * e2))
    return dirs


def ray_to_mains(m: case.Model, sc: "Scene", mains_bodies: set, point: Sequence[float], d: Sequence[float]) -> Tuple[bool, Optional[Dict[str, Any]]]:
    """Whether a drip along d could arrive at the point from outside the case, and the Mains copper it reaches if so."""
    back = sc.first_hit(point, tuple(-x for x in d))
    if back is not None:
        return False, None
    fwd = sc.first_hit(point, d)
    if fwd is None:
        return True, None
    mains = fwd["solid"] in mains_bodies
    if fwd["solid"] == "board" and abs(fwd["normal"][2]) > 0.5:
        lp = m.board_local(fwd["point"])
        layer = "F.Cu" if fwd["normal"][2] > 0 else "B.Cu"
        mains = m.board.mains_layer(layer).distance(Point(lp[0], lp[1])) < 1e-6
    if mains:
        return True, {"from": [round(x, 2) for x in point], "hits": fwd["solid"], "at": [round(x, 2) for x in fwd["point"]]}
    return True, None


def check_c15(m: case.Model, form: str = "single") -> List[Dict[str, Any]]:
    P = m.P
    out = []
    sc = scene(m, form)
    mains_bodies = {n for n, b in m.bodies.items() if b["mains"]}
    tip, cyl, cone_len = P("finger.tip_dia_mm"), P("finger.probe_dia_mm"), P("finger.cone_length_mm")
    cone_deg = P("installed.drip_cone_deg")
    cone = cone_directions(case.gravity(m), cone_deg)
    cone_rows: List[Dict[str, Any]] = []
    admits = P("finger.admits_nothing_below_mm")
    zt = P("case.z_lid_top_mm")
    finger_rows = []
    drip_rows = []
    finger_ok = True
    drip_ok = True
    arrays = mains_arrays(m)
    fitted_open = {which: fitted_free_opening(m, which) for which in ("typical", "largest_common")}
    for op in m.openings:
        # finger
        row = {"opening": op["id"], "kind": op["kind"], "smaller_dimension_mm": op["min_dim"], "larger_dimension_mm": op["max_dim"]}
        pts = [(u, v, z, 0.0) for (u, v, z) in op["points"]]
        near = copper_distance(m, pts)
        nearest = min(near.values(), key=lambda x: x[0])
        if op["min_dim"] < admits:
            row.update({"admits": "nothing", "depth_mm": 0.0, "remaining_to_mains_copper_mm": nearest[0], "nearest": nearest[1],
                        "path": "a %.1f mm tip cannot enter a %.2f mm opening" % (tip, op["min_dim"])})
            finger_ok &= nearest[0] > 0
        elif op["kind"] == "blade aperture":
            # all three receptacles fitted: the bay is left as the opening round the boots; the typical envelope is the pass rule, the largest common one is reported alongside
            bay = sh_box(op["u"] - op["du"] / 2, op["v"] - op["dv"] / 2, op["u"] + op["du"] / 2, op["v"] + op["dv"] / 2)
            uc, vc = blade_centre(m, op["id"].split()[-1])
            blade_rect = sh_box(uc - P("blade.thickness_mm") / 2, vc - P("blade.width_mm") / 2, uc + P("blade.thickness_mm") / 2, vc + P("blade.width_mm") / 2)
            per_env = {}
            for which, free in fitted_open.items():
                pieces = [g for g in (free.geoms if hasattr(free, "geoms") else [free]) if g.intersects(bay) and not g.is_empty]
                here = unary_union(pieces) if pieces else ShPolygon()
                per_env[which] = {"widest_disc_mm": widest_disc(here), "to_blade_mm": float(here.distance(blade_rect)) if not here.is_empty else float("inf")}
                per_env[which]["admits_nothing"] = per_env[which]["widest_disc_mm"] < admits
            typical = per_env["typical"]
            row.update({"admits": "nothing", "depth_mm": 0.0, "remaining_to_mains_copper_mm": nearest[0], "nearest": nearest[1],
                        "remaining_to_blade_mm": typical["to_blade_mm"], "receptacles_fitted": list(BLADE_REFS), "free_opening_round_the_boots": per_env,
                        "path": f"all three receptacles fitted (typical envelope): the opening left round the boot is at most {typical['widest_disc_mm']:.2f} mm wide, under the {tip:.1f} mm tip; "
                                f"largest common envelope {per_env['largest_common']['widest_disc_mm']:.2f} mm wide, reported alongside"})
            finger_ok &= typical["admits_nothing"] and typical["to_blade_mm"] > 0 and nearest[0] > 0
        else:
            row.update({"admits": "unexamined", "depth_mm": 0.0})
            finger_ok = False
        finger_rows.append(row)
        # drip: the pass rule is the cone about installed vertical, falling onto the tray's outer top face; the six axis directions follow as information
        pts_cone = op["points"][:: max(1, len(op["points"]) // 30)]
        reach_count, hit_rows = 0, []
        for p in pts_cone:
            for d in cone:
                reachable_p, hit = ray_to_mains(m, sc, mains_bodies, p, d)
                reach_count += int(reachable_p)
                if hit:
                    hit_rows.append(hit)
        cone_rows.append({"opening": op["id"], "kind": op["kind"], "points_cast": len(pts_cone) * len(cone), "reachable_from_outside": reach_count,
                          "reaches_mains_copper": len(hit_rows) > 0, "example": hit_rows[0] if hit_rows else None})
        if hit_rows:
            drip_ok = False
        residual = op["kind"] in ("blade aperture", "cable notch")
        for dname, d in DIRECTIONS.items():
            hits = []
            reachable = False
            for p in op["points"]:
                reachable_p, hit = ray_to_mains(m, sc, mains_bodies, p, d)
                reachable |= reachable_p
                if hit:
                    hits.append(hit)
            drip_rows.append({"opening": op["id"], "down": dname, "reachable_from_outside": bool(reachable), "reaches_mains_copper": len(hits) > 0,
                              "example": hits[0] if hits else None, "residual": residual, "information_only": True})
    # residual gaps for blade bays and the cable notch
    boot = case.boot_box(m, "typical")
    gap = P("boots.clearance_mm")
    residuals = {"blade bays": f"with the receptacle boot (typical {boot['across_width']:.1f} x {boot['across_thickness']:.1f}) fitted, an annular gap of {gap:.1f} mm remains round it; a line along z passes it and reaches the board below the blade. This is what the openings leave of the enclosure",
                 "cable notch": "with the three-wire cable fitted the notch (%.1f wide x %.1f high) leaves the gaps round the wires; the notch is %.1f mm above the housing and no copper lies beneath it within the finger's reach" % (
                     P("lid.cable_notch_v_mm")[1] - P("lid.cable_notch_v_mm")[0], P("lid.cable_notch_height_mm"), P("case.z_wall_top_mm") - P("lid.cable_notch_height_mm") - P("parts.header_housing_top_z_mm"))}
    lines = []
    for r in finger_rows:
        lines.append(f"finger {r['opening']:24s} {r['kind']:15s} {r['smaller_dimension_mm']:5.2f} mm: {r['admits']}; remaining to Mains copper {r.get('remaining_to_mains_copper_mm', float('nan')):.2f} mm")
    out.append(result("c15.finger", "C15", finger_ok,
                      f"the stand-in finger enters no opening to a Mains-family conductor, with all three receptacles fitted: {sum(1 for r in finger_rows if r['admits'] == 'nothing')} of {len(finger_rows)} openings admit nothing, the {sum(1 for r in finger_rows if r['kind'] == 'blade aperture')} blade bays included (the opening round a typical boot is at most {max((r['free_opening_round_the_boots']['typical']['widest_disc_mm'] for r in finger_rows if r['kind'] == 'blade aperture'), default=0):.2f} mm, the largest common one {max((r['free_opening_round_the_boots']['largest_common']['widest_disc_mm'] for r in finger_rows if r['kind'] == 'blade aperture'), default=0):.2f} mm, against the {admits:.1f} mm tip)",
                      {"stand_in": f"rigid {cyl:.0f} mm cylinder, {tip:.0f} mm hemispherical tip, {cone_len:.0f} mm cone; more penetrating than the IEC 61032 probe B tip",
                       "probe_B_source": "Lisun data sheet, secondary source; tip radii not obtainable from a free source",
                       "openings": finger_rows, "residuals": residuals}, lines))
    lines = []
    for r in cone_rows:
        lines.append(f"drip {r['opening']:24s} {r['kind']:13s}: {r['reachable_from_outside']:4d} of {r['points_cast']:4d} cone lines open to the outside, reaches Mains copper {'YES' if r['reaches_mains_copper'] else 'no'}")
    info_open = sorted({f"{r['opening']} down {r['down']}" for r in drip_rows if r["reachable_from_outside"] and r["reaches_mains_copper"]})
    out.append(result("c15.drip", "C15", drip_ok,
                      f"installed (plate vertical, component side down), no straight line within {cone_deg:.0f} degrees of vertical, falling onto the tray's outer top face, reaches Mains copper on either layer through any of the {len(cone_rows)} openings; the other five axis directions are information only ({len(info_open)} opening-direction pairs would reach copper if that axis were down)",
                      {"rule": f"pass: no straight line within {cone_deg:.0f} degrees of installed vertical reaches Mains copper (either layer, or a Mains body) through any opening or seam",
                       "installed_vertical": case.gravity(m).tolist(), "cone_half_angle_deg": cone_deg, "cone_lines_per_point": len(cone),
                       "per_opening": cone_rows, "directions": list(DIRECTIONS), "rows": drip_rows, "residuals": residuals,
                       "information_only_pairs_reaching_copper": info_open,
                       "method": "from sample points inside each opening, a line against the direction must leave the case to be a drip path; the line along it is followed to its first solid"}, lines))
    vent_faults = {v.label: m.core.vent_problems(v) for v in m.info["vents"] if m.core.vent_problems(v)}
    web = m.core.web_faults(m.info["vents"])
    if web:
        vent_faults["web"] = [f"{a} and {b} leave {d:.2f} mm of lid" for a, b, d in web]
    outlet_faults = {f"{s.side} slit at v {s.v:.1f}": m.core.outlet_problems(s) for s in m.info["outlets"] if m.core.outlet_problems(s)}
    owebs = m.core.outlet_web_faults(m.info["outlets"])
    if owebs:
        outlet_faults["web"] = [f"slits {a + 1} and {b + 1} leave {d:.2f} mm" for a, b, d in owebs]
    gill = m.core.gill()
    areas = vent_areas(m)
    kinds = {o["kind"] for o in m.openings}
    enumerated = (kinds >= {"louvre", "blade aperture", "cable notch", "seam", "finger slit", "outlet slit"}
                  and sum(1 for o in m.openings if o["kind"] == "louvre") == len(m.info["vents"]) and len(m.info["vents"]) > 0
                  and sum(1 for o in m.openings if o["kind"] == "outlet slit") == len(m.info["outlets"]) > 0)
    out.append(result("c15.openings_enumerated", "C15", enumerated and not vent_faults and not outlet_faults,
                      f"{len(m.openings)} openings are enumerated: " + ", ".join(sorted(kinds)) + f"; every vent stands in the lid's thickened field, clear of the bays and the lid screw, {m.P('envelope.vent_web_mm'):.1f} mm or more of lid between neighbours, with an opening {gill['opening']:.2f} mm wide; {len(m.info['outlets'])} outlet slits stand in the core's zone of the long walls, none wider than {m.core.outlet_max_width():.1f} mm; lid inlet free area {areas['lid_inlet_free_area_mm2']:.0f} mm2, side outlet free area {areas['side_outlet_free_area_mm2']:.0f} mm2; driver access: none with the lid on",
                      {"vent_rule_faults": vent_faults, "outlet_rule_faults": outlet_faults, "gill": gill, "open_areas": areas,
                       "openings": [{"id": o["id"], "kind": o["kind"], "smaller_dimension_mm": o["min_dim"], "larger_dimension_mm": o["max_dim"], "sample_points": len(o["points"])} for o in m.openings],
                       "driver_access_with_lid_on": "none"}))
    return out


def vent_areas(m: case.Model) -> Dict[str, Any]:
    """The open area of the lid's inlets and of the side outlets. The free area of a slot is its length times its width across the flow; for a gill that is the width perpendicular to the slot plane, for an outlet its width times its height."""
    g = m.core.gill()
    inlet_len = sum(v.length() for v in m.info["vents"])
    free = inlet_len * g["width"]
    face = inlet_len * g["opening"]
    outlet = sum(s.width * s.height for s in m.info["outlets"])
    per_side = {side: sum(s.width * s.height for s in m.info["outlets"] if s.side == side) for side in ("left", "right")}
    bays = sum(a["du"] * a["dv"] for a in case.aperture_boxes(m))
    return {"lid_inlet_free_area_mm2": float(free), "lid_inlet_face_opening_area_mm2": float(face), "lid_inlet_slot_count": len(m.info["vents"]),
            "lid_inlet_total_slot_length_mm": float(inlet_len), "side_outlet_free_area_mm2": float(outlet), "side_outlet_area_by_wall_mm2": per_side,
            "side_outlet_slit_count": len(m.info["outlets"]), "blade_bays_open_area_mm2": float(bays),
            "outlet_to_inlet_ratio": float(outlet / free) if free else float("nan")}


# ---------------------------------------------------------------------------------------------------------------------
# The logo and colour-swap geometry, and the seating range
# ---------------------------------------------------------------------------------------------------------------------

def top_height(sc: "Scene", u: float, v: float) -> Optional[float]:
    hit = sc.first_hit((u, v, 40.0), (0, 0, -1))
    return None if hit is None else 40.0 - hit["distance"]


def check_c13(m: case.Model) -> List[Dict[str, Any]]:
    P = m.P
    zt = P("case.z_lid_top_mm")
    zb = m.z_floor_bottom
    depth = P("logo.groove_depth_mm")
    out: List[Dict[str, Any]] = []
    # the two forms share every dimension: one lid geometry, and the two-colour form adds only the colour of the groove floors
    a, b = m.mesh("lid_single"), m.mesh("lid_two")
    same = a.vertices.shape == b.vertices.shape and bool(np.allclose(a.vertices, b.vertices)) and abs(float(a.volume) - float(b.volume)) < 1e-6
    swap_names = ("lid_swap", "tray_swap")
    bands = case.swap_bands(m)
    swap_ok = all(n in m.parts for n in swap_names) and not {"groove_floor", "tray_groove_floor", "inlay"} & set(m.parts)
    inside = {}
    for part, whole, swap in (("lid", "lid_two", "lid_swap"), ("tray", "tray", "tray_swap")):
        if swap not in m.parts:
            continue
        sm, wm = m.mesh(swap), m.mesh(whole)
        z0, z1 = bands[part]
        stuck = m.parts[swap] - m.parts[whole]
        outside = float(stuck.volume) if stuck is not None and hasattr(stuck, "volume") else 0.0
        inside[part] = {"band_z_mm": [float(z0), float(z1)], "swap_bounds_z_mm": [float(sm.bounds[0][2]), float(sm.bounds[1][2])],
                        "swap_volume_mm3": float(sm.volume), "swap_outside_its_part_mm3": outside, "part_volume_mm3": float(wm.volume)}
        swap_ok &= sm.bounds[0][2] >= z0 - 1e-6 and sm.bounds[1][2] <= z1 + 1e-6 and outside < 1e-6 and sm.volume > 1.0
    out.append(result("c13.forms_share_dimensions", "C13", same and swap_ok,
                      "the two lids are one geometry: the two-colour form differs only in which layers of each part print in the second colour, so no inlay part exists and the lid and the tray are one geometry in both forms; the swap layers are the parts lid_swap and tray_swap, each its part cut to its band",
                      {"lid_volume_mm3": float(a.volume), "geometry_identical": bool(same), "swap_parts": inside, "inlay_part_present": "inlay" in m.parts,
                       "shared": ["tray", "plate", "lid outline, lip, toes, vents, bays and screw seat"]}))
    # the logo on the lid
    poly_sh = m.info["mark_geometry"]
    area = m.info.get("mark_area_uv")
    gw = P("logo.groove_width_mm")
    area_sh = ShPolygon(area) if area else m.info["logo_outline"].buffer(gw / 2)
    groove_sh = [(g.polygon(), g.depth) for g in m.info["grooves"]]
    clear = m.core.mark_clearances(area_sh, m.info["lid_flat"], m.info["vents"])
    need = P("envelope.vent_clear_mm")
    bb = area_sh.buffer(0.5).bounds
    sc = Scene(m, ["lid_single"])
    mism = 0
    total = 0
    for u in np.arange(bb[0] + 0.15, bb[2], 0.5):
        for v in np.arange(bb[1] + 0.15, bb[3], 0.5):
            tp = top_height(sc, float(u), float(v))
            q = Point(u, v)
            if poly_sh.boundary.distance(q) < 0.12 or not area_sh.contains(q) or not m.info["lid_flat"].contains(q):
                continue            # a sample on the edge of a groove is not told from the tessellation
            want = zt - depth if poly_sh.contains(q) else zt
            for gp, gd in groove_sh:
                if want == zt and gp.contains(q) and gp.boundary.distance(q) >= 0.12:
                    want = zt - gd
            total += 1
            if tp is None or abs(tp - want) > 0.02:
                mism += 1
    placed = (clear["inside_flat_top"] and clear["edge_of_flat_top_mm"] >= 0.5 and clear["lid_screw_head_mm"] > 2.0 and clear["aperture_mm"] >= need
              and clear["vent_mm"] >= need)
    ext = poly_sh.bounds
    out.append(result("c13.mark_on_lid", "C13", mism == 0 and placed,
                      f"the logo's {total} sample points on the lid top agree with the engraving (grooves {depth:.1f} mm deep, flush outside{'' if not groove_sh else ', the relief grooves %.1f mm deep' % groove_sh[0][1]}); it lies at u {ext[0]:.1f} to {ext[2]:.1f}, v {ext[1]:.1f} to {ext[3]:.1f}, {clear['lid_screw_head_mm']:.1f} mm clear of the lid screw head, {clear['aperture_mm']:.1f} mm of the bays, {min(clear['vent_mm'], 999.0):.1f} mm of the vents",
                      {"mismatched_samples": mism, "samples": total, "extent_uv_mm": list(ext), "clear_of_screw_head_mm": clear["lid_screw_head_mm"],
                       "clearances": clear, "required_clearance_mm": need}))
    # the logo is engraved on both faces in both forms
    import logo as logo_module
    lid_o = m.info["logo_outline"]
    tray_info = m.info["tray_logo"]
    tray_o = tray_info["outline"]
    lid_h = lid_o.bounds[3] - lid_o.bounds[1]
    tray_h = tray_o.bounds[3] - tray_o.bounds[1]
    face = tray_info["face"]
    fb = ShPolygon(face).bounds
    short = min(fb[2] - fb[0], fb[3] - fb[1])
    want_h = P("logo.tray_height_mm")
    faces = {}
    ok_faces = True
    for face_name, geom in (("lid", m.info["mark_geometry"]), ("tray", tray_info["geometry"])):
        core_lines = geom.buffer(-0.12)
        samples = []
        if not core_lines.is_empty:
            minx, miny, maxx, maxy = core_lines.bounds
            for u in np.arange(minx, maxx, 0.3):
                for v in np.arange(miny, maxy, 0.3):
                    if core_lines.contains(Point(u, v)):
                        samples.append((float(u), float(v)))
        faces[face_name] = samples
    bad: Dict[str, int] = {}
    floor_under = []
    lid_scene, tray_scene = Scene(m, ["lid_two"]), Scene(m, ["tray"])
    for u, v in faces["lid"]:
        hit = lid_scene.first_hit((u, v, 40.0), (0, 0, -1))
        if hit is None or abs(40.0 - hit["distance"] - (zt - depth)) > 0.02:
            bad["lid"] = bad.get("lid", 0) + 1
    for u, v in faces["tray"]:
        hit = tray_scene.first_hit((u, v, zb - 20.0), (0, 0, 1))
        if hit is None or abs(zb - 20.0 + hit["distance"] - (zb + depth)) > 0.02:
            bad["tray"] = bad.get("tray", 0) + 1
    tray_solid = m.parts["tray"]
    floor_top = tray_info["floor_under_grooves_mm"] + zb + depth          # the thickened floor's upper face
    classifier = BRepClass3d_SolidClassifier(tray_solid.wrapped)
    for u, v in faces["tray"][::7]:
        # classify the solid itself: no material just below the groove floor, material just above it and material right up to the thickened floor's upper face (a pillar may carry on above)
        inside = [point_in_solid(classifier, u, v, z) for z in (zb + depth - 0.05, zb + depth + 0.05, floor_top - 0.05)]
        floor_under.append(floor_top - (zb + depth) if inside == [False, True, True] else 0.0)
    least_floor = min(floor_under) if floor_under else float("nan")
    e22 = logo_module.engrave(P, P("logo.lid_min_height_mm"))
    pockets = [float(shapely.maximum_inscribed_circle(g, 0.01).length * 2) for g in (e22.geometry.geoms if hasattr(e22.geometry, "geoms") else [e22.geometry])]
    traced = {}
    for name, geom, outline in (("lid", m.info["mark_geometry"], lid_o), ("tray", tray_info["geometry"], tray_o)):
        ring = outline.exterior
        traced[name] = float(ring.intersection(geom.buffer(0.1)).length / ring.length)
    tray_face = ShPolygon(face)
    tray_edge_clear = float(tray_face.exterior.distance(tray_o.buffer(P("logo.groove_width_mm") / 2)))
    tray_off_centre = float(math.hypot((tray_o.bounds[0] + tray_o.bounds[2]) / 2 - tray_face.centroid.x, (tray_o.bounds[1] + tray_o.bounds[3]) / 2 - tray_face.centroid.y))
    sizes_ok = (lid_h >= P("logo.lid_min_height_mm") - 0.05 and abs(tray_h - want_h) <= 0.3 and tray_face.contains(tray_o)
                and tray_edge_clear >= P("logo.tray_edge_clear_mm") - 0.05)
    ok = (len(faces["lid"]) >= 100 and len(faces["tray"]) >= 100 and not bad and min(traced.values()) >= 0.95 and sizes_ok
          and least_floor >= P("envelope.min_wall_mm") - 0.02)
    out.append(result("c13.logo_present_in_each_form", "C13", ok,
                      f"the Staircase logo is engraved {depth:.1f} mm deep on the lid face ({lid_h:.1f} mm tall, at least {P('logo.lid_min_height_mm'):.0f}) and on the tray's outer top face ({tray_h:.1f} mm tall against {want_h:.1f}, centred on that face or kept {P('logo.tray_edge_clear_mm'):.0f} mm from its chamfer), in both colour forms; {len(faces['lid'])} and {len(faces['tray'])} samples along its grooves agree; the floor under the tray's grooves is {least_floor:.2f} mm (the core's minimum wall {P('envelope.min_wall_mm'):.1f})",
                      {"lid_height_mm": lid_h, "tray_height_mm": tray_h, "tray_logo_clear_of_chamfer_mm": tray_edge_clear, "tray_logo_off_face_centre_mm": tray_off_centre, "tray_face_shorter_dimension_mm": short, "tray_expected_height_mm": want_h,
                       "samples": {k: len(v) for k, v in faces.items()}, "wrong_samples": bad, "outline_drawn_fraction": traced,
                       "lid_extent_mm": [lid_o.bounds[2] - lid_o.bounds[0], lid_h], "tray_extent_mm": [tray_o.bounds[2] - tray_o.bounds[0], tray_h],
                       "groove_width_mm": gw, "groove_depth_mm": depth, "widest_pocket_at_a_junction_mm": max(pockets),
                       "floor_under_tray_grooves_mm": least_floor, "tray_floor_pad_mm": tray_info["floor_under_grooves_mm"] - (P("case.floor_mm") - depth),
                       "forms": ["single", "two"], "source": "staircase-logo.svg, silhouette, light, dark (hatch) and sheets groups"}))
    out.append(swap_layers_result(m, faces))
    return out


def swap_layers_result(m: case.Model, faces: Dict[str, Any]) -> Dict[str, Any]:
    """The two-colour form's swap layers stated and proved: where each part's band stands, that every relief floor lies in it with the layers over it
    the colour needs, that a ray down each kind of groove lands on a face in the band, that the band is a pinstripe on each part's chamfer, and what it crosses."""
    P = m.P
    zt, zb = P("case.z_lid_top_mm"), m.z_floor_bottom
    layer = P("printer.layer_mm")
    start = P("forms.two.swap_start_mm")
    thick = P("forms.two.swap_layers") * P("printer.layer_mm")
    top = start + thick
    whole = lambda x: abs(x / layer - round(x / layer)) < 1e-6          # noqa: E731
    bands = case.swap_bands(m)
    logo_depth = P("logo.groove_depth_mm")
    grooves = m.info["grooves"]
    round_g = [g for g in grooves if not g.square]
    bars = [g for g in grooves if g.square]
    depths = {"lid logo": (logo_depth, 2), "streamline grooves": (sorted({g.depth for g in round_g}), 2), "far-end block bars": (sorted({g.depth for g in bars}), 2),
              "tray logo": (logo_depth, 3)}
    rows: Dict[str, Any] = {}
    depth_ok = whole(start) and whole(thick)
    for name, (val, want_layers) in depths.items():
        for d in (val if isinstance(val, list) else [val]):
            layers_over = (top - d) / layer
            good = whole(d) and d >= start - 1e-9 and layers_over >= want_layers - 1e-6
            depth_ok &= good
            rows[name] = {"depth_mm": float(d), "whole_layers": bool(whole(d)), "at_least_swap_start": bool(d >= start - 1e-9), "swap_layers_over_the_floor": float(layers_over),
                          "needs_at_least": want_layers, "ok": bool(good)}
        if isinstance(val, list) and not val:
            depth_ok &= name != "streamline grooves"
    # a ray from outside down each kind of groove lands on its floor, a face in the band
    lid_scene, tray_scene = Scene(m, ["lid_two"]), Scene(m, ["tray"])
    lz0, lz1 = bands["lid"]
    tz0, tz1 = bands["tray"]
    vent_lines = [LineString(v.points) for v in m.info["vents"]]
    through = unary_union(vent_lines).buffer(P.S("lines.groove_width_mm")) if vent_lines else None
    rays: Dict[str, Dict[str, int]] = {}

    def tally(kind: str, ok: bool) -> None:
        r = rays.setdefault(kind, {"samples": 0, "in_band": 0})
        r["samples"] += 1
        r["in_band"] += int(ok)

    def lid_ray(kind: str, u: float, v: float, d: float) -> None:
        hit = lid_scene.first_hit((u, v, 40.0), (0, 0, -1))
        z = None if hit is None else 40.0 - hit["distance"]
        tally(kind, z is not None and abs(z - (zt - d)) <= 0.02 and lz0 - 1e-6 <= z <= lz1 + 1e-6)

    for u, v in faces["lid"]:
        lid_ray("lid logo", u, v, logo_depth)
    for u, v in faces["tray"]:
        hit = tray_scene.first_hit((u, v, zb - 20.0), (0, 0, 1))
        z = None if hit is None else zb - 20.0 + hit["distance"]
        tally("tray logo", z is not None and abs(z - (zb + logo_depth)) <= 0.02 and tz0 - 1e-6 <= z <= tz1 + 1e-6)
    for kind, group in (("streamline grooves", round_g), ("far-end block bars", bars)):
        for g in group:
            line = LineString(g.points)
            for t in np.arange(0.5, line.length - 0.5, 2.0):
                q = line.interpolate(float(t))
                if through is not None and through.contains(q):
                    continue                    # a vent runs here: the groove is cut through, not blind
                lid_ray(kind, float(q.x), float(q.y), g.depth)
    rays_ok = all(r["samples"] >= 20 and r["in_band"] == r["samples"] for r in rays.values()) and set(rays) == {"lid logo", "tray logo", "streamline grooves"} | ({"far-end block bars"} if bars else set())
    # the band stands inside each part's 45 degree chamfer, so the stripe is on the chamfer
    ch_lid, ch_tray = float(m.skin.lid_chamfer), float(P.S("bottom_chamfer_mm"))
    chamfer_ok = top <= ch_lid + 1e-9 and top <= ch_tray + 1e-9
    # what the band crosses
    crosses = lambda bb, z0, z1: bb.min.Z < z1 and bb.max.Z > z0          # noqa: E731
    vent_cross = sum(1 for v in m.info["vents"] if crosses(m.core.gill_cutter(v).bounding_box(), lz0, lz1))
    bay_cross = [a["ref"] for a in case.aperture_boxes(m) if crosses(box_bb(m, a), lz0, lz1)]
    head_r, hole_r = P("screws.lid_head_dia_mm") / 2, P("screws.lid_dia_mm") / 2 + 0.2
    sink_depth = head_r + 0.01 - hole_r
    sink_cross = (zt - sink_depth) < lz1
    slit_cross = [f"{s.side} slit at v {s.v:.1f}" for s in m.info["outlets"] if crosses(m.core.outlet_cutter(s).bounding_box(), tz0, tz1)]
    ok = depth_ok and rays_ok and chamfer_ok and not slit_cross
    block_note = f"the far-end block draws {len(bars)} bars" if bars else f"no block: {m.info.get('far_end_block')}"
    return result("c13.swap_layers_stated_and_proved", "C13", ok,
                  f"the swap band is {start:.1f} to {top:.1f} mm above the bed on each part, {thick / layer:.0f} layers of {layer:.1f} mm, a whole number of layers from the bed; every relief floor lies in it with the swap layers over it that the colour needs (two on the lid, three on the tray); a ray down each kind of groove lands on a face in the band; the band lies inside the {ch_lid:.1f} mm chamfer of each part, so it shows as a stripe on the chamfer; the tray's band crosses {len(slit_cross)} outlet slits; {block_note}; on the lid the band crosses {vent_cross} of {len(m.info['vents'])} vents, {len(bay_cross)} bays and {'the lid screw countersink' if sink_cross else 'not the countersink'}",
                  {"swap_start_mm": start, "swap_thickness_mm": thick, "layer_mm": layer, "start_whole_layers": bool(whole(start)), "thickness_whole_layers": bool(whole(thick)),
                   "reliefs": rows, "rays": rays, "chamfer_height_mm": {"lid": ch_lid, "tray": ch_tray}, "band_top_mm": top,
                   "lid_band_z_mm": [float(lz0), float(lz1)], "tray_band_z_mm": [float(tz0), float(tz1)],
                   "lid_openings_crossed": {"vents": vent_cross, "vents_total": len(m.info["vents"]), "bays": bay_cross, "countersink": bool(sink_cross)},
                   "tray_outlet_slits_crossed": slit_cross, "far_end_block": {"bars": len(bars), "omitted_because": m.info.get("far_end_block")}})


def box_bb(m: case.Model, a: Dict[str, Any]) -> Any:
    """The bounding box of a blade bay's cut through the lid."""
    za, zt = m.P("case.z_lid_under_mm"), m.P("case.z_lid_top_mm")
    return case.box(a["u"] - a["du"] / 2, a["u"] + a["du"] / 2, a["v"] - a["dv"] / 2, a["v"] + a["dv"] / 2, za - m.P("lid.collar_below_mm") - 1, zt + 1).bounding_box()


# ---------------------------------------------------------------------------------------------------------------------
# Receptacle boots on the blades
# ---------------------------------------------------------------------------------------------------------------------

def box_surface_points(u0: float, u1: float, v0: float, v1: float, z0: float, z1: float, step: float = 0.4) -> np.ndarray:
    """Points on the six faces of a box, edges and corners included."""
    def axis(a: float, b: float) -> np.ndarray:
        return np.linspace(a, b, max(int(math.ceil((b - a) / step)), 1) + 1)
    us, vs, zs = axis(u0, u1), axis(v0, v1), axis(z0, z1)
    pts = []
    for u in (u0, u1):
        pts += [(u, v, z) for v in vs for z in zs]
    for v in (v0, v1):
        pts += [(u, v, z) for u in us for z in zs]
    for z in (z0, z1):
        pts += [(u, v, z) for u in us for v in vs]
    return np.array(pts)


def blade_centre(m: case.Model, ref: str) -> Tuple[float, float]:
    pads = m.board.refs[ref]["pads"]
    return pads[0]["hole_u"], sum(p["hole_v"] for p in pads) / len(pads)


def boot_removal_with_lid(m: case.Model, pivot: Tuple[float, float], slide_free: float, which: str, wire: bool) -> Dict[str, Any]:
    """Whether the lid can be tilted and drawn out with receptacles fitted: the lid's bay walls, carried through the sweep in the (v, z) plane, against each boot (and its wire)."""
    from shapely.geometry import LineString as Line
    P = m.P
    env = case.boot_box(m, which)
    za, zt = P("case.z_lid_under_mm"), P("case.z_lid_top_mm")
    z_low = za - P("lid.collar_below_mm")
    bend = P("boots.bend_od_multiple") * P("boots.wire_od_mm")
    od = P("boots.wire_od_mm")
    rects = []
    for ap in case.aperture_boxes(m):
        _, vc = blade_centre(m, ap["ref"])
        corners = [(vc - env["across_width"] / 2, 0.0), (vc + env["across_width"] / 2, 0.0), (vc + env["across_width"] / 2, env["length"]), (vc - env["across_width"] / 2, env["length"])]
        rects.append(ShPolygon([m.board_global((0.0, v, z))[1:] for v, z in corners]))
        if wire:
            wc = [(vc - od / 2, env["length"]), (vc + od / 2, env["length"]), (vc + od / 2, env["length"] + bend), (vc - od / 2, env["length"] + bend)]
            rects.append(ShPolygon([m.board_global((0.0, v, z))[1:] for v, z in wc]))
    walls = []
    for ap in case.aperture_boxes(m):
        for v in (ap["v"] - ap["dv"] / 2, ap["v"] + ap["dv"] / 2):
            walls.append(np.array([[v, z_low], [v, zt]]))
    poses, _ = sweep_poses(m, slide_to=max(slide_free, 0.0) + 3.0, slide_step=0.25)
    first = None
    for kind, angle, slide in poses:
        for w in walls:
            moved = lid_poses_xy(w, (kind, angle, slide), pivot)
            line = Line(moved)
            if any(line.distance(r) <= 1e-9 for r in rects):
                first = {"pose": kind, "tilt_deg": angle, "slide_mm": slide}
                break
        if first:
            break
    return {"removable": first is None, "first_contact": first}


def fitted_free_opening(m: case.Model, which: str, fitted: Optional[Sequence[str]] = None) -> Any:
    """The blade bays of the lid with a receptacle boot of the named envelope fitted on each blade of `fitted` (all three when None): the bays' union less the boots' footprints."""
    env = case.boot_box(m, which)
    opening = unary_union([sh_box(a["u"] - a["du"] / 2, a["v"] - a["dv"] / 2, a["u"] + a["du"] / 2, a["v"] + a["dv"] / 2) for a in case.aperture_boxes(m)])
    for ref in (BLADE_REFS if fitted is None else fitted):
        uc, vc = blade_centre(m, ref)
        opening = opening.difference(sh_box(uc - env["across_thickness"] / 2, vc - env["across_width"] / 2, uc + env["across_thickness"] / 2, vc + env["across_width"] / 2))
    return opening


def widest_disc(geom: Any) -> float:
    """The diameter of the largest circle that fits in a (multi)polygon."""
    pieces = list(geom.geoms) if hasattr(geom, "geoms") else [geom]
    return max((float(shapely.maximum_inscribed_circle(g, 0.01).length * 2) for g in pieces if not g.is_empty), default=0.0)


BLADE_REFS = ("J941", "J921", "J911")


def bare_blade_reach(m: case.Model, fitted: Optional[Dict[str, str]] = None) -> Dict[str, Dict[str, float]]:
    """The stand-in finger's tip, placed anywhere in the bays, against each bare blade, with the figures that make the reach.

    Per blade: `gap` the least distance from the tip to the blade (negative when it touches), `width` the opening's width at the
    tip's best place (the largest circle about that point that fits the opening, at most the probe's), and `u`, `v` that place.
    `fitted` names the blades that carry a receptacle boot (blade -> envelope); a fitted boot fills its box, so it takes that
    area from the opening and the blade under it is not bare. The finger is a disc of the probe's cross-section: at a point in
    the opening it goes as deep as the largest disc about that point that fits the opening (its width the opening's smaller
    dimension there), by the stand-in's tip and cone, its tip centre at that depth below the lid face (the standing finger
    check's own convention). Probe: IEC 61032 probe B stand-in of params.yaml `finger` (Lisun data sheet, secondary source).
    """
    P = m.P
    tip, cyl, cone_len = P("finger.tip_dia_mm"), P("finger.probe_dia_mm"), P("finger.cone_length_mm")
    zt = P("case.z_lid_top_mm")
    bays = case.aperture_boxes(m)
    opening = unary_union([sh_box(a["u"] - a["du"] / 2, a["v"] - a["dv"] / 2, a["u"] + a["du"] / 2, a["v"] + a["dv"] / 2) for a in bays])
    for ref, which in (fitted or {}).items():
        env = case.boot_box(m, which)
        uc, vc = blade_centre(m, ref)
        opening = opening.difference(sh_box(uc - env["across_thickness"] / 2, vc - env["across_width"] / 2, uc + env["across_thickness"] / 2, vc + env["across_width"] / 2))
    boundary = opening.boundary
    bw, bt = P("blade.width_mm"), P("blade.thickness_mm")
    rows: Dict[str, Dict[str, float]] = {}
    b = opening.bounds
    for ap in bays:
        if ap["ref"] in (fitted or {}):
            continue
        uc, vc = blade_centre(m, ap["ref"])
        top = m.board_global((0.0, vc, P("blade.standoff_mm") + P("blade.above_shoulder_mm")))[2]        # the blade's tip, carried by the lean
        best = {"gap": float("inf"), "width": 0.0, "u": float("nan"), "v": float("nan")}
        for u in np.arange(b[0] + 0.25, b[2], 0.5):
            for v in np.arange(b[1] + 0.25, b[3], 0.5):
                q = Point(u, v)
                if not opening.contains(q):
                    continue
                width = min(2 * float(boundary.distance(q)), cyl)
                if width < tip:
                    continue
                depth, _ = probe_penetration(width, tip, cyl, cone_len)
                zc = zt - min(depth, 1e3)
                du = max(abs(u - uc) - bt / 2, 0.0)
                dv = max(abs(v - vc) - bw / 2, 0.0)
                dz = max(zc - top, 0.0) if zc > 0 else 0.0
                gap = math.sqrt(du ** 2 + dv ** 2 + dz ** 2) - tip / 2
                if gap < best["gap"]:
                    best = {"gap": gap, "width": width, "u": float(u), "v": float(v)}
        rows[ap["ref"]] = best
    return rows


def finger_reach_to_bare_blades(m: case.Model, fitted: Optional[Dict[str, str]] = None) -> Dict[str, float]:
    """The least gap from the stand-in finger's tip to each bare blade, see bare_blade_reach; negative when it touches."""
    return {ref: row["gap"] for ref, row in bare_blade_reach(m, fitted).items()}


def standing_gap_to_bare_blade(m: case.Model, ref: str, lean_deg: float) -> float:
    """The standing finger check's own gap to one bare blade at a given lean: the tip centred in that blade's bay at the depth the bay's smaller dimension allows."""
    import copy
    P = m.P
    tip, cyl, cone_len = P("finger.tip_dia_mm"), P("finger.probe_dia_mm"), P("finger.cone_length_mm")
    leaned = copy.copy(m)
    leaned.phi = math.radians(lean_deg)
    ap = next(a for a in case.aperture_boxes(m) if a["ref"] == ref)
    uc, vc = blade_centre(m, ref)
    depth, _ = probe_penetration(ap["du"], tip, cyl, cone_len)
    zc = P("case.z_lid_top_mm") - min(depth, 1e3)
    top = leaned.board_global((0.0, vc, P("blade.standoff_mm") + P("blade.above_shoulder_mm")))[2]
    du = max(abs(ap["u"] - uc) - P("blade.thickness_mm") / 2, 0.0)
    dv = max(abs(ap["v"] - vc) - P("blade.width_mm") / 2, 0.0)
    dz = max(zc - top, 0.0) if zc > 0 else 0.0
    return math.sqrt(du ** 2 + dv ** 2 + dz ** 2) - tip / 2


def lean_that_fails_standing_check(m: case.Model, ref: str, limit_deg: float = 5.0) -> Dict[str, Optional[float]]:
    """The least lean, either way from level, at which the standing finger check's bare-blade gap closes, to 0.05 degree; null when it stays open to the limit."""
    out: Dict[str, Optional[float]] = {}
    for name, sign in (("leaning_far_end_up_deg", 1.0), ("leaning_far_end_down_deg", -1.0)):
        found = None
        for k in range(0, int(limit_deg / 0.05) + 1):
            lean = sign * k * 0.05
            if standing_gap_to_bare_blade(m, ref, lean) <= 0.0:
                found = lean
                break
        out[name] = found
    return out


def check_blade_finger(m: case.Model, form: str = "single", fitted: Optional[Sequence[str]] = None) -> List[Dict[str, Any]]:
    """The stand-in finger against the three blades: with all three receptacles fitted (the verdict) and with none (a finding).

    The standing finger check (c15.finger) takes each bay on its own with the tip centred on it. These two results use the
    opening itself, the tip anywhere in it. Fitted is a verdict: all three boots on their blades, the typical envelope the pass
    rule and the largest common one reported alongside. The receptacle-off reach is the owner's stated, accepted residual: it is
    computed with its figures and reported as a finding, and is counted in no verdict.
    """
    P = m.P
    admits = P("finger.admits_nothing_below_mm")
    fitted = tuple(BLADE_REFS if fitted is None else fitted)
    fitted_rows: Dict[str, Any] = {}
    for which in ("typical", "largest_common"):
        free = fitted_free_opening(m, which, fitted)
        fitted_rows[which] = {"widest_disc_in_the_free_opening_mm": widest_disc(free), "admits_nothing": widest_disc(free) < admits,
                              "receptacles_fitted": list(fitted), "free_opening_area_mm2": float(free.area)}
    unfitted = {ref: row["gap"] for ref, row in bare_blade_reach(m, {r: "typical" for r in fitted}).items()}
    ok = fitted_rows["typical"]["admits_nothing"] and not unfitted
    out = [result("c15.finger_blades_receptacle_fitted", "C15", ok,
                  f"with receptacle boots fitted on {'all three blades' if len(fitted) == len(BLADE_REFS) else ', '.join(fitted) + ' only'} the opening left round them admits a disc of at most "
                  + " and ".join(f"{v['widest_disc_in_the_free_opening_mm']:.2f} mm ({k})" for k, v in fitted_rows.items())
                  + f", under the finger's {admits:.1f} mm tip, so no blade is reachable (the pass rule is the typical envelope; the largest common one is reported alongside)",
                  {"envelopes": fitted_rows, "pass_rule_envelope": "typical", "blades_without_a_receptacle_tip_to_blade_mm": unfitted, "boots_assumed": {w: P(f"boots.{w}") for w in ("typical", "largest_common")},
                   "boots_source": {w: P.entry(f"boots.{w}")["source"] for w in ("typical", "largest_common")},
                   "live_metal_reachable_with_boots_fitted": not ok,
                   "note": "an insulated boot is not bare mains metal; the figure is the free opening round the boots, not the boots' own surface"})]
    bare = bare_blade_reach(m)
    bays = {a["ref"]: a for a in case.aperture_boxes(m)}
    blades: Dict[str, Any] = {}
    lines = []
    for ref, row in bare.items():
        lean = lean_that_fails_standing_check(m, ref)
        mixed = finger_reach_to_bare_blades(m, {o: "typical" for o in BLADE_REFS if o != ref}).get(ref)
        blades[ref] = {"tip_to_blade_mm": row["gap"], "tip_at_uv_mm": [row["u"], row["v"]], "gap_the_finger_enters_mm": row["width"],
                       "bay_mm": {"across_thickness_u": bays[ref]["du"], "across_width_v": bays[ref]["dv"]},
                       "standing_check_fails_at_lean": lean, "standing_gap_at_the_nominal_lean_mm": standing_gap_to_bare_blade(m, ref, math.degrees(m.phi)),
                       "this_blade_bare_neighbours_fitted_gap_mm": mixed}
        fails = [f"{v:+.2f} deg ({k.replace('_deg', '').replace('_', ' ')})" for k, v in lean.items() if v is not None]
        lines.append(f"{ref}: tip to blade {row['gap']:.2f} mm in a {row['width']:.2f} mm gap of a bay {bays[ref]['du']:.2f} x {bays[ref]['dv']:.2f}; standing check fails at lean " + (", ".join(fails) if fails else "none within 5 degrees"))
    touched = [r for r, b in blades.items() if b["tip_to_blade_mm"] <= 0.0]
    out.append(finding("c15.finding_blades_no_receptacle", "C15",
                       "with no receptacle fitted the stand-in finger's tip, placed anywhere in the bays, comes " + ", ".join(f"{r} {b['tip_to_blade_mm']:.2f} mm" for r, b in blades.items())
                       + " from each blade" + (f"; it reaches {', '.join(touched)}" if touched else "") + ": a stated, accepted residual (the boots close it), reported and not counted in any verdict",
                       {"blades": blades, "touchable_blades": touched,
                        "blade_pitch_mm": {"J941-J921": blade_centre(m, "J921")[0] - blade_centre(m, "J941")[0], "J921-J911": blade_centre(m, "J911")[0] - blade_centre(m, "J921")[0]},
                        "probe": f"IEC 61032 probe B stand-in: {P('finger.probe_dia_mm'):.0f} mm cylinder, {P('finger.tip_dia_mm'):.0f} mm hemispherical tip, {P('finger.cone_length_mm'):.0f} mm cone (Lisun data sheet, secondary source)",
                        "lean_deg": math.degrees(m.phi), "accepted_by": "the design owner: the verdict is judged with the receptacles fitted",
                        "what_the_standing_check_excludes": "each bay on its own with the tip centred on it: a merged bay and an off-centre tip are not tried"}, lines))
    return out


def check_c18(m: case.Model, form: str = "single") -> List[Dict[str, Any]]:
    """Receptacles with insulating boots pushed on the blades from below: each envelope swept along its blade."""
    P = m.P
    need = P("boots.clearance_mm")
    travel = P("blade.standoff_mm") + P("blade.above_shoulder_mm") + P("boots.withdraw_extra_mm")
    obstacles = {"lid": Scene(m, [f"lid_{form}"]), "tray": Scene(m, ["tray"])}
    part_scenes = {name: Scene(m, [name]) for name in m.bodies if name != "board"}
    rows = []
    ok = True
    lines = []
    for which in ("typical", "largest_common"):
        env = case.boot_box(m, which)
        for ref in ("J941", "J921", "J911"):
            uc, vc = blade_centre(m, ref)
            local = box_surface_points(uc - env["across_thickness"] / 2, uc + env["across_thickness"] / 2, vc - env["across_width"] / 2,
                                       vc + env["across_width"] / 2, 0.0, env["length"] + travel)
            pts = np.array([m.board_global(tuple(p)) for p in local])
            dist = {name: float(sc.closest_distances(pts).min()) for name, sc in obstacles.items()}
            on = min(dist.values())
            off = dist["tray"]
            near_on = min(dist, key=dist.get)
            near_off = "tray"
            # the boot against the other bodies of the board, for information: the boot's seated box, the mouth on the board's face
            seated = np.array([m.board_global(tuple(p)) for p in box_surface_points(uc - env["across_thickness"] / 2, uc + env["across_thickness"] / 2,
                                                                                   vc - env["across_width"] / 2, vc + env["across_width"] / 2, 0.05, env["length"])])
            parts = {}
            for name, psc in part_scenes.items():
                if name == ref:
                    continue
                parts[name] = float(psc.closest_distances(seated[:: 4]).min())
            near_part = min(parts, key=parts.get)
            rows.append({"blade": ref, "envelope": which, "lid_on_least_clearance_mm": on, "lid_on_nearest": near_on, "lid_off_least_clearance_mm": off,
                         "lid_off_nearest": near_off, "per_body_mm": dist, "nearest_other_part": near_part, "nearest_other_part_mm": parts[near_part],
                         "pass": on >= need - 1e-9 and off >= need - 1e-9})
            ok &= on >= need - 1e-9 and off >= need - 1e-9
            lines.append(f"{which:15s} {ref}: lid on {on:5.2f} mm ({near_on}), lid off {off:5.2f} mm ({near_off}); nearest other part {near_part} {parts[near_part]:.2f} mm")
    # neighbouring boots
    us = {ref: blade_centre(m, ref)[0] for ref in ("J941", "J921", "J911")}
    order = sorted(us, key=us.get)
    gaps = {}
    for which in ("typical", "largest_common"):
        env = case.boot_box(m, which)
        gaps[which] = {f"{a}-{b}": (us[b] - us[a]) - env["across_thickness"] for a, b in zip(order, order[1:])}
    pitch_env = P("boots.pitch_pass_envelope")
    gaps_ok = all(g > 0.0 for g in gaps[pitch_env].values())
    lines += [f"boot to boot at {w}: " + ", ".join(f"{k} {v:.2f} mm" for k, v in g.items()) for w, g in gaps.items()]
    # the wire's bend room and the depth below the lid face
    zt = P("case.z_lid_top_mm")
    bend = P("boots.bend_od_multiple") * P("boots.wire_od_mm")
    depth = {w: case.boot_box(m, w)["length"] + bend - zt for w in ("typical", "largest_common")}
    seated_end = {w: case.boot_box(m, w)["length"] for w in ("typical", "largest_common")}
    lines += [f"{w}: boot to {seated_end[w]:.1f} above the board face, wire bend room {bend:.1f} beyond it, so {depth[w]:.2f} mm below the lid face" for w in depth]
    # the lid with receptacles fitted
    _, pivot = sweep_poses(m)
    slide_free = lid_removal_installed(m, form, *sweep_poses(m))["slide_to_free_the_toes_mm"] or 0.0
    removal = {w: {"boots_only": boot_removal_with_lid(m, pivot, slide_free, w, False), "boots_and_straight_wire": boot_removal_with_lid(m, pivot, slide_free, w, True)} for w in ("typical", "largest_common")}
    for w, r in removal.items():
        a, b = r["boots_only"], r["boots_and_straight_wire"]
        lines.append(f"lid off with {w} receptacles fitted: boots alone {'free' if a['removable'] else 'blocked at slide %.2f mm' % a['first_contact']['slide_mm']}; with straight wires {'free' if b['removable'] else 'blocked at slide %.2f mm' % b['first_contact']['slide_mm']}")
    reach = finger_reach_to_bare_blades(m)
    lines.append("stand-in finger tip to each bare blade, tip anywhere in the bays: " + ", ".join(f"{k} {v:.2f} mm" for k, v in reach.items()))
    bays = case.aperture_boxes(m)
    return [result("c18.boot_clearance", "C18", ok and gaps_ok,
                   f"a receptacle boot swept along each blade, fully seated to fully withdrawn plus {P('boots.withdraw_extra_mm'):.0f} mm, keeps {min(r['lid_on_least_clearance_mm'] for r in rows):.2f} mm to the lid and tray with the lid on and {min(r['lid_off_least_clearance_mm'] for r in rows):.2f} mm with it off (needs {need:.1f}) at both envelopes; neighbouring boots are {gaps['typical']['J941-J921']:.2f} mm apart at typical and {gaps['largest_common']['J941-J921']:.2f} mm at largest_common; boot and bend need {depth['typical']:.1f} mm (typical) to {depth['largest_common']:.1f} mm (largest) below the lid face",
                   {"required_clearance_mm": need, "boots": rows, "boot_to_boot_gap_mm": gaps, "boot_to_boot_pass_envelope": pitch_env,
                    "boot_to_boot_ok_at_pass_envelope": gaps_ok,
                    "bay_mm": {"across_thickness_u": bays[0]["du"], "across_width_v": bays[0]["dv"], "lean_allowance_each_side_mm": case.lean_allowance(m)},
                    "wire": {"od_mm": P("boots.wire_od_mm"), "bend_room_mm": bend, "bend_basis": "design allowance; distributor guidance 3 to 5 x OD; no maker figure"},
                    "boot_end_above_board_face_mm": seated_end, "depth_below_lid_face_for_boot_and_bend_mm": depth,
                    "lid_removal_with_receptacles_fitted": removal, "bare_blade_finger_reach_mm": reach,
                    "envelope_status": "assumed, owner to measure his boots",
                    "installed_frame": "the blades point down; the boots push on from below; depth below the lid face is measured downward"}, lines)]


def check_c20(m: case.Model, form: str = "single") -> List[Dict[str, Any]]:
    """The bend room the lid leaves over the header's wire exit, and the largest wire outside diameter it supports at three times the diameter.

    The room is measured on the built lid: rays rise from the top of the mated housing over its whole footprint, the housing carried
    by the board's lean, and the least height at which one meets the lid is the clearance; it is least at the seating range's worst lean. A change to the housing height or to the lid's underside changes the figure.
    """
    P = m.P
    j = m.board.refs["J931"]
    exit_z = P("parts.header_housing_top_z_mm")
    sc = scene(m, form)
    u0, u1 = min(p["u"] for p in j["pads"]) - 1.27, max(p["u"] for p in j["pads"]) + 1.27
    v0, v1 = j["v"] - 1.27, j["v"] + 1.27
    hits = []
    for u in np.linspace(u0, u1, 7):
        for v in np.linspace(v0, v1, 3):
            gu, gv, gz = m.board_global((float(u), float(v), exit_z))       # the housing's top corner as the board's lean carries it
            h = sc.first_hit((gu, gv, gz + 1e-3), (0.0, 0.0, 1.0))
            if h is not None and h["solid"] == f"lid_{form}":
                hits.append(h["point"][2] - gz)
    room = float(min(hits)) if hits else float("nan")
    factor = 3.0
    widest = room / factor if hits else float("nan")
    stated = math.floor(widest * 10.0 + 1e-9) / 10.0 if hits and widest > 0 else 0.0
    passed = bool(hits) and len(hits) == 21 and room > 0.0
    return [result("c20.cable_bend_room", "C20", passed,
                   f"the lid stands {room:.2f} mm over the header's wire exit (z {exit_z:.2f}); at {factor:.0f} times the wire's diameter the room supports wire up to {stated:.1f} mm outside diameter",
                   {"wire_exit_z_mm": exit_z, "lid_underside_over_exit_z_mm": exit_z + room if hits else None, "board_lean_deg": math.degrees(m.phi), "bend_room_mm": room,
                    "bend_room_factor": factor, "largest_wire_od_mm": widest, "largest_wire_od_stated_mm": stated, "rays_meeting_the_lid": len(hits), "rays": 21})]


def run_all(m: case.Model, form: str = "single", include_sweep: bool = True, only: Optional[Sequence[str]] = None) -> List[Dict[str, Any]]:
    """Every check; `only` names the prefixes of the checks to run (for example `("c1.", "c4.")`), the others are skipped."""
    groups = [(check_c1, ("c1.",)), (check_c2_c3, ("c2.", "c3.")), (check_c4, ("c4.",)), (check_c5_c11, ("c5.", "c11.")),
              (check_fixings, ("c5.",)), (check_c6_c9, ("c6.", "c9.")), (check_c7, ("c7.",)), (check_c8, ("c8.",)), (check_c13, ("c13.",)),
              (check_c14, ("c14.",)), (check_c15, ("c15.",)), (check_blade_finger, ("c15.",)), (check_c18, ("c18.",)), (check_c20, ("c20.",)), (check_c16_geometry, ("c16.",))]
    results: List[Dict[str, Any]] = []
    for fn, prefixes in groups:
        if (fn is check_c4 and not include_sweep) or (fn is check_c13 and "lid_two" not in m.parts):
            continue
        if only is not None and not any(any(o.startswith(p) or p.startswith(o) for p in prefixes) for o in only):
            continue
        if fn in (check_c1, check_c2_c3, check_c7, check_c13, check_c14, check_c16_geometry):
            res = fn(m)
        else:
            res = fn(m, form)
        results += [r for r in res if only is None or any(r["name"].startswith(o) for o in only)]
    return results


def triac_screw_figures(P: Any) -> Dict[str, float]:
    """How far a triac screw's tip stands inside the plate and how much thread it engages, over the screw's length tolerance and the tab's thickness range."""
    length = P.entry("triac.tab_screw_length_mm")
    b2 = P.entry("triac.b2_mm")
    plate = P("plate.thickness_mm")
    tip_max = length["max"] - b2["min"]
    engagement_min = length["min"] - b2["max"]
    need = P("triac.tab_screw_min_engagement_mm")
    d = P("triac.tab_screw_dia_mm")
    clamp = P("triac.tab_screw_torque_Nm") * 1000.0 / (P("triac.tab_screw_torque_coefficient") * d)        # N, from T = K F d with T in N mm
    area = math.pi * P("triac.plate_tap_drill_mm") * engagement_min                                         # shear surface at the tap-drilled diameter, a smaller cylinder than the thread's
    shear = clamp / area
    return {"tip_depth_max_mm": tip_max, "engagement_min_mm": engagement_min, "plate_thickness_mm": plate, "tip_margin_mm": plate - tip_max,
            "required_engagement_mm": need, "clamp_force_N": clamp, "shear_surface_mm2": area, "shear_stress_MPa": shear,
            "alloy_shear_MPa": P("triac.plate_alloy_shear_MPa"), "screw_length_mm": [length["min"], length["max"]], "tab_thickness_mm": [b2["min"], b2["max"]]}


def check_c16_geometry(m: case.Model) -> List[Dict[str, Any]]:
    """What the seating range changes in one build: lead clearance under the board, the plate's holes at the tab hole height and the triac screws' depth and thread."""
    P = m.P
    out = []
    gaps = {}
    for name in ("T911_leads", "T921_leads", "J941", "J921", "J911"):
        gaps[name] = float(m.bodies[name]["shape"].distance_to(m.parts["tray"]))
    least = min(gaps.values())
    # the plate's holes, tapped through from the triac side: found by scanning z at each triac's u with a ray along -v that passes the whole plate
    sc = Scene(m, ["plate"])
    found = {}
    T = P("plate.thickness_mm")
    for ref in case.TRIAC_REFS:
        through = []
        for z in np.arange(m.tab_hole_z - 2.5, m.tab_hole_z + 2.5, 0.05):
            hit = sc.first_hit((m.triac_u[ref], m.v_plate + 1.0, float(z)), (0, -1, 0), length=T + 5.0)
            if hit is None:
                through.append(float(z))
        found[ref] = (sum(through) / len(through)) if through else None
    plate_ok = all(v is not None and abs(v - m.tab_hole_z) < 0.1 for v in found.values())
    pl = m.info["plate"]
    head_r = P("triac.tab_screw_head_dia_mm") / 2
    heads = {"lower_edge_margin_mm": m.tab_hole_z - head_r - pl["z0"], "upper_edge_margin_mm": pl["z1"] - (m.tab_hole_z + head_r)}
    heads_ok = min(heads.values()) >= P("plate.screw_edge_distance_mm")
    out.append(result("c16.seat_clear_of_leads_and_plate_hole", "C16", least > 0.3 and plate_ok and heads_ok,
                      f"at this seating the leads and blade legs stand at least {least:.2f} mm off the tray, the plate's holes are tapped through at the tab hole height ({m.tab_hole_z:.2f}) and each screw head stands {min(heads.values()):.2f} mm inside the plate's edges",
                      {"lead_to_tray_mm": gaps, "plate_hole_z_mm": found, "tab_hole_z_mm": m.tab_hole_z, "body_underside_mm": m.body_underside,
                       "lean_deg": P("seating.lean_deg"), "gap_board_edge_to_plate_mm": float(m.board.outline.bounds[1]) - m.v_plate,
                       "screw_head_margins_mm": heads, "tapped_through": True}))
    f = triac_screw_figures(P)
    out.append(result("c16.triac_screw_tip_and_engagement", "C16",
                      f["tip_depth_max_mm"] < f["plate_thickness_mm"] and f["engagement_min_mm"] >= f["required_engagement_mm"] and f["shear_stress_MPa"] < f["alloy_shear_MPa"],
                      f"over the screw's length tolerance and the tab's thickness range an M3 x {P('triac.tab_screw_length_mm'):.0f} tip stands at most {f['tip_depth_max_mm']:.3f} mm inside the {f['plate_thickness_mm']:.1f} mm plate "
                      f"({f['tip_margin_mm']:.3f} mm short of its back face) and engages at least {f['engagement_min_mm']:.3f} mm of thread (needs {f['required_engagement_mm']:.1f}); "
                      f"the {f['clamp_force_N']:.0f} N clamp load shears {f['shear_stress_MPa']:.0f} MPa at that engagement against {f['alloy_shear_MPa']:.0f} MPa",
                      dict(f, arithmetic=f"tip {f['screw_length_mm'][1]:.2f} - {f['tab_thickness_mm'][0]:.2f} = {f['tip_depth_max_mm']:.2f}; engagement {f['screw_length_mm'][0]:.2f} - {f['tab_thickness_mm'][1]:.2f} = {f['engagement_min_mm']:.2f}")))
    return out


def combo_overrides(overrides: Dict[str, Any], skin: Optional[str], combo: Tuple[str, ...]) -> Dict[str, Any]:
    """The parameter overrides of one extreme combination: `combo` names min or max for each of the six axes of SEATING_AXES."""
    bu, lean, tfc, routing, play, edge = combo
    base = case.Params.load(overrides, skin)
    o = dict(overrides)
    o["seating.body_underside_mm"] = base.entry("seating.body_underside_mm")[bu]
    o["seating.lean_deg"] = base.entry("seating.lean_deg")[lean]
    o["seating.tab_face_to_lead_centre_mm"] = base.entry("seating.tab_face_to_lead_centre_mm")[tfc]
    o["seating.outline_routing_mm"] = base.entry("seating.outline_routing_mm")[routing]
    o["seating.lead_play_mm"] = base.entry("seating.lead_play_mm")[play]
    o["seating.plate_edge_offset_mm"] = base.entry("seating.plate_edge_offset_mm")[edge]
    return o


def _seating_combo(args: Tuple[Dict[str, Any], Optional[str], Tuple[str, ...]]) -> Dict[str, Any]:
    """One extreme combination of body height, lean, tab-face distance, outline routing tolerance and lead play, rebuilt and checked in full."""
    overrides, skin, combo = args
    os.nice(5)
    o = combo_overrides(overrides, skin, combo)
    m = case.build(o, forms=("single",), skin=skin)
    results = run_all(m, include_sweep=True)
    counted = verdicts(results)
    clearance = next(r for r in results if r["name"] == "c1.creepage_all_mains_copper")
    boots = next(r for r in results if r["name"] == "c18.boot_clearance")
    return {"seating": {"body_underside_mm": o["seating.body_underside_mm"], "lean_deg": o["seating.lean_deg"],
                        "tab_face_to_lead_centre_mm": o["seating.tab_face_to_lead_centre_mm"], "outline_routing_mm": o["seating.outline_routing_mm"],
                        "lead_play_mm": o["seating.lead_play_mm"], "plate_edge_offset_mm": o["seating.plate_edge_offset_mm"], "tab_hole_height_mm": m.tab_hole_z},
            "all_pass": all(r["passed"] for r in counted), "failed": [r["name"] for r in counted if not r["passed"]], "checks_run": len(counted),
            "findings": {r["name"]: r["figures"]["blades"] for r in results if r.get("kind") == "finding"},
            "least_creepage_mm": clearance["figures"]["least_mm"],
            "least_lead_mm": next(r for r in results if r["name"] == "c1.creepage_bare_lead_to_plate")["figures"]["creepage_mm"],
            "gap_mm": next(r for r in results if r["name"] == "c1.gap_over_tolerances")["figures"]["gap_of_this_build_mm"],
            "lid_sweep_min_mm": next(r for r in results if r["name"] == "c4.lid_sweep")["figures"]["minimum_clearance_mm"],
            "boot_least_clearance_mm": min(min(b["lid_on_least_clearance_mm"], b["lid_off_least_clearance_mm"]) for b in boots["figures"]["boots"]),
            "driver_tilt_deg": dict(m.info.get("driver_tilt_deg", {})), "creepage_required_mm": m.basis["creepage_mains_mm"]}


SEATING_AXES = ("body height", "lean", "tab-face distance", "outline routing tolerance", "lead play", "plate edge (ledge print allowance and board thickness)")


def seating_combinations() -> List[Tuple[str, ...]]:
    """Every extreme of the six tolerance axes: 64 combinations."""
    return [c for c in itertools.product(("min", "max"), repeat=len(SEATING_AXES))]


def seating_range(overrides: Dict[str, Any], skin: Optional[str] = None, workers: int = 4,
                  combos: Optional[Sequence[Tuple[str, ...]]] = None) -> List[Dict[str, Any]]:
    """Every extreme combination of body height, lean, tab-face distance, outline routing tolerance, lead play and plate edge, each rebuilt and checked, up to four at a time."""
    import multiprocessing
    combos = list(combos) if combos is not None else seating_combinations()
    jobs = [(overrides, skin, c) for c in combos]
    if workers > 1:
        with multiprocessing.get_context("spawn").Pool(min(workers, 4)) as pool:
            rows = pool.map(_seating_combo, jobs, chunksize=1)
    else:
        rows = [_seating_combo(j) for j in jobs]
    least = min(r["least_creepage_mm"] for r in rows)
    need = rows[0]["creepage_required_mm"]
    return [result("c16.seating_range", "C16", all(r["all_pass"] for r in rows) and least >= need,
                   f"all {len(rows)} extreme combinations of body height, lean, tab-face distance, outline routing tolerance, lead play and plate edge rebuild and pass every check; the least straight line from Mains copper to the plate is {least:.3f} mm against {need:.1f} mm",
                   {"combinations": rows, "worst_creepage_mm": least, "required_mm": need, "axes": list(SEATING_AXES),
                    "range_source": "params.yaml seating block, each entry unconfirmed: the owner measures it on the delivered board"},
                   [f"body {r['seating']['body_underside_mm']:.2f} lean {r['seating']['lean_deg']:+.1f} tab face {r['seating']['tab_face_to_lead_centre_mm']:.3f} "
                    f"routing {r['seating']['outline_routing_mm']:+.1f} play {r['seating']['lead_play_mm']:+.3f} edge {r['seating']['plate_edge_offset_mm']:+.2f} "
                    f"(hole {r['seating']['tab_hole_height_mm']:.2f}, gap {r['gap_mm']:.3f}): pass {r['all_pass']} ({r['checks_run']} checks), nearest copper {r['least_creepage_mm']:.3f}, lead {r['least_lead_mm']:.3f}, sweep {r['lid_sweep_min_mm']:.3f}, boots {r['boot_least_clearance_mm']:.2f}"
                    + ("" if r["all_pass"] else " FAILED " + ", ".join(r["failed"])) for r in rows]),
            seating_range_finding(rows)]


HEIGHT_RANGE_STATES = ("nominal gap", "narrowest gap", "widest gap")


def height_range_overrides(overrides: Dict[str, Any], skin: Optional[str], end: str, state: str) -> Dict[str, Any]:
    """One build of the plate-height range: the plate at the least (`min`) or the greatest (`max`) height the case takes, the lower edge unchanged, and the board-edge-to-plate gap
    nominal or at its narrowest or widest (the tab-face distance, the outline routing tolerance and the lead play all at the one extreme, as the gap's own range states them)."""
    base = case.Params.load(overrides, skin)
    o = dict(overrides)
    o["plate.height_mm"] = base("plate.height_min_mm") if end == "min" else base("plate.height_max_mm")
    if state != "nominal gap":
        narrow = state == "narrowest gap"
        o["seating.tab_face_to_lead_centre_mm"] = base.entry("seating.tab_face_to_lead_centre_mm")["min" if narrow else "max"]
        o["seating.outline_routing_mm"] = base.entry("seating.outline_routing_mm")["min" if narrow else "max"]
        o["seating.lead_play_mm"] = base.entry("seating.lead_play_mm")["max" if narrow else "min"]
    return o


def _height_case(args: Tuple[Dict[str, Any], Optional[str], str, str]) -> Dict[str, Any]:
    """One end of the plate-height range at one gap state, rebuilt and checked in full by the same path the seating range uses."""
    overrides, skin, end, state = args
    os.nice(5)
    o = height_range_overrides(overrides, skin, end, state)
    m = case.build(o, forms=("single",), skin=skin)
    results = run_all(m, include_sweep=True)
    counted = verdicts(results)
    return {"end": end, "state": state, "plate_height_mm": o["plate.height_mm"], "plate_upper_edge_z_mm": m.info["plate"]["z1"],
            "all_pass": all(r["passed"] for r in counted), "failed": [r["name"] for r in counted if not r["passed"]], "checks_run": len(counted),
            "least_creepage_mm": next(r for r in results if r["name"] == "c1.creepage_all_mains_copper")["figures"]["least_mm"],
            "opening_z_mm": next(r for r in results if r["name"] == "c2.wall_opening_within_unit_opening")["figures"]["opening_z_mm"],
            "case_top_margin_mm": next(r for r in results if r["name"] == "c2.plate_covers_case_top")["figures"]["margin_mm"],
            "gap_mm": next(r for r in results if r["name"] == "c1.gap_over_tolerances")["figures"]["gap_of_this_build_mm"]}


def plate_height_range(overrides: Dict[str, Any], skin: Optional[str] = None, workers: int = 4) -> List[Dict[str, Any]]:
    """The case's checks at the least and the greatest plate height, each at the nominal gap and at the gap's two extremes, each rebuilt and checked, up to four at a time."""
    import multiprocessing
    jobs = [(overrides, skin, end, state) for end in ("min", "max") for state in HEIGHT_RANGE_STATES]
    if workers > 1:
        with multiprocessing.get_context("spawn").Pool(min(workers, 4)) as pool:
            rows = pool.map(_height_case, jobs, chunksize=1)
    else:
        rows = [_height_case(j) for j in jobs]
    base = case.Params.load(overrides, skin)
    lo, hi = base("plate.height_min_mm"), base("plate.height_max_mm")
    need = case.basis()["creepage_mains_mm"]
    least = min(r["least_creepage_mm"] for r in rows)
    return [result("c16.plate_height_range", "C16", all(r["all_pass"] for r in rows) and least >= need,
                   f"the case's checks hold at the least plate height, {lo:.1f} mm, and the greatest, {hi:.1f} mm, with the lower edge unchanged, each at the nominal gap and at the narrowest and widest: {len(rows)} rebuilds, "
                   f"{sum(1 for r in rows if r['all_pass'])} pass every check; the least straight line from Mains copper to the plate is {least:.3f} mm against {need:.1f} mm",
                   {"heights_mm": [lo, hi], "rows": rows, "worst_creepage_mm": least, "required_mm": need, "states": list(HEIGHT_RANGE_STATES)},
                   [f"plate {r['plate_height_mm']:.1f} mm (upper edge z {r['plate_upper_edge_z_mm']:.2f}), {r['state']} (gap {r['gap_mm']:.3f}): pass {r['all_pass']} ({r['checks_run']} checks), "
                    f"nearest copper {r['least_creepage_mm']:.3f}, case-top margin {r['case_top_margin_mm']:.3f}, opening z {r['opening_z_mm'][0]:.2f} to {r['opening_z_mm'][1]:.2f}"
                    + ("" if r["all_pass"] else " FAILED " + ", ".join(r["failed"])) for r in rows])]


def seating_range_finding(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """The receptacle-off bare-blade reach at every extreme of the seating range: reported with the range, never counted in its verdict."""
    name = "c15.finding_blades_no_receptacle"
    touched = {}
    lines = []
    for r in rows:
        blades = r["findings"][name]
        label = (f"body {r['seating']['body_underside_mm']:.2f} lean {r['seating']['lean_deg']:+.1f} tab face {r['seating']['tab_face_to_lead_centre_mm']:.3f} "
                 f"routing {r['seating']['outline_routing_mm']:+.1f} play {r['seating']['lead_play_mm']:+.3f} edge {r['seating']['plate_edge_offset_mm']:+.2f}")
        reached = sorted(ref for ref, b in blades.items() if b["tip_to_blade_mm"] <= 0.0)
        touched[label] = reached
        lines.append(f"{label}: " + ", ".join(f"{ref} {b['tip_to_blade_mm']:.2f} mm" for ref, b in blades.items()) + (f"; tip reaches {', '.join(reached)}" if reached else "; no blade reached"))
    return finding("c15.finding_blades_no_receptacle_seating_range", "C15",
                   f"with no receptacle fitted the stand-in finger reaches a bare blade in {sum(1 for v in touched.values() if v)} of {len(rows)} extreme seatings: a stated, accepted residual, reported and not counted in the range's verdict",
                   {"reached_blades_by_seating": touched, "combinations": {k: r["findings"][name] for k, r in zip(touched, rows)}}, lines)


# ---------------------------------------------------------------------------------------------------------------------
# Command line
# ---------------------------------------------------------------------------------------------------------------------

def render_text(results: List[Dict[str, Any]], verbose: bool = True) -> str:
    out = []
    for r in results:
        label = "finding" if r.get("kind") == "finding" else ("PASS" if r["passed"] else "FAIL")
        out.append(f"{label}  {r['name']:44s} [{r['criterion']}]  {r['summary']}")
        if verbose:
            for line in r["lines"]:
                out.append("        " + line)
    counted = verdicts(results)
    failed = [r for r in counted if not r["passed"]]
    findings = len(results) - len(counted)
    out.append(f"RESULT  {'PASS' if not failed else 'FAIL'}  {len(counted) - len(failed)} of {len(counted)} checks pass; {findings} finding{'s' if findings != 1 else ''} reported, not counted")
    return "\n".join(out)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Check the printed case of the heater wall board against its geometry criteria.")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--json-out", help="also write the JSON result to this path")
    parser.add_argument("--set", action="append", default=[], metavar="KEY=VALUE", help="override a params.yaml value")
    parser.add_argument("--range", action="store_true", help="rebuild and check at every extreme of the seating range")
    parser.add_argument("--height-range", action="store_true", help="rebuild and check at the least and the greatest plate height, each at the nominal gap and at its two extremes")
    parser.add_argument("--form", choices=("single", "two"), default="single", help="the lid form the checks run on")
    parser.add_argument("--skin", help="the skin to check (flow, or another skin the file holds); the params.yaml default when omitted")
    parser.add_argument("--only", help="comma-separated prefixes of the checks to run, for example c1.,c15.; every check when omitted")
    args = parser.parse_args(argv)
    overrides = case.parse_overrides(args.set)
    model = case.build(overrides, skin=args.skin)
    only = [s for s in args.only.split(",") if s] if args.only else None
    results = run_all(model, args.form, only=only)
    if args.range:
        results += seating_range(overrides, model.P.skin_name)
    if args.height_range:
        results += plate_height_range(overrides, model.P.skin_name)
    payload = {"criterion": TRACE, "board_sha256": model.board.sha256, "overrides": overrides, "skin": model.P.skin_name,
               "seating": {"body_underside_mm": model.body_underside, "lean_deg": model.P("seating.lean_deg"),
                           "tab_face_to_lead_centre_mm": model.P("seating.tab_face_to_lead_centre_mm"), "outline_routing_mm": model.P("seating.outline_routing_mm"),
                           "lead_play_mm": model.P("seating.lead_play_mm"), "plate_edge_offset_mm": model.P("seating.plate_edge_offset_mm"), "tab_hole_height_mm": model.tab_hole_z},
               "basis": model.basis, "passed": all(r["passed"] for r in verdicts(results)), "findings": [r["name"] for r in results if r.get("kind") == "finding"],
               "checks": results}
    payload = jsonable(payload)
    if args.json_out:
        os.makedirs(os.path.dirname(os.path.abspath(args.json_out)), exist_ok=True)
        with open(args.json_out, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=1)
    if args.format == "json":
        print(json.dumps(payload, indent=1))
    else:
        print(render_text(payload["checks"]))
    return 0 if payload["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
