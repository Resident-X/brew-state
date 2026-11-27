#!/usr/bin/env python3
"""Does the exported case fit the board as built? The exported files, read as a printer or viewer reads them, against the board's own model.

    python fit.py                     every result as text, the files read from out/ (task hw:case first)
    python fit.py --format json       the same as JSON
    python fit.py --controls          also run the negative controls: the exports mirrored in X, in Y, and the logo checked against its mirror image
    python fit.py --out DIR           read the exports from DIR

The check reads two things and nothing of the case model: (a) the files case.py wrote into out/ (the STL of every part, the print STLs, the
3MFs), which are right-handed physical shapes in the frame X = u, Y = -v, Z = z, and (b) the board's three-dimensional model that
kicad-cli exported from the layout file (board_model.py, cached in board-model/), plus the nominal figures of params.yaml and the artwork of the
logo. It does not build the case, and no (u, v) of the case model is used to judge anything.

Placement is a translation derived from the board model alone: the board body's low-X, high-Y corner goes to the origin of the exported
frame, and its component face, the plane the tops of the surface-mount pads make (the face is established from the pad solids, not assumed:
the pad solids with no drilled hole beside them sit on it), to Z = 0. The board's underside is then its lowest solid, the board's own copper
and body together, which is the board's thickness as the layout states it (1.6 mm) to within the copper's rounding. A board model
whose component face looks toward -Z is refused, since placing it would take a reflection, which is the very error this check exists to find.

Every result is named and carries its measured figure, the expectation and the tolerance it is held to. Tolerances are chosen from what the
meshes resolve: a hole located from a section of an STL is good to about 0.02 mm, so a position is held to 0.05 mm; a distance measured from
sampled surface points is good to the sampling step, so a clearance is held to 0.1 mm; the volume of an intersection is held to a bound of
0.5 cubic millimetres.

The logo is read on the face as the installed viewer sees it, standing in front of the wall facing it. In the physical frame the wall is toward
+Y and, installed, gravity is +Z, so the viewer's forward is +Y, up is -Z and right is -X. The lid face looks down, seen from below with the
wall at the bottom of the view: view right is -X and view up is -Y. The tray's outer top face looks up, seen from above with the wall at the
top: view right is -X and view up is +Y. The grooves are cut from the exported mesh at mid groove depth and compared, by intersection over
union on a raster after a search over offsets, with the engraving made from the artwork (x right, y up as the artwork reads) and with its
mirror images and half turn; it must reach 0.85 and beat each of the others by 0.4.

The negative controls hand the same check functions meshes mirrored in one axis about the board's centre line, windings corrected so that only
the handedness differs, and the logo check the mirrored artwork; each must fail the named results that locate a feature.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import math
import os
import sys
import zipfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from functools import reduce
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.dont_write_bytecode = True

import numpy as np  # noqa: E402
import shapely  # noqa: E402
import trimesh  # noqa: E402
from scipy.signal import fftconvolve  # noqa: E402
from scipy.sparse import coo_matrix  # noqa: E402
from scipy.sparse.csgraph import connected_components  # noqa: E402
from scipy.spatial import cKDTree  # noqa: E402
from shapely import affinity  # noqa: E402
from shapely.geometry import LineString, Point, Polygon  # noqa: E402
from shapely.ops import polygonize, unary_union  # noqa: E402

import board_model  # noqa: E402
import logo as logo_module  # noqa: E402

PARTS = ("tray", "plate", "lid_single", "lid_two", "lid_swap", "tray_swap")
PRINTED = ("tray", "lid_single", "lid_two")
FORMS = {"single": ("tray", "lid_single", "plate"), "two": ("tray", "lid_two", "plate", "lid_swap", "tray_swap")}
SWAP_OF = {"tray": "tray_swap", "lid_two": "lid_swap"}

# tolerances, each stated in the result that uses it
POSITION_TOL_MM = 0.05          # a feature located from a section of an exported mesh
FACE_TOL_MM = 0.02              # a plane read off a mesh's bounds
CLEARANCE_TOL_MM = 0.1          # a distance from sampled surface points (the sampling step is about 0.05 mm)
VOLUME_BOUND_MM3 = 0.5          # the volume two solids may share and still count as not intersecting
SEAT_PLANE_MM = 0.02            # the board's underside is held to the seats within this: seats reach the plane just below, none the plane just above
SEAT_ABOVE_MAX_MM2 = 1.0        # the tray's material allowed just above the underside plane inside the footprint (sliver faces of the tessellation)
SEAT_MIN_AREA_MM2 = 20.0        # the seats under the board, at least, so that "nothing above" is not met by an empty tray
SHAPE_TOL_MM = 0.05             # a part and its copy in another file: bounds and centre of mass
SHAPE_REL_TOL = 0.005           # volume, area and inertia of a part and its copy, relative (the files are tessellated separately)
LOGO_IOU_MIN = 0.85
LOGO_IOU_MARGIN = 0.4
RASTER_MM = 0.1

BLADE_HOLE_D_MM = 1.4           # the pad holes of the three blades, in pairs along the blade's width
TRIAC_LEAD_HOLE_D_MM = 1.1      # the pad holes of a triac's three leads, in a row
HOLE_D_TOL_MM = 0.05


# ---------------------------------------------------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------------------------------------------------

@dataclass
class Result:
    name: str
    ok: bool
    measured: Any
    expected: Any
    tolerance: Any
    unit: str
    note: str = ""

    def as_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)


def _fmt(value: Any) -> str:
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(_fmt(v) for v in value) + "]"
    if isinstance(value, float):
        return f"{value:.3f}"
    return str(value)


def render_text(results: Sequence[Result]) -> str:
    lines = []
    for r in results:
        lines.append(f"{'PASS' if r.ok else 'FAIL'}  {r.name}: measured {_fmt(r.measured)} {r.unit}, expected {_fmt(r.expected)}, tolerance {_fmt(r.tolerance)}"
                     + (f"  ({r.note})" if r.note else ""))
    failed = sum(1 for r in results if not r.ok)
    lines.append(f"{len(results) - failed} of {len(results)} pass" + (f", {failed} FAIL" if failed else ""))
    return "\n".join(lines)


# ---------------------------------------------------------------------------------------------------------------------
# Sections of a mesh
# ---------------------------------------------------------------------------------------------------------------------

def section_material(mesh: trimesh.Trimesh, axis: int, value: float, snap: float = 2e-3) -> Any:
    """The material of a mesh in the plane `axis` = `value`, as a shapely geometry in the other two axes (in their order), voids as holes.

    The segments where the plane cuts the triangles are joined end to end where their ends lie within `snap`, polygonised, and the faces
    combined by even-odd (each ring flips what is inside it)."""
    origin, normal = [0.0] * 3, [0.0] * 3
    origin[axis], normal[axis] = value, 1.0
    segments = trimesh.intersections.mesh_plane(mesh, normal, origin)
    if len(segments) == 0:
        return Polygon()
    keep = [i for i in range(3) if i != axis]
    points = segments[:, :, keep].reshape(-1, 2)
    pairs = cKDTree(points).query_pairs(snap, output_type="ndarray")
    n = len(points)
    graph = coo_matrix((np.ones(len(pairs)), (pairs[:, 0], pairs[:, 1])), shape=(n, n))
    _, label = connected_components(graph, directed=False)
    centre = np.zeros((label.max() + 1, 2))
    np.add.at(centre, label, points)
    centre /= np.bincount(label)[:, None]
    ends = label.reshape(-1, 2)
    lines = [LineString([centre[a], centre[b]]) for a, b in ends if a != b]
    faces = list(polygonize(unary_union(lines)))
    if not faces:
        return Polygon()
    return reduce(lambda a, b: a.symmetric_difference(b), [Polygon(p.exterior) for p in faces])


def polygons_of(geometry: Any) -> List[Polygon]:
    if geometry.is_empty:
        return []
    return list(geometry.geoms) if hasattr(geometry, "geoms") else [geometry]


def voids_of(geometry: Any) -> List[Polygon]:
    """The enclosed voids (holes) of a section's material."""
    return [Polygon(ring) for poly in polygons_of(geometry) for ring in poly.interiors]


def equivalent_diameter(poly: Polygon) -> float:
    return 2.0 * math.sqrt(poly.area / math.pi)


def mirror_mesh(mesh: trimesh.Trimesh, axis: int, about: float) -> trimesh.Trimesh:
    """The mesh reflected in the plane `axis` = `about`, the winding reversed so the normals stay outward and the volume stays positive."""
    vertices = np.array(mesh.vertices, dtype=float)
    vertices[:, axis] = 2.0 * about - vertices[:, axis]
    return trimesh.Trimesh(vertices=vertices, faces=np.asarray(mesh.faces)[:, ::-1].copy(), process=False)


# ---------------------------------------------------------------------------------------------------------------------
# The board's model, placed
# ---------------------------------------------------------------------------------------------------------------------

class BoardModelError(SystemExit):
    pass


@dataclass
class Hole:
    x: float
    y: float
    d: float


@dataclass
class BoardModel:
    shift: np.ndarray                   # added to the STEP file's coordinates to place the board against the exported case
    thickness: float                    # the board's whole thickness, the pad solids' tops to the lowest solid
    bottom: float                       # the board's underside, the lowest solid, as a Z in the placed frame
    body: trimesh.Trimesh               # the board body, placed
    outline: Polygon                    # the body's outline at mid thickness, drilled holes as interiors
    holes: List[Hole]
    slots: List[Polygon]                # the open area of each slot, mouth included
    h1: Hole
    blades: List[Tuple[float, Tuple[float, float]]]   # (x, (y low, y high)) of each blade's pair of pad holes
    triac_rows: List[Tuple[Tuple[float, ...], float]]  # (x of each of the three leads, y of the row) of each triac, by x
    component_face: Dict[str, int]      # the pad solids that sit on each face with nothing through the board beside them
    placed_centre: Tuple[float, float]


_BOARD_CACHE: Dict[Tuple[str, float], BoardModel] = {}


def load_board_model(step: Optional[str] = None, check_fresh: bool = True) -> BoardModel:
    """The board's model from the cached STEP file, placed against the exported case by the translation its own corners give."""
    step = step or board_model.STEP
    if check_fresh and step == board_model.STEP:
        problem = board_model.stale()
        if problem:
            raise BoardModelError(problem)
    key = (step, os.path.getmtime(step))
    if key in _BOARD_CACHE:
        return _BOARD_CACHE[key]
    from build123d import import_step
    from solids import to_mesh
    solids = import_step(step).solids()
    bodies = sorted(solids, key=lambda s: -s.volume)
    body = bodies[0]
    bb = body.bounding_box()
    body_thickness = bb.max.Z - bb.min.Z
    through_xy, thin = [], []
    for s in bodies[1:]:
        b = s.bounding_box()
        centre = ((b.min.X + b.max.X) / 2, (b.min.Y + b.max.Y) / 2)
        if b.max.Z - b.min.Z > body_thickness:
            through_xy.append(centre)
        elif b.max.Z - b.min.Z < 0.1:
            thin.append((centre, b.max.Z > bb.max.Z + 1e-6, b.min.Z < bb.min.Z - 1e-6, b))
    tree = cKDTree(np.array(through_xy)) if through_xy else None
    faces = {"+Z": 0, "-Z": 0}
    pad_tops = []
    for centre, on_top, on_bottom, b in thin:
        if tree is not None and tree.query(centre)[0] < 0.3:
            continue                    # the ring of a drilled hole's barrel, on both faces: no face to tell
        faces["+Z" if on_top else "-Z"] += int(on_top or on_bottom)
        if on_top:
            pad_tops.append(b.max.Z)
    if faces["+Z"] <= faces["-Z"]:
        raise BoardModelError(f"the board model's component face (the face its surface-mount pads sit on) is not toward +Z ({faces}): "
                              "placing it would take a reflection, which is what this check finds")
    top = max(pad_tops)
    shift = np.array([-bb.min.X, -bb.max.Y, -top])
    bottom = min(s.bounding_box().min.Z for s in solids) + shift[2]
    mesh = to_mesh(body, 0.005, 0.1)
    mesh = trimesh.Trimesh(vertices=np.asarray(mesh.vertices) + shift, faces=mesh.faces, process=False)
    mid = section_material(mesh, 2, float(mesh.bounds[:, 2].mean()))
    outline = max(polygons_of(mid), key=lambda p: p.area)
    holes = [Hole(p.centroid.x, p.centroid.y, equivalent_diameter(p)) for p in (Polygon(r) for r in outline.interiors)]
    notches = Polygon(outline.exterior).convex_hull.difference(Polygon(outline.exterior))
    slots = [g for g in polygons_of(notches) if g.area > 1e-3]
    slots.sort(key=lambda g: g.centroid.y)
    h1 = max(holes, key=lambda h: h.d)
    pair_holes = [h for h in holes if abs(h.d - BLADE_HOLE_D_MM) <= HOLE_D_TOL_MM]
    blades = []
    for h in sorted(pair_holes, key=lambda h: (h.x, h.y)):
        if blades and abs(blades[-1][0] - h.x) < 0.01 and len(blades[-1][1]) == 1:
            blades[-1] = (blades[-1][0], blades[-1][1] + (h.y,))
        else:
            blades.append((h.x, (h.y,)))
    blades = [(x, (min(ys), max(ys))) for x, ys in blades if len(ys) == 2]
    lead_holes = sorted((h for h in holes if abs(h.d - TRIAC_LEAD_HOLE_D_MM) <= HOLE_D_TOL_MM), key=lambda h: (round(h.y, 2), h.x))
    rows: List[List[Hole]] = []
    for h in lead_holes:
        if rows and abs(rows[-1][0].y - h.y) < 0.05 and h.x - rows[-1][-1].x < 3.0:      # one row: the same Y, the leads 2.54 apart
            rows[-1].append(h)
        else:
            rows.append([h])
    triac_rows = sorted(((tuple(h.x for h in r), r[0].y) for r in rows if len(r) == 3), key=lambda t: t[0][0])
    model = BoardModel(shift, -bottom, bottom, mesh, outline, holes, slots, h1, blades, triac_rows, faces,
                       (float(outline.bounds[0] + outline.bounds[2]) / 2, float(outline.bounds[1] + outline.bounds[3]) / 2))
    _BOARD_CACHE[key] = model
    return model


# ---------------------------------------------------------------------------------------------------------------------
# The exports
# ---------------------------------------------------------------------------------------------------------------------

def load_meshes(out: str) -> Dict[str, trimesh.Trimesh]:
    """The STL of every part, as a viewer reads it."""
    missing = [n for n in PARTS if not os.path.exists(os.path.join(out, f"{n}.stl"))]
    if missing:
        raise SystemExit(f"{out}: {', '.join(m + '.stl' for m in missing)} missing: run `task hw:case` first")
    return {n: trimesh.load(os.path.join(out, f"{n}.stl")) for n in PARTS}


def mirrored(meshes: Dict[str, trimesh.Trimesh], axis: int, about: float) -> Dict[str, trimesh.Trimesh]:
    return {n: mirror_mesh(m, axis, about) for n, m in meshes.items()}


def _params() -> Any:
    import case
    return case.Params.load()


# ---------------------------------------------------------------------------------------------------------------------
# Mounting hole pilot, blade bays
# ---------------------------------------------------------------------------------------------------------------------

def check_pilot(meshes: Dict[str, trimesh.Trimesh], board: BoardModel, P: Any) -> List[Result]:
    """The tray's pilot hole for the board's mounting screw lies on the axis of the board's mounting hole."""
    pilot_d = P("case.pilot_dia_mm")
    bottom = P("screws.h1_pilot_bottom_z_mm")
    z = (bottom + board.bottom) / 2
    section = section_material(meshes["tray"], 2, z)
    candidates = [v for v in voids_of(section) if abs(equivalent_diameter(v) - pilot_d) <= 0.15
                  and math.hypot(v.centroid.x - board.h1.x, v.centroid.y - board.h1.y) <= 3.0]
    if not candidates:
        return [Result("pilot_on_h1_axis", False, "no pilot hole within 3 mm of the axis", [board.h1.x, board.h1.y], POSITION_TOL_MM, "mm",
                       f"tray section at Z {z:.2f}, a void of diameter {pilot_d} +-0.15")]
    best = min(candidates, key=lambda v: math.hypot(v.centroid.x - board.h1.x, v.centroid.y - board.h1.y))
    err = math.hypot(best.centroid.x - board.h1.x, best.centroid.y - board.h1.y)
    return [Result("pilot_on_h1_axis", err <= POSITION_TOL_MM, round(err, 4), 0.0, POSITION_TOL_MM, "mm",
                   f"pilot of diameter {equivalent_diameter(best):.2f} at ({best.centroid.x:.3f}, {best.centroid.y:.3f}), the board's hole H1 at ({board.h1.x:.3f}, {board.h1.y:.3f}); tray section at Z {z:.2f}")]


def _rectangular(poly: Polygon, least_side: float = 5.0) -> bool:
    rect = poly.minimum_rotated_rectangle
    xs, ys = rect.exterior.coords.xy
    sides = sorted([math.hypot(xs[1] - xs[0], ys[1] - ys[0]), math.hypot(xs[2] - xs[1], ys[2] - ys[1])])
    return poly.area / rect.area >= 0.95 and sides[0] >= least_side


def check_bays(meshes: Dict[str, trimesh.Trimesh], board: BoardModel, P: Any, lid: str) -> List[Result]:
    """Each blade's pad holes lie inside a bay opening of the lid, the bay centred across X on the blade or blades it serves, and no bay is without a blade."""
    mesh = meshes[lid]
    z = float(mesh.bounds[1][2]) - (P("logo.groove_depth_mm") + 0.6)
    section = section_material(mesh, 2, z)
    bays = [v for v in voids_of(section) if _rectangular(v)]
    if not board.blades:
        return [Result(f"bays_{lid}", False, "no blade pad holes in the board model", 3, 0, "pairs")]
    served: Dict[int, List[Tuple[float, Tuple[float, float]]]] = {i: [] for i in range(len(bays))}
    outside = []
    least_edge = math.inf
    for blade in board.blades:
        x, (y0, y1) = blade
        homes = [i for i, b in enumerate(bays) if all(b.contains(Point(x, y)) for y in (y0, y1))]
        if not homes:
            outside.append(blade)
            continue
        served[homes[0]].append(blade)
        least_edge = min(least_edge, *(bays[homes[0]].exterior.distance(Point(x, y)) for y in (y0, y1)))
    centre_err = 0.0
    for i, blades in served.items():
        if blades:
            span = (min(b[0] for b in blades) + max(b[0] for b in blades)) / 2
            centre_err = max(centre_err, abs(bays[i].centroid.x - span))
    empty = [i for i, b in served.items() if not b]
    return [
        Result(f"bays_hold_blade_pad_holes_{lid}", not outside, len(board.blades) - len(outside), len(board.blades), 0, "blades inside a bay",
               f"{len(bays)} bays found in the section at Z {z:.2f}; the pad holes of every blade lie inside one" + (f"; outside: {outside}" if outside else "")
               + (f"; nearest hole to a bay edge {least_edge:.2f} mm" if least_edge < math.inf else "")),
        Result(f"bays_centred_on_blades_across_x_{lid}", (not outside) and centre_err <= POSITION_TOL_MM, round(centre_err, 4), 0.0, POSITION_TOL_MM, "mm",
               "the bay's centre in X against the middle of the blades it holds"),
        Result(f"no_bay_without_blade_{lid}", not empty and len(bays) > 0, len(empty), 0, 0, "bays without a blade",
               f"{len(bays)} bays, each holding at least one blade"),
    ]


# ---------------------------------------------------------------------------------------------------------------------
# The triacs: the plate
# ---------------------------------------------------------------------------------------------------------------------

def check_triacs(meshes: Dict[str, trimesh.Trimesh], board: BoardModel, P: Any) -> List[Result]:
    """The plate's tapped-through holes on the triacs' middle leads; the plate beyond the board's plate-side edge at the seating figures' distance."""
    out: List[Result] = []
    plate = meshes["plate"]
    if len(board.triac_rows) != 2:
        return [Result("triac_lead_rows_in_board_model", False, len(board.triac_rows), 2, 0, "rows of three lead holes")]
    row_y = board.triac_rows[0][1]
    middles = [row[0][1] for row in board.triac_rows]
    tfc = P("seating.tab_face_to_lead_centre_mm")
    tab_z = P("seating.body_underside_mm") + P("triac.A_mm") - P("triac.L_mm")
    # the plate's inner face
    plate_face = float(plate.bounds[0][1])
    edge_y = float(board.outline.bounds[3])
    out.append(Result("plate_inner_face_at_tab_face_distance", abs(plate_face - (row_y + tfc)) <= FACE_TOL_MM, round(plate_face, 4), round(row_y + tfc, 4), FACE_TOL_MM, "mm Y",
                      f"the lead row at Y {row_y:.3f} plus the tab face to lead centre distance {tfc}"))
    beyond = plate_face >= edge_y - FACE_TOL_MM and plate_face > row_y
    out.append(Result("plate_beyond_the_plate_side_edge", beyond, round(plate_face, 3), f">= {edge_y:.3f}", FACE_TOL_MM, "mm Y",
                      "the plate's inner face lies beyond the board's plate-side edge, on the lead-hole side of the row"))
    # tapped holes, through the whole plate: voids of the plate section half way through it
    depth = P("plate.thickness_mm")
    drill = P("triac.plate_tap_drill_mm")
    section = section_material(plate, 1, plate_face + depth / 2)
    found, worst = [], 0.0
    for mid in middles:
        near = [v for v in voids_of(section) if abs(equivalent_diameter(v) - drill) <= 0.3 and math.hypot(v.centroid.x - mid, v.centroid.y - tab_z) <= 4.0]
        if not near:
            found.append(None)
            continue
        v = min(near, key=lambda v: math.hypot(v.centroid.x - mid, v.centroid.y - tab_z))
        found.append((round(v.centroid.x, 3), round(v.centroid.y, 3)))
        worst = max(worst, abs(v.centroid.x - mid))
    all_found = all(f is not None for f in found)
    out.append(Result("tapped_holes_on_triac_middle_leads", all_found and worst <= POSITION_TOL_MM, round(worst, 4) if all_found else "no tapped hole near a middle lead", 0.0,
                      POSITION_TOL_MM, "mm in X", f"holes of diameter {drill} in the plate section {depth / 2:.1f} mm behind its inner face at (X, Z) {found}; middle leads at X {[round(m, 3) for m in middles]}"))
    z_err = max((abs(f[1] - tab_z) for f in found if f is not None), default=math.inf)
    out.append(Result("tapped_holes_at_tab_hole_height", all_found and z_err <= POSITION_TOL_MM, round(z_err, 4) if all_found else "no tapped hole", 0.0, POSITION_TOL_MM, "mm in Z",
                      f"the tab hole height {tab_z:.3f} above the component face: the seating body underside plus the body height less the tab-top to hole distance"))
    return out


def polygons_of_lines(geometry: Any) -> List[Any]:
    if geometry.is_empty:
        return []
    return list(geometry.geoms) if hasattr(geometry, "geoms") else [geometry]


# ---------------------------------------------------------------------------------------------------------------------
# Slot mouths, clearance, seats
# ---------------------------------------------------------------------------------------------------------------------

def _distance_to_slots(mesh: trimesh.Trimesh, board: BoardModel) -> float:
    """The least distance from a mesh's surface to the open area of either slot (the notch polygon extruded through the board's thickness), from sampled surface points."""
    least = math.inf
    for slot in board.slots:
        x0, y0, x1, y1 = slot.bounds
        window = 6.0
        centres = mesh.triangles_center
        near = (centres[:, 0] > x0 - window) & (centres[:, 0] < x1 + window) & (centres[:, 1] > y0 - window) & (centres[:, 1] < y1 + window)
        if not near.any():
            continue
        sub = trimesh.Trimesh(vertices=mesh.vertices, faces=mesh.faces[near], process=False)
        count = int(min(max(sub.area * 400, 2000), 600000))
        points, _ = trimesh.sample.sample_surface(sub, count, seed=7)
        d_xy = shapely.distance(slot, shapely.points(points[:, :2]))
        dz = np.maximum(0.0, np.maximum(points[:, 2] - 0.0, board.bottom - points[:, 2]))
        least = min(least, float(np.sqrt(d_xy ** 2 + dz ** 2).min()))
    return least


def check_slots(meshes: Dict[str, trimesh.Trimesh], board: BoardModel, P: Any) -> List[Result]:
    keep = P("seat.slot_keepout_mm")
    out: List[Result] = []
    if len(board.slots) != 2:
        return [Result("slots_in_board_model", False, len(board.slots), 2, 0, "slots")]
    gaps = {name: _distance_to_slots(meshes[name], board) for name in ("tray", "lid_single", "lid_two")}
    least = min(gaps.values())
    out.append(Result("slot_mouths_clear_air", least >= keep - CLEARANCE_TOL_MM, round(least, 3), f">= {keep}", CLEARANCE_TOL_MM, "mm",
                      "the least distance from the tray or either lid to the open area of either slot, mouth included: " + ", ".join(f"{n} {g:.2f}" for n, g in gaps.items())))
    wall_air = []
    section = section_material(meshes["tray"], 2, 1.0)
    mouth_x = float(max(s.bounds[2] for s in board.slots))
    for slot in board.slots:
        y = slot.centroid.y
        hit = section.intersection(LineString([(mouth_x, y), (mouth_x + 20.0, y)]))
        pieces = polygons_of_lines(hit)
        wall_air.append(min(g.bounds[0] for g in pieces) - mouth_x if pieces else math.inf)
    expected = P("case.interior_right_mm")
    err = max(abs(a - expected) for a in wall_air)
    out.append(Result("tray_right_wall_at_slot_mouths", err <= POSITION_TOL_MM, [round(a, 3) for a in wall_air], expected, POSITION_TOL_MM, "mm of clear air",
                      f"along each slot's centre line from the mouth at X {mouth_x:.2f} to the tray's inner wall, tray section at Z 1.0; the tray's right wall is positioned from the slot mouths"))
    return out


def _board_body_volume_in(mesh: trimesh.Trimesh, board: BoardModel) -> float:
    inter = trimesh.boolean.intersection([board.body, mesh], engine="manifold")
    return float(abs(inter.volume)) if len(inter.faces) else 0.0


def check_clearance(meshes: Dict[str, trimesh.Trimesh], board: BoardModel) -> List[Result]:
    out = []
    t = board.thickness
    shared = {name: _board_body_volume_in(meshes[name], board) for name in ("tray", "lid_single", "lid_two", "plate")}
    for name, volume in shared.items():
        out.append(Result(f"board_body_clear_of_{name}", volume <= VOLUME_BOUND_MM3, round(volume, 4), 0.0, VOLUME_BOUND_MM3, "mm3 shared",
                          f"the volume the board body shares with the {name} (boolean intersection of the two meshes)"))
    inner = board.outline.buffer(-0.3)
    below = section_material(meshes["tray"], 2, board.bottom - SEAT_PLANE_MM).intersection(inner).area
    above = section_material(meshes["tray"], 2, board.bottom + SEAT_PLANE_MM).intersection(inner).area
    out.append(Result("board_lies_on_its_seats", below >= SEAT_MIN_AREA_MM2 and above <= SEAT_ABOVE_MAX_MM2, round(above, 3), f"<= {SEAT_ABOVE_MAX_MM2} above, seats below", SEAT_PLANE_MM, "mm2 of tray above the underside",
                      f"tray material under the board's footprint (edges 0.3 mm in): {below:.1f} mm2 just below the underside plane (Z {board.bottom - SEAT_PLANE_MM:.2f}), {above:.3f} mm2 just above it (Z {board.bottom + SEAT_PLANE_MM:.2f}); the board's underside, its lowest solid, at Z {board.bottom:.3f} (thickness {t:.3f})"))
    return out


# ---------------------------------------------------------------------------------------------------------------------
# The logo
# ---------------------------------------------------------------------------------------------------------------------

def _raster(geometry: Any, bounds: Tuple[float, float, float, float]) -> np.ndarray:
    from PIL import Image, ImageDraw
    x0, y0, x1, y1 = bounds
    w, h = int(math.ceil((x1 - x0) / RASTER_MM)), int(math.ceil((y1 - y0) / RASTER_MM))
    image = Image.new("1", (w, h), 0)
    draw = ImageDraw.Draw(image)
    for g in polygons_of(geometry):
        if g.geom_type != "Polygon":
            continue
        draw.polygon([((x - x0) / RASTER_MM, (y1 - y) / RASTER_MM) for x, y in g.exterior.coords], fill=1)
        for ring in g.interiors:
            draw.polygon([((x - x0) / RASTER_MM, (y1 - y) / RASTER_MM) for x, y in ring.coords], fill=0)
    return np.array(image, dtype=float)


ORIENTATIONS = {"as_read": (1, 1), "mirrored_x": (-1, 1), "mirrored_y": (1, -1), "half_turn": (-1, -1)}


def read_logo(mesh: trimesh.Trimesh, face: str, artwork: Any, groove_depth: float) -> Dict[str, float]:
    """The overlap (intersection over union, best over every offset) of the grooves cut from a mesh's logo face, seen by the installed viewer, with the artwork as it reads and its three turns and mirrors."""
    if face == "lid":
        z = float(mesh.bounds[1][2]) - groove_depth / 2
        sx, sy = -1.0, -1.0
    else:
        z = float(mesh.bounds[0][2]) + groove_depth / 2
        sx, sy = -1.0, 1.0
    material = section_material(mesh, 2, z)
    grooves = Polygon(material.convex_hull.exterior).difference(material) if not material.is_empty else Polygon()
    view = affinity.scale(grooves, sx, sy, origin=(0, 0))
    field_image = _raster(view, view.bounds)
    scores = {}
    for name, (ax, ay) in ORIENTATIONS.items():
        shape = affinity.scale(artwork, ax, ay, origin=(0, 0))
        b = shape.bounds
        template = _raster(affinity.translate(shape, -b[0], -b[1]), (0, 0, b[2] - b[0], b[3] - b[1]))
        if template.shape[0] > field_image.shape[0] or template.shape[1] > field_image.shape[1]:
            scores[name] = 0.0
            continue
        inter = fftconvolve(field_image, template[::-1, ::-1], mode="valid")
        window = fftconvolve(field_image, np.ones_like(template), mode="valid")
        scores[name] = float((inter / (template.sum() + window - inter)).max())
    return scores


def artworks(P: Any) -> Dict[str, Any]:
    """The engraving of the artwork at each face's height, x right and y up as the artwork reads."""
    return {"lid": logo_module.engrave(P, P.S("mark.lid_height_mm")).geometry, "tray": logo_module.engrave(P, P("logo.tray_height_mm")).geometry}


def check_logo(meshes: Dict[str, trimesh.Trimesh], P: Any, artwork: Optional[Dict[str, Any]] = None) -> List[Result]:
    art = artwork or artworks(P)
    depth = P("logo.groove_depth_mm")
    out = []
    for name, mesh, face in (("lid_single", meshes["lid_single"], "lid"), ("lid_two", meshes["lid_two"], "lid"), ("tray_top", meshes["tray"], "tray")):
        scores = read_logo(mesh, face, art[face], depth)
        others = max(v for k, v in scores.items() if k != "as_read")
        ok = scores["as_read"] >= LOGO_IOU_MIN and scores["as_read"] - others >= LOGO_IOU_MARGIN
        where = "from below with the wall at the bottom of the view (view right -X, view up -Y)" if face == "lid" else "from above with the wall at the top of the view (view right -X, view up +Y)"
        out.append(Result(f"logo_reads_right_way_round_{name}", ok, round(scores["as_read"], 3), f">= {LOGO_IOU_MIN} and {LOGO_IOU_MARGIN} above every other", f"{LOGO_IOU_MIN}, margin {LOGO_IOU_MARGIN}", "intersection over union",
                          f"grooves cut at mid depth {depth / 2:.2f}, seen {where}; the others: " + ", ".join(f"{k} {v:.3f}" for k, v in scores.items() if k != "as_read")))
    return out


# ---------------------------------------------------------------------------------------------------------------------
# Handedness and the other files
# ---------------------------------------------------------------------------------------------------------------------

def _signature(mesh: trimesh.Trimesh) -> Dict[str, Any]:
    return {"volume": float(mesh.volume), "area": float(mesh.area), "centre": np.asarray(mesh.center_mass, dtype=float), "inertia": np.asarray(mesh.moment_inertia, dtype=float),
            "bounds": np.asarray(mesh.bounds, dtype=float)}


def _same(a: Dict[str, Any], b: Dict[str, Any]) -> Tuple[bool, str]:
    dv = abs(a["volume"] - b["volume"]) / max(abs(a["volume"]), 1e-9)
    da = abs(a["area"] - b["area"]) / max(a["area"], 1e-9)
    dc = float(np.abs(a["centre"] - b["centre"]).max())
    db = float(np.abs(a["bounds"] - b["bounds"]).max())
    di = float(np.linalg.norm(a["inertia"] - b["inertia"]) / np.linalg.norm(a["inertia"]))
    ok = dv <= SHAPE_REL_TOL and da <= SHAPE_REL_TOL and dc <= SHAPE_TOL_MM and db <= SHAPE_TOL_MM and di <= SHAPE_REL_TOL
    return ok, f"volume {dv * 100:.3f} %, area {da * 100:.3f} %, centre of mass {dc:.3f} mm, bounds {db:.3f} mm, inertia {di * 100:.3f} %"


def _turned(mesh: trimesh.Trimesh, rotation: np.ndarray) -> trimesh.Trimesh:
    """A mesh turned by a proper rotation and lowered to the bed (least Z at 0, least X and Y at 0), winding unchanged."""
    vertices = np.asarray(mesh.vertices) @ rotation.T
    vertices = vertices - vertices.min(axis=0)
    return trimesh.Trimesh(vertices=vertices, faces=mesh.faces, process=False)


def read_3mf(path: str) -> Dict[str, trimesh.Trimesh]:
    """The objects of a 3MF file by name, vertices as written (the build items must carry no transform)."""
    ns = {"m": "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"}
    with zipfile.ZipFile(path) as archive:
        root = ET.fromstring(archive.read("3D/3dmodel.model"))
    objects = {}
    for obj in root.iterfind(".//m:object", ns):
        mesh = obj.find("m:mesh", ns)
        vertices = np.array([[float(v.get(k)) for k in "xyz"] for v in mesh.iterfind("m:vertices/m:vertex", ns)])
        triangles = np.array([[int(t.get(k)) for k in ("v1", "v2", "v3")] for t in mesh.iterfind("m:triangles/m:triangle", ns)])
        objects[obj.get("name")] = (obj.get("id"), trimesh.Trimesh(vertices=vertices, faces=triangles, process=True))
    moved = [i for i in root.iterfind(".//m:build/m:item", ns) if i.get("transform") not in (None, "1 0 0 0 1 0 0 0 1 0 0 0")]
    if moved:
        raise SystemExit(f"{path}: a build item carries a transform; the objects are read as written")
    return {name: m for name, (_, m) in objects.items()}


def check_files(out: str, meshes: Dict[str, trimesh.Trimesh]) -> List[Result]:
    import case
    results: List[Result] = []
    bad = [n for n, m in meshes.items() if not (m.is_watertight and m.is_winding_consistent and m.volume > 0)]
    results.append(Result("exports_watertight_with_outward_winding", not bad, len(bad), 0, 0, "parts failing",
                          "every STL is watertight, consistently wound and of positive signed volume (outward normals)" + (f"; failing: {bad}" if bad else "")))
    for name in PRINTED:
        path = os.path.join(out, f"{name}.print.stl")
        if not os.path.exists(path):
            results.append(Result(f"print_stl_is_the_stl_turned_{name}", False, "missing", "present", 0, "", f"{path} missing: run `task hw:case`"))
            continue
        printed = trimesh.load(path)
        rotation = case.print_rotation(name)
        proper = abs(np.linalg.det(rotation) - 1.0) < 1e-9
        ok, note = _same(_signature(printed), _signature(_turned(meshes[name], rotation)))
        positive = printed.is_watertight and printed.volume > 0
        results.append(Result(f"print_stl_is_the_stl_turned_{name}", ok and proper and positive, note, "equal", f"{SHAPE_REL_TOL * 100:.1f} % and {SHAPE_TOL_MM} mm", "",
                              f"the print STL against the exported STL turned by print_rotation (determinant {np.linalg.det(rotation):+.0f}, a proper rotation) and lowered to the bed; watertight with positive volume: {positive}"))
    for form, names in FORMS.items():
        path = os.path.join(out, f"case-{form}.3mf")
        if not os.path.exists(path):
            results.append(Result(f"3mf_{form}_objects_are_the_stls", False, "missing", "present", 0, "", f"{path} missing: run `task hw:case`"))
            continue
        objects = read_3mf(path)
        notes, ok = [], set(objects) == set(names)
        if not ok:
            notes.append(f"objects {sorted(objects)} against {sorted(names)}")
        for name in names:
            if name not in objects:
                continue
            obj = objects[name]
            if not (obj.is_watertight and obj.volume > 0):
                ok = False
                notes.append(f"{name}: not watertight with positive volume")
            if form == "two" and name in SWAP_OF:
                swap = meshes[SWAP_OF[name]]
                whole = meshes[name]
                vol = obj.volume + swap.volume
                dv = abs(vol - whole.volume) / whole.volume
                centre = (obj.volume * obj.center_mass + swap.volume * swap.center_mass) / vol
                dc = float(np.abs(centre - whole.center_mass).max())
                within = bool((obj.bounds[0] >= whole.bounds[0] - SHAPE_TOL_MM).all() and (obj.bounds[1] <= whole.bounds[1] + SHAPE_TOL_MM).all())
                good = dv <= SHAPE_REL_TOL and dc <= SHAPE_TOL_MM and within
                notes.append(f"{name} less its swap band: volume {dv * 100:.3f} % and centre of mass {dc:.3f} mm from the STL")
            else:
                good, note = _same(_signature(obj), _signature(meshes[name]))
                notes.append(f"{name}: {note}")
            ok &= good
        results.append(Result(f"3mf_{form}_objects_are_the_stls", ok, "; ".join(notes), "equal", f"{SHAPE_REL_TOL * 100:.1f} % and {SHAPE_TOL_MM} mm", "",
                              "every object of the 3MF is the part's STL (the base part with its swap band removed in the two-colour form), right-handed with outward winding"))
    contained = []
    for base, swap in (("tray", "tray_swap"), ("lid_two", "lid_swap"), ("lid_single", "lid_swap")):
        s, b = meshes[swap], meshes[base]
        z = float(s.bounds[:, 2].mean())
        outside = section_material(s, 2, z).difference(section_material(b, 2, z)).area
        inside_bounds = bool((s.bounds[0] >= b.bounds[0] - SHAPE_TOL_MM).all() and (s.bounds[1] <= b.bounds[1] + SHAPE_TOL_MM).all())
        contained.append((base, swap, round(outside, 4), inside_bounds))
    results.append(Result("swap_bands_inside_their_base_parts", all(o <= 0.05 and i for _, _, o, i in contained), [c[2] for c in contained], 0.0, 0.05, "mm2 of band outside its base",
                          "the swap band's section at mid band, less the base part's section; " + ", ".join(f"{b}/{s}" for b, s, _, _ in contained)))
    return results


# ---------------------------------------------------------------------------------------------------------------------
# Whole checks, controls
# ---------------------------------------------------------------------------------------------------------------------

def fit_results(meshes: Dict[str, trimesh.Trimesh], board: BoardModel, P: Optional[Any] = None, artwork: Optional[Dict[str, Any]] = None) -> List[Result]:
    """Every result that locates a case feature against the board, from case-frame meshes: the part the controls re-run."""
    P = P or _params()
    results: List[Result] = []
    results += check_pilot(meshes, board, P)
    for lid in ("lid_single", "lid_two"):
        results += check_bays(meshes, board, P, lid)
    results += check_triacs(meshes, board, P)
    results += check_slots(meshes, board, P)
    results += check_clearance(meshes, board)
    results += check_logo(meshes, P, artwork)
    return results


def all_results(out: Optional[str] = None) -> List[Result]:
    out = out or os.path.join(HERE, "out")
    meshes = load_meshes(out)
    board = load_board_model()
    return fit_results(meshes, board) + check_files(out, meshes)


def mirror_artwork(artwork: Dict[str, Any]) -> Dict[str, Any]:
    return {k: affinity.scale(v, -1, 1, origin=(0, 0)) for k, v in artwork.items()}


def controls(out: Optional[str] = None) -> Dict[str, List[Result]]:
    """The results of the negative controls, in memory: the exports mirrored in X and in Y about the board's centre line, and the unmirrored
    exports checked against the mirrored artwork."""
    out = out or os.path.join(HERE, "out")
    meshes = load_meshes(out)
    board = load_board_model()
    P = _params()
    cx, cy = board.placed_centre
    return {"mirror_x": fit_results(mirrored(meshes, 0, cx), board, P),
            "mirror_y": fit_results(mirrored(meshes, 1, cy), board, P),
            "mirrored_artwork": check_logo(meshes, P, mirror_artwork(artworks(P)))}


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Check the exported case against the board's own three-dimensional model.")
    parser.add_argument("--out", default=os.path.join(HERE, "out"), help="the folder case.py exported into")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--controls", action="store_true", help="also run the negative controls (the exports mirrored in X and in Y, the mirrored artwork) and list what fails")
    args = parser.parse_args(argv)
    results = all_results(args.out)
    report: Dict[str, Any] = {"results": [r.as_dict() for r in results], "pass": all(r.ok for r in results)}
    text = [render_text(results)]
    if args.controls:
        report["controls"] = {}
        for name, rs in controls(args.out).items():
            failed = [r.name for r in rs if not r.ok]
            report["controls"][name] = failed
            text.append(f"control {name}: fails {len(failed)}: {', '.join(failed) if failed else 'nothing (the control is not caught)'}")
    print(json.dumps(report, indent=1, default=lambda o: o.tolist() if hasattr(o, "tolist") else str(o)) if args.format == "json" else "\n".join(text))
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
