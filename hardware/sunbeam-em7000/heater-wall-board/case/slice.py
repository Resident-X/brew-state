#!/usr/bin/env python3
"""Slice each printed part with PrusaSlicer in its print orientation, supports off and then supports auto.

    python slice.py                       every printed part
    python slice.py --part tray           one part
    PRUSASLICER=/path/to/PrusaSlicer python slice.py

The parts are read from out/<part>.print.stl, which case.py writes already turned to the print
orientation and lowered to the bed. The summary of both runs goes to slice/<part>.json and the
slicer's own output to slice/<part>.log. G-code stays in slice/ and is not committed.

Each supports-auto run (the diagnostic: the stated print is supports off) is attributed to the model's faces: the support is grouped into regions,
each the support under one feature, with the face angle or roof span it holds up, and `supported_faces_that_are_critical` lists any supported face that
IS one of the critical faces (decided face by face with check.critical_face_selector; expected empty) while `flush_to_critical_plane` lists support that
merely stands against a critical face's plane. The slicer's own automatic detection (threshold 0) is run as a third mode and recorded the same way.

Each summary names the slicer's own version, the sha256 of every file the sliced geometry comes from
(`inputs`; `stale()` reads them back, and the tests fail on a summary whose inputs have changed), and where the
supports-auto run put support: clusters of support extrusion with their bounding box, z range and filament
length, in print coordinates (the G-code's own) and in the model frame the criteria's regions are stated in.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import hashlib
import subprocess
import sys
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import case  # noqa: E402,I001  (build123d before vtk)
import check  # noqa: E402
import shapely  # noqa: E402
import trimesh  # noqa: E402
from scipy.sparse import coo_matrix  # noqa: E402
from scipy.sparse.csgraph import connected_components  # noqa: E402
from scipy.spatial import cKDTree  # noqa: E402
from shapely.geometry import LineString, Point, Polygon as ShPolygon  # noqa: E402
from shapely.ops import unary_union  # noqa: E402
PARTS = ("tray", "lid_single", "lid_two")
ORIENTATION = {"tray": "outer top face down on the bed (floor down, as modelled)", "lid_single": "face down", "lid_two": "face down"}
FILAMENT_DIAMETER = 1.75
CENTER = (110.0, 110.0)          # where the slicer puts the middle of the part's footprint on the bed
COLUMN_MM = 0.5                  # support is attributed per column of this plan size
PAD_REACH_MM = 4.0               # support with no face above it is the slicer's margin round a feature when a supported face is this near
FLUSH_MM = 0.1                   # support this near a critical face's plane stands against it
FIRST_LAYER_MM = 0.2             # support that high or lower with no face above it is a first-layer patch
FLAT_DEG = 1.0                   # a downward face within this of the horizontal is a flat roof
CLUSTER_CELL_MM = 3.0            # support extrusions less than a cell apart, in a layer or the next, are one cluster
SOURCES = ("params.yaml", "case.py", "check.py", "core.py", "skins.py", "solids.py", "streamlines.py", "logo.py", "staircase-logo.svg",
           "printer-220-asa.ini", "support-auto.ini")


def sources() -> List[str]:
    """The files the sliced geometry and the slicer's settings come from, as paths from the case folder: the case's own sources and
    settings, the board files case.py reads, and the two modules it reads the board with."""
    outside = [case.BOARD_PCB, case.BOARD_PRO, case.BASIS, case.bg.__file__, case.sexpr.__file__]
    return list(SOURCES) + [os.path.relpath(p, HERE) for p in outside]


def sha256(path: str) -> str:
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def pins(part: str, out_dir: str) -> Dict[str, str]:
    """The sha256 of every input of a part's slice: the sources, and the print-orientation STL itself."""
    found = {name: sha256(os.path.join(HERE, name)) for name in sources()}
    stl = os.path.join(out_dir, f"{part}.print.stl")
    found[os.path.relpath(stl, HERE)] = sha256(stl)
    return found


def stale(summary: Dict[str, Any]) -> List[str]:
    """The source files a summary pins that no longer match the file on disk, by name, and any it does not pin; empty when the summary is current.
    The print-orientation STL is pinned too, as the part that was sliced, but it is a generated file and is not compared."""
    recorded = summary.get("inputs", {})
    now = {name: sha256(os.path.join(HERE, name)) for name in sources()}
    return sorted(k for k in set(now) | {k for k in recorded if not k.endswith(".print.stl")} if recorded.get(k) != now.get(k))


def slicer_version() -> str:
    """The version line the slicer prints for itself."""
    done = subprocess.run([slicer_command(), "--help"], capture_output=True, text=True, timeout=120)
    lines = (done.stdout or done.stderr).splitlines()
    if done.returncode != 0 or not lines or not lines[0].startswith("PrusaSlicer"):
        raise SystemExit(f"{slicer_command()} --help did not give a PrusaSlicer version line (exit status {done.returncode})")
    return lines[0].strip()


def slicer_command() -> str:
    return os.environ.get("PRUSASLICER") or "/Applications/PrusaSlicer.app/Contents/MacOS/PrusaSlicer"


def parse_time(text: str) -> float:
    total = 0.0
    for value, unit in re.findall(r"(\d+)([dhms])", text):
        total += int(value) * {"d": 86400, "h": 3600, "m": 60, "s": 1}[unit]
    return total


def support_clusters(segments: List[Tuple[float, float, float, float, float, float]]) -> List[Dict[str, Any]]:
    """Support extrusion (z, x0, y0, x1, y1, filament mm) grouped into clusters that touch: segments within a cell of one another, in a layer or its neighbour."""
    if not segments:
        return []
    levels = {z: i for i, z in enumerate(sorted({round(s[0], 3) for s in segments}))}
    parent: Dict[Tuple[int, int, int], Tuple[int, int, int]] = {}

    def find(cell):
        while parent[cell] != cell:
            parent[cell] = parent[parent[cell]]
            cell = parent[cell]
        return cell

    def cells_of(seg):
        z, x0, y0, x1, y1, _ = seg
        steps = max(1, int(math.hypot(x1 - x0, y1 - y0) / (CLUSTER_CELL_MM / 2)))
        return {(math.floor((x0 + (x1 - x0) * k / steps) / CLUSTER_CELL_MM), math.floor((y0 + (y1 - y0) * k / steps) / CLUSTER_CELL_MM), levels[round(z, 3)])
                for k in range(steps + 1)}

    segment_cells = []
    for seg in segments:
        cells = cells_of(seg)
        segment_cells.append(cells)
        for c in cells:
            parent.setdefault(c, c)
    for c in list(parent):
        for dz in (0, 1):
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    n = (c[0] + dx, c[1] + dy, c[2] + dz)
                    if n != c and n in parent:
                        parent[find(n)] = find(c)
    for cells in segment_cells:
        first = next(iter(cells))
        for c in cells:
            parent[find(c)] = find(first)
    groups: Dict[Tuple[int, int, int], List[int]] = {}
    for i, cells in enumerate(segment_cells):
        groups.setdefault(find(next(iter(cells))), []).append(i)
    clusters = []
    for members in groups.values():
        pts = np.array([[segments[i][1], segments[i][2]] for i in members] + [[segments[i][3], segments[i][4]] for i in members])
        zs = [segments[i][0] for i in members]
        clusters.append({"x_mm": [round(float(pts[:, 0].min()), 2), round(float(pts[:, 0].max()), 2)],
                         "y_mm": [round(float(pts[:, 1].min()), 2), round(float(pts[:, 1].max()), 2)],
                         "z_mm": [round(min(zs), 2), round(max(zs), 2)],
                         "filament_mm": round(sum(segments[i][5] for i in members), 1), "segments": len(members)})
    clusters.sort(key=lambda c: -c["filament_mm"])
    return clusters


def parse_gcode(path: str, segments_out: Optional[list] = None) -> Dict[str, Any]:
    """Print time, filament, layers, extent and support material, with where the support lies, read from a PrusaSlicer G-code file."""
    info: Dict[str, Any] = {}
    support_segments: List[Tuple[float, float, float, float, float, float]] = []
    outer: List[Tuple[float, float]] = []
    layers = 0
    kind = ""
    support_mm = 0.0
    total_mm = 0.0
    lo = [math.inf, math.inf, math.inf]
    hi = [-math.inf, -math.inf, -math.inf]
    x = y = z = 0.0
    with open(path, encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if line.startswith(";TYPE:"):
                kind = line[6:].strip()
            elif line.startswith(";LAYER_CHANGE"):
                layers += 1
            elif line.startswith("; estimated printing time (normal mode)"):
                info["print_time_text"] = line.split("=", 1)[1].strip()
                info["print_time_s"] = parse_time(info["print_time_text"])
            elif line.startswith("; filament used [mm]"):
                info["filament_mm"] = float(line.split("=", 1)[1])
            elif line.startswith("; filament used [g]"):
                info["filament_g"] = float(line.split("=", 1)[1])
            elif line.startswith("; filament used [cm3]"):
                info["filament_cm3"] = float(line.split("=", 1)[1])
            elif line.startswith("G1") or line.startswith("G0"):
                prev_x, prev_y = x, y
                fields = dict((w[0], w[1:]) for w in line.split(";")[0].split()[1:] if len(w) > 1)
                for key in "XYZ":
                    if key in fields:
                        try:
                            value = float(fields[key])
                        except ValueError:
                            continue
                        if key == "X":
                            x = value
                        elif key == "Y":
                            y = value
                        else:
                            z = value
                e = float(fields["E"]) if "E" in fields and re.fullmatch(r"-?[\d.]+", fields["E"]) else 0.0
                if e > 0 and ("X" in fields or "Y" in fields):
                    total_mm += e
                    if kind == "External perimeter":
                        outer.append((x, y))
                    if kind.startswith("Support"):
                        support_mm += e
                        support_segments.append((z, prev_x, prev_y, x, y, e))
                    lo = [min(lo[0], x), min(lo[1], y), min(lo[2], z)]
                    hi = [max(hi[0], x), max(hi[1], y), max(hi[2], z)]
    area = math.pi * (FILAMENT_DIAMETER / 2) ** 2
    info["layers"] = layers
    info["bounding_box_mm"] = {"min": [round(v, 2) for v in lo], "max": [round(v, 2) for v in hi],
                               "size": [round(h - l, 2) for l, h in zip(lo, hi)]}
    info["extruded_mm"] = round(total_mm, 1)
    info["support_generated"] = support_mm > 0.0
    info["support_filament_mm"] = round(support_mm, 1)
    info["support_volume_mm3"] = round(support_mm * area, 1)
    info["support_clusters"] = support_clusters(support_segments)
    if segments_out is not None:
        segments_out.extend(support_segments)
    info["outer_perimeter_xy_extent_mm"] = ([round(min(p[0] for p in outer), 2), round(min(p[1] for p in outer), 2), round(max(p[0] for p in outer), 2), round(max(p[1] for p in outer), 2)]
                                            if outer else None)
    return info


def support_points(segments: Sequence[Tuple[float, float, float, float, float, float]], step_mm: float = 0.25) -> np.ndarray:
    """Support extrusion (z, x0, y0, x1, y1, filament mm) as points (z, x, y, filament mm) spaced along each extrusion."""
    out = []
    for z, x0, y0, x1, y1, e in segments:
        n = max(1, int(math.hypot(x1 - x0, y1 - y0) / step_mm))
        for k in range(n):
            t = (k + 0.5) / n
            out.append((z, x0 + (x1 - x0) * t, y0 + (y1 - y0) * t, e / n))
    return np.array(out, dtype=float).reshape(-1, 4)


def solid_section(mesh: trimesh.Trimesh, z: float) -> Any:
    """The solid of the mesh at height z as a shapely area, or None."""
    segs = trimesh.intersections.mesh_plane(mesh, [0, 0, 1], [0, 0, z])
    if len(segs) == 0:
        return None
    lines = unary_union([LineString(np.round(s[:, :2], 4)) for s in segs if np.linalg.norm(s[0, :2] - s[1, :2]) > 1e-6])
    area = shapely.build_area(lines)
    return None if area is None or area.is_empty else area


def components(mesh: trimesh.Trimesh, faces: np.ndarray) -> np.ndarray:
    """Label every face of the mesh with the connected group of `faces` (joined by shared edges) it belongs to, -1 for the other faces."""
    labels = np.full(len(mesh.faces), -1)
    if len(faces) == 0:
        return labels
    adj = mesh.face_adjacency
    keep = np.isin(adj[:, 0], faces) & np.isin(adj[:, 1], faces)
    index = {f: i for i, f in enumerate(faces)}
    graph = coo_matrix((np.ones(int(keep.sum())), ([index[a] for a, _ in adj[keep]], [index[b] for _, b in adj[keep]])), shape=(len(faces), len(faces)))
    _, lab = connected_components(graph, directed=False)
    labels[faces] = lab
    return labels


def first_face_above(mesh: trimesh.Trimesh, origins: np.ndarray) -> np.ndarray:
    """For each origin, the downward-facing face a vertical ray upward from it meets first, or -1."""
    down = np.where(mesh.face_normals[:, 2] < -1e-3)[0]
    tri = mesh.triangles[down]
    cell = 2.0
    lo = np.floor(tri[:, :, :2].min(axis=1) / cell).astype(int)
    hi = np.floor(tri[:, :, :2].max(axis=1) / cell).astype(int)
    grid: Dict[Tuple[int, int], List[int]] = {}
    for t in range(len(down)):
        for a in range(lo[t, 0], hi[t, 0] + 1):
            for b in range(lo[t, 1], hi[t, 1] + 1):
                grid.setdefault((a, b), []).append(t)
    found = np.full(len(origins), -1)
    for n, (x, y, z0) in enumerate(origins):
        cand = grid.get((int(math.floor(x / cell)), int(math.floor(y / cell))))
        if not cand:
            continue
        cand = np.array(cand)
        a = tri[cand]
        x0, y0, x1, y1, x2, y2 = a[:, 0, 0], a[:, 0, 1], a[:, 1, 0], a[:, 1, 1], a[:, 2, 0], a[:, 2, 1]
        den = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
        ok = np.abs(den) > 1e-12
        safe = np.where(ok, den, 1.0)
        l1 = np.where(ok, ((y1 - y2) * (x - x2) + (x2 - x1) * (y - y2)) / safe, -1.0)
        l2 = np.where(ok, ((y2 - y0) * (x - x2) + (x0 - x2) * (y - y2)) / safe, -1.0)
        l3 = 1.0 - l1 - l2
        inside = ok & (l1 >= -1e-9) & (l2 >= -1e-9) & (l3 >= -1e-9)
        if not inside.any():
            continue
        zs = l1[inside] * a[inside, 0, 2] + l2[inside] * a[inside, 1, 2] + l3[inside] * a[inside, 2, 2]
        zs = np.where(zs >= z0 - 1e-6, zs, np.inf)
        k = int(np.argmin(zs))
        if np.isfinite(zs[k]):
            found[n] = down[cand[inside][k]]
    return found


def roof_record(mesh: trimesh.Trimesh, faces: np.ndarray, to_model) -> Dict[str, Any]:
    """A flat roof (connected flat downward faces): its span (the widest inscribed circle's diameter), its size, and whether the solid under the roof's layer
    stands on both ends of that span."""
    tris = mesh.triangles[faces]
    z = float(tris[:, :, 2].mean())
    area = unary_union([ShPolygon(t[:, :2]).buffer(0.003) for t in tris if abs(ShPolygon(t[:, :2]).area) > 1e-9]).buffer(-0.003)
    shape = max(area.geoms, key=lambda g: g.area) if area.geom_type == "MultiPolygon" else area
    line = shapely.maximum_inscribed_circle(shape, 0.01)
    centre, edge = np.array(line.coords[0]), np.array(line.coords[1])
    radius = float(np.linalg.norm(edge - centre))
    anchored = False
    if radius > 0:
        way = (edge - centre) / radius
        far = shape.exterior.intersection(LineString([tuple(centre), tuple(centre - way * 100.0)]))
        far_point = np.array(far.geoms[0].coords[0] if hasattr(far, "geoms") and len(far.geoms) else (far.coords[0] if not far.is_empty else centre - way * radius), dtype=float)
        solid = solid_section(mesh, z - 0.1)
        anchored = bool(solid is not None and solid.contains(Point(*(edge + 0.12 * way))) and solid.contains(Point(*(far_point - 0.12 * way))))
    rect = np.array(shape.minimum_rotated_rectangle.exterior.coords)[:4]
    sides = sorted([float(np.linalg.norm(rect[1] - rect[0])), float(np.linalg.norm(rect[2] - rect[1]))])
    middle = to_model(np.array([[centre[0], centre[1], z]]))[0]
    return {"span_mm": round(2.0 * radius, 2), "long_mm": round(sides[1], 2), "short_mm": round(sides[0], 2), "area_mm2": round(float(shape.area), 1),
            "print_z_mm": round(z, 2), "anchored_both_ends_of_span": anchored, "model_frame_uv": [round(float(middle[0]), 1), round(float(middle[1]), 1)]}


def region_problems(region: Dict[str, Any], limits: Dict[str, float]) -> List[str]:
    """What stops a supports-auto region being one of the kinds the record accepts: sloped faces not flatter than the overhang limit (within the stated
    tolerance), flat roofs no wider than the bridge limit and standing on both ends of their span, and first-layer patches. Reads only the recorded fields."""
    problems: List[str] = []
    if region["kind"] == "first_layer_patch":
        if region["print_z_mm"][1] > limits["first_layer_mm"] + 1e-6:
            problems.append(f"patch with no face above it reaches print z {region['print_z_mm'][1]}")
        return problems
    if region["kind"] == "unattributed":
        return ["support with no model face above it and not a first-layer patch"]
    if region["flatter_than_limit_mm2"] >= limits["noise_area_mm2"]:
        problems.append(f"{region['flatter_than_limit_mm2']} mm2 of sloped face flatter than {limits['overhang_limit_deg']} deg")
    for roof in region["roofs"]:
        if roof["area_mm2"] < limits["noise_area_mm2"]:
            continue
        if roof["span_mm"] > limits["bridge_limit_mm"] + 1e-9:
            problems.append(f"flat roof of span {roof['span_mm']} mm at print z {roof['print_z_mm']}, wider than the {limits['bridge_limit_mm']} mm bridge limit")
        if not roof["anchored_both_ends_of_span"]:
            problems.append(f"flat roof at print z {roof['print_z_mm']} (span {roof['span_mm']} mm) is not anchored on both ends of its span")
    return problems


def critical_entries_problems(entries: Sequence[Dict[str, Any]], limits: Dict[str, float]) -> List[str]:
    """Why a run's supported critical facets are not tolerated: a flat roof, or a facet flatter than the overhang check's own limit (less its stated tolerance).

    Supported critical facets whose areas together, over the whole run of one part, are smaller than the noise area are tessellation ripple
    (a sliver triangle on a cone or at a boolean's edge), the same figure by which the region rule and the model's overhang check set such
    faces aside: where the slicer drops a trace of support depends on the mesh's handedness and placement, and faces that small are not faces
    that need holding up. The total is taken over every entry, a flat roof's included, so many small entries cannot each hide under the figure.
    At or above the noise area in total every entry is judged on its own: none may be a flat roof or flatter than the limit. The entries stay in
    the record and in the diagnostic note either way."""
    problems: List[str] = []
    if sum(float(e["facet_area_mm2"]) for e in entries) < limits["noise_area_mm2"]:
        return problems
    for entry in entries:
        if entry["flat_roof"]:
            problems.append(f"{entry['critical_feature']}: a flat roof under it is held up by support")
        if entry["angle_deg"][0] < limits["min_sloped_angle_deg"]:
            problems.append(f"{entry['critical_feature']}: a facet at {entry['angle_deg'][0]} deg, flatter than {limits['min_sloped_angle_deg']:.2f} deg, is held up by support")
    return problems


def diagnostic_note(auto: Dict[str, Any], auto0: Dict[str, Any]) -> str:
    """What a slicer's automatic support would touch on a critical face, in words, from the two diagnostic runs' records."""
    def one(label: str, run: Dict[str, Any]) -> str:
        hits = run["supported_faces_that_are_critical"]
        if not hits:
            return f"{label}: no critical face is held up by support"
        return f"{label}: " + "; ".join(f"{h['filament_mm']:.1f} mm of support under {h['facet_area_mm2']:.2f} mm2 of the {h['critical_feature']} "
                                          f"(facets at {h['angle_deg'][0]} to {h['angle_deg'][1]} deg, print z {h['facet_print_z_mm'][0]} to {h['facet_print_z_mm'][1]}"
                                          f"{', a flat roof' if h['flat_roof'] else ', none a flat roof'})" for h in hits)
    return ("Diagnostic only: the stated print has no support. If a slicer's automatic support were turned on, " + one(f"at the record's threshold ({auto['support_filament_mm']:.0f} mm in all)", auto)
            + "; " + one(f"at the slicer's own detection ({auto0['support_filament_mm']:.0f} mm in all)", auto0) + ".")


def attribute_support(mesh: trimesh.Trimesh, points: np.ndarray, to_model, selector, plane_boxes: Sequence[Tuple[str, Sequence[float]]],
                      limits: Dict[str, float]) -> Dict[str, Any]:
    """Attribute support to the model's faces. `points` are support points (z, x, y, filament mm) in the mesh's print frame, `to_model` carries
    print-frame points to the case frame, `selector` picks the critical faces (check.critical_face_selector) and `plane_boxes` are the critical
    faces stated as planes. Each column of support is traced up to the first downward face above it; support with no face above it is the slicer's
    margin round a feature when a supported face is near, else a first-layer patch. Support is then grouped into regions, one per supported face
    group (the bed-side edge is split into its left run, right run and far end)."""
    result: Dict[str, Any] = {"regions": [], "support_by_kind_mm": {}, "supported_faces_that_are_critical": [], "flush_to_critical_plane": []}
    if len(points) == 0:
        return result
    normals = mesh.face_normals
    angle = np.degrees(np.arccos(np.clip(np.abs(normals[:, 2]), 0.0, 1.0)))
    areas = mesh.area_faces
    centre_z = mesh.triangles_center[:, 2]
    down = np.where(normals[:, 2] < -1e-3)[0]
    face_group = components(mesh, down)
    roof_faces = down[(angle[down] < FLAT_DEG) & (centre_z[down] > 0.05)]
    roof_group = components(mesh, roof_faces)
    # columns
    cell = np.floor(points[:, 1:3] / COLUMN_MM).astype(int)
    keys = cell[:, 0] * 100000 + cell[:, 1]
    unique, inverse = np.unique(keys, return_inverse=True)
    top = np.full(len(unique), -1.0)
    np.maximum.at(top, inverse, points[:, 0])
    count = np.bincount(inverse)
    cx = np.bincount(inverse, points[:, 1]) / count
    cy = np.bincount(inverse, points[:, 2]) / count
    hit = first_face_above(mesh, np.c_[cx, cy, top - 0.1])
    group = np.where(hit >= 0, face_group[np.maximum(hit, 0)], -1)
    supported = hit >= 0
    if supported.any():
        xy_tree = cKDTree(np.c_[cx[supported], cy[supported]])
        h_tree = cKDTree(np.c_[cx[supported], cy[supported], 2.0 * top[supported]])
        loose = np.where(~supported)[0]
        if len(loose):
            d_xy, _ = xy_tree.query(np.c_[cx[loose], cy[loose]])
            _, nearest = h_tree.query(np.c_[cx[loose], cy[loose], 2.0 * top[loose]])
            group[loose] = np.where(d_xy <= PAD_REACH_MM, group[supported][nearest], -1)
    column_model = to_model(np.c_[cx, cy, top - 0.1])
    low, high = to_model(mesh.vertices).min(axis=0), to_model(mesh.vertices).max(axis=0)
    # a face group that reaches the bed is the bed-side edge: split into runs by side
    reaches_bed = {int(g) for g in np.unique(group[supported]) if g >= 0 and mesh.triangles[hit[supported][group[supported] == g]][:, :, 2].min() < 0.05}
    def side(i: int) -> str:
        if column_model[i, 1] >= low[1] + 0.78 * (high[1] - low[1]):
            return "far"
        return "left" if column_model[i, 0] < (low[0] + high[0]) / 2 else "right"
    column_region = [("patch", "") if group[i] < 0 else (int(group[i]), side(i) if int(group[i]) in reaches_bed else "") for i in range(len(unique))]
    names = sorted({r for r in column_region}, key=str)
    point_region = [column_region[j] for j in inverse]
    point_hit = hit[inverse]
    point_model = to_model(np.c_[points[:, 1], points[:, 2], points[:, 0] - 0.1])
    planes = [(n, np.array(b, dtype=float)) for n, b in plane_boxes]
    for name in names:
        in_region = np.array([r == name for r in point_region])
        cols = [i for i in range(len(unique)) if column_region[i] == name]
        faces = np.unique(hit[cols][hit[cols] >= 0]).astype(int)
        filament = float(points[in_region, 3].sum())
        pm = point_model[in_region]
        region: Dict[str, Any] = {"filament_mm": round(filament, 1), "print_z_mm": [round(float(points[in_region, 0].min()), 2), round(float(points[in_region, 0].max()), 2)],
                                  "layers": [int(round(points[in_region, 0].min() / 0.2)), int(round(points[in_region, 0].max() / 0.2))],
                                  "model_frame": {"u_mm": [round(float(pm[:, 0].min()), 1), round(float(pm[:, 0].max()), 1)], "v_mm": [round(float(pm[:, 1].min()), 1), round(float(pm[:, 1].max()), 1)],
                                                  "z_mm": [round(float(pm[:, 2].min()), 2), round(float(pm[:, 2].max()), 2)]}}
        if len(faces) == 0:
            region.update(kind="first_layer_patch" if name[0] == "patch" and region["print_z_mm"][1] <= limits["first_layer_mm"] + 1e-6 else "unattributed",
                          feature="support with no model face above it (the slicer's first-layer footprint beside the outline)", sloped_face_angle_deg=None,
                          flatter_than_limit_mm2=0.0, roofs=[], supported_face_area_mm2=0.0)
        else:
            sloped = faces[angle[faces] >= FLAT_DEG]
            flat = faces[(angle[faces] < FLAT_DEG) & (centre_z[faces] > 0.05)]
            flatter = float(areas[sloped[angle[sloped] < limits["min_sloped_angle_deg"]]].sum()) if len(sloped) else 0.0
            roofs = [roof_record(mesh, np.where(roof_group == g)[0], to_model) for g in sorted({int(roof_group[f]) for f in flat if roof_group[f] >= 0})]
            bed = bool(len(sloped) and mesh.triangles[sloped][:, :, 2].min() < 0.05)
            if len(sloped) and roofs:
                kind, feature = "sloped_faces_and_flat_roofs", "sloped walls with the flat roofs of shallow recesses beside them"
            elif len(sloped):
                kind = "bed_side_roll_in" if bed else "sloped_face"
                feature = (f"rounded bed-side edge of the outline ({round(float(mesh.triangles[sloped][:, :, 2].max()) / 0.2)} layers of roll-in), {name[1]}" if bed else "sloped face")
            else:
                kind = "flat_roof"
                big = max(roofs, key=lambda r: r["area_mm2"]) if roofs else None
                feature = (f"flat roof of a void, {big['short_mm']} wide by {big['long_mm']} long" if big else "flat roof")
            region.update(kind=kind, feature=feature, supported_face_area_mm2=round(float(areas[faces].sum()), 1), flatter_than_limit_mm2=round(flatter, 2), roofs=roofs,
                          sloped_face_angle_deg=([round(float(angle[sloped].min()), 1), round(float(angle[sloped].max()), 1)] if len(sloped) else None))
            tri_model = to_model(mesh.triangles[faces].reshape(-1, 3)).reshape(-1, 3, 3)
            normal_model = to_model(normals[faces] + 0.0) - to_model(np.zeros((1, 3)))
            for face_name, mask in selector(tri_model, normal_model).items():
                if mask.any():
                    picked = faces[mask]
                    under = in_region & np.isin(point_hit, picked)
                    corners = mesh.triangles[picked]
                    result["supported_faces_that_are_critical"].append({
                        "region": None, "critical_feature": face_name, "facet_area_mm2": round(float(areas[picked].sum()), 2),
                        "angle_deg": [round(float(angle[picked].min()), 1), round(float(angle[picked].max()), 1)], "flat_roof": bool((angle[picked] < FLAT_DEG).any()),
                        "filament_mm": round(float(points[under, 3].sum()), 2), "facet_print_z_mm": [round(float(corners[:, :, 2].min()), 2), round(float(corners[:, :, 2].max()), 2)],
                        "support_print_z_mm": [round(float(points[under, 0].min()), 2), round(float(points[under, 0].max()), 2)] if under.any() else None, "_key": name})
        for face_name, box in planes:
            gap = np.maximum.reduce([box[[0, 2, 4]] - pm, pm - box[[1, 3, 5]], np.zeros_like(pm)])
            flush = float(points[in_region, 3][np.linalg.norm(gap, axis=1) <= FLUSH_MM].sum())
            if flush > 0:
                result["flush_to_critical_plane"].append({"region": None, "critical_face": face_name, "filament_mm": round(flush, 2), "_key": name})
        region["problems"] = region_problems(region, limits)
        region["accepted"] = not region["problems"]
        region["_key"] = name
        result["regions"].append(region)
    result["regions"].sort(key=lambda r: -r["filament_mm"])
    index = {r["_key"]: i + 1 for i, r in enumerate(result["regions"])}
    for r in result["regions"]:
        r["id"] = index[r.pop("_key")]
    for entry in result["supported_faces_that_are_critical"] + result["flush_to_critical_plane"]:
        entry["region"] = index[entry.pop("_key")]
    kinds: Dict[str, float] = {}
    for r in result["regions"]:
        kinds[r["kind"]] = round(kinds.get(r["kind"], 0.0) + r["filament_mm"], 1)
    result["support_by_kind_mm"] = kinds
    return result


class Placement:
    """Where the slicer put a part on the bed, and how to carry a G-code point back to the model frame the criteria's regions are stated in. The exported STLs are in the physical frame, so the way back is the inverse of the print turn and then the reflection into the model frame."""

    def __init__(self, part: str, out_dir: str):
        printed = trimesh.load(os.path.join(out_dir, f"{part}.print.stl")).bounds
        model = trimesh.load(os.path.join(out_dir, f"{part}.stl")).bounds
        self.rotation = case.print_rotation(part)
        corners = np.array([[x, y, z] for x in model[:, 0] for y in model[:, 1] for z in model[:, 2]])
        turned = corners @ self.rotation.T
        self.shift = -turned.min(axis=0)
        expected = np.array([turned.min(axis=0) + self.shift, turned.max(axis=0) + self.shift])
        if float(np.abs(expected - printed).max()) > 0.05:
            raise SystemExit(f"{part}: the print-orientation STL is not the model STL turned by case.print_rotation and lowered to the bed (differs by {np.abs(expected - printed).max():.3f} mm)")
        self.offset = np.array([CENTER[0] - (printed[0, 0] + printed[1, 0]) / 2, CENTER[1] - (printed[0, 1] + printed[1, 1]) / 2, 0.0])
        self.gcode_bounds = printed + self.offset

    def to_model(self, points: np.ndarray) -> np.ndarray:
        return ((np.asarray(points, dtype=float) - self.offset - self.shift) @ self.rotation) @ case.PHYSICAL

    def model_box(self, x: Sequence[float], y: Sequence[float], z: Sequence[float]) -> Dict[str, List[float]]:
        corners = np.array([[a, b, c] for a in x for b in y for c in z])
        moved = self.to_model(corners)
        return {"u_mm": [round(float(moved[:, 0].min()), 2), round(float(moved[:, 0].max()), 2)],
                "v_mm": [round(float(moved[:, 1].min()), 2), round(float(moved[:, 1].max()), 2)],
                "z_mm": [round(float(moved[:, 2].min()), 2), round(float(moved[:, 2].max()), 2)]}


def run_slicer(part: str, mode: str, stl: str, out_dir: str, log, placement: Placement, context: Dict[str, Any]) -> Dict[str, Any]:
    gcode = os.path.join(out_dir, f"{part}.{mode}.gcode")
    command = [slicer_command(), "--export-gcode", "--load", os.path.join(HERE, "printer-220-asa.ini")]
    if mode.startswith("supports-auto"):
        command += ["--load", os.path.join(HERE, "support-auto.ini")]
    if mode == "supports-auto-threshold-0":
        command += ["--support-material-threshold", "0"]
    command += ["--center", f"{CENTER[0]:g},{CENTER[1]:g}", "--output", gcode, stl]
    done_text = lambda text: text.replace(os.path.dirname(HERE) + os.sep, "").replace(HERE + os.sep, "").replace(os.path.expanduser("~"), "~")
    log.write(done_text("$ " + " ".join(command)) + "\n")
    done = subprocess.run(command, capture_output=True, text=True, timeout=900)
    log.write(done_text(done.stdout + done.stderr) + f"exit status {done.returncode}\n\n")
    if done.returncode != 0 or not os.path.exists(gcode):
        raise SystemExit(f"PrusaSlicer failed on {part} ({mode}); see slice/{part}.log")
    segments: List[Any] = []
    result = parse_gcode(gcode, segments)
    result["gcode"] = os.path.basename(gcode)
    extent = result.pop("outer_perimeter_xy_extent_mm")
    want = placement.gcode_bounds
    if extent is None or max(abs(extent[0] - want[0, 0]), abs(extent[1] - want[0, 1]), abs(extent[2] - want[1, 0]), abs(extent[3] - want[1, 1])) > 1.0:
        raise SystemExit(f"{part} ({mode}): the slicer put the part at {extent}, not where its STL and --center {CENTER} place it ({want[:, :2].tolist()})")
    for cluster in result["support_clusters"]:
        cluster["model_frame"] = placement.model_box(cluster["x_mm"], cluster["y_mm"], cluster["z_mm"])
    if mode != "supports-off":
        points = support_points(segments)
        points[:, 1] -= placement.offset[0]
        points[:, 2] -= placement.offset[1]
        result.update(attribute_support(trimesh.load(stl), points, lambda p: ((np.asarray(p, dtype=float) - placement.shift) @ placement.rotation) @ case.PHYSICAL,
                                        context["selector"], context["planes"], context["limits"]))
    return result


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Slice the printed parts of the case.")
    parser.add_argument("--part", choices=PARTS + ("all",), default="all")
    parser.add_argument("--out", default=os.path.join(HERE, "out"), help="folder holding the <part>.print.stl files")
    parser.add_argument("--dest", default=os.path.join(HERE, "slice"))
    args = parser.parse_args(argv)
    os.makedirs(args.dest, exist_ok=True)
    version = slicer_version()
    model = case.build({}, forms=("single",))
    limits = {"overhang_limit_deg": float(model.P("printer.overhang_limit_deg")), "bridge_limit_mm": float(model.P("printer.bridge_limit_mm")),
              "noise_area_mm2": float(model.P("printer.noise_area_mm2")), "min_sloped_angle_deg": check.min_unflagged_angle_deg(float(model.P("printer.overhang_limit_deg"))), "first_layer_mm": FIRST_LAYER_MM}
    for part in PARTS if args.part == "all" else (args.part,):
        stl = os.path.join(args.out, f"{part}.print.stl")
        if not os.path.exists(stl):
            raise SystemExit(f"{stl} is missing: run case.py first")
        placement = Placement(part, args.out)
        with open(os.path.join(args.dest, f"{part}.log"), "w", encoding="utf-8") as log:
            context = {"selector": check.critical_face_selector(model, part), "planes": check.critical_plane_boxes(model, part), "limits": limits}
            off = run_slicer(part, "supports-off", stl, args.dest, log, placement, context)
            auto = run_slicer(part, "supports-auto", stl, args.dest, log, placement, context)
            auto0 = run_slicer(part, "supports-auto-threshold-0", stl, args.dest, log, placement, context)
        summary = {"part": part, "orientation": ORIENTATION[part], "printer": "generic open-frame 220 x 220 x 250, 0.4 mm nozzle, 0.2 mm layers, ASA 245/100, brim, draft shield",
                   "slicer": version, "inputs": pins(part, args.out), "support_frame": "support_clusters are in print coordinates (the G-code's: x, y on the bed, z up); each carries model_frame, the same box in the case's own frame (u, v, z) that case.py's regions use",
                   "limits": limits,
                   "supports_off": off, "supports_auto": auto, "supports_auto_threshold_0": auto0, "diagnostic_note": diagnostic_note(auto, auto0), "support_free": not auto["support_generated"] and not off["support_generated"]}
        with open(os.path.join(args.dest, f"{part}.json"), "w", encoding="utf-8") as handle:
            json.dump(summary, handle, indent=1)
        print(f"{part}: {off['print_time_text']}, {off['filament_mm']:.0f} mm / {off['filament_g']:.1f} g, {off['layers']} layers, "
              f"support with supports auto: {auto['support_generated']} ({auto['support_filament_mm']:.0f} mm in {len(auto['regions'])} regions, "
              f"{auto0['support_filament_mm']:.0f} mm at threshold 0), critical faces supported: {len(auto['supported_faces_that_are_critical'])}, "
              f"regions the record does not accept: {sum(1 for r in auto['regions'] if not r['accepted'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
