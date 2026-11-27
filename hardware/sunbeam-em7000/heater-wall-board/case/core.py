"""The safety core of the printed case: what no skin may change.

The core owns the pilasters and their end faces, the board seat and everything that follows the seating
scatter, the slot stand-off and the slot mouths, every screw position and boss, the blade and cable apertures and their
minimum sizes, the louvre safety rules (the gill angle, the slot width, the field of the lid in which a through-slot may
stand and its distance from the apertures and the lid screw) and the envelope limits. The envelope is two plan polygons:

    keep_in    the cavity the board and its parts need, a minimum wall round it, the pilasters and the lid screw's boss;
    keep_out   the most a plan outline may occupy: the plate's outline less the wall-bolt access zones, the length limit
               and, for anything that stands the whole height of the wall, the path of the lid's toes.

A skin draws plan outlines between the two; `Core.validate_outline` refuses an outline that leaves either polygon. The
checks read the core for every safety figure and the meshes for everything the skin shapes.

The core also owns the installed orientation (`installed` in params.yaml: the plate vertical, the board's component side
down), the receptacle boots' envelopes and the blade bays sized from them, the outlet slits' permitted zone and width, and
the floor under an engraved groove.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
from shapely.geometry import LineString, MultiPolygon, Point, Polygon as ShPolygon, box as sh_box
from shapely.ops import unary_union

from solids import clean_polygon, polyhedron_between

Point2 = Tuple[float, float]


class OutlineRefused(ValueError):
    """A plan outline that leaves the space between the keep-in and the keep-out polygons."""


# ---------------------------------------------------------------------------------------------------------------------
# Frame figures the core owns
# ---------------------------------------------------------------------------------------------------------------------

def case_extent(m: Any) -> Dict[str, float]:
    """The tray's outer extent in u and z at the pilasters, which the plate is centred on."""
    P = m.P
    pil = P("case.pilaster_out_mm")
    wall = P("case.wall_mm")
    left = -P("case.interior_left_mm") - wall - pil
    right = 45.0 + P("case.interior_right_mm") + wall + pil
    return {"u0": left, "u1": right, "z0": m.z_floor_bottom, "z1": P("case.z_lid_top_mm")}


def pilaster_u(m: Any) -> Tuple[float, float]:
    P = m.P
    wall = P("case.wall_mm")
    left_in, right_in = -P("case.interior_left_mm"), 45.0 + P("case.interior_right_mm")
    pil = P("case.pilaster_out_mm")
    return ((left_in - wall - pil + left_in) / 2, (right_in + right_in + wall + pil) / 2)


def toe_u(m: Any) -> Tuple[float, float]:
    """The u of the pocket and toe in each pilaster: toward the outer face, so the toe clears the wall when the lid slides out."""
    off = m.P("lid.toe_from_outer_mm")
    e = case_extent(m)
    return (e["u0"] + off, e["u1"] - off)


def pocket_profile(m: Any) -> List[Point2]:
    """The pilaster pocket in (offset from the plate-end face, z): a groove open at its +v end with an undercut lobe under a hook."""
    P = m.P
    zt = P("case.z_wall_top_mm")
    zl = zt - 4.0
    k = P("printer.roof_slope")
    end = P("case.pilaster_len_mm") + 0.75
    run = 1.2 / k
    return [(0.8, zt - 3.35), (0.8, zt - 2.05), (0.8 + run, zt - 0.85), (0.8 + run, zt + 0.5), (end, zt + 0.5), (end, zl),
            (2.0, zl), (2.0, zt - 3.35)]


def toe_profile(m: Any) -> List[Point2]:
    """The lid toe in (offset from the plate-end face, z): a finger with a barb whose upper face lies 0.3 under the hook's roof."""
    P = m.P
    zt = P("case.z_wall_top_mm")
    za = P("case.z_lid_under_mm")
    k = P("printer.roof_slope")
    tip_v, root_v, finger_far = 1.1, 2.6, 5.1
    roof_c = (zt - 2.05) - k * 0.8                 # the roof's line: z = roof_c + k v
    c = roof_c - 0.3                               # the barb's upper face, 0.3 under it
    tip_z = c + k * tip_v
    top_root_z = c + k * root_v
    z_end = zt - 3.75
    if not P("lid.toe_barb"):
        return [(root_v, za + 0.01), (finger_far, za + 0.01), (finger_far, z_end), (root_v, z_end)]
    return [(root_v, za + 0.01), (finger_far, za + 0.01), (finger_far, z_end), (root_v, z_end), (root_v, tip_z - 1.0), (tip_v, tip_z),
            (root_v, top_root_z)]


LOCATING_RIB_V = (14.0, 44.0)       # the locating ribs standing against the left wall (v of each centre)
LOCATING_RIB_HALF = 1.0             # half of a locating rib's length along v


def gravity(m: Any) -> np.ndarray:
    """The installed direction of gravity as a unit vector in the case frame (params.yaml `installed`)."""
    g = np.asarray(m.P("installed.gravity"), dtype=float)
    return g / np.linalg.norm(g)


def boot_box(m: Any, which: str) -> Dict[str, float]:
    """A boot envelope: its size across the blade's width (along v), across its thickness (along u) and along the blade."""
    across_w, across_t, length = m.P(f"boots.{which}")
    return {"across_width": float(across_w), "across_thickness": float(across_t), "length": float(length)}


def lean_allowance(m: Any) -> float:
    """How far a boot's axis, tilted by the seating's lean, moves along v by the lid's face: tan(largest lean) x the lid face height."""
    P = m.P
    lean = max(abs(P.entry("seating.lean_deg")["min"]), abs(P.entry("seating.lean_deg")["max"]))
    return math.tan(math.radians(lean)) * P("case.z_lid_top_mm")


def aperture_boxes(m: Any) -> List[Dict[str, Any]]:
    """The blade bays of the lid: the larger of the boots' envelopes and the clearance all round, widened along v by the lean allowance, over each blade."""
    P = m.P
    c = P("lid.aperture_clearance_mm")
    envs = [boot_box(m, name) for name in ("typical", "largest_common")]
    du = max(e["across_thickness"] for e in envs) + 2 * c
    dv = max(e["across_width"] for e in envs) + 2 * c + 2 * lean_allowance(m)
    found = []
    for ref in ("J941", "J921", "J911"):
        pads = m.board.refs[ref]["pads"]
        found.append({"ref": ref, "u": pads[0]["u"], "v": sum(p["v"] for p in pads) / len(pads), "du": du, "dv": dv})
    return found


# ---------------------------------------------------------------------------------------------------------------------
# Vents: the louvre rules and the gill a through-slot is cut as
# ---------------------------------------------------------------------------------------------------------------------

@dataclass
class Vent:
    """A through-slot given by its centre line (u, v points) in the mid-plane of the lid's thickened field.

    The line runs in the direction a reader of the plan follows it; the slot's upper opening lies on its right-hand
    side (the side of -n, n being the line's tangent turned a quarter turn counter-clockwise) and its lower opening on
    the left, which is the gill: the slot plane stands at the louvre angle from the lid's normal.
    """
    points: List[Point2]
    label: str = "vent"

    def length(self) -> float:
        return float(sum(math.dist(a, b) for a, b in zip(self.points, self.points[1:])))


def _tangents_normals(points: Sequence[Point2]) -> Tuple[np.ndarray, np.ndarray]:
    p = np.asarray(points, dtype=float)
    t = np.zeros_like(p)
    t[1:-1] = p[2:] - p[:-2]
    t[0] = p[1] - p[0]
    t[-1] = p[-1] - p[-2]
    t /= np.linalg.norm(t, axis=1)[:, None]
    n = np.stack([-t[:, 1], t[:, 0]], axis=1)
    return t, n


@dataclass
class Outlet:
    """An outlet slit: vertical (long along z) through a long wall, at v, `width` along v, from `z_top` to `z_top + height` (z grows downward when installed)."""
    side: str
    v: float
    width: float
    height: float
    z_top: float = 0.0

    @property
    def z_bottom(self) -> float:
        return self.z_top + self.height


class Core:
    """The core of a built model: its frame figures, its envelope polygons and its vent rules."""

    def __init__(self, m: Any):
        P = m.P
        self.m = m
        self.wall = P("case.wall_mm")
        self.min_wall = P("envelope.min_wall_mm")
        self.pil = P("case.pilaster_out_mm")
        self.v_end = m.v_end
        self.v_pil = m.v_end + P("case.pilaster_len_mm")
        self.left_in = -P("case.interior_left_mm")
        self.right_in = 45.0 + P("case.interior_right_mm")
        self.far_in = P("case.v_far_wall_inner_mm")
        self.far_out = self.far_in + self.wall
        self.left_out = self.left_in - self.wall
        self.right_out = self.right_in + self.wall
        self.lug_depth = P("screws.lug_v_depth_mm")
        self.lug_w = P("screws.lug_u_width_mm")
        self.screw_uv = (P("screws.lid_u_mm"), P("screws.lid_v_mm"))
        self.z_floor_bottom = m.z_floor_bottom
        self.z_wall_top = P("case.z_wall_top_mm")
        self.z_lid_under = P("case.z_lid_under_mm")
        self.z_lid_top = P("case.z_lid_top_mm")
        e = case_extent(m)
        plate_len, bolt = P("plate.length_mm"), P("plate.bolt_zone_mm")
        cu = (e["u0"] + e["u1"]) / 2
        self.keep_out_u = (cu - plate_len / 2 + bolt, cu + plate_len / 2 - bolt)
        self.v_max = self.far_out + self.lug_depth
        # the lowest a toe goes while the lid is drawn out, and the full-height walls' limit beside the toe path
        self.toe_path_z_min = min(z for _, z in toe_profile(m))
        self.low_zone_top = self.toe_path_z_min - P("envelope.toe_path_margin_mm")
        tu = toe_u(m)
        half = P("lid.toe_width_mm") / 2 + P("envelope.toe_path_side_margin_mm")
        self.toe_limits = (tu[0] + half, tu[1] - half)
        self._build_polygons()

    # -- the envelope ---------------------------------------------------------------------------------------------------
    def _build_polygons(self) -> None:
        cavity = sh_box(self.left_in, self.v_end, self.right_in, self.far_in)
        body = cavity.buffer(self.min_wall, join_style=1, resolution=16).intersection(sh_box(-1e3, self.v_end, 1e3, 1e3))
        r = self.m.P("envelope.pilaster_corner_relief_mm")
        lo, ro = self.left_out - self.pil, self.right_out + self.pil
        pil_left = ShPolygon([(lo, self.v_end), (self.left_out, self.v_end), (self.left_out, self.v_pil), (lo + r, self.v_pil), (lo, self.v_pil - r)])
        pil_right = ShPolygon([(self.right_out, self.v_end), (ro, self.v_end), (ro, self.v_pil - r), (ro - r, self.v_pil), (self.right_out, self.v_pil)])
        uc, vc = self.screw_uv
        boss = sh_box(uc - 3.6, self.far_in, uc + 3.6, vc + 3.3)
        self.cavity = cavity
        self.pilasters = (pil_left, pil_right)
        self.keep_in = unary_union([body, pil_left, pil_right, boss])
        u0, u1 = self.keep_out_u
        self.keep_out_low = sh_box(u0, self.v_end, u1, self.v_max)
        left_lim, right_lim = self.toe_limits
        self.keep_out_high = unary_union([sh_box(u0, self.v_end, u1, self.v_pil + 1e-9),
                                          sh_box(left_lim, self.v_end, right_lim, self.v_max)])

    def keep_out(self, layer: str) -> ShPolygon:
        """The most a plan outline may occupy: `low` for a solid whose top stands under the toe path, `high` for a full-height wall."""
        return {"low": self.keep_out_low, "high": self.keep_out_high}[layer]

    def validate_outline(self, outline: Sequence[Point2], layer: str, name: str = "outline") -> ShPolygon:
        """The outline as a polygon, or OutlineRefused naming what it leaves.

        `layer` is `high` for the tray's full-height walls, `low` for a skirt or rib standing under the toe path and for
        the lid, which stands above it.
        """
        poly = ShPolygon(clean_polygon(outline))
        if not poly.is_valid or poly.is_empty:
            raise OutlineRefused(f"{name} is not a simple polygon")
        short = self.keep_in.difference(poly)
        if short.area > 1e-4:
            raise OutlineRefused(f"{name} leaves the keep-in polygon (cavity, minimum wall {self.min_wall:.2f}, pilasters, screw boss): "
                                 f"{short.area:.3f} mm2 of it lies outside, within u {short.bounds[0]:.2f} to {short.bounds[2]:.2f}, "
                                 f"v {short.bounds[1]:.2f} to {short.bounds[3]:.2f}")
        over = poly.difference(self.keep_out(layer))
        if over.area > 1e-4:
            raise OutlineRefused(f"{name} leaves the {layer} keep-out polygon: {over.area:.3f} mm2 of it lies outside, within u "
                                 f"{over.bounds[0]:.2f} to {over.bounds[2]:.2f}, v {over.bounds[1]:.2f} to {over.bounds[3]:.2f}")
        return poly

    # -- the vents --------------------------------------------------------------------------------------------------------
    @property
    def vent_zone(self) -> ShPolygon:
        """The thickened field of the lid, the only place a through-slot may stand, less the land."""
        P = self.m.P
        u0, u1 = P("lid.pad_u_mm")
        v0, v1 = P("lid.pad_v_mm")
        land = P("envelope.vent_land_mm")
        return sh_box(u0 + land, v0 + land, u1 - land, v1 - land)

    def vent_width(self) -> float:
        """The slot width in use: the core's louvre.width_mm, or a narrower one a skin names; never wider."""
        P = self.m.P
        limit = P("louvre.width_mm")
        skin_width = getattr(self.m.skin, "louvre_width", None)
        width = skin_width() if skin_width is not None else limit
        if width > limit + 1e-9:
            raise OutlineRefused(f"the {self.m.skin.name} skin's slot width {width:.2f} exceeds the core's {limit:.2f}")
        return float(width)

    def gill(self) -> Dict[str, float]:
        """The figures of the gill: slot width, angle, the horizontal width of each opening, the shift between the upper and the lower opening."""
        P = self.m.P
        w, angle = self.vent_width(), P("louvre.angle_deg")
        a = math.radians(angle)
        thick = P("lid.top_louvre_mm")
        zt, za = self.z_lid_top, self.z_lid_under
        pad_h = thick - (zt - za)
        zmid = (za - pad_h + zt) / 2
        return {"width": w, "angle": angle, "opening": w / math.cos(a), "shift_per_mm": math.tan(a), "pad_h": pad_h, "zmid": zmid,
                "thickness": thick, "top_shift": (zt - zmid) * math.tan(a), "separation": thick * math.tan(a)}

    def vent_footprint(self, vent: Vent) -> ShPolygon:
        """The plan region a vent's cut passes through from the lid's top face to the underside of its thickened field."""
        g = self.gill()
        t, n = _tangents_normals(vent.points)
        p = np.asarray(vent.points, dtype=float)
        hw = g["opening"] / 2
        pieces = []
        for k in (-1.0, 0.0, 1.0):
            c = p + n * (k * g["top_shift"] * -1.0)
            pieces.append(LineString(c).buffer(hw, cap_style=2, join_style=1))
        return unary_union(pieces)

    def clear_of(self) -> ShPolygon:
        """What a through-slot's footprint keeps vent_clear away from: the aperture boxes with their collars and the lid screw's countersink."""
        P = self.m.P
        wall = P("lid.collar_wall_mm")
        boxes = [sh_box(a["u"] - a["du"] / 2 - wall, a["v"] - a["dv"] / 2 - wall, a["u"] + a["du"] / 2 + wall, a["v"] + a["dv"] / 2 + wall)
                 for a in aperture_boxes(self.m)]
        uc, vc = self.screw_uv
        screw = Point(uc, vc).buffer(P("screws.lid_head_dia_mm") / 2)
        return unary_union(boxes + [screw])

    def vent_problems(self, vent: Vent) -> List[str]:
        """What a vent breaks of the core's rules, empty when it keeps them."""
        P = self.m.P
        g = self.gill()
        problems = []
        fp = self.vent_footprint(vent)
        if not self.vent_zone.contains(fp):
            problems.append("stands outside the lid's thickened field")
        if fp.distance(self.clear_of()) < P("envelope.vent_clear_mm"):
            problems.append("comes within %.1f mm of an aperture, its collar or the lid screw" % P("envelope.vent_clear_mm"))
        if g["opening"] >= P("finger.admits_nothing_below_mm"):
            problems.append("opens wider than the test finger's tip")
        return problems

    def mid_band(self, vent: Vent) -> ShPolygon:
        """The plan region of a vent's cut at the middle of the thickened field."""
        return LineString(vent.points).buffer(self.gill()["opening"] / 2, cap_style=2, join_style=1)

    def web_faults(self, vents: Sequence[Vent]) -> List[Tuple[str, str, float]]:
        """The pairs of vents whose cuts leave less than vent_web_mm of lid between them at the middle of the field."""
        web = self.m.P("envelope.vent_web_mm")
        bands = [self.mid_band(v) for v in vents]
        faults = []
        for i in range(len(vents)):
            for j in range(i + 1, len(vents)):
                d = bands[i].distance(bands[j])
                if d < web - 1e-9:
                    faults.append((vents[i].label, vents[j].label, float(d)))
        return faults

    def admissible_runs(self, line: Sequence[Point2], min_length: float = 3.0, step: float = 0.25,
                        avoid: Optional[ShPolygon] = None) -> List[List[Point2]]:
        """The stretches of a top-face centre line along which a gill slot keeps the core's rules, each at least min_length long.

        The line is the slot's upper opening's centre line; the returned lines are the slot's mid-plane centre lines.
        """
        g = self.gill()
        poly = np.asarray(line, dtype=float)
        seg = np.linalg.norm(np.diff(poly, axis=0), axis=1)
        s = np.concatenate([[0.0], np.cumsum(seg)])
        count = max(int(s[-1] / step), 2)
        grid = np.linspace(0.0, s[-1], count + 1)
        pts = np.stack([np.interp(grid, s, poly[:, 0]), np.interp(grid, s, poly[:, 1])], axis=1)
        t, n = _tangents_normals([tuple(p) for p in pts])
        mid = pts + n * g["top_shift"]
        zone, clear = self.vent_zone, self.clear_of()
        if avoid is not None:
            clear = unary_union([clear, avoid])
        need = self.m.P("envelope.vent_clear_mm")
        hw = g["opening"] / 2
        ok = []
        for i in range(len(pts)):
            probe = [Point(*(pts[i] + n[i] * k)) for k in (0.0, g["top_shift"], 2 * g["top_shift"])]
            good = all(zone.contains(q.buffer(hw)) and q.distance(clear) >= need + hw for q in probe)
            ok.append(good)
        runs, start = [], None
        for i, flag in enumerate(ok + [False]):
            if flag and start is None:
                start = i
            if not flag and start is not None:
                if grid[i - 1] - grid[start] >= min_length:
                    runs.append([tuple(map(float, q)) for q in mid[start:i]])
                start = None
        return runs

    def gill_cutter(self, vent: Vent) -> Any:
        """The solid a vent cuts from the lid: its section, a parallelogram at the louvre angle, swept along its centre line."""
        g = self.gill()
        t, n = _tangents_normals(vent.points)
        p = np.asarray(vent.points, dtype=float)
        hw = g["opening"] / 2
        z_lo, z_hi = g["zmid"] - 2.4, g["zmid"] + 2.4
        rings = []
        for z in (z_lo, z_hi):
            shift = -(z - g["zmid"]) * g["shift_per_mm"]
            left = p + n * (shift + hw)
            right = p + n * (shift - hw)
            rings.append([tuple(q) for q in np.vstack([left, right[::-1]])])
        return polyhedron_between(rings[0], z_lo, rings[1], z_hi)

    def vent_openings(self, vents: Sequence[Vent]) -> List[Dict[str, Any]]:
        """Each vent as an opening for the finger and drip checks: its sizes and the points a line is cast from."""
        g = self.gill()
        ang = math.radians(g["angle"])
        ops = []
        for i, vent in enumerate(vents):
            p = np.asarray(vent.points, dtype=float)
            seg = np.linalg.norm(np.diff(p, axis=0), axis=1)
            s = np.concatenate([[0.0], np.cumsum(seg)])
            length = s[-1]
            t, n = _tangents_normals(vent.points)
            pts = []
            for arc in np.arange(0.5, length - 0.4, 2.0):
                q = np.array([np.interp(arc, s, p[:, 0]), np.interp(arc, s, p[:, 1])])
                nn = np.array([np.interp(arc, s, n[:, 0]), np.interp(arc, s, n[:, 1])])
                nn /= np.linalg.norm(nn)
                for dz in (-0.9, 0.0, 0.9):
                    for dw in (-g["width"] / 2 + 0.1, 0.0, g["width"] / 2 - 0.1):
                        off = dw * math.cos(ang) - dz * math.sin(ang)
                        zz = g["zmid"] + (dw * math.sin(ang) + dz * math.cos(ang))
                        pt = q + nn * off
                        pts.append((float(pt[0]), float(pt[1]), zz))
            mid = len(p) // 2
            ops.append({"id": vent.label, "kind": "louvre", "min_dim": g["width"], "max_dim": float(length), "points": pts,
                        "u": float(p[mid, 0]), "v": float(p[mid, 1]), "z": g["zmid"]})
        return ops

    # -- the outlets ------------------------------------------------------------------------------------------------------
    def outlet_zone(self) -> Dict[str, Dict[str, Any]]:
        """Where an outlet slit may stand in each long wall of the tray, in the installed frame just under the tray's outer top face.

        A slit is a vertical cut (long along z) through the wall; its v range lies between `v0` and `v1` and outside every
        `exclude` interval (the hold-down finger's window and the locating ribs against the wall), and its z range between
        `z0` (a land under the print-bed face) and `z1` (short of the board's front-face plane). No slit stands in the tray's top face.
        """
        P = self.m.P
        v0 = self.v_pil + P("outlets.start_gap_mm")
        v1 = self.far_in - P("outlets.end_gap_mm")
        z0 = self.z_floor_bottom + P("case.floor_mm") + P("outlets.top_land_mm")
        z1 = P("outlets.bottom_limit_z_mm")
        clear = P("outlets.feature_clear_mm")
        left_ex = [(v - LOCATING_RIB_HALF - clear, v + LOCATING_RIB_HALF + clear) for v in LOCATING_RIB_V]
        if P("seat.finger"):
            half = P("seat.finger_width_mm") / 2 + P("seat.finger_slit_mm")
            fv = P("seat.finger_v_mm")
            left_ex.append((fv - half - clear, fv + half + clear))
        return {"left": {"u_in": self.left_in, "u_out": self.left_out, "v0": v0, "v1": v1, "z0": z0, "z1": z1, "exclude": left_ex},
                "right": {"u_in": self.right_in, "u_out": self.right_out, "v0": v0, "v1": v1, "z0": z0, "z1": z1, "exclude": []}}

    def outlet_max_width(self) -> float:
        """The widest an outlet slit may be: the stand-in finger's tip enters no opening narrower than itself, and params.yaml keeps a margin of that."""
        return float(self.m.P("outlets.max_width_mm"))

    def outlet_free(self, side: str, v: float, width: float, height: float) -> bool:
        """Whether a slit of this width and height centred at v stands wholly in the zone, off every exclusion."""
        return not self.outlet_problems(Outlet(side, v, width, height, self.outlet_zone()[side]["z0"]))

    def outlet_problems(self, slit: "Outlet") -> List[str]:
        """What an outlet slit breaks of the core's rules, empty when it keeps them."""
        P = self.m.P
        zone = self.outlet_zone()[slit.side]
        problems = []
        lo, hi = slit.v - slit.width / 2, slit.v + slit.width / 2
        if lo < zone["v0"] - 1e-9 or hi > zone["v1"] + 1e-9:
            problems.append("stands outside the permitted stretch of the wall")
        if any(hi > a - 1e-9 and lo < b + 1e-9 for a, b in zone["exclude"]):
            problems.append("stands against the hold-down finger's window or a locating rib")
        if slit.width > self.outlet_max_width() + 1e-9:
            problems.append("is wider than the stand-in finger's tip allows")
        if slit.height < P("outlets.min_height_mm") - 1e-9 or slit.z_top < zone["z0"] - 1e-9 or slit.z_bottom > zone["z1"] + 1e-9:
            problems.append("stands outside the permitted height of the wall")
        return problems

    def outlet_web_faults(self, slits: Sequence["Outlet"]) -> List[Tuple[int, int, float]]:
        web = self.m.P("outlets.web_mm")
        faults = []
        for i in range(len(slits)):
            for j in range(i + 1, len(slits)):
                a, b = slits[i], slits[j]
                if a.side != b.side:
                    continue
                gap = abs(a.v - b.v) - (a.width + b.width) / 2
                if gap < web - 1e-9:
                    faults.append((i, j, float(gap)))
        return faults

    def outlet_cutter(self, slit: "Outlet") -> Any:
        """The solid a slit cuts from the tray: from beyond the outer face to a little inside the wall's inner face."""
        from solids import box
        zone = self.outlet_zone()[slit.side]
        reach = 9.0
        if slit.side == "left":
            u0, u1 = zone["u_out"] - reach, zone["u_in"] + 0.2
        else:
            u0, u1 = zone["u_in"] - 0.2, zone["u_out"] + reach
        return box(u0, u1, slit.v - slit.width / 2, slit.v + slit.width / 2, slit.z_top, slit.z_bottom)

    def outlet_openings(self, slits: Sequence["Outlet"]) -> List[Dict[str, Any]]:
        """Each slit as an opening for the finger and drip checks."""
        ops = []
        for i, s in enumerate(slits):
            zone = self.outlet_zone()[s.side]
            u_mid = (zone["u_in"] + zone["u_out"]) / 2
            pts = [(u_mid, s.v + dv, z) for dv in (-s.width / 2 + 0.2, 0.0, s.width / 2 - 0.2)
                   for z in np.linspace(s.z_top + 0.2, s.z_bottom - 0.2, max(int(s.height / 1.0) + 1, 2))]
            ops.append({"id": f"outlet {s.side} {i + 1}", "kind": "outlet slit", "min_dim": s.width, "max_dim": s.height, "points": pts,
                        "u": u_mid, "v": s.v, "z": (s.z_top + s.z_bottom) / 2})
        return ops

    # -- the floor under a groove -----------------------------------------------------------------------------------------
    def floor_pad_top(self, depth: float) -> float:
        """The height the cavity floor must reach under an engraved groove of this depth: the groove, then the core's minimum wall."""
        return self.z_floor_bottom + depth + self.m.P("envelope.min_wall_mm")

    # -- the mark ---------------------------------------------------------------------------------------------------------
    def mark_clearances(self, mark: ShPolygon, flat: ShPolygon, vents: Sequence[Vent]) -> Dict[str, float]:
        """How far a mark (or its panel) stands from the edge of the lid's flat top, the lid screw's head, the apertures and the vents."""
        P = self.m.P
        uc, vc = self.screw_uv
        screw = float(mark.distance(Point(uc, vc))) - P("screws.lid_head_dia_mm") / 2
        boxes = unary_union([sh_box(a["u"] - a["du"] / 2, a["v"] - a["dv"] / 2, a["u"] + a["du"] / 2, a["v"] + a["dv"] / 2) for a in aperture_boxes(self.m)])
        vent_union = unary_union([self.vent_footprint(v) for v in vents]) if vents else None
        return {"inside_flat_top": bool(flat.contains(mark)),
                "edge_of_flat_top_mm": float(flat.exterior.distance(mark)) if flat.contains(mark) else -float(mark.difference(flat).area),
                "lid_screw_head_mm": screw, "aperture_mm": float(mark.distance(boxes)),
                "vent_mm": float(mark.distance(vent_union)) if vent_union is not None else float("inf")}
