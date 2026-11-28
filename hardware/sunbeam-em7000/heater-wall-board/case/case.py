#!/usr/bin/env python3
"""The parametric printed case of the heater wall board: model, exports and drawings.

The model reads the board's layout file and project file at build time (outline,
slots, mounting hole, pads, courtyards, the nets of the Mains classes) and the
figures in params.yaml, and builds the tray, the lid in each colour form, the
engraved logo grooves, the spreader plate and simple solids for the
board and its parts. No insulating film or other loose part is modelled: the plate stands clear of the board's pads and the
tray's printed end wall fills the volume the plate leaves. Everything is built in a case MODEL frame in millimetres:

    u = x_pcb - ox     0 to 45 across the board
    v = y_pcb - oy     0 at the board's plate-side edge, 75 at the blade end
    z                  up from the board's component face (board at z -1.6 to 0)

ox and oy are read from Edge.Cuts. KiCad's y runs down the screen in the top view, so
(u, v, z) is a LEFT-handed frame. It is a working frame that never leaves the process:
distances and every check are the same in it as in the physical object. Everything that
leaves the model (STEP, STL, the print STLs, the 3MFs and the renders) is written in
the right-handed PHYSICAL frame, reached by one reflection (`PHYSICAL`, `physical`,
`physical_mesh`):

    X = u,  Y = -v,  Z = z

This is the frame in which kicad-cli exports the board's own three-dimensional model
(X = x_pcb, Y = -y_pcb, F.Cu on +Z), moved by the origin: a board model exported with
`--user-origin 0x0mm` lies against the exported case when translated by (-ox, +oy,
-board thickness) and not otherwise changed. The print STLs are the physical STLs turned
by `print_rotation` and moved to the bed.

The command line exports every printed part
as STEP and STL, a 3MF per colour form, the plate
drawing and the case drawings:

    python case.py --out out --set seating.body_underside_mm=2.55
    python case.py --skin flow

The model is a safety core and a selectable skin. The core (core.py, and the builders
below that follow the board, the end wall, the seat, the screws and the pilasters) fixes
everything the board relies on and the envelope a plan outline must lie in; a skin
(skins.py, chosen by the `skin` entry of params.yaml or --skin) supplies the plan
outline of the walls and the lid beyond the core, the edge treatment, the vent pattern
the core cuts as 45 degree gills, the relief grooves, the mark and the colours.

Run it with the interpreter `task hw:cad` creates.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import math
import os
import re
import sys
from dataclasses import dataclass, field
from xml.sax.saxutils import escape
from typing import Any, Dict, List, Optional, Sequence, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
BOARD_DIR = os.path.dirname(HERE)
REPO = os.path.abspath(os.path.join(BOARD_DIR, "..", "..", ".."))
TOOLS = os.path.join(REPO, "hardware", "tools")
sys.path.insert(0, TOOLS)
sys.dont_write_bytecode = True

import numpy as np  # noqa: E402
import trimesh  # noqa: E402
import yaml  # noqa: E402
from build123d import (Axis, Box, Cylinder, Location, Part, Plane, Polygon, Pos, Rot, Solid,  # noqa: E402
                       extrude, export_step, export_stl)
from shapely import affinity  # noqa: E402
from shapely.geometry import MultiPolygon, Point, Polygon as ShPolygon, box as sh_box  # noqa: E402
from shapely.geometry import LineString  # noqa: E402
from shapely.ops import unary_union  # noqa: E402

import board_geometry as bg  # noqa: E402
import sexpr  # noqa: E402
from solids import (box, ccw, chamfer_prism, chamfer_top, chamfered, cyl_v, cyl_z, fuse, offset_polygon, prism, prism_uz,  # noqa: E402,F401
                    prism_vz, tear_point_v, tear_v, to_mesh)
from core import (Core, LOCATING_RIB_HALF, LOCATING_RIB_V, Outlet, OutlineRefused, Vent, aperture_boxes, boot_box, case_extent,  # noqa: E402,F401
                  gravity, lean_allowance, pilaster_u, pocket_profile, toe_profile, toe_u)

BOARD_PCB = os.path.join(BOARD_DIR, "heater-wall-board.kicad_pcb")
BOARD_PRO = os.path.join(BOARD_DIR, "heater-wall-board.kicad_pro")
BASIS = os.path.join(BOARD_DIR, "separation-basis.yaml")
PARAMS = os.path.join(HERE, "params.yaml")
MAINS_FAMILY = ("Mains", "MainsTrunk", "MainsBranch")
TRIAC_REFS = ("T921", "T911")


# ---------------------------------------------------------------------------------------------------------------------
# Parameters
# ---------------------------------------------------------------------------------------------------------------------

class Params:
    """params.yaml with command-line style overrides: `section.name` addresses an entry, its `value` is replaced."""

    def __init__(self, data: Dict[str, Any]):
        self.data = data

    @classmethod
    def load(cls, overrides: Optional[Dict[str, Any]] = None, skin: Optional[str] = None) -> "Params":
        """params.yaml with the chosen skin's mark and colours read at the top-level addresses `mark` and `forms`."""
        with open(PARAMS, encoding="utf-8") as handle:
            params = cls(yaml.safe_load(handle))
        name = skin or (overrides or {}).get("skin") or params.data["skin"]["value"]
        if name not in params.data["skins"]:
            raise SystemExit(f"unknown skin {name!r}; the skins are {', '.join(params.data['skins'])}")
        params.data["skin"]["value"] = name
        for section in ("mark", "forms"):
            params.data[section] = params.data["skins"][name][section]
        for key, value in (overrides or {}).items():
            if key != "skin":
                params.set(key, value)
        return params

    @property
    def skin_name(self) -> str:
        return self.data["skin"]["value"]

    def S(self, key: str) -> Any:
        """A figure of the chosen skin: `S("louvre.rows")` reads skins.<skin>.louvre.rows."""
        return self.entry(f"skins.{self.skin_name}.{key}")["value"]

    def entry(self, key: str) -> Dict[str, Any]:
        node: Any = self.data
        for part in key.split("."):
            node = node[part]
        return node

    def __call__(self, key: str) -> Any:
        return self.entry(key)["value"]

    def set(self, key: str, value: Any) -> None:
        self.entry(key)["value"] = value

    def sourced(self) -> bool:
        """Whether every entry carries a source string."""
        def walk(node: Any, path: str) -> List[str]:
            if isinstance(node, dict) and "value" in node:
                return [] if isinstance(node.get("source"), str) and node["source"] else [path]
            if isinstance(node, dict):
                return [p for k, v in node.items() for p in walk(v, f"{path}.{k}" if path else k)]
            return []
        return not walk(self.data, "")

    def entries(self) -> List[Tuple[str, Dict[str, Any]]]:
        found: List[Tuple[str, Dict[str, Any]]] = []

        def walk(node: Any, path: str) -> None:
            if isinstance(node, dict) and "value" in node:
                found.append((path, node))
            elif isinstance(node, dict):
                for key, value in node.items():
                    walk(value, f"{path}.{key}" if path else key)
        walk(self.data, "")
        return found


def parse_overrides(items: Sequence[str]) -> Dict[str, Any]:
    found: Dict[str, Any] = {}
    for item in items:
        key, _, value = item.partition("=")
        if not key or not _:
            raise SystemExit(f"--set wants key=value, got {item!r}")
        found[key.strip()] = yaml.safe_load(value)
    return found


def basis() -> Dict[str, float]:
    """The signed separation figures, read from the board's separation basis record."""
    with open(BASIS, encoding="utf-8") as handle:
        record = yaml.safe_load(handle)
    return {
        "creepage_mains_mm": float(record["mains_to_mains"]["creepage_mm"]),
        "clearance_mains_mm": float(record["mains_to_mains"]["clearance_mm"]),
        "terminal_clearance_mm": float(record["mains_to_mains"]["terminal_clearance_mm"]),
        "creepage_lv_mm": float(record["mains_to_low_voltage"]["creepage_mm"]),
        "clearance_lv_mm": float(record["mains_to_low_voltage"]["clearance_mm"]),
    }


# ---------------------------------------------------------------------------------------------------------------------
# The board, read from the layout file
# ---------------------------------------------------------------------------------------------------------------------

@dataclass
class Board:
    ox: float
    oy: float
    thickness: float
    outline: ShPolygon                      # in the case frame, notches of the slots included
    slots: List[ShPolygon]                  # open area of each slot, mouth included
    h1: Tuple[float, float, float]          # u, v, drill diameter
    refs: Dict[str, Dict[str, Any]]         # per reference: u, v, rot, courtyard box, pads
    tht: List[Tuple[str, str, float, float, float]]  # (ref, pad, u, v, drill) through-hole leads
    mains_items: List[Dict[str, Any]]       # {label, layer, geom, net, kind}
    all_items: List[Dict[str, Any]]
    mains_nets: List[str]
    sha256: str = ""

    def mains_layer(self, layer: str) -> Any:
        return unary_union([i["geom"] for i in self.mains_items if i["layer"] == layer])


def _net_classes() -> Tuple[Dict[str, Dict[str, Any]], List[Dict[str, Any]]]:
    with open(BOARD_PRO, encoding="utf-8") as handle:
        pro = json.load(handle)
    settings = pro.get("net_settings", {})
    return {c["name"]: c for c in settings.get("classes", [])}, settings.get("netclass_patterns", [])


def _effective_class(net: str, classes: Dict[str, Dict[str, Any]], patterns: List[Dict[str, Any]]) -> str:
    best: Tuple[float, str] = (float("inf"), "Default")
    for pattern in patterns:
        if fnmatch.fnmatchcase(net, pattern["pattern"]):
            cls = classes.get(pattern["netclass"], {})
            best = min(best, (cls.get("priority", 2147483647), pattern["netclass"]))
    return best[1]


def read_board() -> Board:
    import hashlib
    raw = open(BOARD_PCB, "rb").read()
    tree = sexpr.parse_one(raw.decode("utf-8"))
    table = bg.net_table(tree)
    loops = bg.edge_loops(tree)
    outline_loop = max(loops, key=lambda loop: loop.area())
    xs = [p[0] for p in outline_loop.points]
    ys = [p[1] for p in outline_loop.points]
    ox, oy = min(xs), min(ys)
    thickness = float(sexpr.child(sexpr.child(tree, "general"), "thickness")[1])

    def uv(point: Tuple[float, float]) -> Tuple[float, float]:
        return (point[0] - ox, point[1] - oy)

    outline = ShPolygon([uv(p) for p in outline_loop.points]).buffer(0)
    hull = outline.convex_hull
    notches = hull.difference(outline)
    slots = [g for g in (list(notches.geoms) if hasattr(notches, "geoms") else [notches]) if g.area > 1e-3]
    slots.sort(key=lambda g: g.centroid.y)

    classes, patterns = _net_classes()
    mains_nets: List[str] = []
    net_names = set()

    refs: Dict[str, Dict[str, Any]] = {}
    tht: List[Tuple[str, str, float, float, float]] = []
    items: List[Dict[str, Any]] = []
    h1 = (0.0, 0.0, 0.0)
    for fp in sexpr.children(tree, "footprint"):
        name = bg.reference(fp) or "?"
        x, y, rot = bg.placement(fp, f"footprint {name}")
        pad_objs = bg.footprint_pads(fp, table)
        pad_nodes = sexpr.children(fp, "pad")
        courtyard: List[Tuple[float, float]] = []
        for node in fp[1:]:
            if isinstance(node, list) and sexpr.head(node).startswith("fp_"):
                layer = sexpr.child(node, "layer")
                if layer is not None and str(layer[1]) == "F.CrtYd":
                    pts = _item_points(node, name)
                    courtyard += [bg.placed(p, (x, y, rot)) for p in pts]
        court_box = None
        if courtyard:
            cx = [uv(p)[0] for p in courtyard]
            cy = [uv(p)[1] for p in courtyard]
            court_box = (min(cx), min(cy), max(cx), max(cy))
        pads_info = []
        for node, pad in zip(pad_nodes, pad_objs):
            ptype = str(node[2]) if len(node) > 2 else ""
            drill_node = sexpr.child(node, "drill")
            drill = 0.0
            if drill_node is not None:
                atoms = [str(v) for v in drill_node[1:] if isinstance(v, str)]
                if atoms and atoms[0] == "oval":
                    drill = float(atoms[1])
                elif atoms:
                    drill = float(atoms[0])
            u, v = uv(pad.centre)
            hole = uv(bg.placed(bg.xy(sexpr.child(node, "at"), f"pad of {name}"), (x, y, rot)))
            pads_info.append({"number": pad.number, "u": u, "v": v, "hole_u": hole[0], "hole_v": hole[1], "net": pad.net, "type": ptype, "drill": drill,
                              "shape": pad.shape, "size": pad.size, "angle": pad.angle, "pad": pad})
            if ptype == "np_thru_hole" and name == "H1":
                h1 = (hole[0], hole[1], drill)
            elif ptype == "thru_hole" and drill > 0:
                tht.append((name, pad.number, hole[0], hole[1], drill))
            if pad.net:
                net_names.add(pad.net)
        refs[name] = {"u": uv((x, y))[0], "v": uv((x, y))[1], "rot": rot, "courtyard": court_box, "pads": pads_info,
                      "lib_id": str(fp[1])}
    segments = sexpr.children(tree, "segment") + sexpr.children(tree, "arc")
    vias = sexpr.children(tree, "via")
    zones = sexpr.children(tree, "zone")
    for node in segments + vias + zones:
        net_names.add(bg.item_net(node, table, "item"))
    net_names.discard("")
    family = {n for n in net_names if _effective_class(n, classes, patterns) in MAINS_FAMILY}
    mains_nets = sorted(family)

    def add(label: str, layer: str, geom: Any, net: str, kind: str) -> None:
        items.append({"label": label, "layer": layer, "geom": geom, "net": net, "kind": kind, "mains": net in family})

    for name, ref in refs.items():
        for info in ref["pads"]:
            pad = info["pad"]
            if not pad.net:
                continue
            poly = ShPolygon([uv(p) for p in pad.outline()])
            for layer in ("F.Cu", "B.Cu"):
                if pad.on(layer):
                    add(f"pad {pad.number} of {name}", layer, poly, pad.net, "pad")
    for index, seg in enumerate(segments):
        net = bg.item_net(seg, table, "segment")
        layer = str(sexpr.child(seg, "layer")[1])
        width = float(sexpr.child(seg, "width")[1])
        if sexpr.head(seg) == "arc":
            pts = bg.arc_points(bg.xy(sexpr.child(seg, "start"), "arc"), bg.xy(sexpr.child(seg, "mid"), "arc"),
                                bg.xy(sexpr.child(seg, "end"), "arc"))
        else:
            pts = [bg.xy(sexpr.child(seg, "start"), "segment"), bg.xy(sexpr.child(seg, "end"), "segment")]
        add(f"track {index} on {net}", layer, LineString([uv(p) for p in pts]).buffer(width / 2), net, "track")
    for index, via in enumerate(vias):
        net = bg.item_net(via, table, "via")
        at = uv(bg.xy(sexpr.child(via, "at"), "via"))
        size = float(sexpr.child(via, "size")[1])
        for layer in ("F.Cu", "B.Cu"):
            add(f"via {index} on {net}", layer, Point(at).buffer(size / 2), net, "via")
    for zone in zones:
        net = bg.item_net(zone, table, "zone")
        zname = sexpr.child(zone, "name")
        label = str(zname[1]) if zname is not None else net
        for fill in sexpr.children(zone, "filled_polygon"):
            layer = str(sexpr.child(fill, "layer")[1])
            pts = [uv(bg.xy(c, "fill")) for c in sexpr.child(fill, "pts")[1:]]
            if len(pts) >= 3:
                add(f"zone {label} fill", layer, ShPolygon(pts).buffer(0), net, "zone")
    mains_items = [i for i in items if i["mains"]]
    return Board(ox, oy, thickness, outline, slots, (h1[0], h1[1], h1[2]), refs, tht, mains_items, items, mains_nets,
                 hashlib.sha256(raw).hexdigest())


def _item_points(node: list, name: str) -> List[Tuple[float, float]]:
    head = sexpr.head(node)
    what = f"footprint {name}"
    if head in ("fp_line",):
        return [bg.xy(sexpr.child(node, "start"), what), bg.xy(sexpr.child(node, "end"), what)]
    if head in ("fp_rect",):
        (x1, y1) = bg.xy(sexpr.child(node, "start"), what)
        (x2, y2) = bg.xy(sexpr.child(node, "end"), what)
        return [(x1, y1), (x2, y1), (x2, y2), (x1, y2)]
    if head in ("fp_poly",):
        return [bg.xy(c, what) for c in sexpr.child(node, "pts")[1:]]
    if head in ("fp_circle",):
        c = bg.xy(sexpr.child(node, "center"), what)
        e = bg.xy(sexpr.child(node, "end"), what)
        r = math.dist(c, e)
        return [(c[0] - r, c[1]), (c[0] + r, c[1]), (c[0], c[1] - r), (c[0], c[1] + r)]
    if head in ("fp_arc",):
        return bg.arc_points(bg.xy(sexpr.child(node, "start"), what), bg.xy(sexpr.child(node, "mid"), what),
                             bg.xy(sexpr.child(node, "end"), what))
    return []


# ---------------------------------------------------------------------------------------------------------------------
# Solid helpers (solids.py) and the core's frame figures (core.py)
# ---------------------------------------------------------------------------------------------------------------------

# ---------------------------------------------------------------------------------------------------------------------
# The model
# ---------------------------------------------------------------------------------------------------------------------

@dataclass
class Model:
    P: Params
    board: Board
    basis: Dict[str, float]
    phi: float
    pivot_v: float
    v_plate: float
    v_end: float
    tab_hole_z: float
    body_underside: float
    triac_u: Dict[str, float]
    skin: Any = None
    core: Any = None
    parts: Dict[str, Any] = field(default_factory=dict)       # printed or bought parts, in the case frame
    bodies: Dict[str, Dict[str, Any]] = field(default_factory=dict)  # board and part bodies: shape, mains flag
    screws: List[Dict[str, Any]] = field(default_factory=list)
    supports: List[Dict[str, Any]] = field(default_factory=list)
    openings: List[Dict[str, Any]] = field(default_factory=list)
    info: Dict[str, Any] = field(default_factory=dict)
    _meshes: Dict[str, trimesh.Trimesh] = field(default_factory=dict)

    # -- frames ---------------------------------------------------------------------------------------------------
    def to_board_frame(self, shape: Any) -> Any:
        """A shape drawn on the untilted board, carried to where the lean puts it."""
        if abs(self.phi) < 1e-12:
            return shape
        return shape.rotate(Axis((0, self.pivot_v, 0), (1, 0, 0)), math.degrees(self.phi))

    def board_local(self, point: Tuple[float, float, float]) -> Tuple[float, float, float]:
        """A case point in the board's own untilted frame (the inverse of to_board_frame)."""
        u, v, z = point
        c, s = math.cos(self.phi), math.sin(self.phi)
        dv = v - self.pivot_v
        return (u, self.pivot_v + dv * c + z * s, z * c - dv * s)

    def board_global(self, point: Tuple[float, float, float]) -> Tuple[float, float, float]:
        u, v, z = point
        c, s = math.cos(self.phi), math.sin(self.phi)
        dv = v - self.pivot_v
        return (u, self.pivot_v + dv * c - z * s, z * c + dv * s)

    def mesh(self, name: str) -> trimesh.Trimesh:
        if name not in self._meshes:
            shape = self.parts[name] if name in self.parts else self.bodies[name]["shape"]
            same = next((n for n, s in self.parts.items() if s is shape and n in self._meshes), None)     # the two lids are one solid
            self._meshes[name] = self._meshes[same] if same else to_mesh(shape)
        return self._meshes[name]

    # -- derived figures ------------------------------------------------------------------------------------------
    @property
    def z_floor_bottom(self) -> float:
        return self.P("case.z_floor_bottom_mm")

    def floor_top(self, v: float) -> float:
        P = self.P
        t = P("case.floor_far_mm") if v >= P("case.floor_far_from_v_mm") else P("case.floor_mm")
        return self.z_floor_bottom + t

    def underside_z(self, v: float) -> float:
        """The board's underside plane at v after the lean."""
        t = self.board.thickness
        return (-t + (v - self.pivot_v) * math.sin(self.phi)) / math.cos(self.phi)

    def top_z(self, v: float) -> float:
        return ((v - self.pivot_v) * math.sin(self.phi)) / math.cos(self.phi)


SUPPORTS = [(3.0, 10.0), (21.0, 9.0), (39.0, 9.5), (3.0, 31.0), (21.0, 31.0), (3.0, 52.0), (21.0, 52.0), (39.0, 52.0),
            (3.0, 61.0), (21.0, 61.0), (39.0, 61.0)]


def frame(overrides: Optional[Dict[str, Any]] = None, skin: Any = None) -> Model:
    """The model's frame, skin and core, before any solid is built."""
    import skins
    name = skin if isinstance(skin, str) else None
    P = Params.load(overrides, name)
    board = read_board()
    shift = P("seating.outline_routing_mm")
    if shift:
        # the routed outline's tolerance moves the board's edges and the slot mouths along v; the pads, holes and leads stay put
        board.outline = affinity.translate(board.outline, 0.0, shift)
        board.slots = [affinity.translate(slot, 0.0, shift) for slot in board.slots]
    sep = basis()
    phi = math.radians(P("seating.lean_deg"))
    pivot_v = P("seating.pad_row_v_mm")
    triac_u = {ref: board.refs[ref]["pads"][1]["hole_u"] for ref in TRIAC_REFS}
    row_v = board.refs["T911"]["pads"][0]["hole_v"]
    if abs(row_v - pivot_v) > 1e-6 or abs(board.thickness - P("parts.board_thickness_mm")) > 1e-6:
        raise SystemExit("params.yaml disagrees with the board file about the pad row or the board thickness")
    tfc = P("seating.tab_face_to_lead_centre_mm")
    v_plate = pivot_v + P("seating.lead_play_mm") - tfc
    v_end = v_plate
    body_underside = P("seating.body_underside_mm")
    tab_hole_z = body_underside + P("triac.A_mm") - P("triac.L_mm")
    m = Model(P, board, sep, phi, pivot_v, v_plate, v_end, tab_hole_z, body_underside, triac_u)
    m.skin = skin if (skin is not None and not isinstance(skin, str)) else skins.make(P.skin_name, P)
    m.core = Core(m)
    return m


def build(overrides: Optional[Dict[str, Any]] = None, forms: Sequence[str] = ("single", "two"), skin: Any = None) -> Model:
    """The model in a skin: a skin's name, a Skin object, or None for the params.yaml default."""
    m = frame(overrides, skin)
    P = m.P

    build_bodies(m)
    build_tray(m)
    build_plate(m)
    for form in forms:
        build_lid(m, form)
    build_openings(m)
    return m


# -- board and part bodies --------------------------------------------------------------------------------------------

def build_bodies(m: Model) -> None:
    P, board = m.P, m.board
    t = board.thickness
    slab = prism(list(board.outline.exterior.coords)[:-1], -t, 0.0)
    for slot in board.slots:
        pass  # the notches are part of the outline polygon already
    hu, hv, hd = board.h1
    slab = slab - cyl_z(hu, hv, -t - 1, 1, hd / 2)
    m.bodies["board"] = {"shape": m.to_board_frame(slab), "mains": False, "kind": "board"}

    # triacs: upright against the plate, the board tilts beneath them
    B, C, F, A = P("triac.B_mm"), P("triac.C_mm"), P("triac.F_mm"), P("triac.A_mm")
    b2, hole_d = P("triac.b2_mm"), P("triac.hole_dia_mm")
    bu = m.body_underside
    c1, lw = P("triac.c1_mm"), P("triac.lead_width_mm")
    prot = P("seating.lead_protrusion_below_board_mm")
    for ref in TRIAC_REFS:
        u = m.triac_u[ref]
        body = box(u - B / 2, u + B / 2, m.v_plate, m.v_plate + C, bu, bu + A - F)
        tab = box(u - B / 2, u + B / 2, m.v_plate, m.v_plate + b2, bu + A - F, bu + A)
        tab = tab - cyl_v(u, m.tab_hole_z, m.v_plate - 1, m.v_plate + b2 + 1, hole_d / 2)
        m.bodies[f"{ref}_body"] = {"shape": body + tab, "mains": False, "kind": "triac"}
        leads = []
        for pad in board.refs[ref]["pads"]:
            lead_v = m.pivot_v + P("seating.lead_play_mm")          # the lead sits in its hole off the hole's centre by the play
            leads.append(box(pad["hole_u"] - lw / 2, pad["hole_u"] + lw / 2, lead_v - c1 / 2, lead_v + c1 / 2, -t - prot, bu))
        m.bodies[f"{ref}_leads"] = {"shape": fuse(leads), "mains": True, "kind": "leads"}
        # the tab screw: M3 pan head on the case side of the tab, shaft into the plate
        r = P("triac.tab_screw_dia_mm") / 2
        head_h = P("triac.tab_screw_head_height_mm")
        head_r = P("triac.tab_screw_head_dia_mm") / 2
        face = m.v_plate + b2
        tip = face - P("triac.tab_screw_length_mm")
        m.screws.append({"id": f"tab screw {ref}", "kind": "tab", "u": u, "z": m.tab_hole_z, "axis": "v",
                         "v0": tip, "v1": face + head_h, "radius": r,
                         "head_radius": head_r, "head_v0": face, "head_v1": face + head_h, "touchable": False,
                         "shape": cyl_v(u, m.tab_hole_z, tip, face, r)
                         + cyl_v(u, m.tab_hole_z, face, face + head_h, head_r)})

    # varistors, optos, resistors, header with housing, blades: drawn on the untilted board then tilted with it
    local: List[Tuple[str, Any, bool]] = []
    for ref in ("RV911", "RV921"):
        c = board.refs[ref]["courtyard"]
        cu, cv = (c[0] + c[2]) / 2, (c[1] + c[3]) / 2
        D, W, H = P("parts.varistor_D_mm"), P("parts.varistor_W_mm"), P("parts.varistor_height_mm")
        local.append((ref, box(cu - D / 2, cu + D / 2, cv - W / 2, cv + W / 2, 0.5, H), False))
    inset, oh = P("parts.opto_inset_mm"), P("parts.opto_height_mm")
    for ref in ("U911", "U921"):
        c = board.refs[ref]["courtyard"]
        local.append((ref, box(c[0] + inset, c[2] - inset, c[1] + inset, c[3] - inset, 0, oh), False))
    rh = P("parts.resistor_height_mm")
    for ref in ("R911", "R912", "R921", "R922"):
        c = board.refs[ref]["courtyard"]
        local.append((ref, box(c[0] + 0.2, c[2] - 0.2, c[1] + 0.2, c[3] - 0.2, 0, rh), False))
    j = board.refs["J931"]
    local.append(("J931", box(min(p["u"] for p in j["pads"]) - 1.27, max(p["u"] for p in j["pads"]) + 1.27,
                              j["v"] - 1.27 - 0.1, j["v"] + 1.27 + 0.1, 0, P("parts.header_housing_top_z_mm")), False))
    bw, bt = P("blade.width_mm"), P("blade.thickness_mm")
    top = P("blade.standoff_mm") + P("blade.above_shoulder_mm")
    for ref in ("J941", "J921", "J911"):
        info = board.refs[ref]
        vs = [p["hole_v"] for p in info["pads"]]
        bu_ = info["pads"][0]["hole_u"]
        cv = sum(vs) / 2
        blade = box(bu_ - bt / 2, bu_ + bt / 2, cv - bw / 2, cv + bw / 2, 0, top)
        legs = [box(bu_ - bt / 2, bu_ + bt / 2, v - 0.35, v + 0.35, -t - P("blade.leg_length_below_board_mm"), 0) for v in vs]
        local.append((ref, blade + fuse(legs), True))
    for ref, shape, mains in local:
        m.bodies[ref] = {"shape": m.to_board_frame(shape), "mains": mains, "kind": "part"}

    # the board's mounting screw, H1
    r, head_r = P("screws.h1_dia_mm") / 2, P("screws.h1_head_dia_mm") / 2
    head_h, length = P("screws.h1_head_height_mm"), P("screws.h1_length_mm")
    shape = cyl_z(hu, hv, -t - (length - t), 0, r) + cyl_z(hu, hv, 0, head_h, head_r)
    m.screws.append({"id": "H1 screw", "kind": "h1", "u": hu, "v": hv, "axis": "z", "z0": -t - (length - t), "z1": head_h,
                     "radius": r, "head_radius": head_r, "shape": m.to_board_frame(shape), "touchable": False,
                     "local": True})


# -- the tray ---------------------------------------------------------------------------------------------------------

def tray_body(m: Model, spec: Any, zb: float, zt: float) -> Any:
    """The tray's outer solid: its full-height walls, a skirt under the lid's toe path when the skin draws one, then the skin's own additions."""
    core = m.core
    neck = spec.neck
    if spec.skirt is None:
        body = chamfer_prism(neck, zb, zt, bottom=spec.bottom_chamfer, square_at_v=m.v_end)
    else:
        skirt = core.validate_outline(spec.skirt.outline, "low", f"the {m.skin.name} skin's skirt outline")
        if skirt.difference(skirt).area > 0 or ShPolygon(neck).difference(skirt).area > 1e-4:
            raise OutlineRefused(f"the {m.skin.name} skin's skirt does not cover its full-height walls")
        ring = spec.skirt.outline
        z_top = core.low_zone_top
        low = chamfer_prism(ring, zb, z_top, top=spec.skirt.top_chamfer, bottom=spec.bottom_chamfer, square_at_v=m.v_end)
        high = prism(neck, z_top - 2.0 * max(spec.skirt.top_chamfer, 0.5), zt)
        body = low + high
        m.info["skirt_outline"] = [tuple(p) for p in ring]
    if spec.extras is not None:
        body = spec.extras(m, body)
    return body


def insert_hole_solid(m: Model, u: float, z: float) -> Any:
    """The heat-set insert's hole in a pilaster, a tear-drop hole from the end face to the maker's depth."""
    P = m.P
    return tear_point_v(u, z, m.v_end - 1, m.v_plate + P("case.insert_hole_depth_mm"), P("case.insert_hole_dia_mm") / 2)


def head_solid(m: Model, u: float, z: float) -> Any:
    """The tray-to-plate screw's countersunk head, in the plate's back face."""
    P = m.P
    v_back = m.v_plate - P("plate.thickness_mm")
    return cyl_v(u, z, v_back, v_back + P("screws.tray_plate_head_height_mm"), P("screws.tray_plate_head_dia_mm") / 2)


def pocket_solid(m: Model, u: float) -> Any:
    """The pocket under the hook in the pilaster at u, for the lid's toe."""
    return prism_vz([(m.v_end + a, b) for a, b in pocket_profile(m)], u - m.P("lid.pocket_width_mm") / 2, u + m.P("lid.pocket_width_mm") / 2)


def build_tray(m: Model) -> None:
    P, board = m.P, m.board
    zb = m.z_floor_bottom
    zt = P("case.z_wall_top_mm")
    spec = m.skin.tray(m.core)
    neck = m.core.validate_outline(spec.neck, "high", f"the {m.skin.name} skin's tray outline")
    m.info["tray_outline"] = [tuple(p) for p in spec.neck]
    tray = tray_body(m, spec, zb, zt)
    left_in, right_in = -P("case.interior_left_mm"), 45.0 + P("case.interior_right_mm")
    far_in = P("case.v_far_wall_inner_mm")
    split = P("case.floor_far_from_v_mm")
    # the end wall closes the plate end below the plate's raised lower edge, in the volume the narrower plate leaves; the cavity is cut
    # back to its board-side face, which stands the seam behind the plate plane, so only the floor and the pilasters reach the plane
    end_wall = end_wall_box(m)
    tray = tray + end_wall
    tray = tray - box(left_in, right_in, m.v_plate - P("plate.end_wall_board_recess_mm"), split, m.floor_top(0), zt + 1)
    tray = tray - box(left_in, right_in, split, far_in, m.floor_top(split + 1), zt + 1)
    m.info["end_wall"] = end_wall

    # seat group, drawn on the untilted board and tilted with it, then clipped to the tray's volume
    t = board.thickness
    low = -20.0
    size = P("seat.support_size_mm")
    seat: List[Any] = []
    for (u, v) in SUPPORTS:
        seat.append(box(u - size / 2, u + size / 2, v - size / 2, v + size / 2, low, -t))
        m.supports.append({"kind": "pillar", "u": u, "v": v, "size": size})
    hu, hv, hd = board.h1
    boss_r = P("screws.h1_boss_dia_mm") / 2
    seat.append(cyl_z(hu, hv, low, -t, boss_r))
    m.supports.append({"kind": "h1 boss", "u": hu, "v": hv, "size": boss_r * 2})
    # blade backing rib and its cross buttresses
    blades = [board.refs[r]["pads"] for r in ("J941", "J921", "J911")]
    cvs = [sum(p["v"] for p in pads) / len(pads) for pads in blades]
    cv = cvs[0]
    rib_w = P("seat.rib_width_mm")
    bu_list = [pads[0]["u"] for pads in blades]
    rib_u0, rib_u1 = min(bu_list) - 3.5, max(bu_list) + 3.0
    seat.append(box(rib_u0, rib_u1, cv - rib_w / 2, cv + rib_w / 2, low, -t))
    m.supports.append({"kind": "backing rib", "u0": rib_u0, "u1": rib_u1, "v0": cv - rib_w / 2, "v1": cv + rib_w / 2})
    bw = P("seat.buttress_width_mm")
    mids = [(bu_list[0] + bu_list[1]) / 2, (bu_list[1] + bu_list[2]) / 2]
    for bu_ in [rib_u0 + bw / 2 + 0.2] + mids + [rib_u1 - bw / 2 - 0.2]:
        seat.append(box(bu_ - bw / 2, bu_ + bw / 2, cv - 6.0, far_in - 1.0, low, -t))
        m.supports.append({"kind": "buttress", "u": bu_, "v0": cv - 6.0, "v1": far_in - 1.0})
    seat_shape = m.to_board_frame(fuse(seat))
    seat_shape = seat_shape & box(left_in - 0.01, right_in + 0.01, m.v_end, far_in + 0.01, zb + 0.6, 30.0)
    tray = tray + seat_shape
    # locating ribs on the left wall and the far wall: they stand a small gap off the board edge
    gap = P("seat.locating_gap_mm")
    rib_t = -gap - left_in
    ribs = []
    for v in LOCATING_RIB_V:
        ribs.append(box(left_in, left_in + (0 - gap - left_in), v - LOCATING_RIB_HALF, v + LOCATING_RIB_HALF, m.floor_top(v) - 0.3, 3.0))
    ribs.append(box(32.0, 34.0, 75.0 + gap, far_in, m.floor_top(far_in) - 0.3, 3.0))
    tray = tray + fuse(ribs)

    # hold-down finger on the left wall: a window in the wall, a thin finger and a 45 degree hook
    fv, fw, ft = P("seat.finger_v_mm"), P("seat.finger_width_mm"), P("seat.finger_thickness_mm")
    slit = P("seat.finger_slit_mm")
    wall = P("case.wall_mm")
    zwin0 = m.floor_top(fv) + 1.0
    zwin1 = 7.0
    half = fw / 2 + slit
    if P("seat.finger"):
        window = prism_vz([(fv - half, zwin0), (fv + half, zwin0), (fv + half, zwin1), (fv, zwin1 + P("printer.roof_slope") * half), (fv - half, zwin1)],
                          left_in - wall - 0.1, left_in + 0.0)
        tray = tray - window
        finger = box(left_in - ft, left_in + 0.0, fv - fw / 2, fv + fw / 2, m.floor_top(fv) - 0.3, 6.0)
        over = P("seat.finger_overhang_mm")
        # the hook's underside rises at 45 degrees from the tip back to the finger; the lead-in face above it is steeper
        tip = (over, 0.1)
        under_end = (left_in - ft, 0.1 + P("printer.roof_slope") * (over - (left_in - ft)))
        lead_end = (left_in - ft, under_end[1] + 1.2)
        hook = m.to_board_frame(prism_uz([tip, lead_end, under_end], fv - fw / 2, fv + fw / 2))
        tray = tray + finger + hook
        m.info["finger"] = {"v": fv, "tip": tip, "u_root": left_in - ft}

    # tray-to-plate screws and the lid hooks live in the pilasters
    pu = pilaster_u(m)
    pilot_r = P("case.pilot_dia_mm") / 2
    screw_r = P("screws.tray_plate_dia_mm") / 2
    for u in pu:
        for z in P("screws.tray_plate_z_mm"):
            tray = tray - insert_hole_solid(m, u, z)
            v_back = m.v_plate - P("plate.thickness_mm")
            m.screws.append({"id": f"tray screw u{u:g} z{z:g}", "kind": "tray_plate", "u": u, "z": z, "axis": "v",
                             "v0": v_back, "v1": v_back + P("screws.tray_plate_length_mm"), "radius": screw_r,
                             "head_radius": P("screws.tray_plate_head_dia_mm") / 2, "head_v0": v_back,
                             "head_v1": v_back + P("screws.tray_plate_head_height_mm"), "touchable": False,
                             "shape": cyl_v(u, z, v_back, v_back + P("screws.tray_plate_length_mm"), screw_r)})
            m.screws.append({"id": f"insert u{u:g} z{z:g}", "kind": "insert", "u": u, "z": z, "axis": "v", "v0": m.v_plate,
                             "v1": m.v_plate + P("case.insert_hole_depth_mm"), "radius": P("case.insert_hole_dia_mm") / 2 + P("case.insert_wall_min_mm"),
                             "touchable": False, "shape": insert_hole_solid(m, u, z)})
    # pocket under the hook, in each pilaster, for the lid's toe
    for u in toe_u(m):
        tray = tray - pocket_solid(m, u)

    # cable notch at the top of the right wall
    n0, n1 = P("lid.cable_notch_v_mm")
    nh = P("lid.cable_notch_height_mm")
    tray = tray - box(right_in - 0.01, right_in + wall + 0.01, n0, n1, zt - nh, zt + 1)

    # outlet slits: vertical cuts through the long walls, high in the installed frame, as the skin draws them
    outlets = m.skin.outlets(m.core)
    bad = {f"{s.side} slit at v {s.v:.1f}": m.core.outlet_problems(s) for s in outlets if m.core.outlet_problems(s)}
    web = m.core.outlet_web_faults(outlets)
    if bad or web:
        raise OutlineRefused("outlet slits break the core's rules: " + "; ".join(f"{k} {', '.join(v)}" for k, v in bad.items())
                             + "; ".join(f"slits {a + 1} and {b + 1} leave {d:.2f} mm" for a, b, d in web))
    m.info["outlets"] = outlets
    if outlets:
        tray = tray.cut(*[m.core.outlet_cutter(s) for s in outlets])

    # the logo engraved in the tray's outer top face, the face that prints on the bed; the floor is thickened inside under it
    mark = m.skin.tray_mark(m.core)
    depth_g = P("logo.groove_depth_mm")
    pad_top = m.core.floor_pad_top(depth_g)
    cavity = sh_box(left_in, m.v_end, right_in, far_in)
    pad = ShPolygon(mark.outline).buffer(P("logo.pad_margin_mm") + P("logo.groove_width_mm") / 2, join_style=1).intersection(cavity)
    tray = tray + geometry_cutter(pad, zb + 1.0, pad_top)
    engraving_cut = geometry_cutter(mark.geometry, zb - 1.0, zb + depth_g)
    m.info["tray_logo"] = {"geometry": mark.geometry, "outline": mark.outline, "pad": pad, "floor_under_grooves_mm": pad_top - (zb + depth_g),
                           "face": mark.area, "height_mm": mark.outline.bounds[3] - mark.outline.bounds[1]}

    # the far-end lug: lowered under the lid's pad and drilled for the lid screw
    uc, vc = P("screws.lid_u_mm"), P("screws.lid_v_mm")
    lug_w = P("screws.lug_u_width_mm")
    far_out = far_in + wall
    lug_top = P("case.z_lid_under_mm") - 1.2
    tray = tray - box(uc - lug_w / 2 - 0.1, uc + lug_w / 2 + 0.1, far_out, far_out + P("screws.lug_v_depth_mm") + 0.1,
                      lug_top, zt + 1)
    tray = tray - cyl_z(uc, vc, lug_top - 8.0, lug_top + 0.1, pilot_r)
    m.info["lug_top"] = lug_top
    lr = P("screws.lid_dia_mm") / 2
    head_r, head_h = P("screws.lid_head_dia_mm") / 2, P("screws.lid_head_height_mm")
    z_lid_top = P("case.z_lid_top_mm")
    m.screws.append({"id": "lid screw", "kind": "lid", "u": uc, "v": vc, "axis": "z", "z0": z_lid_top - P("screws.lid_length_mm"),
                     "z1": z_lid_top, "radius": lr, "head_radius": head_r, "touchable": True,
                     "shape": cyl_z(uc, vc, z_lid_top - P("screws.lid_length_mm"), z_lid_top - head_h, lr)
                     + cyl_z(uc, vc, z_lid_top - head_h, z_lid_top, head_r)})
    # the board's mounting boss: a pilot drilled down from the boss top, ending above the floor's underside
    tray = tray - cyl_z(hu, hv, P("screws.h1_pilot_bottom_z_mm"), 1.0, pilot_r)
    m.info["tray_envelope"] = tray        # the tray before its engraving is cut: a superset, for the sweep's exact distances
    m.parts["tray"] = tray - engraving_cut
    m.info.update({"tray_pilaster_u": pu, "toe_u": toe_u(m)})


# -- the plate --------------------------------------------------------------------------------------------------------

def plate_geometry(m: Model) -> Dict[str, float]:
    """The plate's edges in the case frame: its length centres it on the case's extent, its lower edge is the ledge's height (the figure of
    `plate.lower_edge_z_mm` less the seating range's plate-edge offset) and its upper edge is that plus the bar's height. The former
    outline, the `plate.length_mm` by `plate.former_height_mm` window centred on the case's extent, is kept apart as its own figure."""
    P = m.P
    e = case_extent(m)
    cu, cz = (e["u0"] + e["u1"]) / 2, (e["z0"] + e["z1"]) / 2
    L, H = P("plate.length_mm"), P("plate.former_height_mm")
    z0 = plate_lower_edge(m)
    return {"u0": cu - L / 2, "u1": cu + L / 2, "z0": z0, "z1": z0 + P("plate.height_mm"), "cu": cu,
            "former_z0": cz - H / 2, "former_z1": cz + H / 2, "former_u0": cu - L / 2, "former_u1": cu + L / 2}


def plate_lower_edge(m: Model) -> float:
    """The height of the tray's ledge, where the bar's lower edge rests, above the board's component face in this build."""
    return m.P("plate.lower_edge_z_mm") + m.P("seating.plate_edge_offset_mm")


def end_wall_box(m: Model, edge: Optional[float] = None) -> Any:
    """The tray's printed end wall: the tray's full outer width at the plate end, from the floor's underside up to a ledge at the plate's
    lower edge, in the volume the narrower plate leaves, its back face 0.5 mm in front of the machine wall's plane. The bar's lower edge
    rests on the ledge. Its board-side face is recessed behind the plate plane across the cavity's width, so it stands further from the
    board than the plate does. Its sides and its back face carry the tray's own bottom chamfer, so the body's chamfer runs on round the wall;
    the bottom edge on the board-side face, where the wall meets the tray body, stays square."""
    P = m.P
    e = case_extent(m)
    top = plate_lower_edge(m) if edge is None else edge
    back = m.v_plate - P("plate.thickness_mm") + P("plate.end_wall_wall_clear_mm")
    chamfer = float(m.skin.tray(m.core).bottom_chamfer)
    outline = [(e["u0"], back), (e["u1"], back), (e["u1"], m.v_plate), (e["u0"], m.v_plate)]
    return chamfer_prism(outline, m.z_floor_bottom, top, bottom=chamfer, square_at_v=m.v_plate)


def build_plate(m: Model) -> None:
    P = m.P
    g = plate_geometry(m)
    u0, u1, z0, z1, cu = g["u0"], g["u1"], g["z0"], g["z1"], g["cu"]
    T = P("plate.thickness_mm")
    plate = box(u0, u1, m.v_plate - T, m.v_plate, z0, z1)
    # countersunk holes for the tray screws from the back face
    head_r = P("screws.tray_plate_countersink_dia_mm") / 2
    r_clear = 1.7
    for u in pilaster_u(m):
        for z in P("screws.tray_plate_z_mm"):
            plate = plate - cyl_v(u, z, m.v_plate - T - 1, m.v_plate + 1, r_clear)
            cone = Pos(u, m.v_plate - T, z) * Rot(X=-90) * Solid.make_cone(head_r, r_clear, head_r - r_clear, Plane.XY)
            plate = plate - cone
    # tab screw holes, tapped through the whole plate from the triac side, at the tab hole height
    for ref in TRIAC_REFS:
        plate = plate - cyl_v(m.triac_u[ref], m.tab_hole_z, m.v_plate - T - 1, m.v_plate + 1, P("triac.plate_tap_drill_mm") / 2)
    # wall bolt holes: one at each end, centred in the bolt zone at the plate's mid-height
    bz = P("plate.bolt_zone_mm")
    cz = (z0 + z1) / 2
    for end, sign in ((u0, 1), (u1, -1)):
        plate = plate - cyl_v(end + sign * (bz / 2), cz, m.v_plate - T - 1, m.v_plate + 1, P("plate.bolt_dia_mm") / 2 + 0.25)
    m.parts["plate"] = plate
    m.info["plate"] = {"u0": u0, "u1": u1, "z0": z0, "z1": z1, "cu": cu, "cz": cz, "bolt_zs": [cz],
                       "former_z0": g["former_z0"], "former_z1": g["former_z1"]}


def wall_opening(m: Model) -> Dict[str, float]:
    """The opening in the machine's plastic wall: the plate and the tray's end wall together plus the clearance each side, in the case frame."""
    P = m.P
    pl = m.info["plate"]
    ew = m.info["end_wall"].bounding_box()
    c = P("plate.wall_opening_clearance_mm")
    return {"u0": min(pl["u0"], float(ew.min.X)) - c, "u1": max(pl["u1"], float(ew.max.X)) + c,
            "z0": min(pl["z0"], float(ew.min.Z)) - c, "z1": max(pl["z1"], float(ew.max.Z)) + c, "clearance": c}


# -- the lid ----------------------------------------------------------------------------------------------------------

def build_lid(m: Model, form: str) -> None:
    """The lid. Both colour forms have one geometry: the two-colour form differs only in the colour of the groove floors, a filament change at the groove depth."""
    P = m.P
    za, zt = P("case.z_lid_under_mm"), P("case.z_lid_top_mm")
    core, skin = m.core, m.skin
    other = "lid_single" if form == "two" else "lid_two"
    if other in m.parts:
        m.parts[f"lid_{form}"] = m.parts[other]
        if form == "two":
            _swap_parts(m)
        return
    ch = skin.lid_chamfer
    outline_uv = [tuple(p) for p in skin.lid_outline(core)]
    core.validate_outline(outline_uv, "low", f"the {skin.name} skin's lid outline")
    gap = P("case.lid_end_gap_mm")
    outline = [(u, v + gap) if abs(v - m.v_end) < 1e-9 else (u, v) for u, v in outline_uv]
    drop = skin.lid_drop_lip(core)
    z_bottom = core.low_zone_top + (za - core.z_wall_top) if drop is not None else za
    lid = chamfer_prism(outline, z_bottom, zt, top=ch)
    m.info["lid_outline"] = outline
    m.info["lid_flat"] = ShPolygon(outline).buffer(-ch, join_style=2, mitre_limit=10.0)
    # the skin's perimeter drop-lip, which hides the seam between lid and tray down to the tray's skirt: the lid is one extrusion
    # down to the lip's bottom, and everything inside the lip is cut away from below, so lid and lip share one outer face
    if drop is not None:
        lid = lid - geometry_cutter(ShPolygon(outline).buffer(2.0).difference(drop), z_bottom - 1.0, za)
        m.info["lid_drop_lip"] = {"region": drop, "z_bottom": z_bottom, "shadow_line_mm": za - core.z_wall_top}
    # underside: pad for the louvre field, the fit lip, the toes, the lug pad, the bay collars
    pu0, pu1 = P("lid.pad_u_mm")
    pv0, pv1 = P("lid.pad_v_mm")
    pad_h = P("lid.top_louvre_mm") - (zt - za)
    lid = lid + box(pu0, pu1, pv0, pv1, za - pad_h, za + 0.01)
    lip_h, lip_t = P("lid.lip_height_mm"), P("lid.lip_thickness_mm")
    left_in, right_in = -P("case.interior_left_mm"), 45.0 + P("case.interior_right_mm")
    far_in = P("case.v_far_wall_inner_mm")
    seam = P("case.seam_mm")
    v_start = m.v_end + 1.0
    n0, n1 = P("lid.cable_notch_v_mm")
    bays = aperture_boxes(m)
    relief = P("lid.lip_relief_mm")
    bay_v0 = min(a["v"] - a["dv"] / 2 for a in bays)
    bay_u1 = max(a["u"] + a["du"] / 2 for a in bays)
    lips = [box(left_in + seam, left_in + seam + lip_t, v_start, bay_v0 - relief, za - lip_h, za + 0.01),
            box(right_in - seam - lip_t, right_in - seam, v_start, n0 - 0.5, za - lip_h, za + 0.01),
            box(right_in - seam - lip_t, right_in - seam, n1 + 0.5, far_in - seam, za - lip_h, za + 0.01),
            box(bay_u1 + relief, right_in - seam, far_in - seam - lip_t, far_in - seam, za - lip_h, za + 0.01)]
    lid = lid + fuse(lips)
    # toes: a finger down into each pilaster pocket with a 45 degree barb under the hook
    tw = P("lid.toe_width_mm")
    for u in toe_u(m):
        lid = lid + prism_vz([(m.v_end + a, b) for a, b in toe_profile(m)], u - tw / 2, u + tw / 2)
    # lug pad under the lid screw
    uc, vc = P("screws.lid_u_mm"), P("screws.lid_v_mm")
    lug_top = m.info["lug_top"]
    far_out = P("case.v_far_wall_inner_mm") + P("case.wall_mm")
    pad_region = skin.lid_lug_pad(core)
    if pad_region is None:
        lid = lid + box(uc - 3.6, uc + 3.6, far_out + P("case.seam_mm"), vc + 3.3, lug_top + P("case.seam_mm"), za + 0.01)
    else:
        lid = lid + geometry_cutter(pad_region, lug_top + P("case.seam_mm"), za + 0.01)
    # bay collars, kept inside the tray's walls, and the bays through the lid and the collars
    wall = P("lid.collar_wall_mm")
    collar_h = P("lid.collar_below_mm")
    inner = sh_box(left_in + seam, v_start, right_in - seam, far_in - seam)
    for ap in bays:
        collar = sh_box(ap["u"] - ap["du"] / 2 - wall, ap["v"] - ap["dv"] / 2 - wall, ap["u"] + ap["du"] / 2 + wall, ap["v"] + ap["dv"] / 2 + wall).intersection(inner)
        lid = lid + geometry_cutter(collar, za - collar_h, za + 0.01)
    lid = lid - fuse([box(ap["u"] - ap["du"] / 2, ap["u"] + ap["du"] / 2, ap["v"] - ap["dv"] / 2, ap["v"] + ap["dv"] / 2, za - collar_h - 1, zt + 1)
                      for ap in bays])
    m.info["lid_envelope"] = lid          # the lid before its vents, grooves, screw hole and engraving are cut: a superset, for the sweep's exact distances
    # vents: through-slots the core cuts as gills at the louvre angle through the thick field
    vents = skin.vents(core)
    bad = {v.label: core.vent_problems(v) for v in vents if core.vent_problems(v)} if skin.vents_are_policed else {}
    if bad:
        raise OutlineRefused("vents break the core's rules: " + "; ".join(f"{k} {', '.join(v)}" for k, v in bad.items()))
    m.info["vents"] = vents
    if vents:
        lid = lid.cut(*[core.gill_cutter(v) for v in vents])
    # relief grooves: shallow recesses in the top face that are not through-openings
    grooves = skin.grooves(core)
    m.info["grooves"] = grooves
    m.info["far_end_block"] = skin.block(core).get("reason") if hasattr(skin, "block") else "the skin draws no block"
    if grooves:
        lid = lid.cut(*[groove_cutter(g, zt) for g in grooves])
    # lid screw: a 90 degree countersink and the clearance hole
    head_r = P("screws.lid_head_dia_mm") / 2
    hole_r = P("screws.lid_dia_mm") / 2 + 0.2
    depth = head_r + 0.01 - hole_r
    cone = Pos(uc, vc, zt - depth) * Solid.make_cone(hole_r, head_r + 0.01, depth, Plane.XY)
    lid = lid - cyl_z(uc, vc, za - 3, zt + 1, hole_r) - cone
    # the logo, engraved: the same groove depth in both colour forms, no inlay part
    spec = skin.mark(core, vents)
    depth_m = P("logo.groove_depth_mm")
    lid = lid - geometry_cutter(spec.geometry, zt - depth_m, zt + 1)
    m.parts[f"lid_{form}"] = lid
    m.info["mark_geometry"] = spec.geometry
    m.info["logo_outline"] = spec.outline
    m.info["mark_area_uv"] = list(spec.area) if spec.area else None
    if form == "two":
        _swap_parts(m)


def _swap_parts(m: Model) -> None:
    """The two-colour form's swap layers as their own parts: the lid and the tray each cut to their band, once.

    Both colour forms share one geometry; these parts only say which of it prints in the second colour.
    """
    if "lid_swap" in m.parts:
        return
    bands = swap_bands(m)
    wide = 1e3
    for part, whole, name in (("lid", "lid_two", "lid_swap"), ("tray", "tray", "tray_swap")):
        z0, z1 = bands[part]
        m.parts[name] = m.parts[whole] & box(-wide, wide, -wide, wide, z0, z1)


def swap_bands(m: Model) -> Dict[str, Tuple[float, float]]:
    """The two-colour form's swap layers, per printed part, as a band of z in the case frame.

    Each part prints with its outer face on the bed (the tray's outer top face, the lid's face). It prints in its own colour to
    `forms.two.swap_start_mm` above the bed, then `forms.two.swap_layers` whole layers in the second colour, then its own
    colour again. A filament change colours the whole layer, so everything of the part inside the band is the second colour:
    the groove floors, and a line round every outside and opening wall the band crosses.
    """
    P = m.P
    start = P("forms.two.swap_start_mm")
    thick = P("forms.two.swap_layers") * P("printer.layer_mm")
    zt, zb = P("case.z_lid_top_mm"), m.z_floor_bottom
    return {"lid": (zt - start - thick, zt - start), "tray": (zb + start, zb + start + thick)}


def geometry_cutter(shape: Any, z0: float, z1: float) -> Any:
    """A prism of a shapely geometry (polygons with holes) from z0 to z1, each polygon built as one face with its holes and extruded."""
    from build123d import Face, Vector, Wire
    polys = list(shape.geoms) if hasattr(shape, "geoms") else [shape]
    solids = []
    for poly in polys:
        if poly.is_empty or poly.area < 1e-4:
            continue
        outer = Wire.make_polygon([Vector(x, y, z0) for x, y in ccw(list(poly.exterior.coords)[:-1])], close=True)
        inners = [Wire.make_polygon([Vector(x, y, z0) for x, y in ccw(list(ring.coords)[:-1])[::-1]], close=True) for ring in poly.interiors]
        solid = extrude(Face(outer, inners), z1 - z0)
        if abs(solid.volume - poly.area * (z1 - z0)) > 1e-3 * poly.area * (z1 - z0) + 1e-6:
            raise SystemExit(f"a prism of a {poly.area:.2f} mm2 polygon came out with volume {solid.volume:.3f}, not {poly.area * (z1 - z0):.3f}")
        solids.append(solid)
    return fuse(solids)


def groove_cutter(g: Any, zt: float) -> Any:
    """The solid a relief groove removes from the lid's top face."""
    return geometry_cutter(g.polygon(), zt - g.depth, zt + 1)


# -- openings ---------------------------------------------------------------------------------------------------------

def build_openings(m: Model) -> None:
    """Every opening of the assembled case with its kind, smaller dimension and the points a line is cast from."""
    P = m.P
    za, zt = P("case.z_lid_under_mm"), P("case.z_lid_top_mm")
    ops: List[Dict[str, Any]] = list(m.core.vent_openings(m.info["vents"]))
    ops += m.core.outlet_openings(m.info["outlets"])
    for ap in aperture_boxes(m):
        ops.append({"id": f"blade bay {ap['ref']}", "kind": "blade aperture", "min_dim": ap["du"], "max_dim": ap["dv"],
                    "points": [(ap["u"], ap["v"], zt - 0.1)], "u": ap["u"], "v": ap["v"], "z": zt, "du": ap["du"], "dv": ap["dv"]})
    n0, n1 = P("lid.cable_notch_v_mm")
    right_in = 45.0 + P("case.interior_right_mm")
    nh = P("lid.cable_notch_height_mm")
    zt_wall = P("case.z_wall_top_mm")
    npts = [(right_in + 1.0, v, zt_wall - nh / 2) for v in np.linspace(n0 + 0.5, n1 - 0.5, 5)]
    ops.append({"id": "cable notch", "kind": "cable notch", "min_dim": nh, "max_dim": n1 - n0, "points": npts,
                "u": right_in + 1.0, "v": (n0 + n1) / 2, "z": zt_wall - nh / 2})
    seam = P("case.seam_mm")
    left_in = -P("case.interior_left_mm")
    wall = P("case.wall_mm")
    far_in = P("case.v_far_wall_inner_mm")
    seam_pts = {
        "left wall top seam": [(left_in - wall / 2, v, zt_wall + seam / 2) for v in np.linspace(m.v_end + 12, far_in - 2, 12)],
        "right wall top seam": [(right_in + wall / 2, v, zt_wall + seam / 2) for v in np.linspace(m.v_end + 12, n0 - 1, 5)]
        + [(right_in + wall / 2, v, zt_wall + seam / 2) for v in np.linspace(n1 + 1, far_in - 2, 5)],
        "far wall top seam": [(u, far_in + wall / 2, zt_wall + seam / 2) for u in np.linspace(left_in + 3, right_in - 3, 12)],
        "pilaster top seam": [(u, m.v_end + 4.0, zt_wall + seam / 2) for u in list(pilaster_u(m)) + [-5.0, 52.0]],
    }
    for name, pts in seam_pts.items():
        ops.append({"id": name, "kind": "seam", "min_dim": seam, "max_dim": 40.0, "points": pts, "u": pts[0][0], "v": pts[0][1],
                    "z": zt_wall + seam / 2})
    # the hold-down finger's slits through the left wall
    fv, fw, slit = P("seat.finger_v_mm"), P("seat.finger_width_mm"), P("seat.finger_slit_mm")
    for sign, label in ((-1, "below"), (1, "above")):
        v = fv + sign * (fw / 2 + slit / 2)
        ops.append({"id": f"finger slit {label}", "kind": "finger slit", "min_dim": slit, "max_dim": 8.0,
                    "points": [(left_in - wall / 2, v, z) for z in (-3.0, 0.0, 3.0, 6.0)], "u": left_in - wall / 2, "v": v, "z": 2.0})
    ops += m.skin.extra_openings(m)
    m.openings = ops


# -- driver approach to the tab screws ----------------------------------------------------------------------------------

def driver_clearances(m: Model, ref: str, tilt_deg: float) -> Dict[str, float]:
    from build123d import Cylinder, Pos, Axis
    P = m.P
    u, z = m.triac_u[ref], m.tab_hole_z
    r = P("screws.driver_dia_mm") / 2
    v0 = m.v_plate + P("triac.b2_mm") + P("triac.tab_screw_head_height_mm")
    length = 85.0
    # a build123d cylinder along z, turned to the driver axis and moved to the screw head
    shaft = Cylinder(r, length)
    shaft = shaft.rotate(Axis((0, 0, 0), (1, 0, 0)), -(90.0 - tilt_deg))
    a = math.radians(tilt_deg)
    centre = (u, v0 + math.cos(a) * length / 2, z + math.sin(a) * length / 2)
    shaft = Pos(*centre) * shaft
    sb = shaft.bounding_box()
    found = {}
    skip = {f"{ref}_body", f"{ref}_leads"}
    candidates = {name: m.parts[name] for name in ("tray", "plate")}
    candidates.update({name: body["shape"] for name, body in m.bodies.items() if name not in skip})
    for name, ob in candidates.items():
        ob_bb = ob.bounding_box()
        gap_box = max(max(ob_bb.min.X - sb.max.X, sb.min.X - ob_bb.max.X, 0.0), max(ob_bb.min.Y - sb.max.Y, sb.min.Y - ob_bb.max.Y, 0.0),
                      max(ob_bb.min.Z - sb.max.Z, sb.min.Z - ob_bb.max.Z, 0.0))
        found[name] = float(shaft.distance_to(ob)) if gap_box < 6.0 else gap_box
    return found


def driver_tilt(m: Model, ref: str, margin: float = 0.3) -> Tuple[float, Dict[str, float]]:
    """The least driver tilt, in half degrees up to the limit, at which the shaft clears everything with the lid off."""
    limit = m.P("screws.driver_max_tilt_deg")
    angle = 0.0
    while angle <= limit + 1e-9:
        gaps = driver_clearances(m, ref, angle)
        if min(gaps.values()) >= margin:
            return angle, gaps
        angle += 0.5
    return float("nan"), driver_clearances(m, ref, limit)



# ---------------------------------------------------------------------------------------------------------------------
# Exports and drawings
# ---------------------------------------------------------------------------------------------------------------------

PRINTED = {"tray": "tray", "lid_single": "lid (single-colour form)", "lid_two": "lid (two-colour form)"}


PRINT_TURNED = ("lid_single", "lid_two")          # the parts printed face down: turned half a revolution about the X axis from the physical frame

PHYSICAL = np.diag([1.0, -1.0, 1.0])              # model frame (u, v, z) to the right-handed physical frame (X = u, Y = -v, Z = z): a reflection


def physical(shape: Any) -> Any:
    """A shape of the model frame as the right-handed physical shape: reflected in the plane v = 0 (the model frame is left-handed). The result is a valid solid of the same volume."""
    return shape.mirror(Plane.XZ)


def physical_mesh(mesh: trimesh.Trimesh) -> trimesh.Trimesh:
    """A mesh of the model frame in the physical frame: y negated and the triangle winding reversed, so the normals stay outward and the volume stays positive."""
    return trimesh.Trimesh(vertices=np.asarray(mesh.vertices) @ PHYSICAL.T, faces=np.asarray(mesh.faces)[:, ::-1].copy(), process=False)


def print_rotation(name: str) -> np.ndarray:
    """The turn from a printed part's exported (physical) STL to its print orientation, as a 3 x 3 matrix; the part is then moved so its lowest point stands on the bed at z 0 and its least X and Y at 0."""
    return np.diag([1.0, -1.0, -1.0]) if name in PRINT_TURNED else np.eye(3)


def model_stl_mesh(shape: Any) -> trimesh.Trimesh:
    """A model-frame shape tessellated as the STL export tessellates it (0.01 mm, 0.1 rad) and carried to the physical frame.

    The mesh is reflected, not the solid: a reflected solid tessellates differently (a 45 degree cone gains facets a little
    flatter than 45 degrees), and the printability figures are stated on the facets of the model's own tessellation."""
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "part.stl")
        export_stl(shape, path, tolerance=0.01, angular_tolerance=0.1)
        return physical_mesh(trimesh.load(path, process=False))


def print_mesh(mesh: trimesh.Trimesh, name: str) -> trimesh.Trimesh:
    """A printed part's physical mesh in its stated print orientation, on the bed (turned by `print_rotation`, a proper rotation, then moved so its lowest point is at z 0 and its least X and Y at 0)."""
    turned = np.asarray(mesh.vertices) @ print_rotation(name).T
    return trimesh.Trimesh(vertices=turned - turned.min(axis=0), faces=np.asarray(mesh.faces).copy(), process=False)


class InsertRefused(ValueError):
    """The heat-set insert's hole is outside what its maker publishes, or the seat fails its check, so nothing is exported."""


def export_all(m: Model, out: str, forms: Sequence[str] = ("single", "two")) -> List[str]:
    import check  # the check imports this module; the insert's seat is refused here, on every export path, as the check refuses it
    seat = check.tray_insert_seat(m)
    if not seat["passed"]:
        raise InsertRefused(seat["summary"])
    os.makedirs(out, exist_ok=True)
    written = []
    meshes = {}
    for name in ("tray", "plate", "lid_single", "lid_two", "lid_swap", "tray_swap"):
        if name not in m.parts:
            continue
        step = os.path.join(out, f"{name}.step")
        stl = os.path.join(out, f"{name}.stl")
        export_step(physical(m.parts[name]), step)
        meshes[name] = model_stl_mesh(m.parts[name])
        meshes[name].export(stl)
        written += [step, stl]
    for name in PRINTED:
        if name in meshes:
            stl = os.path.join(out, f"{name}.print.stl")
            print_mesh(meshes[name], name).export(stl)
            written.append(stl)
    for form in forms:
        written.append(write_3mf(m, form, os.path.join(out, f"case-{form}.3mf")))
    written.append(plate_drawing_svg(m, os.path.join(out, "plate-drawing.svg")))
    written.append(case_drawings_svg(m, os.path.join(out, "case-drawings.svg")))
    return written


def part_colours(m: Model, form: str) -> Dict[str, str]:
    P = m.P
    colours = {"tray": P(f"forms.{form}.tray_colour"), f"lid_{form}": P(f"forms.{form}.lid_colour"),
               "plate": P("forms.plate_colour")}
    if form == "two":
        if "lid_swap" in m.parts:
            colours["lid_swap"] = P("forms.two.lid_floor_colour")
        if "tray_swap" in m.parts:
            colours["tray_swap"] = P("forms.two.tray_floor_colour")
    return colours


def colour_solids(m: Model, form: str) -> Dict[str, Any]:
    """The solid each coloured object of a colour form carries. In the two-colour form the swap parts are their own objects and the base
    parts have their band removed, so no two objects overlap."""
    shapes = {name: m.parts[name] for name in part_colours(m, form)}
    if form == "two":
        for base, swap in (("lid_two", "lid_swap"), ("tray", "tray_swap")):
            if swap in shapes:
                shapes[base] = m.parts[base] - m.parts[swap]
    return shapes


def write_3mf(m: Model, form: str, path: str) -> str:
    """One 3MF per colour form, every part a separate object with its own colour."""
    import lib3mf
    wrapper = lib3mf.Wrapper()
    model = wrapper.CreateModel()
    model.SetUnit(lib3mf.ModelUnit.MilliMeter)
    group = model.AddBaseMaterialGroup()
    colours = part_colours(m, form)
    index = {}
    for name, colour in colours.items():
        r, g, b = int(colour[1:3], 16), int(colour[3:5], 16), int(colour[5:7], 16)
        index[name] = group.AddMaterial(name, wrapper.RGBAToColor(r, g, b, 255))
    shapes = colour_solids(m, form)
    for name in colours:
        mesh = physical_mesh(to_mesh(shapes[name], tolerance=0.01))
        obj = model.AddMeshObject()
        obj.SetName(name)
        positions, triangles = [], []
        for x, y, z in mesh.vertices:
            p = lib3mf.Position()
            p.Coordinates[0], p.Coordinates[1], p.Coordinates[2] = float(x), float(y), float(z)
            positions.append(p)
        for a, b, c in mesh.faces:
            t = lib3mf.Triangle()
            t.Indices[0], t.Indices[1], t.Indices[2] = int(a), int(b), int(c)
            triangles.append(t)
        obj.SetGeometry(positions, triangles)
        obj.SetObjectLevelProperty(group.GetResourceID(), index[name])
        model.AddBuildItem(obj, wrapper.GetIdentityTransform())
    model.QueryWriter("3mf").WriteToFile(path)
    return path


SVG_HEAD = '<?xml version="1.0" encoding="UTF-8"?>\n<svg xmlns="http://www.w3.org/2000/svg" width="{w}mm" height="{h}mm" viewBox="{vb}">\n'


def _poly_path(points: Sequence[Tuple[float, float]], fy) -> str:
    return " ".join(f"{x:.3f},{fy(y):.3f}" for x, y in points)


def wrap_lines(lines: Sequence[str], width_mm: float, size: float = 1.9) -> List[str]:
    """Lines broken to fit a sheet width, a monospace character being about 0.6 of the font size wide."""
    import textwrap
    chars = max(20, int(width_mm / (0.6 * size)))
    out: List[str] = []
    for line in lines:
        out += textwrap.wrap(line, chars) or [""]
    return out


class Sheet:
    """A small SVG writer in millimetres at 1:1, with text kept inside the sheet."""

    def __init__(self, width: float, height: float, title: str):
        self.width, self.height = width, height
        self.parts: List[str] = [SVG_HEAD.format(w=f"{width:.2f}", h=f"{height:.2f}", vb=f"0 0 {width:.3f} {height:.3f}"),
                                 f"<title>{escape(title)}</title>\n",
                                 '<rect width="100%" height="100%" fill="#ffffff"/>\n',
                                 '<g font-family="monospace" font-size="2.1" fill="#111">\n']

    def poly(self, pts: Sequence[Tuple[float, float]], style: str) -> None:
        self.parts.append('<polygon points="' + " ".join(f"{x:.3f},{y:.3f}" for x, y in pts) + f'" style="{style}"/>\n')

    def line(self, a: Tuple[float, float], b: Tuple[float, float], style: str) -> None:
        self.parts.append(f'<line x1="{a[0]:.3f}" y1="{a[1]:.3f}" x2="{b[0]:.3f}" y2="{b[1]:.3f}" style="{style}"/>\n')

    def circle(self, c: Tuple[float, float], r: float, style: str) -> None:
        self.parts.append(f'<circle cx="{c[0]:.3f}" cy="{c[1]:.3f}" r="{r:.3f}" style="{style}"/>\n')

    def text(self, x: float, y: float, s: str, fill: str = "#111", size: float = 2.1, anchor: str = "start") -> None:
        self.parts.append(f'<text x="{x:.2f}" y="{y:.2f}" fill="{fill}" font-size="{size}" text-anchor="{anchor}">{escape(s)}</text>\n')

    def shape(self, g: Any, fx, fy, style: str) -> None:
        for poly in (g.geoms if hasattr(g, "geoms") else [g]):
            if poly.is_empty:
                continue
            self.poly([(fx(x), fy(y)) for x, y in poly.exterior.coords], style)
            for ring in poly.interiors:
                self.poly([(fx(x), fy(y)) for x, y in ring.coords], style)

    def save(self, path: str) -> str:
        open(path, "w", encoding="utf-8").write("".join(self.parts) + "</g>\n</svg>\n")
        return path


def plate_drawing_svg(m: Model, path: str) -> str:
    """The plate drawing at 1:1, seen from the case side (the inner face, looking toward the wall; u to the right, z up): outline, screws, bolt zones and the length arithmetic. The tapped tab holes enter this inner face; the countersinks are on the back face, the wall face, and show here by their head diameter."""
    P = m.P
    pl = m.info["plate"]
    e = case_extent(m)
    L, H = pl["u1"] - pl["u0"], pl["z1"] - pl["z0"]
    margin = 10.0
    sheet = Sheet(L + 2 * margin, H + 2 * margin + 52, "Spreader plate drawing, 1:1, seen from the case side (the inner face)")
    fx = lambda u: margin + (u - pl["u0"])  # noqa: E731
    fy = lambda z: margin + 14 + (pl["z1"] - z)  # noqa: E731
    for i, t in enumerate(wrap_lines(["SPREADER PLATE, a standard flat aluminium bar, nothing cut from it but its holes, seen from the case side (the inner face, looking toward the wall, the case's far end behind the viewer), 1:1, millimetres. "
                                      f"{H:.0f} mm wide (its height installed) x {P('plate.thickness_mm'):.0f} mm thick, cut to {L:.0f} mm long. Its lower edge rests on the tray's end-wall ledge, z {pl['z0']:.1f} above the board face; its upper edge stands at z {pl['z1']:.1f}. "
                                      f"The case holds at any height from {P('plate.height_min_mm'):.1f} to {P('plate.height_max_mm'):.1f} mm; the standard widths between are 20 and 25 mm. The stock's width tolerance is an assumption, to be read from the supplier's standard when the bar is sourced."], L, 2.0)):
        sheet.text(margin, margin + 2 + 3.6 * i, t, size=2.0)
    sheet.poly([(fx(pl["u0"]), fy(pl["z1"])), (fx(pl["u1"]), fy(pl["z1"])), (fx(pl["u1"]), fy(pl["z0"])), (fx(pl["u0"]), fy(pl["z0"]))],
               "fill:#e9ebee;stroke:#000;stroke-width:0.25")
    sheet.poly([(fx(e["u0"]), fy(e["z1"])), (fx(e["u1"]), fy(e["z1"])), (fx(e["u1"]), fy(e["z0"])), (fx(e["u0"]), fy(e["z0"]))],
               "fill:none;stroke:#06c;stroke-width:0.2;stroke-dasharray:1.5 1")
    sheet.text(fx(e["u0"]) + 1, fy(e["z1"]) + 3, f"case outline {e['u1'] - e['u0']:.2f} x {e['z1'] - e['z0']:.2f}", fill="#06c", size=1.9)
    bz = P("plate.bolt_zone_mm")
    for end, sign, name in ((pl["u0"], 1, "left"), (pl["u1"], -1, "right")):
        x0 = end if sign > 0 else end - bz
        sheet.poly([(fx(x0), fy(pl["z1"])), (fx(x0 + bz), fy(pl["z1"])), (fx(x0 + bz), fy(pl["z0"])), (fx(x0), fy(pl["z0"]))],
                   "fill:#fbe7cf;fill-opacity:0.7;stroke:#c60;stroke-width:0.12;stroke-dasharray:1 1")
        for cz in pl["bolt_zs"]:
            cx = end + sign * bz / 2
            sheet.circle((fx(cx), fy(cz)), P("plate.bolt_washer_dia_mm") / 2, "fill:none;stroke:#c60;stroke-width:0.12")
            sheet.circle((fx(cx), fy(cz)), P("plate.bolt_dia_mm") / 2 + 0.25, "fill:#fff;stroke:#000;stroke-width:0.2")
        sheet.text(fx(x0 + bz / 2), fy(pl["z0"]) + 4, f"bolt zone {bz:.1f}", fill="#c60", size=1.9, anchor="middle")
    for u in pilaster_u(m):
        for z in P("screws.tray_plate_z_mm"):
            sheet.circle((fx(u), fy(z)), P("screws.tray_plate_countersink_dia_mm") / 2, "fill:#fff;stroke:#000;stroke-width:0.2")
            sheet.circle((fx(u), fy(z)), P("screws.tray_plate_head_dia_mm") / 2, "fill:none;stroke:#000;stroke-width:0.12")
            sheet.circle((fx(u), fy(z)), 1.7, "fill:#9a9a9a;stroke:#000;stroke-width:0.12")
    seat = P.entry("seating.body_underside_mm")
    nominal = seat["value"] + P("triac.A_mm") - P("triac.L_mm")
    lo = seat["min"] + P("triac.A_mm") - P("triac.L_mm")
    hi = seat["max"] + P("triac.A_mm") - P("triac.L_mm")
    for i, ref in enumerate(TRIAC_REFS):
        u = m.triac_u[ref]
        sheet.line((fx(u), fy(lo)), (fx(u), fy(hi)), "stroke:#c00;stroke-width:1.2;stroke-opacity:0.35")
        sheet.circle((fx(u), fy(nominal)), P("triac.plate_tap_drill_mm") / 2 + 0.3, "fill:#fff;stroke:#c00;stroke-width:0.25")
        sheet.text(fx(u) + (-3 if i == 0 else 3), fy(nominal) - 2.5, f"{ref} tab screw u {u:.2f} z {nominal:.2f}", fill="#c00", size=1.8, anchor="end" if i == 0 else "start")
    ty = fy(pl["z0"]) + 12
    edge = P("plate.lower_edge_z_mm")
    lines = [
        "Red bar: the tab hole height range %.2f to %.2f above the board face (nominal %.2f). The tab holes stand %.2f to %.2f mm (nominal %.2f) above the bar's lower edge, the distance to mark and drill from the lower edge: M3 holes (tapping drill %.1f) drilled and tapped through the whole bar from this face; the screws are M3 x %.0f." % (
            lo, hi, nominal, lo - edge, hi - edge, nominal - edge, P("triac.plate_tap_drill_mm"), P("triac.tab_screw_length_mm")),
        "The range is unconfirmed: the owner measures the delivered board before marking the bar.",
        "Two M3 countersunk holes, one for each pilaster's insert, countersunk on the back face (the wall face, away from the viewer; countersink %.1f across, for the %.1f mm head shown by the inner circle), take the tray screws at z %s above the board face (%s above the lower edge), the two %.1f mm or more apart. Set each M3 heat-set insert flush and square in its pilaster's end face before the bar is fitted: a proud insert holds the tray off the bar. The bar's two tray-screw holes are marked from the printed tray with the bar seated on its ledge, then drilled and countersunk until each head sits flush with or below the back face; the back face lies on the machine wall. The two M3 tapped-through holes enter the inner face drawn here." % (
            P("screws.tray_plate_countersink_dia_mm"), P("screws.tray_plate_head_dia_mm"), ", ".join(f"{z:g}" for z in P("screws.tray_plate_z_mm")), ", ".join(f"{z - edge:g}" for z in P("screws.tray_plate_z_mm")), P("plate.min_head_to_head_mm")),
        "Wall bolts M4, one at the plate's mid-height (z %.2f) at each end, washer dia %.1f, standing in the %.1f mm end zones outside the case." % (pl["cz"], P("plate.bolt_washer_dia_mm"), bz),
        "Length arithmetic: case outer width at the plate %.2f + 2 x bolt zone %.1f = %.2f, not more than the plate length %.1f (margin %.2f)." % (
            e["u1"] - e["u0"], bz, e["u1"] - e["u0"] + 2 * bz, L, L - (e["u1"] - e["u0"] + 2 * bz)),
        "Wall opening = the plate and the tray's end wall together + %.1f per side: %.1f x %.1f, within the unit's opening in the plastic wall (z %.1f to %.1f)." % (
            wall_opening(m)["clearance"], wall_opening(m)["u1"] - wall_opening(m)["u0"], wall_opening(m)["z1"] - wall_opening(m)["z0"],
            P("plate.unit_opening_bottom_z_mm"), P("plate.unit_opening_top_z_mm")),
        "Interface material between the triac faces and the plate, and between the plate and the wall, is not in the catalogue and is stated in the case record.",
    ]
    lines = wrap_lines(lines, L, 1.9)
    for i, line in enumerate(lines):
        sheet.text(margin, ty + 3.4 * i, line, size=1.9)
    sheet.height = max(sheet.height, ty + 3.4 * len(lines) + margin)
    sheet.parts[0] = SVG_HEAD.format(w=f"{sheet.width:.2f}", h=f"{sheet.height:.2f}", vb=f"0 0 {sheet.width:.3f} {sheet.height:.3f}")
    return sheet.save(path)


def case_drawings_svg(m: Model, path: str) -> str:
    """Plan and two elevations of the case at 1:1 with the push-on direction, board supports, screw centres, driver lines and slot clearances."""
    P = m.P
    from shapely import union_all
    tray_mesh, lid_mesh = m.mesh("tray"), m.mesh("lid_single")

    def silhouette(mesh: trimesh.Trimesh, ax: Tuple[int, int]) -> Any:
        tri = mesh.vertices[mesh.faces][:, :, list(ax)]
        polys = [ShPolygon(t) for t in tri if abs((t[1, 0] - t[0, 0]) * (t[2, 1] - t[0, 1]) - (t[2, 0] - t[0, 0]) * (t[1, 1] - t[0, 1])) > 1e-9]
        return union_all([p.buffer(0.001) for p in polys]).simplify(0.02)

    sil = {k: unary_union([silhouette(tray_mesh, ax), silhouette(lid_mesh, ax)]) for k, ax in (("plan", (0, 1)), ("side", (1, 2)), ("end", (0, 2)))}
    pl = m.info["plate"]
    op = P("plate.wall_opening_clearance_mm")
    margin, gap = 10.0, 16.0
    plan_box = (-8.0, -8.0, 56.0, 86.0)             # u0, v0, u1, v1
    side_box = (-8.0, min(pl["z0"], m.z_floor_bottom) - 2, 86.0, pl["z1"] + 2)   # v0, z0, v1, z1
    wo = wall_opening(m)
    end_box = (wo["u0"] - 2, wo["z0"] - 2, wo["u1"] + 2, wo["z1"] + 2)
    pw, ph = plan_box[2] - plan_box[0], plan_box[3] - plan_box[1]
    sw, sh = side_box[2] - side_box[0], side_box[3] - side_box[1]
    ew, eh = end_box[2] - end_box[0], end_box[3] - end_box[1]
    right_w = max(sw, ew)
    width = margin + pw + gap + right_w + margin
    height = margin + 16 + max(ph, sh + gap + 16 + eh) + 70
    sheet = Sheet(width, height, "Case drawings: plan, side elevation and end elevation, 1:1, millimetres")
    plan_o = (margin, margin + 16)
    side_o = (margin + pw + gap, margin + 16)
    end_o = (margin + pw + gap, margin + 16 + sh + gap + 14)
    pfx = lambda u: plan_o[0] + (u - plan_box[0])  # noqa: E731
    pfy = lambda v: plan_o[1] + (v - plan_box[1])  # noqa: E731
    sfx = lambda v: side_o[0] + (v - side_box[0])  # noqa: E731
    sfy = lambda z: side_o[1] + (side_box[3] - z)  # noqa: E731
    efx = lambda u: end_o[0] + (u - end_box[0])  # noqa: E731
    efy = lambda z: end_o[1] + (end_box[3] - z)  # noqa: E731

    for i, t in enumerate(wrap_lines(["HEATER WALL BOARD CASE: plan, side and end elevation, each a true view of the physical object from the side its title names. Millimetres, 1:1. Case frame: u across the board 0 to 45, v from the board's plate edge, z up from the board face; the plan is seen from the lid side (the lid faces down when installed), so v runs down the sheet."], width - 2 * margin, 2.2)):
        sheet.text(margin, margin + 2 + 3.6 * i, t, size=2.2)
    # ---- plan
    sheet.text(plan_o[0], plan_o[1] - 3, "PLAN (seen from the lid side, looking at the board's component face, as the board's layout is drawn: plate at the top, u to the right)", size=2.0)
    sheet.shape(sil["plan"], pfx, pfy, "fill:#eef0f2;stroke:#000;stroke-width:0.2")
    sheet.shape(m.board.outline, pfx, pfy, "fill:none;stroke:#080;stroke-width:0.15;stroke-dasharray:1 0.6")
    sheet.line((pfx(plan_box[0]), pfy(m.v_plate)), (pfx(plan_box[2]), pfy(m.v_plate)), "stroke:#555;stroke-width:0.8")
    sheet.text(pfx(plan_box[0]) + 1, pfy(m.v_plate) - 1.5, "plate inner face", fill="#555", size=1.8)
    for s in m.supports:
        if s["kind"] == "pillar":
            h = s["size"] / 2
            sheet.shape(sh_box(s["u"] - h, s["v"] - h, s["u"] + h, s["v"] + h), pfx, pfy, "fill:#d79bc0;stroke:#000;stroke-width:0.1")
        elif s["kind"] == "h1 boss":
            sheet.shape(Point(s["u"], s["v"]).buffer(s["size"] / 2), pfx, pfy, "fill:#d79bc0;stroke:#000;stroke-width:0.1")
        elif s["kind"] == "backing rib":
            sheet.shape(sh_box(s["u0"], s["v0"], s["u1"], s["v1"]), pfx, pfy, "fill:#e8873f;stroke:#000;stroke-width:0.1")
        elif s["kind"] == "buttress":
            sheet.shape(sh_box(s["u"] - 0.6, s["v0"], s["u"] + 0.6, s["v1"]), pfx, pfy, "fill:#f0b27a;stroke:#000;stroke-width:0.1")
    for slot in m.board.slots:
        sheet.shape(slot, pfx, pfy, "fill:#fff;stroke:#c00;stroke-width:0.2")
        sheet.shape(slot.buffer(P("seat.slot_keepout_mm")), pfx, pfy, "fill:none;stroke:#c00;stroke-width:0.1;stroke-dasharray:0.8 0.8")
        v = slot.centroid.y
        right_in = 45.0 + P("case.interior_right_mm")
        sheet.line((pfx(45.0), pfy(v)), (pfx(right_in), pfy(v)), "stroke:#c00;stroke-width:0.15")
        sheet.text(pfx(right_in) + 1.5, pfy(v) + 0.7, f"mouth {right_in - 45.0:.1f} to wall (needs {P('seat.slot_keepout_mm'):.1f})", fill="#c00", size=1.7)
    for s in m.screws:
        if s["kind"] in ("lid", "h1"):
            sheet.circle((pfx(s["u"]), pfy(s["v"])), s["radius"], "fill:#000")
            label = "lid screw, driven from +z" if s["kind"] == "lid" else "H1 screw"
            sheet.text(pfx(s["u"]) + 3.5, pfy(s["v"]) + 0.7, f"{label} ({s['u']:.2f}, {s['v']:.2f})", size=1.7)
        elif s["kind"] == "tray_plate":
            sheet.line((pfx(s["u"]), pfy(s["v0"])), (pfx(s["u"]), pfy(s["v1"])), f"stroke:#000;stroke-width:{2 * s['radius']:.2f};stroke-opacity:0.45")
    tilts = {ref: driver_tilt(m, ref)[0] for ref in TRIAC_REFS}
    m.info["driver_tilt_deg"] = tilts
    for ref, ang in tilts.items():
        u = m.triac_u[ref]
        v0 = m.v_plate + P("triac.b2_mm") + P("triac.tab_screw_head_height_mm")
        sheet.line((pfx(u), pfy(v0)), (pfx(u), pfy(84)), "stroke:#06c;stroke-width:0.4;stroke-dasharray:2 1")
        sheet.text(pfx(u) + 1.5, pfy(50 if ref == "T921" else 24), f"driver line {ref} u {u:.1f}", fill="#06c", size=1.7)
    hv = P("seat.finger_v_mm")
    sheet.line((pfx(-0.5), pfy(hv)), (pfx(1.0), pfy(hv)), "stroke:#080;stroke-width:1.4")
    sheet.text(pfx(1.6), pfy(hv) + 0.7, "hold-down finger", fill="#080", size=1.7)
    # ---- side elevation
    sheet.text(side_o[0], side_o[1] - 3, "SIDE ELEVATION (seen from the low-u side, the hold-down finger's wall; plate at left, v to the right)", size=2.0)
    sheet.shape(sil["side"], sfx, sfy, "fill:#eef0f2;stroke:#000;stroke-width:0.2")
    bb = m.bodies["board"]["shape"].bounding_box()
    sheet.shape(sh_box(bb.min.Y, bb.min.Z, bb.max.Y, bb.max.Z), sfx, sfy, "fill:#7fbf9a;stroke:#000;stroke-width:0.1")
    sheet.shape(sh_box(m.v_plate - P("plate.thickness_mm"), pl["z0"], m.v_plate, pl["z1"]), sfx, sfy, "fill:#bfc7ca;stroke:#000;stroke-width:0.15")
    for ref in TRIAC_REFS[:1]:
        body = m.bodies[f"{ref}_body"]["shape"].bounding_box()
        sheet.shape(sh_box(body.min.Y, body.min.Z, body.max.Y, body.max.Z), sfx, sfy, "fill:#858a90;stroke:#000;stroke-width:0.1")
    cv = sum(p["v"] for p in m.board.refs["J921"]["pads"]) / 2
    ztop = P("case.z_lid_top_mm")
    sheet.line((sfx(cv), sfy(ztop + 12)), (sfx(cv), sfy(ztop + 2.5)), "stroke:#c00;stroke-width:0.6")
    sheet.poly([(sfx(cv) - 1.4, sfy(ztop + 4.5)), (sfx(cv) + 1.4, sfy(ztop + 4.5)), (sfx(cv), sfy(ztop + 1.8))], "fill:#c00")
    sheet.text(sfx(cv) + 2.5, sfy(ztop + 8), "push-on -z", fill="#c00", size=1.8)
    for s in m.screws:
        if s["axis"] == "v":
            sheet.line((sfx(s["v0"]), sfy(s["z"])), (sfx(s["v1"]), sfy(s["z"])), f"stroke:#000;stroke-width:{2 * s['radius']:.2f}")
        elif s["axis"] == "z":
            sheet.line((sfx(s["v"]), sfy(s["z0"])), (sfx(s["v"]), sfy(s["z1"])), f"stroke:#000;stroke-width:{2 * s['radius']:.2f}")
    for ref, ang in tilts.items():
        v0 = m.v_plate + P("triac.b2_mm") + P("triac.tab_screw_head_height_mm")
        t = math.tan(math.radians(ang))
        sheet.line((sfx(v0), sfy(m.tab_hole_z)), (sfx(v0 + 80), sfy(m.tab_hole_z + 80 * t)), "stroke:#06c;stroke-width:0.4;stroke-dasharray:2 1")
    sheet.text(sfx(30), sfy(m.tab_hole_z + 30 * math.tan(math.radians(max(tilts.values())))) - 3, "driver approach to the tab screws, lid off", fill="#06c", size=1.7)
    rib = next(s for s in m.supports if s["kind"] == "backing rib")
    sheet.text(side_o[0], sfy(P("case.z_floor_bottom_mm")) + 5, "backing rib (v %.1f) under J911, J921, J941 carries the push-on load to the floor" % ((rib["v0"] + rib["v1"]) / 2), size=1.7)
    # ---- end elevation
    sheet.text(end_o[0], end_o[1] - 3, "END ELEVATION (seen from the far end, looking toward the wall; u to the right)", size=2.0)
    sheet.shape(sh_box(end_box[0], end_box[1], end_box[2], end_box[3]), efx, efy, "fill:none")
    sheet.shape(sh_box(pl["u0"], pl["z0"], pl["u1"], pl["z1"]), efx, efy, "fill:#dfe3e6;stroke:#444;stroke-width:0.15")
    sheet.shape(sh_box(wo["u0"], wo["z0"], wo["u1"], wo["z1"]), efx, efy, "fill:none;stroke:#c60;stroke-width:0.15;stroke-dasharray:3 1")
    sheet.shape(sil["end"], efx, efy, "fill:#eef0f2;stroke:#000;stroke-width:0.2")
    for u in m.info["tray_pilaster_u"]:
        for z in P("screws.tray_plate_z_mm"):
            sheet.circle((efx(u), efy(z)), P("screws.tray_plate_dia_mm") / 2, "fill:#000")
    for ref in TRIAC_REFS:
        sheet.circle((efx(m.triac_u[ref]), efy(m.tab_hole_z)), P("triac.tab_screw_dia_mm") / 2, "fill:#000")
    sheet.text(efx(wo["u0"]) + 1, efy(wo["z1"]) - 1.2, f"wall opening = the plate and the end wall + {op:.1f} per side", fill="#c60", size=1.7)
    # ---- legend
    ly = margin + 16 + max(ph, sh + gap + 14 + eh) + 8
    legend = [
        "Board is held by: 11 pillars and the H1 boss and screw (seat plane tilted with the board's lean), the backing rib, the hold-down finger on the left wall and the locating ribs. The lid holds nothing.",
        "Lid: two toes under hooks on the pilasters at the plate end, one M3 x 10 countersunk screw from +z at the far end. It comes off by lifting the far end and drawing it out along the pilaster grooves.",
        "Tray to plate: two M3 x %.0f countersunk screws, one in each pilaster, from the plate's back face into an M3 heat-set insert set flush in the pilaster's end face; the inserts are set flush and square before the bar is fitted (a proud insert holds the tray off the bar), and the bar's two holes are marked from the printed tray with the bar seated on its ledge, each countersunk head sitting flush with or below the bar's back face. Tab screws: M3 x 5 through the tab into the plate's tapped-through holes, reached with the lid off along the blue lines." % P("screws.tray_plate_length_mm"),
        "No barrier: the plate's lower edge stands %.1f mm above the board face, resting on the tray's end-wall ledge, so no plate metal faces the board edge, the pads or the leads; the tray's printed end wall fills the volume the plate leaves, unfilled plastic with no creepage credit." % P("plate.lower_edge_z_mm"),
        "Opening in the plastic wall: the plate and the end wall together plus %.1f per side. Slot mouths keep %.1f mm of clear air to the right wall." % (op, 3.0),
    ]
    legend = wrap_lines(legend, width - 2 * margin, 1.8)
    for i, line in enumerate(legend):
        sheet.text(margin, ly + 3.2 * i, line, size=1.8)
    sheet.height = ly + 3.2 * len(legend) + margin
    sheet.parts[0] = SVG_HEAD.format(w=f"{sheet.width:.2f}", h=f"{sheet.height:.2f}", vb=f"0 0 {sheet.width:.3f} {sheet.height:.3f}")
    return sheet.save(path)


# ---------------------------------------------------------------------------------------------------------------------
# Command line
# ---------------------------------------------------------------------------------------------------------------------

def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Build the printed case of the heater wall board and export it.")
    parser.add_argument("--out", default=os.path.join(HERE, "out"), help="folder the exports are written to")
    parser.add_argument("--set", action="append", default=[], metavar="KEY=VALUE",
                        help="override a params.yaml value, e.g. seating.body_underside_mm=2.55")
    parser.add_argument("--form", choices=("single", "two", "both"), default="both")
    parser.add_argument("--skin", help="the skin to build (flow); the params.yaml default when omitted")
    args = parser.parse_args(argv)
    forms = ("single", "two") if args.form == "both" else (args.form,)
    model = build(parse_overrides(args.set), forms, args.skin)
    try:
        written = export_all(model, args.out, forms)
    except InsertRefused as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 1
    for path in written:
        print(os.path.relpath(path, HERE))
    return 0


if __name__ == "__main__":
    sys.exit(main())
