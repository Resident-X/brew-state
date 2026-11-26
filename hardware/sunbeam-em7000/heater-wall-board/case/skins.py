"""The skin of the printed case: what the styling supplies and nothing else. Flow is the one skin the owner chose; the base class is the seam the core is written against.

A skin is handed the core and draws, in plan, the outline of the tray's walls and of the lid beyond what the core fixes, the
edge treatment, the vent pattern (centre lines the core then cuts as 45 degree gills), the shallow relief grooves that are
not through-openings, the mark with its panel, and the colours that params.yaml holds under `skins`. Every outline is
validated by the core against its keep-in and keep-out polygons, so a skin cannot take anything the board relies on.
"""

from __future__ import annotations

import math
import os
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np
from shapely import affinity
from shapely.geometry import LineString, Point, Polygon as ShPolygon, box as sh_box
from shapely.ops import unary_union

from solids import box, chamfered, clean_polygon, prism, prism_uz, prism_vz, fuse, chamfer_prism
from core import Core, Outlet, OutlineRefused, Vent
import logo as logo_module

Point2 = Tuple[float, float]


@dataclass
class Skirt:
    """A low body round the tray, under the path of the lid's toes, wider than the full-height walls."""
    outline: List[Point2]
    top_chamfer: float


@dataclass
class TraySpec:
    neck: List[Point2]                                   # plan outline of the full-height walls, pilasters included
    bottom_chamfer: float = 0.0                          # 45 degree chamfer round the bed-side perimeter
    skirt: Optional[Skirt] = None
    extras: Optional[Callable[[Any, Any], Any]] = None   # (model, tray solid) -> tray solid, the skin's additions


@dataclass
class Groove:
    """A relief groove: a centre line with a width and a depth, round at both ends, cut into the lid's top face."""
    points: List[Point2]
    width: float
    depth: float
    square: bool = False                                 # square ends instead of round: a bar, which a face-down print bridges across its width

    def polygon(self) -> ShPolygon:
        if self.square:
            return LineString(self.points).buffer(self.width / 2, cap_style=2, join_style=2)
        return LineString(self.points).buffer(self.width / 2, cap_style=1, join_style=1, resolution=8).simplify(0.01)


@dataclass
class MarkSpec:
    geometry: Any                                        # the logo's engraved grooves in the case frame (u, v), one shapely geometry
    outline: ShPolygon                                   # the logo's silhouette
    area: Optional[List[Point2]] = None                  # the area the logo stands alone in, when the skin draws one round it


def placed_lid_logo(P: Any, height: float, centre: Optional[Tuple[float, float]] = None, right: Optional[float] = None,
                    top: Optional[float] = None) -> Tuple[Any, ShPolygon]:
    """The engraved logo for the lid face: its grooves and silhouette, centred on `centre` or with its greatest-u edge at `right` and its greatest-v edge at `top` (the model frame)."""
    e = logo_module.engrave(P, height)
    g, o = e.placed("lid", (0.0, 0.0))
    half = P("logo.groove_width_mm") / 2
    gb = g.bounds
    if centre is not None:
        dx, dy = centre[0], centre[1]
    else:
        dx, dy = right - gb[2], top - gb[3]
    return affinity.translate(g, dx, dy), affinity.translate(o, dx, dy)


def placed_tray_logo(P: Any, face: ShPolygon, keep_out: Optional[Any] = None) -> Tuple[Any, ShPolygon, float]:
    """The engraved logo for the tray's outer top face, `logo.tray_height_mm` tall and centred on that face.

    The face is the flat region of the tray's top (bed-side) face, so its edge is where the chamfer begins. The logo is shifted
    off centre, along v then along u, only as far as it takes to keep `logo.tray_edge_clear_mm` between the logo and that edge,
    and the call refuses a face that cannot hold it. The floor is thickened under the logo to keep the core's minimum wall under
    its grooves, so that thickened pad (the logo's outline and the pad margin) may not enter `keep_out`, the plan region over
    the blade legs where the floor is as thin as the legs and the lean allow; the logo moves off centre, toward the plate, as far
    as that takes. Returns the grooves, the silhouette and the height.
    """
    height = P("logo.tray_height_mm")
    e = logo_module.engrave(P, height)
    g, o = e.placed("tray", (0.0, 0.0))
    clear = P("logo.tray_edge_clear_mm")
    keep = face.buffer(-clear, join_style=1)
    cu, cv = face.centroid.x, face.centroid.y
    centre = (cu, cv)
    if keep.is_empty:
        raise OutlineRefused(f"the tray top is too small to hold the logo {clear:.1f} mm from its chamfer")
    ob = o.bounds
    half = ((ob[2] - ob[0]) / 2 + P("logo.groove_width_mm") / 2, (ob[3] - ob[1]) / 2 + P("logo.groove_width_mm") / 2)

    pad = P("logo.pad_margin_mm") + P("logo.groove_width_mm") / 2

    def fits(c: Tuple[float, float]) -> bool:
        if not keep.contains(sh_box(c[0] - half[0], c[1] - half[1], c[0] + half[0], c[1] + half[1])):
            return False
        if keep_out is None:
            return True
        return not affinity.translate(o, c[0], c[1]).buffer(pad, join_style=1).intersects(keep_out)

    if not fits(centre):
        step = 0.1
        found = None
        for n in range(1, 800):                 # along v first, the axis the logo stays centred on
            for dv in (-n * step, n * step):
                if fits((cu, cv + dv)):
                    found = (cu, cv + dv)
                    break
            if found:
                break
        for n in range(1, 400):                 # only then across
            if found:
                break
            for du in (n * step, -n * step):
                for m in range(0, 800):
                    for dv in ((0.0,) if m == 0 else (m * step, -m * step)):
                        if fits((cu + du, cv + dv)):
                            found = (cu + du, cv + dv)
                            break
                    if found:
                        break
                if found:
                    break
        if found is None:
            raise OutlineRefused(f"the logo, {height:.0f} mm tall, does not fit the tray top {clear:.1f} mm from its chamfer")
        centre = found
    return affinity.translate(g, centre[0], centre[1]), affinity.translate(o, centre[0], centre[1]), height


def body_outline(core: Core, chamfer: float, tab: Sequence[Point2]) -> List[Point2]:
    """The tray's plan: pilasters at the plate end, the walls, the far wall carrying the given tab (points from right to left)."""
    pts = [(core.left_out - core.pil, core.v_end), (core.right_out + core.pil, core.v_end), (core.right_out + core.pil, core.v_pil),
           (core.right_out, core.v_pil), (core.right_out, core.far_out)] + list(tab) + [(core.left_out, core.far_out),
           (core.left_out, core.v_pil), (core.left_out - core.pil, core.v_pil)]
    return clean_polygon(chamfered(pts, chamfer, core.v_end))


class Skin:
    """What every skin has: a name, colours in params.yaml, and the hooks below. The defaults draw nothing of their own."""
    name = "skin"
    vents_are_policed = True          # the core refuses vents that break its rules, unless the skin clips them to the rules itself

    def __init__(self, P: Any):
        self.P = P

    @property
    def lid_chamfer(self) -> float:
        return self.P.S("chamfer_mm")

    def tray(self, core: Core) -> TraySpec:
        raise NotImplementedError

    def lid_outline(self, core: Core) -> List[Point2]:
        return list(self.tray(core).neck)

    def vents(self, core: Core) -> List[Vent]:
        return []

    def grooves(self, core: Core) -> List[Groove]:
        return []

    def mark(self, core: Core, vents: Sequence[Vent]) -> MarkSpec:
        """The logo on the lid face."""
        raise NotImplementedError

    def tray_face(self, core: Core) -> ShPolygon:
        """The flat region of the tray's outer top face (the bed-side face): the tray's outline less its top chamfer."""
        spec = self.tray(core)
        return ShPolygon(spec.neck).buffer(-spec.bottom_chamfer, join_style=2) if spec.bottom_chamfer else ShPolygon(spec.neck)

    def tray_mark(self, core: Core) -> MarkSpec:
        """The logo on the tray's outer top face."""
        raise NotImplementedError

    def outlets(self, core: Core) -> List[Outlet]:
        """The convection slits in the long walls, inside the zone the core permits."""
        return []

    def lid_drop_lip(self, core: Core) -> Optional[ShPolygon]:
        """The plan region of a perimeter lip hanging from the lid, when the skin has one."""
        return None

    def lid_lug_pad(self, core: Core) -> Optional[ShPolygon]:
        """The plan region of the lid's pad under the lid screw, when the skin draws one; None keeps the core's box."""
        return None

    def extra_openings(self, m: Any) -> List[Dict[str, Any]]:
        """Openings the skin adds beyond the core's own, for the finger and drip checks."""
        return []


REGISTRY: Dict[str, Callable[[Any], Skin]] = {}


def make(name: str, P: Any) -> Skin:
    if name not in REGISTRY:
        raise SystemExit(f"unknown skin {name!r}; the skins are {', '.join(REGISTRY)}")
    return REGISTRY[name](P)


class FlowSkin(Skin):
    """Organic: one pebble in plan and section, streamlines on the lid that part round the bays and the logo's stone and rejoin."""
    name = "flow"

    def louvre_width(self) -> float:
        return float(self.P.S("louvre_width_mm"))

    @property
    def lid_chamfer(self) -> float:
        return self.P.S("chamfer_mm")

    # -- the outline ------------------------------------------------------------------------------------------------------
    def pebble(self, core: Core) -> List[Point2]:
        """The pebble in plan: the pilasters' outer faces carried on as slightly bowed sides, large round corners and a broad shallow arc at the far end.

        It is the outward offset by the corner radius of a convex inner shape (the sides, a shallow far arc), cut at the plate end.
        """
        P = self.P
        uc = core.screw_uv[0]
        pil_hw = (core.right_out + core.pil - (core.left_out - core.pil)) / 2
        R = P.S("outline.corner_radius_mm")
        sag = P.S("outline.far_sagitta_mm")
        bow = P.S("outline.side_bow_mm")
        a_s = pil_hw - R
        v_apex = core.v_max - R
        v_f = v_apex - sag
        v_lo = core.v_end - R - 1.0
        t = np.linspace(0.0, 1.0, 41)
        vs = core.v_pil + (v_f - core.v_pil) * t
        bows = bow * 4.0 * t * (1.0 - t)
        right = [(uc + a_s, v_lo), (uc + a_s, core.v_pil)] + [(uc + a_s + b, v) for v, b in zip(vs, bows)]
        half_far = a_s
        r_far = (half_far ** 2 + sag ** 2) / (2.0 * sag)
        ang = np.linspace(0.0, math.asin(half_far / r_far), 40)
        arc = [(uc + r_far * math.sin(x), v_apex - r_far * (1.0 - math.cos(x))) for x in ang]
        right += arc[::-1]
        left = [(2 * uc - x, y) for x, y in right[::-1]]
        inner = ShPolygon(right + left[1:])
        shape = inner.buffer(R, quad_segs=24).intersection(sh_box(-1e3, core.v_end, 1e3, 1e3))
        ring = [tuple(p) for p in shape.simplify(0.004).exterior.coords][:-1]
        ring = [(u, core.v_end) if abs(v - core.v_end) < 1e-7 else (u, v) for u, v in ring]
        return clean_polygon(ring)

    def neck(self, core: Core) -> List[Point2]:
        """The tray's full-height outline: the chamfered body without a tab, united with a tab of square corners, `tab_half_width_mm` each side of the lid screw, cut to the pebble so its outer face is the lid rim's face."""
        uc = core.screw_uv[0]
        h = self.P.S("tab_half_width_mm")
        body = ShPolygon(body_outline(core, 1.5, []))
        tab = sh_box(uc - h, core.far_out - 0.5, uc + h, core.v_max + 5.0).intersection(ShPolygon(self.pebble(core)))
        joined = unary_union([body, tab])
        return clean_polygon([tuple(p) for p in joined.exterior.coords][:-1])

    def tray(self, core: Core) -> TraySpec:
        return TraySpec(neck=self.neck(core), bottom_chamfer=self.P.S("bottom_chamfer_mm"), skirt=Skirt(self.pebble(core), 0.0))

    def lid_outline(self, core: Core) -> List[Point2]:
        return self.pebble(core)

    def tray_face(self, core: Core) -> ShPolygon:
        return ShPolygon(self.pebble(core)).buffer(-self.P.S("bottom_chamfer_mm"), join_style=1)

    def cable_gate(self, core: Core) -> ShPolygon:
        """The plan region cut through the right-hand lip for the cable: the notch's v range, led toward the plate by `cable_gate_lead_mm`, outside the right wall."""
        P = self.P
        seam = P("case.seam_mm")
        n0, n1 = P("lid.cable_notch_v_mm")
        return sh_box(core.right_out, n0 - P.S("cable_gate_lead_mm") - seam, core.right_out + 1e3, n1 + seam)

    def lid_drop_lip(self, core: Core) -> Optional[ShPolygon]:
        """The lid's perimeter drop-lip: the pebble outside the full-height walls and their tab, from just beyond the pilasters round to the far end.

        It hangs from the lid to a fine shadow line above the tray's skirt, so lid and tray read as one pebble. It lies over the
        skirt's top, where the lid's toes never go, and moves with the lid when it is drawn out. A gate through the right-hand lip,
        over the cable notch and leading it toward the plate by the slide that frees the toes, lets the cable out at every pose.
        """
        P = self.P
        pebble = ShPolygon(self.pebble(core))
        inner = ShPolygon(self.tray(core).neck).buffer(P.S("lip_gap_mm"), join_style=1)
        lip = pebble.difference(inner).intersection(sh_box(-1e3, core.v_pil + P.S("lip_front_gap_mm"), 1e3, 1e3))
        lip = lip.buffer(-0.4, join_style=1).buffer(0.4, join_style=1)
        return lip.difference(self.cable_gate(core))

    def lid_lug_pad(self, core: Core) -> Optional[ShPolygon]:
        """The pebble across the tab's width and the lip gap beyond it, from the far wall's outer face: it reaches the pebble's face and overlaps both lip ends, so the lid's rim is one piece above the tab."""
        P = self.P
        uc = core.screw_uv[0]
        reach = P.S("tab_half_width_mm") + P.S("lip_gap_mm") + 0.5
        return ShPolygon(self.pebble(core)).intersection(sh_box(uc - reach, core.far_out + P("case.seam_mm"), uc + reach, core.v_max + 5.0))

    def extra_openings(self, m: Any) -> List[Dict[str, Any]]:
        """The seam between the drop-lip and the skirt, all round."""
        info = m.info["lid_drop_lip"]
        z = (m.core.low_zone_top + info["z_bottom"]) / 2
        pts = []
        for poly in (info["region"].geoms if hasattr(info["region"], "geoms") else [info["region"]]):
            ring = poly.buffer(-0.5).exterior
            for d in np.arange(0.0, ring.length, 6.0):
                q = ring.interpolate(d)
                pts.append((float(q.x), float(q.y), z))
        return [{"id": "lip seam", "kind": "seam", "min_dim": m.core.z_lid_under - m.core.z_wall_top, "max_dim": 200.0, "points": pts,
                 "u": pts[0][0], "v": pts[0][1], "z": z}]

    def outlets(self, core: Core) -> List[Outlet]:
        """Equal slits on one grid along each wall, a slit standing wherever the core allows.

        The right wall's row starts at `first_v_mm` and runs on the pitch to the end of the zone; the left wall's grid is the right's
        shifted half a pitch, so a left slit stands behind a right web and no sight line runs square through both walls.
        """
        P = self.P
        zone = core.outlet_zone()
        out: List[Outlet] = []
        width, height, pitch = P.S("outlets.width_mm"), P.S("outlets.height_mm"), P.S("outlets.pitch_mm")
        for side, first in (("right", P.S("outlets.first_v_mm")), ("left", P.S("outlets.first_v_mm") + pitch / 2)):
            k = 0
            while first + k * pitch + width / 2 <= zone[side]["v1"] + 1e-9:
                v = first + k * pitch
                if core.outlet_free(side, v, width, height):
                    out.append(Outlet(side, v, width, height, zone[side]["z0"]))
                k += 1
        return out

    # -- the lid's stone and streamlines ---------------------------------------------------------------------------------
    def stone(self, core: Core) -> ShPolygon:
        """The logo's stone: a soft rectangle round the logo, which the streamlines part round. It is not drawn."""
        P = self.P
        cu, cv = P.S("mark.centre_uv_mm")
        _, o = placed_lid_logo(P, P.S("mark.lid_height_mm"), centre=(cu, cv))
        b = o.bounds
        w, h = b[2] - b[0], b[3] - b[1]
        m = P.S("mark.margin_mm") + P("logo.groove_width_mm") / 2
        r = P.S("mark.corner_radius_mm")
        return sh_box(cu - w / 2 - m + r, cv - h / 2 - m + r, cu + w / 2 + m - r, cv + h / 2 + m - r).buffer(r, quad_segs=16)

    def mark(self, core: Core, vents: Sequence[Vent]) -> MarkSpec:
        g, o = placed_lid_logo(self.P, self.P.S("mark.lid_height_mm"), centre=tuple(self.P.S("mark.centre_uv_mm")))
        return MarkSpec(g, o, area=list(self.stone(core).exterior.coords)[:-1])

    def tray_mark(self, core: Core) -> MarkSpec:
        face = self.tray_face(core)
        b = face.bounds
        from core import aperture_boxes
        legs = unary_union([sh_box(a["u"] - a["du"] / 2, a["v"] - a["dv"] / 2, a["u"] + a["du"] / 2, a["v"] + a["dv"] / 2) for a in aperture_boxes(core.m)])
        g, o, _ = placed_tray_logo(self.P, face, keep_out=legs)
        return MarkSpec(g, o, area=list(face.exterior.coords)[:-1])


REGISTRY["flow"] = FlowSkin


def _flow_lines(self: "FlowSkin", core: Core) -> Dict[str, Any]:
    """The streamlines of the lid, the islands they part round, and the region they run in.

    The region is the lid's flat face inset by the groove's half width and a land, less the lid screw and the block of bays; the
    lines end on its margin or on the obstacles' offsets, never on a cut of their own.
    """
    import streamlines as sl
    from core import aperture_boxes
    P = self.P
    ch = self.lid_chamfer
    outline = ShPolygon(self.pebble(core))
    gw = P.S("lines.groove_width_mm")
    edge = ch + gw / 2 + P.S("lines.edge_land_mm")
    clear = P.S("lines.obstacle_clear_mm")
    collar = P("lid.collar_wall_mm")
    aps = unary_union([sh_box(a["u"] - a["du"] / 2 - collar, a["v"] - a["dv"] / 2 - collar, a["u"] + a["du"] / 2 + collar, a["v"] + a["dv"] / 2 + collar)
                       for a in aperture_boxes(core.m)])
    apertures = aps.buffer(clear, join_style=1)
    stone = self.stone(core)
    stone_clear = stone.buffer(clear, join_style=1)
    uc, vc = core.screw_uv
    screw = Point(uc, vc).buffer(P("screws.lid_head_dia_mm") / 2 + P.S("lines.screw_clear_mm") + gw / 2)
    block = sh_box(-1e3, apertures.bounds[1], 1e3, 1e3)       # the far-end zone of the bays and the lid screw: the lines end on its offset
    region = outline.buffer(-edge, join_style=2).difference(screw).difference(block)
    region = max(region.geoms, key=lambda g: g.area) if hasattr(region, "geoms") else region
    field = sl.Field(region, [stone_clear], P.S("lines.grid_mm"))
    hug = stone_clear.exterior.buffer(P.S("lines.hug_mm"))
    count = int(P.S("lines.count"))
    lines = []
    for k in range(1, count + 1):
        for line in field.contour(k / (count + 1)):
            if len(line) < 4:
                continue
            smooth_line = sl.resample(sl.smooth(line, 2), 0.5)
            # a contour that runs along the stone's offset instead of round it is the stone's own level, not a stream: it is trimmed away
            rest = LineString(smooth_line).difference(hug)
            for piece in (rest.geoms if hasattr(rest, "geoms") else [rest]):
                if piece.geom_type == "LineString" and piece.length >= P.S("lines.min_line_mm"):
                    pts = sl.resample([tuple(q) for q in piece.coords], 0.5)
                    lines.append(pts if pts[0][1] <= pts[-1][1] else pts[::-1])
    lines.sort(key=lambda ln: (round(ln[0][0] / 3.0), ln[0][1]))
    # where two lines would run nearer than a groove and its land, the later one stops: no two grooves merge into a pocket
    gap = gw + P.S("lines.min_land_mm")
    kept_geom: Any = None
    thinned: List[List[Point2]] = []
    for ln in lines:
        geom = LineString(ln)
        rest = geom if kept_geom is None else geom.difference(kept_geom.buffer(gap, cap_style=2))
        for piece in (rest.geoms if hasattr(rest, "geoms") else [rest]):
            if piece.geom_type == "LineString" and piece.length >= P.S("lines.min_line_mm"):
                thinned.append([tuple(q) for q in piece.coords])
                kept_geom = piece if kept_geom is None else kept_geom.union(piece)
    # a stretch the stone's hug cut off from the plate end is the stone's wake, not a stream: it is dropped
    plate_end = region.bounds[1]
    lines = [ln for ln in thinned if min(ln[0][1], ln[-1][1]) <= plate_end + 1.0]
    return {"lines": lines, "apertures": apertures, "stone": stone_clear, "region": region, "field": field, "outline": outline}


def _flow_streamlines(self: "FlowSkin", core: Core) -> List[List[Point2]]:
    key = id(core)
    if getattr(self, "_streamline_key", None) != key:
        self._streamlines = self._flow_lines(core)["lines"]
        self._streamline_key = key
    return self._streamlines


def _bridge_bands(self: "FlowSkin", core: Core) -> List[float]:
    """The v of every structural bridge: one even pitch across the thickened field, shared by every streamline so the breaks line up."""
    P = self.P
    v0, v1 = P("lid.pad_v_mm")
    pitch = P.S("lines.bridge_pitch_mm")
    n = int((v1 - v0) // pitch)
    first = v0 + ((v1 - v0) - n * pitch) / 2 + pitch / 2
    return [first + k * pitch for k in range(n)]


def _clip_to_v(piece: List[Point2], lo: Optional[float], hi: Optional[float]) -> List[Point2]:
    """The piece of a line between the two v (either may be None), its ends cut where the line crosses them and its direction kept."""
    pts = [tuple(p) for p in piece]
    forward = pts[0][1] <= pts[-1][1]
    walk = pts if forward else pts[::-1]
    out: List[Point2] = []
    for a, b in zip(walk, walk[1:]):
        lo_v, hi_v = a[1], b[1]
        if hi is not None and lo_v >= hi:
            break
        if lo is not None and hi_v <= lo:
            continue
        if not out:
            if lo is not None and lo_v < lo < hi_v:
                f = (lo - lo_v) / (hi_v - lo_v)
                out.append((a[0] + f * (b[0] - a[0]), lo))
            else:
                out.append(a)
        if hi is not None and lo_v < hi < hi_v:
            f = (hi - lo_v) / (hi_v - lo_v)
            out.append((a[0] + f * (b[0] - a[0]), hi))
            return out if forward else out[::-1]
        out.append(b)
    return out if forward else out[::-1]


def _flow_vents(self: "FlowSkin", core: Core) -> List[Vent]:
    """The streamlines' stretches over the thickened field, cut as vents of the grooves' own width, even and mirrored about the lid's long axis.

    Every streamline is handed to the core walked from the lid's long axis outward in its lean: a line on the low-u side from its far
    end to its plate end, a line on the high-u side as drawn, so each gill leans toward the axis and the two sides mirror each other.
    A run is cut at the shared bridge bands (the lid left standing, `bridge_mm` along v). A line is vented only when it carries a
    complete set of runs, one more than there are bands and each at least the least run, and only when its mirror line does too; the
    others stay grooves along their whole length. If any piece of a line would stand nearer than the core's web to a vent already
    placed, that line and its mirror both stay grooves. Every vented line then starts and ends on the same two v: its lowest run is
    clipped to the greatest of the lowest runs' starting v and its highest to the least of the highest runs' ending v.
    """
    P = self.P
    shortest = P.S("lines.min_run_mm")
    bridge = P.S("lines.bridge_mm")
    bands = self._bridge_bands(core)
    web = P("envelope.vent_web_mm")
    avoid = self.stone(core).buffer(P("envelope.vent_clear_mm"))
    axis = core.screw_uv[0]
    lines = self.streamlines(core)
    side = [1 if sum(p[0] for p in ln) / len(ln) > axis else -1 for ln in lines]
    pieces_of: Dict[int, List[List[Point2]]] = {}
    for index, line in enumerate(lines):
        walked = line if side[index] > 0 else line[::-1]
        pieces: List[List[Point2]] = []
        for run in core.admissible_runs(walked, shortest, avoid=avoid):
            cur: List[Point2] = []
            for p in run:
                if any(abs(p[1] - b) < bridge / 2 for b in bands):
                    if cur:
                        pieces.append(cur)
                    cur = []
                else:
                    cur.append(p)
            if cur:
                pieces.append(cur)
        pieces = [pc for pc in pieces if len(pc) >= 2]
        if len(pieces) == len(bands) + 1 and all(LineString(pc).length >= shortest for pc in pieces):
            pieces_of[index] = pieces

    def mirror_of(index: int) -> Optional[int]:
        want = 2 * axis - lines[index][0][0]
        others = [j for j in pieces_of if side[j] != side[index]]
        near = min(others, key=lambda j: abs(lines[j][0][0] - want), default=None)
        return near if near is not None and abs(lines[near][0][0] - want) < 1.0 else None

    chosen: List[int] = []
    placed: Any = None
    for index in sorted(pieces_of):
        twin = mirror_of(index)
        if index in chosen or twin is None or mirror_of(twin) != index:
            continue
        bands_here = [core.mid_band(Vent(pc, "candidate")) for j in (index, twin) for pc in pieces_of[j]]
        if placed is not None and any(b.distance(placed) < web for b in bands_here):
            continue
        chosen += [index, twin]
        placed = unary_union(bands_here) if placed is None else placed.union(unary_union(bands_here))
    chosen.sort()
    low = max((min(min(p[1] for p in pc) for pc in pieces_of[j]) for j in chosen), default=None)
    high = min((max(max(p[1] for p in pc) for pc in pieces_of[j]) for j in chosen), default=None)
    vents: List[Vent] = []
    self._vent_line = {}
    for index in chosen:
        ordered = sorted(pieces_of[index], key=lambda pc: min(p[1] for p in pc))
        for k, piece in enumerate(ordered):
            piece = _clip_to_v(piece, low if k == 0 else None, high if k == len(ordered) - 1 else None)
            if len(piece) < 2 or LineString(piece).length < shortest:
                raise OutlineRefused(f"the vents' common start and end leave a run on streamline {index + 1} under the least run of {shortest:.1f} mm")
            vents.append(Vent(piece, f"vent {len(vents) + 1}"))
            self._vent_line[vents[-1].label] = index
    self._vents_placed = vents
    return vents


def _bay_openings(core: Core) -> List[Any]:
    """The lid's blade bays merged into the openings a reader sees, left to right, each as a rectangle (u0, v0, u1, v1)."""
    from core import aperture_boxes
    merged = unary_union([sh_box(a["u"] - a["du"] / 2, a["v"] - a["dv"] / 2, a["u"] + a["du"] / 2, a["v"] + a["dv"] / 2) for a in aperture_boxes(core.m)])
    return sorted((tuple(g.bounds) for g in (merged.geoms if hasattr(merged, "geoms") else [merged])), key=lambda b: b[0])


def _flow_block(self: "FlowSkin", core: Core) -> Dict[str, Any]:
    """The far-end block: a blind grille of bars that mirrors the wide bay, so the far end reads as one row, wide bay, narrow bay, block.

    The block is as wide as the widest opening the bays make, as long along v as the bays, and stands the gap between the two bay
    openings beyond the last of them. Its bars run along v, side by side across u, each a square-ended groove, evenly spaced.
    The block is decoration and never stops a build: where it does not fit (nearer than the edge land to the lid's chamfer, nearer
    than `block.clear_mm` to a bay's collar or to the lid screw's clear zone, or room for fewer than two bars) the skin draws no
    block, and the returned dict carries no bars and a plain `reason`.
    """
    P = self.P
    openings = _bay_openings(core)
    none: Dict[str, Any] = {"bars": [], "reason": None, "openings": openings}
    if len(openings) < 2:
        none["reason"] = "the bays make one opening, so there is no row to complete"
        return none
    widest = max(openings, key=lambda b: b[2] - b[0])
    width = widest[2] - widest[0]
    gap = min(b[0] - a[2] for a, b in zip(openings, openings[1:]))
    v0, v1 = min(b[1] for b in openings), max(b[3] for b in openings)
    u0 = max(b[2] for b in openings) + gap
    u1 = u0 + width
    n = int(P.S("block.bars"))
    w, d = P.S("lines.groove_width_mm"), P.S("lines.groove_depth_mm")
    # a narrower bay takes fewer bars: the most, up to `block.bars`, that keep the least land between them
    while n > 2 and (width - n * w) / (n - 1) < P.S("lines.min_land_mm") - 1e-9:
        n -= 1
    land = (width - n * w) / (n - 1) if n > 1 else 0.0
    if n < 2 or land < P.S("lines.min_land_mm") - 1e-9:
        none["reason"] = f"the block is {width:.2f} mm wide, room for fewer than two bars with {P.S('lines.min_land_mm'):.2f} mm between them"
        return none
    rect = sh_box(u0, v0, u1, v1)
    flat = ShPolygon(self.pebble(core)).buffer(-self.lid_chamfer, join_style=2)
    edge = flat.exterior.distance(rect) if flat.contains(rect) else 0.0
    collar = P("lid.collar_wall_mm")
    from core import aperture_boxes
    collars = unary_union([sh_box(a["u"] - a["du"] / 2 - collar, a["v"] - a["dv"] / 2 - collar, a["u"] + a["du"] / 2 + collar, a["v"] + a["dv"] / 2 + collar)
                           for a in aperture_boxes(core.m)])
    to_collar = collars.distance(rect)
    uc, vc = core.screw_uv
    zone = Point(uc, vc).buffer(P("screws.lid_head_dia_mm") / 2 + P.S("lines.screw_clear_mm"))
    to_screw = zone.distance(rect)
    least = P.S("block.clear_mm")
    faults = []
    if edge < P.S("lines.edge_land_mm") - 1e-9:
        faults.append(f"it comes {edge:.2f} mm from the lid's chamfer, under the {P.S('lines.edge_land_mm'):.1f} mm edge land")
    if to_collar < least - 1e-9:
        faults.append(f"it comes {to_collar:.2f} mm from a bay collar, under the {least:.1f} mm it keeps")
    if to_screw < least - 1e-9:
        faults.append(f"it comes {to_screw:.2f} mm from the lid screw's clear zone, under the {least:.1f} mm it keeps")
    if faults:
        none["reason"] = "; ".join(faults)
        return none
    bars = [Groove([(u0 + w / 2 + k * (w + land), v0), (u0 + w / 2 + k * (w + land), v1)], w, d, square=True) for k in range(n)]
    return {"bars": bars, "reason": None, "rect": rect, "land_mm": land, "to_chamfer_mm": edge, "to_collar_mm": to_collar, "to_screw_zone_mm": to_screw,
            "u": (u0, u1), "v": (v0, v1), "gap_mm": gap, "openings": openings}


def _flow_grooves(self: "FlowSkin", core: Core) -> List[Groove]:
    """A groove along every streamline, round at both ends, the width of the vents' opening, and the far-end block's bars; where a vent runs the groove is cut through."""
    P = self.P
    w, d = P.S("lines.groove_width_mm"), P.S("lines.groove_depth_mm")
    return [Groove([tuple(p) for p in line], w, d) for line in self.streamlines(core)] + self.block(core)["bars"]


FlowSkin._flow_lines = _flow_lines
FlowSkin.streamlines = _flow_streamlines
FlowSkin._bridge_bands = _bridge_bands
FlowSkin.vents = _flow_vents
FlowSkin.block = _flow_block
FlowSkin.grooves = _flow_grooves
